"""Point-in-time daily mover research built from Kestrel's local archive."""

from __future__ import annotations

import math
import json
import sqlite3
import statistics
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / ".kestrel-data" / "market-history" / "market-history.sqlite3"
DEFAULT_CATALYSTS = ROOT / "mover_catalysts.json"
MIN_PRICE = 2.0
MIN_MEDIAN_DOLLAR_VOLUME = 5_000_000.0
MIN_PRIOR_SESSIONS = 126
HISTORY_LOOKBACK_SESSIONS = 160
SHORTLIST_SIZE = 500
DISPLAY_PER_DIRECTION = 4
CACHE_SECONDS = 10 * 60
ELIGIBLE_SECURITY_TYPES = {"CS", "ADRC", "ADRP", "GDR"}
METHOD_SOURCES = [
    {
        "name": "MacKinlay event-study method",
        "url": "https://econpapers.repec.org/article/aeajeclit/v_3a35_3ay_3a1997_3ai_3a1_3ap_3a13-39.htm",
        "use": "Separate a company move from the broad market move.",
    },
    {
        "name": "NBER event-study methodology",
        "url": "https://www.nber.org/papers/w10388.pdf",
        "use": "Estimate abnormal returns against a market benchmark.",
    },
]

_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {
    "savedAt": 0.0, "databaseStamp": None, "catalystStamp": None, "payload": None,
}


def _load_catalysts(path: Path = DEFAULT_CATALYSTS) -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _cause_for(symbol: str, session_date: str, fallback: Dict[str, Any],
               catalysts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    evidence = catalysts.get(f"{session_date}:{symbol}")
    if not isinstance(evidence, dict) or evidence.get("status") != "verified":
        return fallback
    sources = evidence.get("sources")
    if not isinstance(sources, list) or not any(
        isinstance(source, dict) and source.get("name") and source.get("url") for source in sources
    ):
        return fallback
    return evidence


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _return(start: Optional[float], end: Optional[float]) -> Optional[float]:
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1.0


def _median(values: Iterable[float]) -> Optional[float]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.median(clean) if clean else None


def _ratio(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if value is None or baseline is None or baseline <= 0:
        return None
    return value / baseline


def _annualised_volatility(closes: List[float]) -> Optional[float]:
    returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, len(closes))
               if closes[index] > 0 and closes[index - 1] > 0]
    if len(returns) < 10:
        return None
    return statistics.stdev(returns) * math.sqrt(252)


def _plain_pre_move(pre_20: Optional[float], volume_build: Optional[float], volatility: Optional[float]) -> str:
    facts: List[str] = []
    if pre_20 is not None:
        if pre_20 >= 0.15:
            facts.append("the shares were already rising strongly")
        elif pre_20 <= -0.15:
            facts.append("the shares had already been falling sharply")
        else:
            facts.append("the prior monthly trend was not extreme")
    if volume_build is not None:
        if volume_build >= 1.5:
            facts.append("trading activity was building before the move")
        elif volume_build <= 0.67:
            facts.append("trading activity had been unusually quiet")
    if volatility is not None and volatility >= 0.8:
        facts.append("large swings were already normal for this share")
    if not facts:
        return "The price archive does not yet contain a dependable advance clue."
    sentence = "; ".join(facts)
    return sentence[0].upper() + sentence[1:] + "."


