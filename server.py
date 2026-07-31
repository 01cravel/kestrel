#!/usr/bin/env python3
"""Local Kestrel development server and market-data proxy."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, time as datetime_time
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from analyst_data import fetch_analyst_intelligence
from price_history import FMP_KEY, historical_prices, intraday_prices
from sec_data import verify_with_sec
from signal_history import calibration_summary, record_signals


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-market-cache.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("KESTREL_PORT", "3050"))

HOLDINGS_UNIVERSE = [
    "MU", "SPY", "NBIS", "VRT", "V", "GLD", "CAT", "NVDA", "RKLB", "LLY",
    "MA", "HCA", "AVGO", "STX", "GOOGL", "AXP", "AMD", "CEG", "QBTS", "COHR", "ONDS",
]

OPPORTUNITY_UNIVERSE = [
    "MSFT", "AMZN", "META", "AAPL", "TSM", "ASML", "COST", "HD", "LIN", "ISRG",
    "NVO", "MELI", "SAP", "SONY", "UL", "TTE",
]

ALL_SYMBOLS = list(dict.fromkeys(HOLDINGS_UNIVERSE + OPPORTUNITY_UNIVERSE))
API_GAP_SECONDS = 1.05
QUOTE_REFRESH_SECONDS = 15 * 60
FULL_REFRESH_SECONDS = 6 * 60 * 60
SEC_REFRESH_SECONDS = 24 * 60 * 60
ANALYST_REFRESH_SECONDS = 24 * 60 * 60
SEC_EXCLUDED_SYMBOLS = {"SPY", "GLD"}


def load_finnhub_key() -> str:
    configured = os.environ.get("FINNHUB_KEY", "").strip()
    if configured:
        return configured

    legacy_path = ROOT / "kestrel-legacy.html"
    if legacy_path.exists():
        content = legacy_path.read_text(encoding="utf-8")
        match = re.search(r"const FINNHUB_KEY = '([^']+)'", content)
        if match:
            return match.group(1)
    return ""


FINNHUB_KEY = load_finnhub_key()
STATE_LOCK = threading.Lock()
REFRESH_EVENT = threading.Event()
LAST_API_CALL = 0.0

STATE: Dict[str, Any] = {
    "status": "starting",
    "message": "Preparing the first assessment",
    "data": {},
    "completed": 0,
    "total": len(ALL_SYMBOLS),
    "lastFullRefresh": None,
    "lastQuoteRefresh": None,
    "keyConfigured": bool(FINNHUB_KEY),
    "historyKeyConfigured": bool(FMP_KEY),
    "priceSnapshots": {},
}


def load_cache() -> None:
    if not CACHE_PATH.exists():
        return
    try:
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if not isinstance(cached.get("data"), dict):
            return
        with STATE_LOCK:
            STATE["data"] = cached["data"]
            STATE["lastFullRefresh"] = cached.get("lastFullRefresh")
            STATE["lastQuoteRefresh"] = cached.get("lastQuoteRefresh")
            STATE["priceSnapshots"] = cached.get("priceSnapshots", {})
            STATE["completed"] = sum(1 for symbol in ALL_SYMBOLS if symbol in STATE["data"])
            STATE["status"] = "cached"
            STATE["message"] = "Showing saved evidence while fresh data loads"
    except (OSError, ValueError, TypeError):
        return


def save_cache() -> None:
    with STATE_LOCK:
        snapshot = {
            "data": STATE["data"],
            "lastFullRefresh": STATE["lastFullRefresh"],
            "lastQuoteRefresh": STATE["lastQuoteRefresh"],
            "priceSnapshots": STATE["priceSnapshots"],
        }
    temporary_path = CACHE_PATH.with_suffix(".tmp")
    try:
        temporary_path.write_text(json.dumps(snapshot), encoding="utf-8")
        temporary_path.replace(CACHE_PATH)
    except OSError:
        return


def finnhub(path: str, params: Dict[str, str]) -> Any:
    global LAST_API_CALL

    elapsed = time.monotonic() - LAST_API_CALL
    if elapsed < API_GAP_SECONDS:
        time.sleep(API_GAP_SECONDS - elapsed)

    query = dict(params)
    query["token"] = FINNHUB_KEY
    url = "https://finnhub.io/api/v1/" + path + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"User-Agent": "Kestrel local portfolio dashboard"})

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            LAST_API_CALL = time.monotonic()
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        LAST_API_CALL = time.monotonic()
        raise RuntimeError(f"Finnhub returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        LAST_API_CALL = time.monotonic()
        raise RuntimeError("Market data was unavailable") from error


def record_price_snapshot(symbol: str, quote: Dict[str, Any]) -> None:
    try:
        price = float(quote.get("c"))
        timestamp = int(quote.get("t") or time.time())
    except (TypeError, ValueError):
        return
    if price <= 0:
        return
    cutoff = int(time.time()) - 3 * 24 * 60 * 60
    with STATE_LOCK:
        snapshots = STATE["priceSnapshots"].setdefault(symbol, [])
        if not snapshots or snapshots[-1].get("timestamp") != timestamp:
            snapshots.append({"timestamp": timestamp, "close": round(price, 6)})
        STATE["priceSnapshots"][symbol] = [
            point for point in snapshots[-300:]
            if int(point.get("timestamp") or 0) >= cutoff
        ]


def intraday_history(symbol: str) -> Dict[str, Any]:
    with STATE_LOCK:
        raw = dict(STATE["data"].get(symbol, {}))
        snapshots = list(STATE["priceSnapshots"].get(symbol, []))
    quote = raw.get("quote") if isinstance(raw.get("quote"), dict) else {}
    try:
        current = float(quote.get("c"))
        open_price = float(quote.get("o"))
        quote_timestamp = int(quote.get("t") or time.time())
    except (TypeError, ValueError):
        raise RuntimeError("A current quote is required for the one-day view")

    eastern = ZoneInfo("America/New_York")
    quote_moment = datetime.fromtimestamp(quote_timestamp, tz=eastern)
    market_open = datetime.combine(quote_moment.date(), datetime_time(9, 30), tzinfo=eastern)
    market_open_timestamp = int(market_open.timestamp())
    session_points = [
        point for point in snapshots
        if market_open_timestamp <= int(point.get("timestamp") or 0) <= quote_timestamp
    ]
    session_points.append({"timestamp": market_open_timestamp, "close": round(open_price, 6)})
    session_points.append({"timestamp": quote_timestamp, "close": round(current, 6)})
    points_by_time = {int(point["timestamp"]): point for point in session_points}
    points = [points_by_time[key] for key in sorted(points_by_time)]
    period_return = ((current - open_price) / open_price * 100) if open_price else None

    return {
        "symbol": symbol,
        "range": "1d",
        "points": points,
        "rawPointCount": len(points),
        "periodReturn": round(period_return, 2) if period_return is not None else None,
        "fetchedAt": int(time.time()),
        "source": "Finnhub current quote and Kestrel snapshots",
        "method": "Session open and locally collected price snapshots",
        "session": {
            "open": open_price,
            "high": quote.get("h"),
            "low": quote.get("l"),
            "current": current,
        },
        "limited": len(points) < 4,
    }


def fetch_symbol(symbol: str, quote_only: bool = False) -> Dict[str, Any]:
    with STATE_LOCK:
        previous = dict(STATE["data"].get(symbol, {}))

    errors: List[str] = []
    result = previous

    try:
        quote = finnhub("quote", {"symbol": symbol})
        if isinstance(quote, dict) and quote.get("c"):
            result["quote"] = quote
            record_price_snapshot(symbol, quote)
        else:
            errors.append("Current price missing")
    except RuntimeError as error:
        errors.append(str(error))

    if not quote_only:
        try:
            metrics = finnhub("stock/metric", {"symbol": symbol, "metric": "all"})
            metric_values = metrics.get("metric") if isinstance(metrics, dict) else None
            if isinstance(metric_values, dict) and metric_values:
                result["metrics"] = metric_values
            else:
                errors.append("Company figures missing")
        except RuntimeError as error:
            errors.append(str(error))

        try:
            recommendations = finnhub("stock/recommendation", {"symbol": symbol})
            if isinstance(recommendations, list):
                result["recommendations"] = recommendations
            else:
                errors.append("Analyst view missing")
        except RuntimeError as error:
            errors.append(str(error))

        previous_earnings_at = int(previous.get("earningsFetchedAt") or 0)
        if previous.get("earnings") and time.time() - previous_earnings_at < ANALYST_REFRESH_SECONDS:
            result["earnings"] = previous["earnings"]
            result["earningsFetchedAt"] = previous_earnings_at
        else:
            try:
                earnings = finnhub("stock/earnings", {"symbol": symbol, "limit": "8"})
                if isinstance(earnings, list):
                    result["earnings"] = earnings
                    result["earningsFetchedAt"] = int(time.time())
                else:
                    errors.append("Earnings surprise history missing")
            except RuntimeError as error:
                errors.append(str(error))

        previous_analyst = previous.get("analystIntelligence") if isinstance(previous.get("analystIntelligence"), dict) else None
        analyst_is_fresh = (
            previous_analyst
            and time.time() - int(previous_analyst.get("fetchedAt") or 0) < ANALYST_REFRESH_SECONDS
        )
        if analyst_is_fresh:
            result["analystIntelligence"] = previous_analyst
        else:
            prior_history = previous_analyst.get("estimateHistory", []) if previous_analyst else []
            result["analystIntelligence"] = fetch_analyst_intelligence(symbol, prior_history)
            if result["analystIntelligence"].get("status") == "error":
                errors.append("Analyst estimate tracking unavailable")

        previous_sec = previous.get("sec") if isinstance(previous.get("sec"), dict) else None
        sec_is_fresh = (
            previous_sec
            and time.time() - int(previous_sec.get("verifiedAt") or 0) < SEC_REFRESH_SECONDS
        )
        if symbol in SEC_EXCLUDED_SYMBOLS:
            result["sec"] = {
                "status": "not_applicable",
                "message": "Company filing checks do not apply to this fund.",
                "verifiedAt": int(time.time()),
            }
        elif sec_is_fresh:
            result["sec"] = previous_sec
        else:
            result["sec"] = verify_with_sec(symbol, result.get("metrics", {}))
            if result["sec"].get("status") == "error":
                errors.append("Official filing check unavailable")

    result["fetchedAt"] = int(time.time())
    result["errors"] = errors
    return result


def full_refresh() -> None:
    if not FINNHUB_KEY:
        with STATE_LOCK:
            STATE["status"] = "error"
            STATE["message"] = "A Finnhub API key is required"
        return

    with STATE_LOCK:
        STATE["status"] = "refreshing"
        STATE["message"] = "Checking holdings first, then new opportunities"
        STATE["completed"] = 0

    for index, symbol in enumerate(ALL_SYMBOLS, start=1):
        assessment_data = fetch_symbol(symbol)
        with STATE_LOCK:
            STATE["data"][symbol] = assessment_data
            STATE["completed"] = index
            STATE["message"] = f"Checked {index} of {len(ALL_SYMBOLS)} companies"
        save_cache()

    now = int(time.time())
    with STATE_LOCK:
        STATE["status"] = "ready"
        STATE["message"] = "Evidence is up to date"
        STATE["lastFullRefresh"] = now
        STATE["lastQuoteRefresh"] = now
    save_cache()


def quote_refresh() -> None:
    if not FINNHUB_KEY:
        return
    with STATE_LOCK:
        STATE["status"] = "refreshing"
        STATE["message"] = "Updating prices"

    for symbol in ALL_SYMBOLS:
        assessment_data = fetch_symbol(symbol, quote_only=True)
        with STATE_LOCK:
            STATE["data"][symbol] = assessment_data

    now = int(time.time())
    with STATE_LOCK:
        STATE["status"] = "ready"
        STATE["message"] = "Evidence is up to date"
        STATE["lastQuoteRefresh"] = now
    save_cache()


def data_worker() -> None:
    load_cache()
    with STATE_LOCK:
        has_complete_cache = all(
            symbol in STATE["data"]
            and "sec" in STATE["data"][symbol]
            and "analystIntelligence" in STATE["data"][symbol]
            for symbol in ALL_SYMBOLS
        )
        last_full = STATE.get("lastFullRefresh") or 0

    if not has_complete_cache or time.time() - last_full > FULL_REFRESH_SECONDS:
        full_refresh()
    else:
        with STATE_LOCK:
            STATE["status"] = "ready"
            STATE["message"] = "Evidence is up to date"

    while True:
        triggered = REFRESH_EVENT.wait(timeout=QUOTE_REFRESH_SECONDS)
        REFRESH_EVENT.clear()
        with STATE_LOCK:
            last_full = STATE.get("lastFullRefresh") or 0
        if triggered or time.time() - last_full > FULL_REFRESH_SECONDS:
            full_refresh()
        else:
            quote_refresh()


class KestrelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/dashboard":
            with STATE_LOCK:
                payload = {
                    "status": STATE["status"],
                    "message": STATE["message"],
                    "completed": STATE["completed"],
                    "total": STATE["total"],
                    "lastFullRefresh": STATE["lastFullRefresh"],
                    "lastQuoteRefresh": STATE["lastQuoteRefresh"],
                    "keyConfigured": STATE["keyConfigured"],
                    "historyKeyConfigured": STATE["historyKeyConfigured"],
                    "holdingsUniverse": HOLDINGS_UNIVERSE,
                    "opportunityUniverse": OPPORTUNITY_UNIVERSE,
                    "data": dict(STATE["data"]),
                }
            self.send_json(payload)
            return
        if parsed.path == "/api/history":
            query = urllib.parse.parse_qs(parsed.query)
            symbol = str(query.get("symbol", [""])[0]).upper()
            range_name = str(query.get("range", ["1y"])[0]).lower()
            if symbol not in ALL_SYMBOLS:
                self.send_json({"ok": False, "message": "Unknown symbol"}, status=400)
                return
            try:
                if range_name == "1d":
                    with STATE_LOCK:
                        quote = STATE["data"].get(symbol, {}).get("quote", {})
                    try:
                        latest_price = float(quote.get("c"))
                    except (AttributeError, TypeError, ValueError):
                        latest_price = None
                    try:
                        payload = intraday_prices(symbol, latest_price)
                    except RuntimeError:
                        payload = intraday_history(symbol)
                else:
                    with STATE_LOCK:
                        quote = STATE["data"].get(symbol, {}).get("quote", {})
                    try:
                        latest_price = float(quote.get("c"))
                    except (AttributeError, TypeError, ValueError):
                        latest_price = None
                    payload = historical_prices(symbol, range_name, latest_price)
                self.send_json(payload)
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/calibration":
            self.send_json(calibration_summary())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/signals":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > 1_000_000:
                    raise ValueError("Invalid signal payload size")
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
                rows = body.get("signals") if isinstance(body, dict) else None
                if not isinstance(rows, list):
                    raise ValueError("Signals must be a list")
                summary = record_signals(rows, body.get("evidenceTimestamp"))
                self.send_json({"ok": True, "calibration": summary})
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=400)
            return
        if parsed.path == "/api/refresh":
            REFRESH_EVENT.set()
            self.send_json({"ok": True, "message": "Refresh queued"}, status=202)
            return
        self.send_json({"ok": False, "message": "Not found"}, status=404)

    def end_headers(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        if self.path.startswith("/api/") and args and str(args[1]) == "200":
            return
        super().log_message(format, *args)


def main() -> None:
    worker = threading.Thread(target=data_worker, name="kestrel-data", daemon=True)
    worker.start()
    server = ThreadingHTTPServer((HOST, PORT), KestrelHandler)
    print(f"Kestrel is running at http://{HOST}:{PORT}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
