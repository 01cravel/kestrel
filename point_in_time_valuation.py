"""As-filed valuation evidence for the Ultimate Portfolio companies.

Every earnings observation is filtered by its SEC filing date before it can be
used. Historical P/E observations pair those as-filed earnings with the first
split-normalized market close available on or after the filing date. Per-share
facts and share counts receive the matching mechanical split factor, preventing
later restatements or corporate actions from distorting the record.
"""

from __future__ import annotations

import csv
import io
import json
import math
import socket
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from sec_data import sec_identity, sec_bytes
from independent_price_check import cross_check_prices, nasdaq_raw_prices
from point_in_time_cashflow import build_company_cashflow


COMPANIES = ("TSM", "GOOGL", "AMZN", "ASML", "MELI", "ETN", "ISRG", "CEG")
EPS_TAGS = (
    ("us-gaap", "EarningsPerShareDiluted"),
    ("us-gaap", "EarningsPerShareBasicAndDiluted"),
    ("ifrs-full", "DilutedEarningsLossPerShare"),
    ("ifrs-full", "BasicAndDilutedEarningsPerShare"),
)
ALLOWED_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "6-K"}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
ADR_RATIOS = {"TSM": 5.0}
ADR_RATIO_SOURCES = {
    "TSM": "https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm",
}
HISTORY_YEARS = 10
MIN_HISTORY_POINTS = 5
CACHE_SECONDS = 12 * 60 * 60
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2020-01-01&format=csvdata"

_LOCK = threading.Lock()
_CACHE: Optional[Dict[str, Any]] = None


def _json_url(url: str) -> Any:
    return json.loads(sec_bytes(url).decode("utf-8"))


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 Kestrel point-in-time valuation research",
        "Accept": "application/json,text/csv,text/plain",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8-sig", errors="replace")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Price or FX source returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
        raise RuntimeError("Price or FX evidence was unavailable") from error


def _parse_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _duration(entry: Dict[str, Any]) -> Optional[int]:
    start = _parse_date(entry.get("start"))
    end = _parse_date(entry.get("end"))
    return (end - start).days if start and end else None


def _eligible(entries: Iterable[Dict[str, Any]], as_of: date) -> List[Dict[str, Any]]:
    rows = []
    for entry in entries:
        filed = _parse_date(entry.get("filed"))
        end = _parse_date(entry.get("end"))
        duration = _duration(entry)
        try:
            value = float(entry.get("val"))
        except (TypeError, ValueError):
            continue
        if (
            entry.get("form") in ALLOWED_FORMS and filed and filed <= as_of
            and end and duration is not None and 20 <= duration <= 430 and math.isfinite(value)
        ):
            rows.append({**entry, "val": value, "_filed": filed, "_end": end, "_duration": duration})
    return rows


def ttm_eps_as_of(entries: Iterable[Dict[str, Any]], as_of: date) -> Optional[Dict[str, Any]]:
    """Return TTM EPS using only facts filed on or before ``as_of``.

    For an interim filing the conventional bridge is used:
    latest annual EPS + current YTD EPS - prior-year comparable YTD EPS.
    """
    rows = _eligible(entries, as_of)
    annuals = [row for row in rows if row["form"] in ANNUAL_FORMS and 300 <= row["_duration"] <= 430]
    if not annuals:
        return None
    annual = max(annuals, key=lambda row: (row["_end"], row["_filed"]))
    result = {
        "eps": annual["val"], "periodEnd": annual["end"], "filed": annual["filed"],
        "form": annual["form"], "accession": annual.get("accn"),
        "method": "Latest as-filed annual diluted EPS", "components": [annual.get("accn")],
    }

    later_interims = [
        row for row in rows
        if row["form"] not in ANNUAL_FORMS and row["_end"] > annual["_end"]
        and row["_duration"] <= 300
    ]
    if not later_interims:
        return result
    latest_end = max(row["_end"] for row in later_interims)
    latest_filed = max(row["_filed"] for row in later_interims if row["_end"] == latest_end)
    latest_accessions = {
        row.get("accn") for row in later_interims
        if row["_end"] == latest_end and row["_filed"] == latest_filed
    }
    filing_rows = [row for row in rows if row.get("accn") in latest_accessions]
    current_candidates = [row for row in filing_rows if row["_end"] == latest_end and row["_duration"] <= 300]
    if not current_candidates:
        return result
    current = max(current_candidates, key=lambda row: row["_duration"])
    prior_candidates = [
        row for row in filing_rows
        if 300 <= (current["_end"] - row["_end"]).days <= 430
        and abs(row["_duration"] - current["_duration"]) <= 35
    ]
    if not prior_candidates:
        return result
    prior = min(
        prior_candidates,
        key=lambda row: (abs((current["_end"] - row["_end"]).days - 365), abs(row["_duration"] - current["_duration"])),
    )
    eps = annual["val"] + current["val"] - prior["val"]
    return {
        "eps": eps, "periodEnd": current["end"], "filed": current["filed"],
        "form": current["form"], "accession": current.get("accn"),
        "method": "As-filed annual EPS plus current YTD minus prior comparable YTD",
        "components": [annual.get("accn"), current.get("accn")],
    }