def _security_identity(connection: sqlite3.Connection, ticker: str, as_of: str) -> Optional[Dict[str, Any]]:
    try:
        row = connection.execute(
            """SELECT name, security_type, active, snapshot_date FROM reference_snapshots
               WHERE ticker=? AND snapshot_date<=?
               ORDER BY snapshot_date DESC, active DESC LIMIT 1""", (ticker, as_of)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return {
        "name": str(row[0]) if row[0] else ticker,
        "securityType": str(row[1] or "").upper(),
        "active": bool(row[2]),
        "snapshotDate": str(row[3]),
    }


def build_mover_snapshot(database: Path = DEFAULT_DATABASE,
                         catalysts_path: Path = DEFAULT_CATALYSTS) -> Dict[str, Any]:
    database = Path(database)
    if not database.exists():
        return {
            "status": "empty", "asOf": None, "movers": [],
            "message": "The historical market archive is not ready yet.",
            "methodSources": METHOD_SOURCES,
        }

    connection = sqlite3.connect(str(database), timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        session_rows = connection.execute(
            "SELECT DISTINCT session_date FROM daily_bars WHERE ticker='SPY' ORDER BY session_date DESC LIMIT ?",
            (HISTORY_LOOKBACK_SESSIONS + 1,),
        ).fetchall()
        sessions = [str(row[0]) for row in reversed(session_rows)]
        if len(sessions) < 2:
            return {
                "status": "learning", "asOf": sessions[-1] if sessions else None, "movers": [],
                "message": "Kestrel needs at least two completed market sessions.",
                "methodSources": METHOD_SOURCES,
            }
        latest, previous = sessions[-1], sessions[-2]
        spy = connection.execute(
            "SELECT session_date, close FROM daily_bars WHERE ticker='SPY' AND session_date BETWEEN ? AND ?",
            (sessions[0], latest),
        ).fetchall()
        spy_closes = {str(row[0]): _number(row[1]) for row in spy}
        market_return = _return(spy_closes.get(previous), spy_closes.get(latest))
        if market_return is None:
            return {
                "status": "incomplete", "asOf": latest, "movers": [],
                "message": "The market benchmark is incomplete for the latest session.",
                "methodSources": METHOD_SOURCES,
            }

        latest_rows = connection.execute(
            """SELECT current.ticker, current.close, current.volume,
                      prior.close AS prior_close, prior.session_date AS prior_session
               FROM daily_bars AS current
               JOIN daily_bars AS prior ON prior.ticker=current.ticker
                 AND prior.session_date=(
                   SELECT MAX(older.session_date) FROM daily_bars AS older
                   WHERE older.ticker=current.ticker AND older.session_date<current.session_date
                 )
               WHERE current.session_date=? AND current.ticker!='SPY'
                 AND current.close>=? AND prior.close>0""",
            (latest, MIN_PRICE),
        ).fetchall()
        candidates: List[Dict[str, Any]] = []
        for row in latest_rows:
            close = _number(row["close"])
            prior_close = _number(row["prior_close"])
            move = _return(prior_close, close)
            benchmark_return = _return(spy_closes.get(str(row["prior_session"])), spy_closes.get(latest))
            if move is None or benchmark_return is None:
                continue
            candidates.append({
                "symbol": str(row["ticker"]), "close": close, "previousClose": prior_close,
                "previousSession": str(row["prior_session"]),
                "volume": _number(row["volume"]), "move": move,
                "benchmarkReturn": benchmark_return,
                "relativeMove": move - benchmark_return,
            })
        candidates.sort(key=lambda item: abs(item["relativeMove"]), reverse=True)
        candidates = candidates[:SHORTLIST_SIZE]
        if not candidates:
            return {
                "status": "ready", "asOf": latest, "movers": [],
                "message": "No price-qualified movers were found.", "methodSources": METHOD_SOURCES,
            }

        placeholders = ",".join("?" for _ in candidates)
        history_start = sessions[0]
        history_rows = connection.execute(
            f"""SELECT ticker, session_date, close, volume FROM daily_bars
                 WHERE ticker IN ({placeholders}) AND session_date BETWEEN ? AND ?
                 ORDER BY ticker, session_date""",
            tuple(item["symbol"] for item in candidates) + (history_start, latest),
        ).fetchall()
        histories: Dict[str, List[sqlite3.Row]] = {}
        for row in history_rows:
            histories.setdefault(str(row["ticker"]), []).append(row)

        qualified: List[Dict[str, Any]] = []
        catalysts = _load_catalysts(catalysts_path)
        for item in candidates:
            identity = _security_identity(connection, item["symbol"], latest)
            if (not identity or not identity["active"]
                    or identity["securityType"] not in ELIGIBLE_SECURITY_TYPES):
                continue
            rows = histories.get(item["symbol"], [])
            prior_rows = [row for row in rows if str(row["session_date"]) <= previous]
            if len(prior_rows) < MIN_PRIOR_SESSIONS:
                continue
            trailing = prior_rows[-20:]
            dollar_volumes = [
                (_number(row["close"]) or 0.0) * (_number(row["volume"]) or 0.0) for row in trailing
            ]
            median_dollar_volume = _median(dollar_volumes)
            if median_dollar_volume is None or median_dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME:
                continue
            closes = [_number(row["close"]) for row in prior_rows]
            closes = [value for value in closes if value is not None and value > 0]
            pre_20 = _return(closes[-21], closes[-1]) if len(closes) >= 21 else None
            pre_5 = _return(closes[-6], closes[-1]) if len(closes) >= 6 else None
            recent_volume = _median(dollar_volumes[-5:])
            earlier_volume = _median(dollar_volumes[:-5])
            volume_build = _ratio(recent_volume, earlier_volume)
            volatility = _annualised_volatility(closes[-21:])
            current_dollar_volume = (item["close"] or 0.0) * (item["volume"] or 0.0)
            volume_multiple = _ratio(current_dollar_volume, median_dollar_volume)
            skipped_sessions = sum(
                1 for session in sessions
                if item["previousSession"] < session < latest
            )
            fallback_cause = {
                "status": "unverified",
                "plainEnglish": "The price and volume move are verified. The business cause is not yet verified, so Kestrel will not invent one.",
                "knownBefore": _plain_pre_move(pre_20, volume_build, volatility),
                "unknown": "A filing, company announcement, regulator decision or credible report still needs timestamped verification.",
            }
            qualified.append({
                **item,
                "name": identity["name"],
                "securityType": identity["securityType"],
                "identityAsOf": identity["snapshotDate"],
                "skippedMarketSessions": skipped_sessions,
                "medianDollarVolume20d": median_dollar_volume,
                "volumeMultiple": volume_multiple,
                "priorSessions": len(prior_rows),
                "preMove": {
                    "return5d": pre_5, "return20d": pre_20,
                    "volumeBuild": volume_build, "annualisedVolatility": volatility,
                    "plainEnglish": _plain_pre_move(pre_20, volume_build, volatility),
                },
                "cause": _cause_for(item["symbol"], latest, fallback_cause, catalysts),
                "tradingGapWarning": (
                    f"No trade was recorded for {skipped_sessions} intervening market session"
                    f"{'s' if skipped_sessions != 1 else ''}; check for a halt or suspension."
                    if skipped_sessions else None
                ),
                "researchOnly": True,
            })

        gains = sorted((item for item in qualified if item["relativeMove"] > 0),
                       key=lambda item: item["relativeMove"], reverse=True)[:DISPLAY_PER_DIRECTION]
        losses = sorted((item for item in qualified if item["relativeMove"] < 0),
                        key=lambda item: item["relativeMove"])[:DISPLAY_PER_DIRECTION]
        movers = gains + losses
        movers.sort(key=lambda item: abs(item["relativeMove"]), reverse=True)
        for rank, mover in enumerate(movers, start=1):
            mover["rank"] = rank
            mover["direction"] = "up" if mover["relativeMove"] > 0 else "down"
        return {
            "status": "ready", "asOf": latest, "previousSession": previous,
            "marketReturn": market_return, "movers": movers,
            "universe": {
                "priceFloor": MIN_PRICE,
                "medianDollarVolumeFloor": MIN_MEDIAN_DOLLAR_VOLUME,
                "minimumHistorySessions": MIN_PRIOR_SESSIONS,
                "marketCapStatus": "unknown",
            },
            "message": "Latest completed US session. A cause is shown only when timestamped evidence is attached.",
            "methodSources": METHOD_SOURCES,
        }
    finally:
        connection.close()


def mover_snapshot(database: Path = DEFAULT_DATABASE) -> Dict[str, Any]:
    database = Path(database)
    stamp = database.stat().st_mtime_ns if database.exists() else None
    catalyst_stamp = DEFAULT_CATALYSTS.stat().st_mtime_ns if DEFAULT_CATALYSTS.exists() else None
    now = time.monotonic()
    with _CACHE_LOCK:
        if (_CACHE["payload"] is not None and _CACHE["databaseStamp"] == stamp
                and _CACHE["catalystStamp"] == catalyst_stamp
                and now - float(_CACHE["savedAt"]) < CACHE_SECONDS):
            return _CACHE["payload"]
    payload = build_mover_snapshot(database)
    with _CACHE_LOCK:
        _CACHE.update({
            "savedAt": now, "databaseStamp": stamp,
            "catalystStamp": catalyst_stamp, "payload": payload,
        })
    return payload
