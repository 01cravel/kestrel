#!/usr/bin/env python3
"""Local Kestrel development server and market-data proxy."""

from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from datetime import date, datetime, time as datetime_time, timezone as dt_timezone
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from analyst_data import fetch_analyst_intelligence
from analyst_sources import BENZINGA_API_KEY, named_analyst_snapshot, refresh_named_analysts
from catalyst_watch import catalyst_watch_snapshot
from company_guidance import sec_guidance_evidence
from earnings_calendar import earnings_context, earnings_radar
from feature_store import session_cutoff
from fund_lookthrough import fund_lookthrough_snapshot
from investor_history import investor_calibration_summary, record_investor_ideas
from learning import learning_status
from market_integrity import DATABENTO_API_KEY, market_integrity_snapshot, refresh_market_integrity
from market_history import MarketHistoryStore
from macro_regime import macro_regime_snapshot
from mover_autopsy import mover_snapshot
from portfolio_science import (
    CANDIDATE_WEIGHTS, MODEL_VERSION as PORTFOLIO_MODEL_VERSION, portfolio_science_snapshot,
)
from price_history import FMP_KEY, benchmark_performance, historical_prices, intraday_prices, portfolio_risk_statistics
from sec_data import verify_with_sec
from security_master import refresh_security_master, security_master_snapshot
from sarwa_sync import connection_status, discard_pending, mark_applied, pending_positions, stage_snapshot
from signal_history import calibration_summary, record_signals
from source_policy import POLICY_VERSION as EVIDENCE_POLICY_VERSION, build_evidence_summary, evidence_policy
from superinvestors import refresh_superinvestors, superinvestor_snapshot
from swing_watchlist import swing_watchlist_snapshot
from universe_ledger import UniverseLedger, market_evidence, security_master_members
from universe_outcomes import UniverseOutcomeCapture


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-market-cache.json"
PORTFOLIO_PATH = ROOT / ".kestrel-portfolio.json"
PORTFOLIO_BACKUP_PATH = ROOT / ".kestrel-portfolio-backup.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("KESTREL_PORT", "3050"))

HOLDINGS_UNIVERSE = [
    "MU", "SPY", "GMOI", "IEMG", "NBIS", "VRT", "V", "GLD", "CAT", "NVDA", "RKLB", "LLY",
    "MA", "HCA", "AVGO", "STX", "GOOGL", "AXP", "AMD", "CEG", "QBTS", "COHR", "ONDS",
    "DELL", "ETN", "CRDO", "MRVL", "NOW", "RGTI", "SPCX", "BTC",
]

BASE_OPPORTUNITY_UNIVERSE = [
    "MSFT", "AMZN", "META", "AAPL", "TSM", "ASML", "COST", "HD", "LIN", "ISRG",
    "NVO", "MELI", "SAP", "SONY", "UL", "TTE",
]

ULTIMATE_PORTFOLIO_SYMBOLS = [
    "VTI", "AVUV", "VEA", "IEMG", "AVDV", "PAVE", "TSM", "GOOGL",
    "AMZN", "ASML", "MELI", "ETN", "ISRG", "CEG", "IBIT", "SGOV",
]

BASE_ALL_SYMBOLS = list(dict.fromkeys(HOLDINGS_UNIVERSE + BASE_OPPORTUNITY_UNIVERSE))
API_GAP_SECONDS = 1.05
QUOTE_REFRESH_SECONDS = 15 * 60
FULL_REFRESH_SECONDS = 6 * 60 * 60
SEC_REFRESH_SECONDS = 24 * 60 * 60
ANALYST_REFRESH_SECONDS = 24 * 60 * 60
SEC_EXCLUDED_SYMBOLS = {"SPY", "GMOI", "IEMG", "GLD", "BTC"}
MARKET_SYMBOLS = {"BTC": "BINANCE:BTCUSDT"}
PORTFOLIO_LOCK = threading.Lock()
UNIVERSE_LEDGER = UniverseLedger()
MARKET_HISTORY_STORE = MarketHistoryStore()
UNIVERSE_OUTCOMES = UniverseOutcomeCapture(UNIVERSE_LEDGER, MARKET_HISTORY_STORE.database)
UNIVERSE_SELECTION_POLICY = "configured-research-universe-v1"
CERTIFIED_UNIVERSE_SELECTION_POLICY = "certified-ideal-portfolio-universe-v1"
UNIVERSE_CHECK_SECONDS = 15 * 60


