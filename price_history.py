"""Lazy, cached historical-price access for Kestrel charts."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from market_integrity import DATABENTO_API_KEY, institutional_history


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-history-cache.json"
FMP_REQUEST_GAP_SECONDS = 0.3
HISTORY_TTL_SECONDS = 12 * 60 * 60
PORTFOLIO_RISK_TTL_SECONDS = 12 * 60 * 60
_PORTFOLIO_RISK_CACHE: Dict[str, Dict[str, Any]] = {}
_PORTFOLIO_RISK_LOCK = threading.Lock()
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
YAHOO_SYMBOLS = {"BTC": "BTC-USD"}

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
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
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
    # Long monthly histories are model inputs as well as chart inputs. Keep the
    # complete monthly sequence instead of applying the denser chart cap, and
    # version that cache separately so previously thinned series are not reused.
    cache_version = "v2" if range_name == "all" else "v1"
    cache_key = f"yahoo:{cache_version}:{symbol}:{range_name}"
    now = int(time.time())
    cached = cache.get(cache_key)
    ttl = 15 * 60 if range_name == "1d" else HISTORY_TTL_SECONDS
    if isinstance(cached, dict) and now - int(cached.get("fetchedAt") or 0) < ttl:
        payload = dict(cached)
    else:
        yahoo_symbol = YAHOO_SYMBOLS.get(symbol, symbol)
        base_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo_symbol)}"
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
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
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
            "points": _downsample(points, maximum=720 if range_name == "all" else 360),
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


def historical_prices(
    symbol: str,
    range_name: str,
    latest_price: Optional[float] = None,
    request_institutional: bool = True,
) -> Dict[str, Any]:
    range_name = range_name.lower()
    if range_name not in RANGE_DAYS:
        raise ValueError("Unsupported history range")
    symbol = symbol.upper()
    if symbol in YAHOO_SYMBOLS:
        return _yahoo_payload(symbol, range_name, latest_price)
    if DATABENTO_API_KEY:
        institutional_key = f"databento:v1:{symbol}:{range_name}"
        now = int(time.time())
        cache = _load_cache()
        cached_institutional = cache.get(institutional_key)
        institutional_payload = None
        if isinstance(cached_institutional, dict) and now - int(cached_institutional.get("fetchedAt") or 0) < HISTORY_TTL_SECONDS:
            institutional_payload = dict(cached_institutional)
        elif request_institutional:
            today = dt.date.today()
            start = today - dt.timedelta(days=RANGE_DAYS[range_name])
            try:
                institutional_payload = institutional_history(symbol, start, today + dt.timedelta(days=1))
                points = []
                for point in institutional_payload.get("points", []):
                    try:
                        date = dt.date.fromisoformat(str(point.get("date"))[:10])
                        close = float(point.get("close"))
                    except (TypeError, ValueError):
                        continue
                    points.append({
                        "date": date.isoformat(),
                        "timestamp": int(dt.datetime.combine(date, dt.time(20, 0), tzinfo=dt.timezone.utc).timestamp()),
                        "close": round(close, 8),
                    })
                if not points:
                    raise RuntimeError("No institutional history points were usable")
                institutional_payload.update({
                    "symbol": symbol,
                    "range": range_name,
                    "points": _downsample(points),
                    "rawPointCount": len(points),
                    "fetchedAt": now,
                })
                cache[institutional_key] = institutional_payload
                _save_cache()
            except RuntimeError:
                institutional_payload = None
        if isinstance(institutional_payload, dict):
            points = list(institutional_payload.get("points", []))
            if latest_price and points:
                last_close = float(points[-1]["close"])
                difference = abs(latest_price - last_close) / last_close * 100 if last_close else None
                institutional_payload["latestCrossCheck"] = {
                    "status": "agrees" if difference is not None and difference <= 5 else "review",
                    "differencePercent": round(difference, 2) if difference is not None else None,
                    "source": "Finnhub current quote",
                }
            first = float(points[0]["close"]) if points else None
            last = float(points[-1]["close"]) if points else None
            institutional_payload["periodReturn"] = round((last - first) / first * 100, 2) if first and last else None
            return institutional_payload
    cache_key = f"v4:{symbol}:{range_name}"
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
                adjusted_close = item.get("adjClose")
                if adjusted_close is None:
                    adjusted_close = item.get("adjustedClose")
                close = float(adjusted_close if adjusted_close is not None else item.get("close"))
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
            "method": "End-of-day closing prices, adjusted where the source provides them",
        }
        cache[cache_key] = payload
        _save_cache()

    if payload.get("source") == "Financial Modeling Prep":
        payload["method"] = "End-of-day closing prices, adjusted where the source provides them"
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


def benchmark_performance(
    symbols: List[str],
    benchmark: str = "SPY",
    ranges: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return small, comparable performance snapshots without exposing chart payloads."""
    requested_ranges = ranges or ["1m", "1y", "5y"]
    if any(range_name not in {"1m", "1y", "5y"} for range_name in requested_ranges):
        raise ValueError("Unsupported performance range")

    ordered_symbols = list(dict.fromkeys([benchmark.upper(), *[symbol.upper() for symbol in symbols]]))
    results: Dict[str, Any] = {}
    errors: Dict[str, Any] = {}

    for symbol in ordered_symbols:
        results[symbol] = {}
        for range_name in requested_ranges:
            try:
                history = historical_prices(symbol, range_name)
                points = list(history.get("points") or [])
                if len(points) < 2:
                    raise RuntimeError("Not enough price history was returned")
                first = points[0]
                last = points[-1]
                start_price = float(first["close"])
                end_price = float(last["close"])
                period_return = (end_price - start_price) / start_price * 100 if start_price else None
                results[symbol][range_name] = {
                    "return": round(period_return, 2) if period_return is not None else None,
                    "startPrice": round(start_price, 6),
                    "endPrice": round(end_price, 6),
                    "startDate": first.get("date"),
                    "endDate": last.get("date"),
                    "source": history.get("source"),
                }
            except (RuntimeError, ValueError, TypeError, KeyError) as error:
                errors.setdefault(symbol, {})[range_name] = str(error)

    return {
        "benchmark": benchmark.upper(),
        "ranges": requested_ranges,
        "data": results,
        "errors": errors,
        "fetchedAt": int(time.time()),
        "method": "Closing-price return, adjusted where the source provides an adjusted series",
    }


