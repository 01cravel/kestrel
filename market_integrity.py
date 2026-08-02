"""Cost-controlled closing-price and corporate-action integrity for Kestrel."""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-market-integrity.json"
DATABENTO_API_KEY = os.environ.get("DATABENTO_API_KEY", "").strip()
DATABENTO_BASE_URL = "https://hist.databento.com/v0/"
DATABENTO_DATASET = "EQUS.SUMMARY"
SCHEMA_VERSION = 2
REFRESH_SECONDS = 12 * 60 * 60
PRICE_TOLERANCE_PERCENT = 0.5
SUPPORTED_FROM = dt.date(2018, 5, 1)
PUBLIC_HISTORY_DAYS = 400
SPLIT_JUMP_THRESHOLD = 3.0

_LOCK = threading.RLock()
_PUBLIC_REQUEST_LOCK = threading.Lock()
_LAST_PUBLIC_REQUEST = 0.0
_STATE: Dict[str, Any] = {
    "status": "starting",
    "message": "Preparing cost-controlled market-data checks",
    "keyConfigured": bool(DATABENTO_API_KEY),
    "updatedAt": None,
    "prices": {},
    "listings": {},
    "actions": {},
    "factors": {},
    "publicPrices": {},
    "publicActions": {},
    "coverage": {
        "prices": False,
        "listings": False,
        "actions": False,
        "factors": False,
        "publicPrices": False,
        "publicActions": False,
    },
    "errors": [],
}


def _load_cache() -> None:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            return
        with _LOCK:
            for field in (
                "updatedAt", "prices", "listings", "actions", "factors",
                "publicPrices", "publicActions", "coverage",
            ):
                if field in payload:
                    _STATE[field] = payload[field]
            _STATE["status"] = "cached"
            _STATE["message"] = "Showing saved market checks while they refresh"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return


def _save_cache() -> None:
    with _LOCK:
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "updatedAt": _STATE["updatedAt"],
            "prices": _STATE["prices"],
            "listings": _STATE["listings"],
            "actions": _STATE["actions"],
            "factors": _STATE["factors"],
            "publicPrices": _STATE["publicPrices"],
            "publicActions": _STATE["publicActions"],
            "coverage": _STATE["coverage"],
        }
    temporary_path = CACHE_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary_path.replace(CACHE_PATH)


