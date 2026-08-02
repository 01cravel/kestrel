"""Named analyst evidence with explicit source, recency and disagreement checks."""

from __future__ import annotations

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
CACHE_PATH = ROOT / ".kestrel-analyst-sources.json"
SECRETS_PATH = ROOT / ".kestrel-secrets.json"


def _load_private_key(name: str) -> str:
    configured = os.environ.get(name, "").strip()
    if configured:
        return configured
    try:
        secrets = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        value = secrets.get(name) if isinstance(secrets, dict) else None
        return str(value or "").strip()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ""


BENZINGA_API_KEY = _load_private_key("BENZINGA_API_KEY")
BENZINGA_URL = "https://api.benzinga.com/api/v2.1/calendar/ratings"
SCHEMA_VERSION = 3
REFRESH_SECONDS = 24 * 60 * 60
LOOKBACK_DAYS = 400
RECENT_DAYS = 120

_LOCK = threading.RLock()
_STATE: Dict[str, Any] = {
    "status": "starting",
    "message": "Preparing named analyst checks",
    "updatedAt": None,
    "lastSuccessfulAt": None,
    "instruments": {},
    "errors": [],
}


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else None
    except (TypeError, ValueError):
        return None


def _load_cache() -> None:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            return
        with _LOCK:
            _STATE["updatedAt"] = payload.get("updatedAt")
            _STATE["lastSuccessfulAt"] = payload.get("lastSuccessfulAt")
            _STATE["instruments"] = payload.get("instruments") or {}
            _STATE["errors"] = payload.get("errors") or []
            _STATE["status"] = payload.get("status") or "cached"
            _STATE["message"] = payload.get("message") or "Showing saved named analyst evidence"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return