def _portfolio_history(symbol: str) -> Dict[str, Any]:
    """Reuse the best fresh one-year series already fetched before making another request."""
    cache = _load_cache()
    now = int(time.time())
    keys = [
        f"databento:v1:{symbol}:1y",
        f"v4:{symbol}:1y",
        f"yahoo:v1:{symbol}:1y",
    ]
    for key in keys:
        cached = cache.get(key)
        if isinstance(cached, dict) and now - int(cached.get("fetchedAt") or 0) < HISTORY_TTL_SECONDS:
            return dict(cached)
    return historical_prices(symbol, "1y", request_institutional=False)


def _compute_portfolio_risk_statistics(symbols: List[str]) -> Dict[str, Any]:
    """Calculate one-year daily return covariance and correlation for a compact portfolio universe."""
    ordered_symbols = list(dict.fromkeys(symbol.upper() for symbol in symbols))
    returns: Dict[str, Dict[str, float]] = {}
    errors: Dict[str, str] = {}
    sources: Dict[str, str] = {}

    for symbol in ordered_symbols:
        try:
            history = _portfolio_history(symbol)
            points = sorted(list(history.get("points") or []), key=lambda point: str(point.get("date") or ""))
            daily: Dict[str, float] = {}
            previous: Optional[float] = None
            for point in points:
                close = float(point["close"])
                date = str(point["date"])
                if previous and close > 0:
                    daily[date] = close / previous - 1
                previous = close
            if len(daily) < 40:
                raise RuntimeError("Fewer than 40 daily return observations were available")
            returns[symbol] = daily
            sources[symbol] = str(history.get("source") or "Unknown")
        except (RuntimeError, ValueError, TypeError, KeyError) as error:
            errors[symbol] = str(error)

    correlations: Dict[str, Dict[str, Optional[float]]] = {symbol: {} for symbol in ordered_symbols}
    covariance: Dict[str, Dict[str, Optional[float]]] = {symbol: {} for symbol in ordered_symbols}
    observations: Dict[str, Dict[str, int]] = {symbol: {} for symbol in ordered_symbols}

    for left in ordered_symbols:
        for right in ordered_symbols:
            left_returns = returns.get(left)
            right_returns = returns.get(right)
            if not left_returns or not right_returns:
                correlations[left][right] = None
                covariance[left][right] = None
                observations[left][right] = 0
                continue
            dates = sorted(set(left_returns).intersection(right_returns))
            observations[left][right] = len(dates)
            if len(dates) < 40:
                correlations[left][right] = None
                covariance[left][right] = None
                continue
            left_values = [left_returns[date] for date in dates]
            right_values = [right_returns[date] for date in dates]
            left_mean = sum(left_values) / len(left_values)
            right_mean = sum(right_values) / len(right_values)
            divisor = len(dates) - 1
            pair_covariance = sum(
                (left_value - left_mean) * (right_value - right_mean)
                for left_value, right_value in zip(left_values, right_values)
            ) / divisor
            left_variance = sum((value - left_mean) ** 2 for value in left_values) / divisor
            right_variance = sum((value - right_mean) ** 2 for value in right_values) / divisor
            denominator = math.sqrt(left_variance * right_variance)
            pair_correlation = pair_covariance / denominator if denominator else None
            correlations[left][right] = round(max(-1.0, min(1.0, pair_correlation)), 4) if pair_correlation is not None else None
            covariance[left][right] = round(pair_covariance * 252, 8)

    return {
        "symbols": ordered_symbols,
        "correlations": correlations,
        "annualCovariance": covariance,
        "observations": observations,
        "errors": errors,
        "sources": sources,
        "fetchedAt": int(time.time()),
        "method": "Pairwise covariance and correlation of daily closing-price returns over one year; covariance annualized using 252 trading days",
    }


def portfolio_risk_statistics(symbols: List[str]) -> Dict[str, Any]:
    """Return a cached portfolio matrix so a page refresh never repeats the full history workload."""
    ordered_symbols = sorted(set(symbol.upper() for symbol in symbols))
    cache_key = ",".join(ordered_symbols)
    now = int(time.time())
    with _PORTFOLIO_RISK_LOCK:
        cached = _PORTFOLIO_RISK_CACHE.get(cache_key)
        if cached and now - int(cached.get("fetchedAt") or 0) < PORTFOLIO_RISK_TTL_SECONDS:
            return dict(cached)
        payload = _compute_portfolio_risk_statistics(ordered_symbols)
        _PORTFOLIO_RISK_CACHE[cache_key] = payload
        return dict(payload)