def clean_positions(raw_positions: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw_positions, dict):
        raise ValueError("Positions must be an object")
    cleaned: Dict[str, Dict[str, Any]] = {}
    for symbol, raw_position in raw_positions.items():
        normalized_symbol = str(symbol).upper()
        if normalized_symbol not in HOLDINGS_UNIVERSE or not isinstance(raw_position, dict):
            continue
        try:
            shares = float(raw_position.get("shares"))
        except (TypeError, ValueError):
            continue
        if shares <= 0:
            continue
        raw_cost = raw_position.get("cost")
        try:
            cost = float(raw_cost) if raw_cost is not None else None
        except (TypeError, ValueError):
            cost = None
        cleaned[normalized_symbol] = {
            "shares": round(shares, 8),
            "cost": round(cost, 8) if cost is not None and cost > 0 else None,
        }
    return cleaned


def load_portfolio() -> Dict[str, Any]:
    with PORTFOLIO_LOCK:
        try:
            payload = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
            positions = clean_positions(payload.get("positions", {}))
            return {
                "positions": positions,
                "updatedAt": payload.get("updatedAt"),
                "source": "private local portfolio file",
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {"positions": {}, "updatedAt": None, "source": "browser storage"}


def save_portfolio(raw_positions: Any) -> Dict[str, Any]:
    positions = clean_positions(raw_positions)
    if not positions:
        raise ValueError("At least one holding is required")
    payload = {
        "positions": positions,
        "updatedAt": int(time.time()),
        "version": 1,
    }
    temporary_path = ROOT / ".kestrel-portfolio.tmp"
    with PORTFOLIO_LOCK:
        if PORTFOLIO_PATH.exists():
            try:
                PORTFOLIO_BACKUP_PATH.write_text(PORTFOLIO_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary_path.replace(PORTFOLIO_PATH)
    return {**payload, "source": "private local portfolio file"}


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
    "total": len(BASE_ALL_SYMBOLS),
    "lastFullRefresh": None,
    "lastQuoteRefresh": None,
    "keyConfigured": bool(FINNHUB_KEY),
    "historyKeyConfigured": bool(FMP_KEY),
    "institutionalDataConfigured": bool(DATABENTO_API_KEY),
    "namedAnalystDataConfigured": bool(BENZINGA_API_KEY),
    "priceSnapshots": {},
}


def opportunity_universe() -> List[str]:
    discovered = [
        str(idea.get("symbol") or "").upper()
        for idea in superinvestor_snapshot().get("ideas", [])
        if idea.get("symbol")
    ]
    return list(dict.fromkeys(BASE_OPPORTUNITY_UNIVERSE + discovered))


def all_symbols() -> List[str]:
    return list(dict.fromkeys(HOLDINGS_UNIVERSE + opportunity_universe()))


def freeze_daily_universe(now: datetime | None = None) -> Dict[str, Any]:
    """Freeze the first post-close information set that is locally available."""
    instant = now or datetime.now(dt_timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Universe snapshot time must include a timezone")
    eastern = instant.astimezone(ZoneInfo("America/New_York"))
    if eastern.weekday() >= 5 or eastern.time() < datetime_time(16, 15):
        return {"status": "waiting", "message": "The US decision cutoff has not passed."}
    decision_date = eastern.date().isoformat()
    # Retain the documented 16:15 cutoff as the lower bound, while recording
    # the exact later instant at which the complete local information set froze.
    lower_bound = session_cutoff(decision_date)
    initial_cutoff = instant.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if initial_cutoff < lower_bound:
        return {"status": "waiting", "message": "The US decision cutoff has not passed."}
    with STATE_LOCK:
        state_status = STATE["status"]
        data = dict(STATE["data"])
    if state_status not in {"ready", "cached"}:
        return {"status": "waiting", "message": "Market and filing evidence is still refreshing."}
    symbols = all_symbols()
    identities = security_master_snapshot(symbols)
    if identities.get("status") not in {"ready", "cached", "partial"}:
        return {"status": "waiting", "message": "Security identities are still refreshing."}
    lookthrough_payload = fund_lookthrough_snapshot(CANDIDATE_WEIGHTS)
    freeze_instant = instant if now is not None else datetime.now(dt_timezone.utc)
    cutoff = freeze_instant.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lookthrough = []
    source_dates = [str(row.get("asOf") or "") for row in lookthrough_payload.get("sources") or []
                    if row.get("asOf")]
    generated_at = lookthrough_payload.get("generatedAt")
    try:
        lookthrough_available = datetime.fromtimestamp(
            int(generated_at), tz=dt_timezone.utc
        ).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        lookthrough_available = None
    if source_dates and lookthrough_available and lookthrough_available <= cutoff:
        lookthrough.append({
            "asOf": min(source_dates), "availableAt": lookthrough_available,
            "complete": lookthrough_payload.get("complete") is True,
            "source": "Official ETF issuer holdings",
            "payload": lookthrough_payload,
        })
    try:
        certification = MARKET_HISTORY_STORE.certify_session(
            decision_date, list(dict.fromkeys(ULTIMATE_PORTFOLIO_SYMBOLS + ["VT"])), cutoff
        )
    except sqlite3.Error:
        # A missing or damaged optional archive can never open certification,
        # but it must not prevent the ordinary fail-closed manifest from being
        # frozen for the day.
        certification = {"status": "unavailable"}
    certified = bool(
        certification.get("status") == "ready" and lookthrough_payload.get("complete") is True
        and lookthrough
    )
    members = (
        certification["members"] if certified
        else security_master_members(identities, symbols, data, cutoff)
    )
    evidence = certification["evidence"] if certified else market_evidence(data, cutoff)
    return UNIVERSE_LEDGER.capture_snapshot(
        decision_date=decision_date, cutoff_utc=cutoff, recorded_at=cutoff,
        model_version=PORTFOLIO_MODEL_VERSION,
        policy_version=EVIDENCE_POLICY_VERSION,
        selection_policy_version=(
            CERTIFIED_UNIVERSE_SELECTION_POLICY if certified else UNIVERSE_SELECTION_POLICY
        ),
        members=members, evidence=evidence, lookthrough=lookthrough,
        controls={
            "selectionPolicyFrozen": True,
            # Current live quotes are timestamped, but the portfolio's complete
            # point-in-time total-return/action archive is not yet certified.
            "pointInTimePrices": certified,
            "adjustmentPolicy": (
                "point_in_time_total_return" if certified else "unverified"
            ),
            "oneWayCostBps": 10,
        },
    )


def update_daily_universe_ledger(now: datetime | None = None) -> Dict[str, Any]:
    """Freeze today's truth set and advance every retained outcome path."""
    instant = now or datetime.now(dt_timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Universe workflow time must include a timezone")
    recorded = instant.astimezone(dt_timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    snapshot = freeze_daily_universe(instant)
    outcomes = UNIVERSE_OUTCOMES.capture(recorded)
    return {"status": "updated", "snapshot": snapshot, "outcomes": outcomes}


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
            symbols = all_symbols()
            STATE["total"] = len(symbols)
            STATE["completed"] = sum(1 for symbol in symbols if symbol in STATE["data"])
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
    except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
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

    if not quote_only and symbol not in BASE_ALL_SYMBOLS and not result.get("profile"):
        try:
            profile = finnhub("stock/profile2", {"symbol": symbol})
            if isinstance(profile, dict) and profile.get("name"):
                result["profile"] = profile
        except RuntimeError as error:
            errors.append(str(error))

    try:
        quote = finnhub("quote", {"symbol": MARKET_SYMBOLS.get(symbol, symbol)})
        if isinstance(quote, dict) and quote.get("c"):
            result["quote"] = quote
            record_price_snapshot(symbol, quote)
        else:
            errors.append("Current price missing")
    except RuntimeError as error:
        errors.append(str(error))

    if not quote_only and symbol == "BTC":
        result["metrics"] = {}
        result["recommendations"] = []
        result["earnings"] = []
        result["analystIntelligence"] = {
            "status": "not_applicable",
            "message": "Stock analyst estimates do not apply to Bitcoin.",
            "fetchedAt": int(time.time()),
        }
        result["sec"] = {
            "status": "not_applicable",
            "message": "Company filing checks do not apply to Bitcoin.",
            "verifiedAt": int(time.time()),
        }
    elif not quote_only:
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


def full_refresh(only_missing: bool = False) -> None:
    if not FINNHUB_KEY:
        with STATE_LOCK:
            STATE["status"] = "error"
            STATE["message"] = "A Finnhub API key is required"
        return

    symbols = all_symbols()
    with STATE_LOCK:
        existing_data = dict(STATE["data"])
    targets = symbols
    if only_missing:
        targets = [
            symbol for symbol in symbols
            if symbol not in existing_data
            or not existing_data[symbol].get("quote")
            or "sec" not in existing_data[symbol]
            or "analystIntelligence" not in existing_data[symbol]
        ]
    completed_before = len(symbols) - len(targets)
    with STATE_LOCK:
        STATE["status"] = "refreshing"
        STATE["message"] = "Checking newly discovered ideas" if only_missing else "Checking holdings first, then new opportunities"
        STATE["completed"] = completed_before
        STATE["total"] = len(symbols)

    for index, symbol in enumerate(targets, start=completed_before + 1):
        assessment_data = fetch_symbol(symbol)
        with STATE_LOCK:
            STATE["data"][symbol] = assessment_data
            STATE["completed"] = index
            STATE["message"] = f"Checked {index} of {len(symbols)} companies"
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

    for symbol in all_symbols():
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
    symbols = all_symbols()
    with STATE_LOCK:
        has_complete_cache = all(
            symbol in STATE["data"]
            and "sec" in STATE["data"][symbol]
            and "analystIntelligence" in STATE["data"][symbol]
            for symbol in symbols
        )
        last_full = STATE.get("lastFullRefresh") or 0

    if not has_complete_cache:
        full_refresh(only_missing=True)
        # A simultaneous manager refresh may have queued the same discovery work.
        REFRESH_EVENT.clear()
    elif time.time() - last_full > FULL_REFRESH_SECONDS:
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
        if parsed.path == "/api/portfolio":
            self.send_json(load_portfolio())
            return
        if parsed.path == "/api/sarwa":
            portfolio = load_portfolio()
            self.send_json(connection_status(len(portfolio.get("positions") or {})))
            return
        if parsed.path == "/api/evidence":
            with STATE_LOCK:
                data = dict(STATE["data"])
            portfolio = load_portfolio()
            sarwa = connection_status(len(portfolio.get("positions") or {}))
            symbols = all_symbols()
            identity = security_master_snapshot(symbols)
            market = market_integrity_snapshot(symbols, data, identity.get("instruments"))
            named_analysts = named_analyst_snapshot(symbols, data)
            macro = macro_regime_snapshot()
            self.send_json(evidence_policy(
                data, sarwa, identity.get("summary"), market.get("summary"), named_analysts.get("summary"), macro
            ))
            return
        if parsed.path == "/api/macro":
            raw_cutoff = (urllib.parse.parse_qs(parsed.query).get("as_of") or [""])[0]
            try:
                cutoff = date.fromisoformat(raw_cutoff) if raw_cutoff else None
            except ValueError:
                self.send_json({"ok": False, "message": "as_of must be YYYY-MM-DD"}, status=400)
                return
            self.send_json(macro_regime_snapshot(cutoff))
            return
        if parsed.path == "/api/security-master":
            self.send_json(security_master_snapshot(all_symbols()))
            return
        if parsed.path == "/api/market-integrity":
            with STATE_LOCK:
                data = dict(STATE["data"])
            symbols = all_symbols()
            identity = security_master_snapshot(symbols)
            self.send_json(market_integrity_snapshot(symbols, data, identity.get("instruments")))
            return
        if parsed.path == "/api/analyst-sources":
            with STATE_LOCK:
                data = dict(STATE["data"])
            self.send_json(named_analyst_snapshot(all_symbols(), data))
            return
        if parsed.path == "/api/superinvestors":
            self.send_json(superinvestor_snapshot())
            return
        if parsed.path == "/api/movers":
            self.send_json(mover_snapshot())
            return
        if parsed.path == "/api/catalyst-watch":
            self.send_json(catalyst_watch_snapshot())
            return
        if parsed.path == "/api/swing-watchlist":
            self.send_json(swing_watchlist_snapshot())
            return
        if parsed.path == "/api/universe-ledger":
            self.send_json(UNIVERSE_LEDGER.latest())
            return
        if parsed.path == "/api/dashboard":
            opportunities = opportunity_universe()
            symbols = list(dict.fromkeys(HOLDINGS_UNIVERSE + opportunities))
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
                    "institutionalDataConfigured": STATE["institutionalDataConfigured"],
                    "namedAnalystDataConfigured": STATE["namedAnalystDataConfigured"],
                    "holdingsUniverse": HOLDINGS_UNIVERSE,
                    "opportunityUniverse": opportunities,
                    "data": dict(STATE["data"]),
                }
            portfolio = load_portfolio()
            sarwa = connection_status(len(portfolio.get("positions") or {}))
            identity = security_master_snapshot(symbols)
            market = market_integrity_snapshot(symbols, payload["data"], identity.get("instruments"))
            named_analysts = named_analyst_snapshot(symbols, payload["data"])
            macro = macro_regime_snapshot()
            payload["securityMaster"] = identity
            payload["marketIntegrity"] = market
            payload["namedAnalysts"] = named_analysts
            payload["superinvestors"] = superinvestor_snapshot()
            payload["macroRegime"] = macro
            payload["evidencePolicy"] = build_evidence_summary(
                payload["data"], sarwa, identity.get("summary"), market.get("summary"), named_analysts.get("summary"), macro
            )
            self.send_json(payload)
            return
        if parsed.path == "/api/history":
            query = urllib.parse.parse_qs(parsed.query)
            symbol = str(query.get("symbol", [""])[0]).upper()
            range_name = str(query.get("range", ["1y"])[0]).lower()
            history_universe = list(dict.fromkeys(all_symbols() + ULTIMATE_PORTFOLIO_SYMBOLS))
            if symbol not in history_universe:
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
        if parsed.path == "/api/performance":
            query = urllib.parse.parse_qs(parsed.query)
            raw_symbols = str(query.get("symbols", [""])[0])
            symbols = list(dict.fromkeys(
                symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()
            ))
            universe = list(dict.fromkeys(all_symbols() + ULTIMATE_PORTFOLIO_SYMBOLS))
            if not symbols or len(symbols) > len(universe):
                self.send_json({"ok": False, "message": "Choose between 1 and 37 symbols"}, status=400)
                return
            if any(symbol not in universe for symbol in symbols):
                self.send_json({"ok": False, "message": "Unknown symbol"}, status=400)
                return
            try:
                self.send_json(benchmark_performance(symbols))
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/portfolio-risk":
            query = urllib.parse.parse_qs(parsed.query)
            raw_symbols = str(query.get("symbols", [""])[0])
            symbols = list(dict.fromkeys(
                symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()
            ))
            universe = list(dict.fromkeys(all_symbols() + ULTIMATE_PORTFOLIO_SYMBOLS))
            if not symbols or len(symbols) > len(universe):
                self.send_json({"ok": False, "message": f"Choose between 1 and {len(universe)} symbols"}, status=400)
                return
            if any(symbol not in universe for symbol in symbols):
                self.send_json({"ok": False, "message": "Unknown symbol"}, status=400)
                return
            try:
                self.send_json(portfolio_risk_statistics(symbols))
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/portfolio-science":
            try:
                self.send_json(portfolio_science_snapshot())
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/calibration":
            self.send_json(calibration_summary())
            return
        if parsed.path == "/api/investor-calibration":
            self.send_json(investor_calibration_summary())
            return
        if parsed.path == "/api/earnings":
            symbol = (urllib.parse.parse_qs(parsed.query).get("symbol") or [""])[0].upper()
            if not symbol.isalnum():
                self.send_json({"ok": False, "message": "A ticker is required"}, status=400)
                return
            try:
                self.send_json(earnings_context(symbol))
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/guidance":
            query = urllib.parse.parse_qs(parsed.query)
            symbol = str((query.get("symbol") or [""])[0]).upper()
            cutoff = (query.get("cutoff") or [None])[0]
            if not symbol.isalnum():
                self.send_json({"ok": False, "message": "A ticker is required"}, status=400)
                return
            try:
                self.send_json(sec_guidance_evidence(symbol, cutoff=cutoff))
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/earnings-radar":
            try:
                self.send_json(earnings_radar(all_symbols()))
            except (RuntimeError, ValueError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=502)
            return
        if parsed.path == "/api/learning":
            self.send_json(learning_status())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/portfolio":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > 100_000:
                    raise ValueError("Invalid portfolio payload size")
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
                positions = body.get("positions") if isinstance(body, dict) else None
                self.send_json({"ok": True, **save_portfolio(positions)})
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=400)
            return
        if parsed.path == "/api/sarwa/snapshot":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > 1_000_000:
                    raise ValueError("Invalid Sarwa snapshot size")
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
                portfolio = load_portfolio()
                pending = stage_snapshot(body, portfolio.get("positions") or {}, HOLDINGS_UNIVERSE)
                self.send_json({"ok": True, "pending": pending})
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=400)
            return
        if parsed.path == "/api/sarwa/apply":
            try:
                positions = pending_positions()
                save_portfolio(positions)
                mark_applied()
                self.send_json({"ok": True, "portfolio": load_portfolio(), "sarwa": connection_status(len(positions))})
            except (OSError, ValueError, TypeError) as error:
                self.send_json({"ok": False, "message": str(error)}, status=400)
            return
        if parsed.path == "/api/sarwa/discard":
            discard_pending()
            portfolio = load_portfolio()
            self.send_json({"ok": True, "sarwa": connection_status(len(portfolio.get("positions") or {}))})
            return
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
        if parsed.path == "/api/investor-signals":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > 1_000_000:
                    raise ValueError("Invalid investor signal payload size")
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
                rows = body.get("ideas") if isinstance(body, dict) else None
                if not isinstance(rows, list):
                    raise ValueError("Investor ideas must be a list")
                summary = record_investor_ideas(rows, body.get("benchmarkPrice"))
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
    identity_worker = threading.Thread(
        target=refresh_security_master,
        args=(all_symbols(),),
        name="kestrel-security-master",
        daemon=True,
    )
    identity_worker.start()
    market_worker = threading.Thread(
        target=refresh_market_integrity,
        args=(all_symbols(),),
        name="kestrel-market-integrity",
        daemon=True,
    )
    market_worker.start()
    def analyst_source_worker() -> None:
        time.sleep(1)
        with STATE_LOCK:
            data = dict(STATE["data"])
        refresh_named_analysts(all_symbols(), data)

    named_worker = threading.Thread(
        target=analyst_source_worker,
        name="kestrel-named-analysts",
        daemon=True,
    )
    named_worker.start()
    def superinvestor_worker() -> None:
        before = set(BASE_ALL_SYMBOLS)
        refresh_superinvestors()
        after = set(all_symbols())
        if after - before:
            refresh_security_master(sorted(after))
            REFRESH_EVENT.set()

    manager_worker = threading.Thread(
        target=superinvestor_worker,
        name="kestrel-superinvestors",
        daemon=True,
    )
    manager_worker.start()
    def universe_snapshot_worker() -> None:
        while True:
            try:
                # The same pass advances every older snapshot. Identical
                # evidence is content-addressed and remains idempotent.
                update_daily_universe_ledger()
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                # Snapshot health is visible through /api/universe-ledger. A
                # failed capture never interrupts the dashboard or overwrites a
                # prior immutable snapshot.
                pass
            if threading.Event().wait(UNIVERSE_CHECK_SECONDS):
                return

    universe_worker = threading.Thread(
        target=universe_snapshot_worker,
        name="kestrel-universe-ledger",
        daemon=True,
    )
    universe_worker.start()
    server = ThreadingHTTPServer((HOST, PORT), KestrelHandler)
    print(f"Kestrel is running at http://{HOST}:{PORT}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
