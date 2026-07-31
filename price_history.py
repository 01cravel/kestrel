"""Lazy, cached historical-price access for Kestrel charts."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-history-cache.json"
FMP_REQUEST_GAP_SECONDS = 0.3
HISTORY_TTL_SECONDS = 12 * 60 * 60
RANGE_DAYS = {
    "1w": 7,
    "1m": 31,
    "1y": 365,
    "5y": 5 * 365,
    "all": 60 * 366,
}
YAHOO_RANGES = {
    "1d": ("1d", "5m"),
    "1w": ("5d", "30m"),
    "1m": ("1mo", "1d"),
    "1y": ("1y", "1d"),
    "5y": ("5y", "1wk"),
}

_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_CACHE: Optional[Dict[str, Any]] = None


def load_fmp_key() -> str:
    configured = os.environ.get("FMP_KEY", "").strip()
    if configured:
        return configured
    legacy_path = ROOT / "kestrel-legacy.html"
    if legacy_path.exists():
        content = legacy_path.read_text(encoding="utf-8")
        match = re.search(r"const FMP_KEY = '([^']+)'", content)
        if match:
            return match.group(1)
    return ""


FMP_KEY = load_fmp_key()


def _load_cache() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        _CACHE = payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        _CACHE = {}
    return _CACHE


def _save_cache() -> None:
    if _CACHE is None:
        return
    temporary_path = CACHE_PATH.with_suffix(".tmp")
    try:
        temporary_path.write_text(json.dumps(_CACHE), encoding="utf-8")
        temporary_path.replace(CACHE_PATH)
    except OSError:
        return


def fmp_json(path: str, params: Dict[str, str]) -> Any:
    global _LAST_REQUEST
    if not FMP_KEY:
        raise RuntimeError("An FMP API key is required for historical prices")
    with _LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST
        if elapsed < FMP_REQUEST_GAP_SECONDS:
            time.sleep(FMP_REQUEST_GAP_SECONDS - elapsed)
        query = dict(params)
        query["apikey"] = FMP_KEY
        url = "https://financialmodelingprep.com/stable/" + path + "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers={"User-Agent": "Kestrel local portfolio dashboard"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                _LAST_REQUEST = time.monotonic()
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            _LAST_REQUEST = time.monotonic()
            if error.code == 402:
                raise RuntimeError("This data is not included for the symbol on the current FMP plan") from error
            raise RuntimeError(f"Historical price service returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            _LAST_REQUEST = time.monotonic()
            raise RuntimeError("Historical prices were unavailable") from error


def _downsample(points: List[Dict[str, Any]], maximum: int = 360) -> List[Dict[str, Any]]:
    if len(points) <= maximum:
        return points
    interior = points[1:-1]
    bucket_count = max(1, (maximum - 2) // 2)
    bucket_size = max(1, math.ceil(len(interior) / bucket_count))
    sampled = [points[0]]
    for start in range(0, len(interior), bucket_size):
        bucket = interior[start:start + bucket_size]
        if not bucket:
            continue
        low = min(bucket, key=lambda point: point["close"])
        high = max(bucket, key=lambda point: point["close"])
        sampled.extend(sorted({low["date"]: low, high["date"]: high}.values(), key=lambda point: point["date"]))
    sampled.append(points[-1])
    return sampled


def _yahoo_payload(symbol: str, range_name: str, latest_price: Optional[float]) -> Dict[str, Any]:
    cache = _load_cache()
    cache_key = f"yahoo:v1:{symbol}:{range_name}"
    now = int(time.time())
    cached = cache.get(cache_key)
    ttl = 15 * 60 if range_name == "1d" else HISTORY_TTL_SECONDS
    if isinstance(cached, dict) and now - int(cached.get("fetchedAt") or 0) < ttl:
        payload = dict(cached)
    else:
        base_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        if range_name == "all":
            query = {
                "period1": "0",
                "period2": str(now),
                "interval": "1mo",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            }
        else:
            yahoo_range, interval = YAHOO_RANGES[range_name]
            query = {
                "range": yahoo_range,
                "interval": interval,
                "events": "div,splits",
                "includeAdjustedClose": "true",
            }
        url = base_url + "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 Kestrel local portfolio dashboard"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                document = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Fallback price service returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise RuntimeError("Fallback price history was unavailable") from error

        chart = document.get("chart", {}) if isinstance(document, dict) else {}
        results = chart.get("result") or []
        if not results:
            message = chart.get("error", {}).get("description") if isinstance(chart.get("error"), dict) else None
            raise RuntimeError(message or "No fallback price history was returned")
        result = results[0]
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators", {})
        quote_rows = indicators.get("quote") or [{}]
        closes = quote_rows[0].get("close") or []
        adjusted_rows = indicators.get("adjclose") or [{}]
        adjusted = adjusted_rows[0].get("adjclose") or []
        use_adjusted = range_name not in {"1d", "1w"} and len(adjusted) == len(timestamps)
        values = adjusted if use_adjusted else closes
        points = []
        for timestamp, close in zip(timestamps, values):
            try:
                parsed_close = float(close)
                parsed_timestamp = int(timestamp)
            except (TypeError, ValueError):
                continue
            moment = dt.datetime.fromtimestamp(parsed_timestamp, tz=dt.timezone.utc)
            points.append({
                "date": moment.date().isoformat(),
                "timestamp": parsed_timestamp,
                "close": round(parsed_close, 6),
            })
        points.sort(key=lambda point: point["timestamp"])
        if not points:
            raise RuntimeError("No usable fallback prices were returned")
        method = {
            "1d": "Five-minute intraday prices",
            "1w": "Thirty-minute prices across five trading days",
            "1m": "Adjusted daily prices",
            "1y": "Adjusted daily prices",
            "5y": "Adjusted weekly prices",
            "all": "Adjusted monthly prices across the available listing history",
        }[range_name]
        payload = {
            "symbol": symbol,
            "range": range_name,
            "points": _downsample(points),
            "rawPointCount": len(points),
            "fetchedAt": now,
            "source": "Yahoo Finance chart feed",
            "method": method,
            "fallback": True,
        }
        cache[cache_key] = payload
        _save_cache()

    points = list(payload.get("points", []))
    if latest_price and points:
        last_close = float(points[-1]["close"])
        difference = abs(latest_price - last_close) / last_close * 100 if last_close else None
        payload["latestCrossCheck"] = {
            "status": "agrees" if difference is not None and difference <= 5 else "review",
            "differencePercent": round(difference, 2) if difference is not None else None,
            "source": "Finnhub current quote",
        }
    first = float(points[0]["close"]) if points else None
    last = float(points[-1]["close"]) if points else None
    payload["periodReturn"] = round((last - first) / first * 100, 2) if first and last else None
    payload["limited"] = range_name == "1d" and len(points) < 4
    return payload


def intraday_prices(symbol: str, latest_price: Optional[float] = None) -> Dict[str, Any]:
    return _yahoo_payload(symbol.upper(), "1d", latest_price)


def historical_prices(symbol: str, range_name: str, latest_price: Optional[float] = None) -> Dict[str, Any]:
    range_name = range_name.lower()
    if range_name not in RANGE_DAYS:
        raise ValueError("Unsupported history range")
    symbol = symbol.upper()
    cache_key = f"v3:{symbol}:{range_name}"
    now = int(time.time())
    cache = _load_cache()
    cached = cache.get(cache_key)
    if isinstance(cached, dict) and now - int(cached.get("fetchedAt") or 0) < HISTORY_TTL_SECONDS:
        payload = dict(cached)
    else:
        today = dt.date.today()
        start = today - dt.timedelta(days=RANGE_DAYS[range_name])
        raw = []
        cursor_to = today
        maximum_batches = 6 if range_name == "all" else 1
        try:
            for _ in range(maximum_batches):
                batch = fmp_json(
                    "historical-price-eod/full",
                    {
                        "symbol": symbol,
                        "from": start.isoformat(),
                        "to": cursor_to.isoformat(),
                    },
                )
                if not isinstance(batch, list):
                    message = batch.get("Error Message") if isinstance(batch, dict) else None
                    raise RuntimeError(message or "Historical prices returned an unexpected response")
                raw.extend(batch)
                if range_name != "all" or len(batch) < 5000:
                    break
                batch_dates = []
                for item in batch:
                    try:
                        batch_dates.append(dt.date.fromisoformat(str(item.get("date", ""))[:10]))
                    except (AttributeError, TypeError, ValueError):
                        continue
                if not batch_dates:
                    break
                next_cursor = min(batch_dates) - dt.timedelta(days=1)
                if next_cursor >= cursor_to or next_cursor <= start:
                    break
                cursor_to = next_cursor
        except RuntimeError:
            return _yahoo_payload(symbol, range_name, latest_price)
        points = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            date_value = str(item.get("date", ""))[:10]
            try:
                close = float(item.get("close"))
                date = dt.date.fromisoformat(date_value)
            except (TypeError, ValueError):
                continue
            points.append({
                "date": date.isoformat(),
                "timestamp": int(dt.datetime.combine(date, dt.time(16, 0), tzinfo=dt.timezone.utc).timestamp()),
                "close": round(close, 6),
            })
        points = list({point["date"]: point for point in points}.values())
        points.sort(key=lambda point: point["date"])
        if not points:
            raise RuntimeError("No historical prices were returned for this symbol")
        payload = {
            "symbol": symbol,
            "range": range_name,
            "points": _downsample(points),
            "rawPointCount": len(points),
            "fetchedAt": now,
            "source": "Financial Modeling Prep",
            "method": "Split-adjusted end-of-day prices",
        }
        cache[cache_key] = payload
        _save_cache()

    points = list(payload.get("points", []))
    if latest_price and points:
        last_close = float(points[-1]["close"])
        difference = abs(latest_price - last_close) / last_close * 100 if last_close else None
        payload["latestCrossCheck"] = {
            "status": "agrees" if difference is not None and difference <= 5 else "review",
            "differencePercent": round(difference, 2) if difference is not None else None,
            "source": "Finnhub current quote",
        }
    first = float(points[0]["close"]) if points else None
    last = float(points[-1]["close"]) if points else None
    payload["periodReturn"] = round((last - first) / first * 100, 2) if first and last else None
    return payload