def _save_cache() -> None:
    with _LOCK:
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "updatedAt": _STATE["updatedAt"],
            "lastSuccessfulAt": _STATE["lastSuccessfulAt"],
            "instruments": _STATE["instruments"],
            "errors": _STATE["errors"],
            "status": _STATE["status"],
            "message": _STATE["message"],
        }
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def _request_ratings(symbols: List[str], start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    if not BENZINGA_API_KEY:
        raise RuntimeError("A Benzinga Analyst Ratings API key is required")
    query = urllib.parse.urlencode({
        "token": BENZINGA_API_KEY,
        "parameters[tickers]": ",".join(symbols),
        "parameters[date_from]": start.isoformat(),
        "parameters[date_to]": end.isoformat(),
        "pagesize": "1000",
        "fields": "*",
    })
    request = urllib.request.Request(
        BENZINGA_URL + "?" + query,
        headers={
            "Accept": "application/json",
            "User-Agent": "Kestrel local portfolio dashboard",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise RuntimeError("The Benzinga key is invalid, expired or was copied incorrectly") from error
        if error.code == 403:
            raise RuntimeError("The Benzinga key is valid but Analyst Ratings access is not included") from error
        if error.code == 429:
            raise RuntimeError("Benzinga rate limit was reached") from error
        raise RuntimeError(f"Benzinga returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
        raise RuntimeError("Named analyst evidence was unavailable") from error
    rows = payload.get("ratings") if isinstance(payload, dict) else None
    return [row for row in (rows or []) if isinstance(row, dict)]


def _direction(rating: Any) -> str:
    normalized = str(rating or "").strip().lower().replace("_", " ")
    if not normalized:
        return "unknown"
    negative = ("sell", "underperform", "underweight", "reduce", "negative")
    positive = ("buy", "outperform", "overweight", "accumulate", "positive")
    neutral = ("hold", "neutral", "equal weight", "market perform", "sector perform", "peer perform")
    if any(value in normalized for value in negative):
        return "negative"
    if any(value in normalized for value in positive):
        return "positive"
    if any(value in normalized for value in neutral):
        return "neutral"
    return "unknown"


def _accuracy(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    return {
        "totalRatings": int(_number(raw.get("total_ratings")) or 0),
        "overallSuccessRate": _number(raw.get("overall_success_rate")),
        "overallAverageReturn": _number(raw.get("overall_average_return")),
        "smartScore": _number(raw.get("smart_score")),
    }


def _normalize(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = str(row.get("ticker") or "").upper()
    date = str(row.get("date") or "")[:10]
    firm = str(row.get("analyst") or row.get("firm_name") or "").strip()
    analyst = str(row.get("analyst_name") or "").strip()
    if not symbol or not date or not firm:
        return None
    current = row.get("rating_current")
    return {
        "id": row.get("id"),
        "symbol": symbol,
        "date": date,
        "firm": firm,
        "analyst": analyst or None,
        "analystId": row.get("analyst_id"),
        "action": row.get("action_company"),
        "rating": current,
        "priorRating": row.get("rating_prior"),
        "direction": _direction(current),
        "priceTarget": _number(row.get("pt_current") or row.get("adjusted_pt_current")),
        "priorPriceTarget": _number(row.get("pt_prior") or row.get("adjusted_pt_prior")),
        "targetAction": row.get("action_pt"),
        "importance": int(_number(row.get("importance")) or 0),
        "accuracy": _accuracy(row.get("ratings_accuracy")),
        "sourceUrl": row.get("url_news") or row.get("url_calendar") or row.get("url"),
        "source": "Benzinga Analyst Ratings API",
    }


def _finnhub_positive_share(raw: Any) -> Optional[float]:
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        return None
    row = raw[0]
    positive = (_number(row.get("strongBuy")) or 0) + (_number(row.get("buy")) or 0)
    total = positive + (_number(row.get("hold")) or 0) + (_number(row.get("sell")) or 0) + (_number(row.get("strongSell")) or 0)
    return positive / total * 100 if total else None


def _summarize(symbol: str, actions: List[Dict[str, Any]], market_data: Dict[str, Any]) -> Dict[str, Any]:
    today = dt.date.today()
    recent = []
    for action in actions:
        try:
            action_date = dt.date.fromisoformat(action["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if (today - action_date).days <= RECENT_DAYS:
            recent.append(action)
    recent.sort(key=lambda item: (item.get("date") or "", item.get("importance") or 0), reverse=True)
    firms = sorted({item["firm"] for item in recent if item.get("firm")})
    analysts = sorted({item["analyst"] for item in recent if item.get("analyst")})
    directional = [item for item in recent if item.get("direction") in {"positive", "neutral", "negative"}]
    positive_share = (
        sum(item["direction"] == "positive" for item in directional) / len(directional) * 100
        if directional else None
    )
    finnhub_share = _finnhub_positive_share(market_data.get(symbol, {}).get("recommendations"))
    difference = abs(positive_share - finnhub_share) if positive_share is not None and finnhub_share is not None else None
    conflict = bool(difference is not None and difference > 30)
    rating_ready = bool(len(firms) >= 3 and directional and difference is not None and not conflict)
    score = None
    if directional:
        values = {"positive": 80, "neutral": 50, "negative": 20}
        score = round(sum(values[item["direction"]] for item in directional) / len(directional), 2)
    return {
        "status": "ready" if rating_ready else "limited" if recent else "unavailable",
        "ratingReady": rating_ready,
        "message": (
            f"{len(firms)} named research firms have recent ratings and the independent consensus check agrees."
            if rating_ready
            else "Named analyst ratings disagree materially with the broader consensus."
            if conflict
            else "Named ratings are present, but the broader consensus cross-check is unavailable."
            if len(firms) >= 3 and directional and difference is None
            else "At least three recent named research firms are required before this evidence affects the rating."
        ),
        "recentActions": recent[:12],
        "recentActionCount": len(recent),
        "uniqueFirms": len(firms),
        "uniqueAnalysts": len(analysts),
        "positiveShare": round(positive_share, 2) if positive_share is not None else None,
        "score": score,
        "crossCheck": {
            "source": "Finnhub recommendation consensus",
            "positiveShare": round(finnhub_share, 2) if finnhub_share is not None else None,
            "differencePoints": round(difference, 2) if difference is not None else None,
            "status": "review" if conflict else "agrees" if difference is not None else "unavailable",
        },
        "source": "Benzinga named analyst ratings",
    }


def refresh_named_analysts(symbols: Iterable[str], market_data: Optional[Dict[str, Any]] = None, force: bool = False) -> Dict[str, Any]:
    normalized = [symbol for symbol in dict.fromkeys(str(value).upper() for value in symbols if value) if symbol != "BTC"]
    if not BENZINGA_API_KEY:
        with _LOCK:
            _STATE["status"] = "not_connected"
            _STATE["message"] = "Named analyst adapter is ready; Benzinga access is not connected"
        return named_analyst_snapshot(normalized, market_data)
    with _LOCK:
        age = time.time() - int(_STATE.get("lastSuccessfulAt") or 0)
        if not force and age < REFRESH_SECONDS and _STATE.get("instruments") and not _STATE.get("errors"):
            _STATE["status"] = "ready"
            _STATE["message"] = "Named analyst evidence is up to date"
            return named_analyst_snapshot(normalized, market_data)
        _STATE["status"] = "refreshing"
        _STATE["message"] = "Checking named analysts, firms, targets and track records"

    today = dt.date.today()
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    for start_index in range(0, len(normalized), 25):
        try:
            rows.extend(_request_ratings(normalized[start_index:start_index + 25], today - dt.timedelta(days=LOOKBACK_DAYS), today))
        except RuntimeError as error:
            errors.append(str(error))
            break
    if not rows and not errors:
        errors.append("Benzinga returned no analyst ratings for the requested universe")
    grouped: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in normalized}
    for row in rows:
        normalized_row = _normalize(row)
        if normalized_row and normalized_row["symbol"] in grouped:
            grouped[normalized_row["symbol"]].append(normalized_row)
    instruments = {
        symbol: _summarize(symbol, grouped[symbol], market_data or {})
        for symbol in normalized
    }
    covered = sum(bool(row.get("recentActions")) for row in instruments.values())
    with _LOCK:
        _STATE["instruments"] = instruments
        _STATE["updatedAt"] = int(time.time())
        _STATE["errors"] = errors
        _STATE["status"] = "ready" if not errors else "partial"
        _STATE["message"] = (
            f"Benzinga Analyst Ratings is connected; current access covers {covered} of {len(normalized)} eligible symbols"
            if not errors and covered < len(normalized)
            else "Named analyst evidence is up to date"
            if not errors
            else "Named analyst evidence needs review"
        )
        if not errors:
            _STATE["lastSuccessfulAt"] = _STATE["updatedAt"]
    try:
        _save_cache()
    except OSError:
        with _LOCK:
            _STATE["status"] = "partial"
            _STATE["errors"].append("The named analyst cache could not be saved")
    return named_analyst_snapshot(normalized, market_data)


def named_analyst_snapshot(symbols: Iterable[str], market_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    normalized = list(dict.fromkeys(str(value).upper() for value in symbols if value))
    with _LOCK:
        state = {
            key: dict(value) if isinstance(value, dict) else list(value) if isinstance(value, list) else value
            for key, value in _STATE.items()
        }
    instruments: Dict[str, Any] = {}
    for symbol in normalized:
        if symbol == "BTC":
            instruments[symbol] = {"status": "not_applicable", "ratingReady": False, "recentActions": []}
            continue
        stored = state["instruments"].get(symbol)
        if isinstance(stored, dict):
            # Re-run only the cross-provider comparison against the latest cached Finnhub consensus.
            actions = stored.get("recentActions") or []
            instruments[symbol] = _summarize(symbol, actions, market_data or {})
        else:
            instruments[symbol] = {
                "status": "not_connected" if not BENZINGA_API_KEY else "unavailable",
                "ratingReady": False,
                "message": (
                    "Named analyst evidence is not connected."
                    if not BENZINGA_API_KEY
                    else "Current Benzinga access returned no ratings for this symbol."
                ),
                "recentActions": [],
                "recentActionCount": 0,
                "uniqueFirms": 0,
                "uniqueAnalysts": 0,
                "positiveShare": None,
                "score": None,
                "source": "Benzinga named analyst ratings",
            }
    rated = [row for symbol, row in instruments.items() if symbol != "BTC"]
    ready = sum(row.get("ratingReady") is True for row in rated)
    covered = sum(bool(row.get("recentActions")) for row in rated)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": state["status"],
        "message": state["message"],
        "updatedAt": state["updatedAt"],
        "lastSuccessfulAt": state["lastSuccessfulAt"],
        "summary": {
            "keyConfigured": bool(BENZINGA_API_KEY),
            "provider": "Benzinga Analyst Ratings API",
            "ratedSymbols": len(rated),
            "coveredSymbols": covered,
            "ratingReady": ready,
            "allRatingReady": bool(rated) and ready == len(rated),
            "minimumIndependentFirms": 3,
            "premiumRequired": True,
        },
        "instruments": instruments,
        "errors": state["errors"],
        "sources": [
            {
                "name": "Benzinga named analyst ratings and analyst accuracy",
                "tier": 2,
                "url": "https://docs.benzinga.com/api-reference/calendar-api/get-ratings",
            },
            {
                "name": "Finnhub recommendation consensus cross-check",
                "tier": 3,
                "url": "https://finnhub.io/docs/api",
            },
            {
                "name": "Morningstar independent fair-value research — future licensed check",
                "tier": 2,
                "url": "https://www.morningstar.com/business/products/institutional-equity-research",
            },
        ],
    }


_load_cache()