def _request_lines(method: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not DATABENTO_API_KEY:
        raise RuntimeError("A Databento API key is required")
    clean_params = {
        key: ",".join(str(value) for value in raw_value) if isinstance(raw_value, (list, tuple)) else str(raw_value)
        for key, raw_value in params.items()
        if raw_value is not None
    }
    url = DATABENTO_BASE_URL + method + "?" + urllib.parse.urlencode(clean_params)
    token = base64.b64encode(f"{DATABENTO_API_KEY}:".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json, application/x-json-stream, text/plain",
            "User-Agent": "Kestrel local portfolio dashboard",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("detail")
            if isinstance(detail, dict):
                detail = detail.get("message")
        except (ValueError, AttributeError):
            detail = None
        if error.code in {401, 403}:
            raise RuntimeError(detail or "Databento authentication or entitlement is missing") from error
        if error.code == 402:
            raise RuntimeError("Databento account payment or dataset entitlement is required") from error
        if error.code == 429:
            raise RuntimeError("Databento rate limit was reached") from error
        raise RuntimeError(detail or f"Databento returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
        raise RuntimeError("Institutional market data was unavailable") from error

    records: List[Dict[str, Any]] = []
    stripped = body.strip()
    if not stripped:
        return records
    try:
        decoded = json.loads(stripped)
        if isinstance(decoded, list):
            return [row for row in decoded if isinstance(row, dict)]
        if isinstance(decoded, dict):
            nested = decoded.get("data")
            return [row for row in nested if isinstance(row, dict)] if isinstance(nested, list) else [decoded]
    except json.JSONDecodeError:
        pass
    for line in stripped.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError("Databento returned an unexpected data format") from error
        if isinstance(row, dict):
            records.append(row)
    return records


def _symbol(row: Dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("nasdaq_symbol") or "").upper()


def _timestamp(row: Dict[str, Any]) -> Any:
    header = row.get("hd") if isinstance(row.get("hd"), dict) else {}
    return row.get("ts_event") or header.get("ts_event") or row.get("date")


def _date(value: Any) -> Optional[dt.date]:
    if isinstance(value, (int, float)):
        seconds = float(value) / 1_000_000_000 if float(value) > 10_000_000_000 else float(value)
        try:
            return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc).date()
        except (OSError, OverflowError, ValueError):
            return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


def _public_chart(symbol: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Read Yahoo's public adjusted chart as a provisional independent check."""
    global _LAST_PUBLIC_REQUEST
    with _PUBLIC_REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_PUBLIC_REQUEST
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        start = int(time.time() - PUBLIC_HISTORY_DAYS * 24 * 60 * 60)
        end = int(time.time() + 24 * 60 * 60)
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + urllib.parse.quote(symbol)
            + "?"
            + urllib.parse.urlencode({
                "period1": start,
                "period2": end,
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            })
        )
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 Kestrel local portfolio dashboard"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                _LAST_PUBLIC_REQUEST = time.monotonic()
                document = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            _LAST_PUBLIC_REQUEST = time.monotonic()
            raise RuntimeError(f"Public adjusted-price check returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
            _LAST_PUBLIC_REQUEST = time.monotonic()
            raise RuntimeError("Public adjusted-price check was unavailable") from error

    results = document.get("chart", {}).get("result") if isinstance(document, dict) else None
    if not results or not isinstance(results[0], dict):
        raise RuntimeError("No public adjusted-price history was returned")
    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    raw_closes = ((indicators.get("quote") or [{}])[0].get("close") or [])
    adjusted_closes = ((indicators.get("adjclose") or [{}])[0].get("adjclose") or [])
    points: List[Dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        raw_close = _number(raw_closes[index]) if index < len(raw_closes) else None
        adjusted_close = _number(adjusted_closes[index]) if index < len(adjusted_closes) else None
        if raw_close and raw_close > 0:
            points.append({
                "date": dt.datetime.fromtimestamp(int(timestamp), tz=dt.timezone.utc).date().isoformat(),
                "close": raw_close,
                "adjustedClose": adjusted_close if adjusted_close and adjusted_close > 0 else None,
            })
    if not points:
        raise RuntimeError("No usable public adjusted-price history was returned")

    split_events = []
    events = result.get("events") if isinstance(result.get("events"), dict) else {}
    for raw in (events.get("splits") or {}).values():
        if not isinstance(raw, dict):
            continue
        numerator = _number(raw.get("numerator"))
        denominator = _number(raw.get("denominator"))
        event_date = _date(raw.get("date"))
        if event_date and numerator and denominator:
            split_events.append({
                "event": "stock_split",
                "eventDate": event_date.isoformat(),
                "ratio": round(numerator / denominator, 8),
                "description": raw.get("splitRatio") or f"{numerator:g}:{denominator:g}",
                "source": "Yahoo Finance chart events",
            })

    unexplained: List[Dict[str, Any]] = []
    split_dates = {event["eventDate"] for event in split_events}
    for previous, current in zip(points, points[1:]):
        ratio = max(previous["close"] / current["close"], current["close"] / previous["close"])
        nearby_split = any(
            abs((dt.date.fromisoformat(current["date"]) - dt.date.fromisoformat(event_date)).days) <= 3
            for event_date in split_dates
        )
        if ratio >= SPLIT_JUMP_THRESHOLD and not nearby_split:
            unexplained.append({
                "date": current["date"],
                "size": round(ratio, 2),
                "message": "A split-sized raw price jump has no matching split event.",
            })

    latest = points[-1]
    prior = points[-2] if len(points) > 1 else None
    price = {
        "date": latest["date"],
        "close": round(latest["close"], 8),
        "adjustedClose": round(latest["adjustedClose"], 8) if latest["adjustedClose"] else None,
        "priorDate": prior["date"] if prior else None,
        "priorClose": round(prior["close"], 8) if prior else None,
        "currency": result.get("meta", {}).get("currency"),
        "source": "Yahoo Finance public adjusted chart",
        "sourceUrl": "https://finance.yahoo.com/",
    }
    action_check = {
        "status": "review" if unexplained else "clear",
        "checkedDays": PUBLIC_HISTORY_DAYS,
        "splitEvents": split_events,
        "unexplainedJumps": unexplained,
        "message": (
            "An unexplained split-sized price jump needs manual review."
            if unexplained
            else "No unexplained split-sized price jump was found in the public adjusted history."
        ),
        "source": "Yahoo adjusted and unadjusted daily history",
    }
    return price, action_check


def _fetch_public_checks(symbols: List[str]) -> tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    prices: Dict[str, Any] = {}
    actions: Dict[str, Any] = {}
    errors: List[str] = []
    for symbol in symbols:
        try:
            price, action = _public_chart(symbol)
            prices[symbol] = price
            actions[symbol] = action
        except RuntimeError as error:
            errors.append(f"{symbol}: {error}")
    return prices, actions, errors


def _fetch_prices(symbols: List[str], start: dt.date, end: dt.date) -> Dict[str, Dict[str, Any]]:
    rows = _request_lines("timeseries.get_range", {
        "dataset": DATABENTO_DATASET,
        "schema": "ohlcv-1d",
        "symbols": symbols,
        "stype_in": "raw_symbol",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "encoding": "json",
        "pretty_px": "true",
        "pretty_ts": "true",
        "map_symbols": "true",
    })
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        symbol = _symbol(row)
        observation_date = _date(_timestamp(row))
        close = _number(row.get("close"))
        if symbol not in symbols or observation_date is None or close is None or close <= 0:
            continue
        prior = latest.get(symbol)
        if not prior or observation_date.isoformat() > prior["date"]:
            latest[symbol] = {
                "date": observation_date.isoformat(),
                "close": round(close, 8),
                "currency": "USD",
                "dataset": DATABENTO_DATASET,
                "source": "Nasdaq NLS+ official consolidated end-of-day summary via Databento",
                "sourceUrl": "https://databento.com/docs/examples/equities/closing-prices",
            }
    return latest


def _fetch_listings(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    rows = _request_lines("security_master.get_last", {
        "symbols": symbols,
        "stype_in": "raw_symbol",
        "countries": "US",
        "encoding": "json",
    })
    grouped: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in symbols}
    for row in rows:
        symbol = _symbol(row)
        if symbol in grouped and row.get("listing_status") in {None, "L"}:
            grouped[symbol].append(row)

    listings: Dict[str, Dict[str, Any]] = {}
    for symbol, candidates in grouped.items():
        primary = [row for row in candidates if row.get("primary_exchange") == row.get("exchange")]
        pool = primary or candidates
        unique = {
            str(row.get("listing_id") or f"{row.get('operating_mic')}:{row.get('figi')}"): row
            for row in pool
        }
        if len(unique) != 1:
            listings[symbol] = {
                "status": "ambiguous" if len(unique) > 1 else "unresolved",
                "candidateCount": len(unique),
                "message": "The primary institutional listing could not be resolved without guessing.",
            }
            continue
        row = next(iter(unique.values()))
        listings[symbol] = {
            "status": "resolved",
            "listingId": row.get("listing_id"),
            "securityId": row.get("security_id"),
            "operatingMic": row.get("operating_mic"),
            "exchange": row.get("exchange"),
            "primaryExchange": row.get("primary_exchange"),
            "currency": row.get("trading_currency"),
            "figi": row.get("figi"),
            "isin": row.get("isin"),
            "usCode": row.get("us_code"),
            "listingStatus": row.get("listing_status"),
        }
    return listings


def _compact_reference_rows(rows: List[Dict[str, Any]], symbols: List[str], listings: Dict[str, Any], kind: str) -> Dict[str, List[Dict[str, Any]]]:
    output: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in symbols}
    for row in rows:
        symbol = _symbol(row)
        if symbol not in output:
            continue
        listing_id = listings.get(symbol, {}).get("listingId")
        if listing_id and row.get("listing_id") and row.get("listing_id") != listing_id:
            continue
        if kind == "factor":
            compact = {
                "eventId": row.get("event_id"),
                "exDate": row.get("ex_date"),
                "status": row.get("status"),
                "factor": _number(row.get("factor")),
                "currency": row.get("currency"),
                "reason": row.get("reason"),
                "option": row.get("option"),
                "detail": row.get("detail"),
                "listingId": row.get("listing_id"),
            }
        else:
            compact = {
                "eventId": row.get("event_unique_id") or row.get("event_id"),
                "event": row.get("event"),
                "eventAction": row.get("event_action"),
                "status": row.get("global_status") or row.get("status"),
                "eventDate": row.get("event_date"),
                "effectiveDate": row.get("effective_date"),
                "exDate": row.get("ex_date"),
                "recordDate": row.get("record_date"),
                "paymentDate": row.get("payment_date"),
                "listingId": row.get("listing_id"),
                "updatedAt": row.get("ts_record"),
            }
        output[symbol].append(compact)
    for symbol in output:
        output[symbol] = output[symbol][-250:]
    return output


def _fetch_reference(symbols: List[str], listings: Dict[str, Any], start: dt.date, end: dt.date) -> tuple[Dict[str, Any], Dict[str, Any]]:
    common = {
        "symbols": symbols,
        "stype_in": "raw_symbol",
        "countries": "US",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "encoding": "json",
    }
    action_rows = _request_lines("corporate_actions.get_range", {**common, "pit": "true", "flatten": "true"})
    factor_rows = _request_lines("adjustment_factors.get_range", common)
    return (
        _compact_reference_rows(action_rows, symbols, listings, "action"),
        _compact_reference_rows(factor_rows, symbols, listings, "factor"),
    )


def refresh_market_integrity(symbols: Iterable[str], force: bool = False) -> Dict[str, Any]:
    normalized = [
        symbol for symbol in dict.fromkeys(str(value).upper() for value in symbols if value)
        if symbol != "BTC"
    ]
    with _LOCK:
        age = time.time() - int(_STATE.get("updatedAt") or 0)
        public_cached = bool(
            _STATE.get("coverage", {}).get("publicPrices")
            and _STATE.get("coverage", {}).get("publicActions")
        )
        if not force and age < REFRESH_SECONDS and public_cached:
            _STATE["status"] = "ready"
            _STATE["message"] = "Cost-controlled price and split checks are up to date"
            return market_integrity_snapshot(normalized)
        _STATE["status"] = "refreshing"
        _STATE["message"] = "Cross-checking daily closes and split-adjusted histories"

    today = dt.date.today()
    errors: List[str] = []
    coverage = {
        "prices": False,
        "listings": False,
        "actions": False,
        "factors": False,
        "publicPrices": False,
        "publicActions": False,
    }
    prices: Dict[str, Any] = {}
    listings: Dict[str, Any] = {}
    actions: Dict[str, Any] = {}
    factors: Dict[str, Any] = {}
    public_prices, public_actions, public_errors = _fetch_public_checks(normalized)
    coverage["publicPrices"] = bool(public_prices)
    coverage["publicActions"] = bool(public_actions)
    errors.extend(public_errors)

    if DATABENTO_API_KEY:
        try:
            prices = _fetch_prices(normalized, today - dt.timedelta(days=14), today + dt.timedelta(days=1))
            coverage["prices"] = True
        except RuntimeError as error:
            errors.append(f"Official closes: {error}")
        try:
            listings = _fetch_listings(normalized)
            coverage["listings"] = True
        except RuntimeError as error:
            errors.append(f"Institutional listings: {error}")
        if coverage["listings"]:
            try:
                actions, factors = _fetch_reference(
                    normalized,
                    listings,
                    today - dt.timedelta(days=400),
                    today + dt.timedelta(days=90),
                )
                coverage["actions"] = True
                coverage["factors"] = True
            except RuntimeError as error:
                # The paid reference-data product is an optional upgrade. Its absence
                # must not disable the cost-controlled daily checks.
                errors.append(f"Optional institutional corporate actions: {error}")

    with _LOCK:
        for name, fresh in (
            ("prices", prices), ("listings", listings), ("actions", actions), ("factors", factors),
            ("publicPrices", public_prices), ("publicActions", public_actions),
        ):
            if fresh:
                _STATE[name] = fresh
        _STATE["coverage"] = coverage
        _STATE["updatedAt"] = int(time.time())
        _STATE["errors"] = errors
        public_complete = len(public_prices) == len(normalized) and len(public_actions) == len(normalized)
        _STATE["status"] = "ready" if public_complete else "partial"
        _STATE["message"] = (
            "Cost-controlled price and split checks are up to date"
            if _STATE["status"] == "ready"
            else "Some public price or split checks need review"
        )
    try:
        _save_cache()
    except OSError:
        with _LOCK:
            _STATE["status"] = "partial"
            _STATE["errors"].append("The market-integrity cache could not be saved")
    return market_integrity_snapshot(normalized)


def _quote_cross_check(price: Dict[str, Any], quote: Dict[str, Any]) -> Dict[str, Any]:
    public_history = bool(price.get("priorClose") and "Yahoo" in str(price.get("source")))
    checked_close = _number(price.get("priorClose") if public_history else price.get("close"))
    quote_date = _date(quote.get("t"))
    checked_date = _date(price.get("date"))
    same_session = bool(not public_history and quote_date and checked_date and quote_date == checked_date)
    independent = _number(quote.get("c" if same_session else "pc"))
    comparison_name = "Finnhub session close/current price" if same_session else "Finnhub previous close"
    if not checked_close or not independent:
        return {"status": "unavailable", "differencePercent": None, "source": comparison_name}
    difference = abs(checked_close - independent) / checked_close * 100
    return {
        "status": "agrees" if difference <= PRICE_TOLERANCE_PERCENT else "review",
        "differencePercent": round(difference, 3),
        "checkedClose": checked_close,
        "checkedDate": price.get("priorDate") if public_history else price.get("date"),
        "independentClose": independent,
        "tolerancePercent": PRICE_TOLERANCE_PERCENT,
        "source": comparison_name,
    }


def market_integrity_snapshot(
    symbols: Iterable[str],
    market_data: Optional[Dict[str, Any]] = None,
    identities: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = list(dict.fromkeys(str(value).upper() for value in symbols if value))
    with _LOCK:
        state = {
            key: dict(value) if isinstance(value, dict) else list(value) if isinstance(value, list) else value
            for key, value in _STATE.items()
        }
    today = dt.date.today()
    records: Dict[str, Any] = {}
    for symbol in normalized:
        if symbol == "BTC":
            records[symbol] = {
                "status": "not_applicable",
                "ratingReady": False,
                "message": "US equity market-data checks do not apply to Bitcoin.",
            }
            continue
        institutional_price = state["prices"].get(symbol) if isinstance(state["prices"].get(symbol), dict) else {}
        public_price = state["publicPrices"].get(symbol) if isinstance(state["publicPrices"].get(symbol), dict) else {}
        price = institutional_price or public_price
        institutional_price_used = bool(institutional_price)
        listing = state["listings"].get(symbol) if isinstance(state["listings"].get(symbol), dict) else {}
        public_action = (
            state["publicActions"].get(symbol)
            if isinstance(state["publicActions"].get(symbol), dict)
            else {}
        )
        quote = (market_data or {}).get(symbol, {}).get("quote", {})
        cross_check = _quote_cross_check(price, quote if isinstance(quote, dict) else {})
        price_date = _date(price.get("date"))
        fresh = bool(price_date and (today - price_date).days <= 4)
        expected_identity = (identities or {}).get(symbol, {})
        expected_figi = expected_identity.get("identifiers", {}).get("figi") if isinstance(expected_identity, dict) else None
        expected_currency = expected_identity.get("listing", {}).get("currency") if isinstance(expected_identity, dict) else None
        if listing:
            identity_agrees = bool(
                listing.get("status") == "resolved"
                and listing.get("currency") == "USD"
                and (not expected_figi or not listing.get("figi") or expected_figi == listing.get("figi"))
            )
        else:
            identity_agrees = bool(expected_identity.get("status") == "resolved" and expected_currency == "USD")
        reference_ready = bool(state["coverage"].get("actions") and state["coverage"].get("factors"))
        public_action_ready = public_action.get("status") == "clear"
        corporate_action_ready = bool(reference_ready or public_action_ready)
        rating_ready = bool(fresh and cross_check.get("status") == "agrees" and identity_agrees and corporate_action_ready)
        institutional_verified = bool(rating_ready and institutional_price_used and reference_ready)
        if rating_ready and institutional_verified:
            status = "verified"
            message = "Official close, independent cross-check and corporate-action state agree."
        elif rating_ready:
            status = "cross_checked"
            message = "Two price feeds agree and no unexplained split-sized jump was found."
        elif price and not fresh:
            status = "stale"
            message = "The checked closing price is too old to support a rating."
        else:
            status = "review"
            message = "A price, identity or split-adjustment check needs review."
        records[symbol] = {
            "status": status,
            "ratingReady": rating_ready,
            "institutionalVerified": institutional_verified,
            "message": message,
            "checkedClose": price or None,
            "officialClose": institutional_price or None,
            "listing": listing or None,
            "crossCheck": cross_check,
            "corporateActionsChecked": corporate_action_ready,
            "adjustmentFactorsChecked": bool(state["coverage"].get("factors")),
            "corporateActionMethod": "institutional" if reference_ready else "public_anomaly_check",
            "recentActionCount": (
                len(state["actions"].get(symbol, []))
                if reference_ready
                else len(public_action.get("splitEvents", []))
            ),
            "recentActions": (
                state["actions"].get(symbol, [])[-5:]
                if reference_ready
                else public_action.get("splitEvents", [])[-5:]
            ),
            "publicActionCheck": public_action or None,
        }

    rated = [record for symbol, record in records.items() if symbol != "BTC"]
    ready_count = sum(record.get("ratingReady") is True for record in rated)
    institutional_count = sum(record.get("institutionalVerified") is True for record in rated)
    summary = {
        "adapterReady": True,
        "keyConfigured": bool(DATABENTO_API_KEY),
        "mode": "institutional" if institutional_count else "cost_controlled",
        "provider": "Databento plus public cross-checks" if DATABENTO_API_KEY else "Public cross-checks",
        "priceSource": (
            "Nasdaq NLS+ official consolidated end-of-day summary"
            if DATABENTO_API_KEY
            else "Yahoo adjusted daily close independently checked against Finnhub"
        ),
        "corporateActionSource": (
            "Optional Databento point-in-time actions when entitled; otherwise split-event and discontinuity checks"
        ),
        "ratedSymbols": len(rated),
        "priceRecords": sum(bool(record.get("checkedClose")) for record in rated),
        "ratingReady": ready_count,
        "allRatingReady": bool(rated) and ready_count == len(rated),
        "institutionalVerified": institutional_count,
        "premiumRequired": False,
        "premiumUpgradeAvailable": True,
        "coverage": state["coverage"],
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": state["status"],
        "message": state["message"],
        "updatedAt": state["updatedAt"],
        "summary": summary,
        "instruments": records,
        "errors": state["errors"],
        "sources": [
            {"name": "CTA/CQ SIP — Tape A and B", "tier": 1, "url": "https://www.nyse.com/data/cta"},
            {"name": "UTP SIP — Tape C", "tier": 1, "url": "https://utpplan.com/PageParts/Overview.html"},
            {"name": "DTCC corporate actions", "tier": 1, "url": "https://www.dtcc.com/data-services/corporate-actions-and-reference-data"},
            {"name": "Databento pay-as-you-go official daily closes", "tier": 2, "url": "https://databento.com/docs/examples/equities/closing-prices"},
            {"name": "Yahoo adjusted history", "tier": 3, "url": "https://finance.yahoo.com/"},
            {"name": "Finnhub independent price check", "tier": 3, "url": "https://finnhub.io/"},
        ],
    }


def institutional_history(symbol: str, start: dt.date, end: dt.date) -> Dict[str, Any]:
    """Fetch and adjust official daily closes; never return an unadjusted series as adjusted."""
    symbol = symbol.upper()
    start = max(start, SUPPORTED_FROM)
    rows = _request_lines("timeseries.get_range", {
        "dataset": DATABENTO_DATASET,
        "schema": "ohlcv-1d",
        "symbols": symbol,
        "stype_in": "raw_symbol",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "encoding": "json",
        "pretty_px": "true",
        "pretty_ts": "true",
        "map_symbols": "true",
    })
    points: List[Dict[str, Any]] = []
    for row in rows:
        observation_date = _date(_timestamp(row))
        close = _number(row.get("close"))
        if observation_date and close and close > 0:
            points.append({"date": observation_date.isoformat(), "close": close})
    points = list({point["date"]: point for point in points}.values())
    points.sort(key=lambda point: point["date"])
    if not points:
        raise RuntimeError("No institutional closing prices were returned")

    listings = _fetch_listings([symbol])
    listing = listings.get(symbol, {})
    if listing.get("status") != "resolved" or not listing.get("listingId"):
        raise RuntimeError("The institutional primary listing was not resolved")
    common = {
        "symbols": symbol,
        "stype_in": "raw_symbol",
        "countries": "US",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "encoding": "json",
    }
    factor_rows = _request_lines("adjustment_factors.get_range", common)
    factors = _compact_reference_rows(factor_rows, [symbol], listings, "factor").get(symbol, [])
    applicable: Dict[tuple[str, str], Dict[str, Any]] = {}
    for factor in factors:
        key = (str(factor.get("eventId")), str(factor.get("exDate")))
        if factor.get("status") == "R":
            applicable.pop(key, None)
        elif factor.get("status") == "A" and factor.get("option") in {None, 1} and factor.get("factor"):
            applicable[key] = factor
    for factor in applicable.values():
        ex_date = str(factor.get("exDate") or "")[:10]
        multiplier = _number(factor.get("factor"))
        if not ex_date or not multiplier:
            continue
        for point in points:
            if point["date"] < ex_date:
                point["close"] *= multiplier
    return {
        "points": [{**point, "close": round(point["close"], 8)} for point in points],
        "rawPointCount": len(points),
        "source": "Nasdaq NLS+ official consolidated closes and Databento adjustment factors",
        "method": "Institutional daily closes adjusted only with listing-matched, active corporate-action factors",
        "institutional": True,
        "limited": start == SUPPORTED_FROM,
    }


_load_cache()