def _eps_facts(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    facts = payload.get("facts") or {}
    for taxonomy, tag in EPS_TAGS:
        concept = (facts.get(taxonomy) or {}).get(tag) or {}
        units = concept.get("units") or {}
        for unit in ("USD/shares", "EUR/shares"):
            rows = units.get(unit)
            if isinstance(rows, list) and rows:
                return [row for row in rows if isinstance(row, dict)], unit.split("/")[0], f"{taxonomy}:{tag}"
    return [], None, None


def _raw_prices(symbol: str, downloader: Callable[[str], str]) -> List[Dict[str, Any]]:
    yahoo_symbol = urllib.parse.quote(symbol)
    query = urllib.parse.urlencode({
        "range": f"{HISTORY_YEARS}y", "interval": "1d", "events": "splits",
        "includeAdjustedClose": "false",
    })
    payload = json.loads(downloader(f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?{query}"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError("No price history was returned")
    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    splits = []
    for event in (((result.get("events") or {}).get("splits") or {}).values()):
        try:
            split_day = datetime.utcfromtimestamp(int(event.get("date"))).date()
            ratio = float(event.get("numerator")) / float(event.get("denominator"))
        except (TypeError, ValueError, ZeroDivisionError, OSError):
            try:
                left, right = str(event.get("splitRatio") or "").split(":", 1)
                ratio = float(left) / float(right)
                split_day = datetime.utcfromtimestamp(int(event.get("date"))).date()
            except (TypeError, ValueError, ZeroDivisionError, OSError):
                continue
        if ratio > 0 and math.isfinite(ratio):
            splits.append((split_day, ratio))
    rows = []
    for timestamp, close in zip(timestamps, closes):
        try:
            value = float(close)
            day = datetime.utcfromtimestamp(int(timestamp)).date()
        except (TypeError, ValueError, OSError):
            continue
        if value > 0 and math.isfinite(value):
            share_factor = math.prod(ratio for split_day, ratio in splits if split_day > day)
            rows.append({"date": day, "close": value, "shareFactor": share_factor})
    if not rows:
        raise RuntimeError("No usable raw closing prices were returned")
    return sorted(rows, key=lambda row: row["date"])


def _ecb_rates(downloader: Callable[[str], str]) -> Dict[date, float]:
    rows = csv.DictReader(io.StringIO(downloader(ECB_URL)))
    result = {}
    for row in rows:
        day = _parse_date(row.get("TIME_PERIOD"))
        try:
            value = float(row.get("OBS_VALUE"))
        except (TypeError, ValueError):
            continue
        if day and value > 0:
            result[day] = value
    return result


def _on_or_after(rows: List[Dict[str, Any]], day: date, limit_days: int = 7) -> Optional[Dict[str, Any]]:
    return next((row for row in rows if day <= row["date"] <= day + timedelta(days=limit_days)), None)


def _on_or_before(values: Dict[date, float], day: date, limit_days: int = 7) -> Optional[float]:
    for offset in range(limit_days + 1):
        value = values.get(day - timedelta(days=offset))
        if value is not None:
            return value
    return None


def _percentile_rank(values: List[float], target: float) -> float:
    if not values:
        return 0.5
    below = sum(value < target for value in values)
    equal = sum(value == target for value in values)
    return (below + 0.5 * equal) / len(values)


def _accession_url(cik: str, accession: Any) -> Optional[str]:
    if not accession:
        return None
    compact = str(accession).replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{compact}/"


def build_company_valuation(symbol: str, cik: str, companyfacts: Dict[str, Any],
                            prices: List[Dict[str, Any]], fx_rates: Dict[date, float],
                            today: Optional[date] = None) -> Dict[str, Any]:
    current_day = today or date.today()
    entries, currency, tag = _eps_facts(companyfacts)
    base = {
        "symbol": symbol, "cik": cik, "companyName": companyfacts.get("entityName"),
        "currency": currency, "taxonomyTag": tag,
        "source": "SEC EDGAR Company Facts", "sourceUrl": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        "priceSource": "Yahoo Finance split-normalized historical close", "priceSourceStatus": "provisional",
        "adrRatio": ADR_RATIOS.get(symbol, 1.0), "adrRatioSource": ADR_RATIO_SOURCES.get(symbol),
    }
    if not entries:
        return {**base, "status": "unavailable", "message": "No standard diluted EPS facts were available."}
    current = ttm_eps_as_of(entries, current_day)
    latest_price = prices[-1] if prices else None
    if not current or not latest_price:
        return {**base, "status": "unavailable", "message": "Earnings or current price evidence was incomplete."}

    def converted_eps(snapshot: Dict[str, Any], price: Dict[str, Any]) -> Optional[float]:
        value = float(snapshot["eps"]) * ADR_RATIOS.get(symbol, 1.0)
        value /= float(price.get("shareFactor") or 1.0)
        if currency == "EUR":
            fx = _on_or_before(fx_rates, price["date"])
            return value * fx if fx else None
        return value if currency == "USD" else None

    history = []
    filing_days = sorted({day for entry in entries if (day := _parse_date(entry.get("filed"))) and day <= current_day})
    cutoff = current_day - timedelta(days=HISTORY_YEARS * 366)
    for filing_day in [day for day in filing_days if day >= cutoff]:
        earnings = ttm_eps_as_of(entries, filing_day)
        price = _on_or_after(prices, filing_day)
        eps = converted_eps(earnings, price) if earnings and price else None
        if not earnings or not price or eps is None or eps <= 0:
            continue
        pe = price["close"] / eps
        if 0 < pe <= 300:
            history.append({
                "knownOn": filing_day.isoformat(), "priceDate": price["date"].isoformat(),
                "price": round(price["close"], 4), "ttmEps": round(eps, 4), "pe": round(pe, 2),
                "filingUrl": _accession_url(cik, earnings.get("accession")),
            })
    # Repeated comparative facts can generate the same valuation state. Keep
    # one record per underlying earnings accession.
    history = list({(row["knownOn"], row["ttmEps"]): row for row in history}.values())
    historical_pes = [row["pe"] for row in history[:-1]] if len(history) > 1 else []
    current_eps = converted_eps(current, latest_price)
    if current_eps is None or current_eps <= 0:
        return {**base, "status": "unavailable", "message": "Reported earnings could not be translated into the traded share currency."}
    current_pe = latest_price["close"] / current_eps
    filed = _parse_date(current.get("filed"))
    filing_age = (current_day - filed).days if filed else None
    price_age = (current_day - latest_price["date"]).days
    annual = current.get("form") in ANNUAL_FORMS
    fresh = filing_age is not None and filing_age <= (450 if annual else 200) and price_age <= 7
    enough_history = len(historical_pes) >= MIN_HISTORY_POINTS
    rank = _percentile_rank(historical_pes, current_pe) if enough_history else None
    verdict = "Not enough history"
    if rank is not None:
        verdict = "Cheaper than usual" if rank <= 0.25 else "Within its own range" if rank <= 0.75 else "More expensive than usual"
    return {
        **base,
        "status": "verified" if fresh and enough_history else "partial",
        "message": "As-filed earnings were paired with prices available after publication.",
        "current": {
            "price": round(latest_price["close"], 2), "priceDate": latest_price["date"].isoformat(),
            "ttmEps": round(current_eps, 4), "pe": round(current_pe, 2),
            "earningsYield": round(100 / current_pe, 2), "filed": current.get("filed"),
            "periodEnd": current.get("periodEnd"), "form": current.get("form"),
            "filingAgeDays": filing_age, "priceAgeDays": price_age,
            "filingUrl": _accession_url(cik, current.get("accession")), "method": current.get("method"),
        },
        "history": history,
        "comparison": {
            "observations": len(historical_pes),
            "medianPe": round(statistics.median(historical_pes), 2) if historical_pes else None,
            "percentile": round(rank * 100, 1) if rank is not None else None,
            "verdict": verdict,
        },
        "ready": fresh and enough_history,
    }


def point_in_time_valuation_snapshot(force: bool = False,
                                     sec_provider: Callable[[str], Any] = _json_url,
                                     downloader: Callable[[str], str] = _download,
                                     today: Optional[date] = None) -> Dict[str, Any]:
    global _CACHE
    now = int(time.time())
    with _LOCK:
        if sec_provider is _json_url and downloader is _download and not force and _CACHE and now - int(_CACHE.get("generatedAt") or 0) < CACHE_SECONDS:
            return dict(_CACHE)
        try:
            fx_rates = _ecb_rates(downloader)
        except RuntimeError:
            fx_rates = {}
        companies: Dict[str, Any] = {}
        cashflow_companies: Dict[str, Any] = {}
        for symbol in COMPANIES:
            try:
                identity = sec_identity(symbol)
                cik = str(identity.get("cik") or "")
                if not cik:
                    raise RuntimeError("No SEC filer identity was available")
                facts = sec_provider(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
                prices = _raw_prices(symbol, downloader)
                record = build_company_valuation(symbol, cik, facts, prices, fx_rates, today=today)
                cashflow_record = build_company_cashflow(symbol, cik, facts, prices, fx_rates, today=today)
                try:
                    independent = nasdaq_raw_prices(symbol, downloader, today=today, years=HISTORY_YEARS)
                    price_record = {
                        **record,
                        "history": [*(record.get("history") or []), *(cashflow_record.get("history") or [])],
                    }
                    price_check = cross_check_prices(price_record, independent)
                except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                    price_check = {
                        "status": "unavailable", "ready": False,
                        "source": "Nasdaq official historical close",
                        "sourceUrl": f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}/historical",
                        "message": str(error), "datesRequired": len(record.get("history") or []) + 1,
                        "datesMatched": 0, "coveragePct": 0.0,
                    }
                record["independentPriceCheck"] = price_check
                record["priceSourceStatus"] = "verified" if price_check.get("ready") else "provisional"
                companies[symbol] = record
                cashflow_companies[symbol] = cashflow_record
            except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                companies[symbol] = {"symbol": symbol, "status": "error", "ready": False, "message": str(error)}
                cashflow_companies[symbol] = {"symbol": symbol, "status": "error", "ready": False, "message": str(error)}
        ready = sum(bool(record.get("ready")) for record in companies.values())
        cashflow_ready = sum(bool(record.get("ready")) for record in cashflow_companies.values())
        price_cross_check_ready = all(
            record.get("priceSourceStatus") == "verified" for record in companies.values()
        )
        price_checks_ready = sum(
            bool((record.get("independentPriceCheck") or {}).get("ready"))
            for record in companies.values()
        )
        cashflow_complete = cashflow_ready == len(COMPANIES)
        complete = ready == len(COMPANIES) and cashflow_complete and price_cross_check_ready
        payload = {
            "status": "complete" if complete else "incomplete",
            "complete": complete,
            "asFiledComplete": ready == len(COMPANIES),
            "priceCrossCheckReady": price_cross_check_ready,
            "priceChecksReady": price_checks_ready,
            "priceChecksTotal": len(COMPANIES),
            "cashFlow": {
                "status": "complete" if cashflow_complete else "incomplete",
                "complete": cashflow_complete,
                "companiesReady": cashflow_ready,
                "companiesTotal": len(COMPANIES),
                "companies": cashflow_companies,
                "method": "As-filed operating cash flow less productive-asset purchases, valued against each company's own history",
                "warning": "Free cash flow can be temporarily depressed by deliberate growth investment; it confirms valuation rather than forecasting returns.",
            },
            "companiesReady": ready, "companiesTotal": len(COMPANIES),
            "companies": companies,
            "method": "Trailing P/E and free-cash-flow yield from SEC facts known on each date, paired with the first split-normalized close and matching share adjustment",
            "warning": (
                "P/E is one valuation lens, not a return forecast. "
                + ("Yahoo working closes agree with Nasdaq's independent official history."
                   if price_cross_check_ready else "Missing or conflicting independent prices keep the science gate closed.")
            ),
            "generatedAt": now,
        }
        if sec_provider is _json_url and downloader is _download:
            _CACHE = dict(payload)
        return payload
