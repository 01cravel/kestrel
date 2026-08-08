"""Versioned point-in-time features built from the adjusted archive.

Every feature for session ``D`` is derived only from sessions at or before
``D``. Nothing here reads a later bar, a restated fundamental or a currently
known universe, so a feature row can be rebuilt identically at any future date.

Features are deliberately price, benchmark and liquidity based. That is what the
archive can support honestly today: ``swing_observations`` stores adjusted
closes, the matching SPY close, 20-session median dollar volume and a
corporate-action cleanliness flag. Fundamentals and estimates are not yet
bitemporal, so they are excluded rather than approximated.

Missing inputs stay missing. A feature row reports ``complete`` and the names of
any absent features; it never fills a gap with a mean, a zero or a later value.
"""

from __future__ import annotations

import datetime as dt
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from zoneinfo import ZoneInfo

from outcome_source import DEFAULT_DATABASE
from swing_radar_policy import (
    MIN_MEDIAN_DOLLAR_VOLUME_20D_USD,
    MIN_PRICE_USD,
    MIN_PRIOR_SESSIONS,
    POLICY_VERSION,
    feature_is_available,
)


FEATURE_VERSION = "2026.08.1"

# Lookbacks are trading sessions, counted back from the decision session.
SHORT_WINDOW = 21
MEDIUM_WINDOW = 63
LONG_WINDOW = 126
HIGH_WINDOW = 252
VOLUME_WINDOW = 60
VOLUME_RECENT = 5
TRADING_SESSIONS_PER_YEAR = 252

EVENT_FEATURE_NAMES: Tuple[str, ...] = (
    "days_since_results",
    "days_since_insider_buy",
    "insider_net_value_90d",
    "material_filings_30d",
)

PRICE_FEATURE_NAMES: Tuple[str, ...] = (
    "excess_return_5d",
    "excess_return_21d",
    "excess_return_63d",
    "excess_return_126d",
    "volatility_21d",
    "volatility_ratio",
    "drawdown_from_252d_high",
    "distance_from_63d_mean",
    "liquidity_surge",
    "log_dollar_volume",
    "return_dispersion_21d",
)

# Event features are optional: an issuer with no ingested filings still yields a
# usable price-only row, and the learning loop reports which set it used.
FEATURE_NAMES: Tuple[str, ...] = PRICE_FEATURE_NAMES

# Insider windows are capped so a long-quiet issuer does not produce an
# unbounded feature that dwarfs everything else once standardised.
MAX_DAYS_SINCE_EVENT = 365


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> Optional[float]:
    number = _finite(value)
    return number if number is not None and number > 0 else None


def _returns(closes: Sequence[float]) -> List[float]:
    return [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]


def _stdev(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def _median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


class SecurityHistory:
    """Adjusted history for one security, oldest first, as-of safe."""

    __slots__ = ("ticker", "security_id", "dates", "closes", "benchmarks", "volumes", "clean")

    def __init__(self, ticker: str, security_id: str) -> None:
        self.ticker = ticker
        self.security_id = security_id
        self.dates: List[str] = []
        self.closes: List[float] = []
        self.benchmarks: List[float] = []
        self.volumes: List[Optional[float]] = []
        self.clean: List[bool] = []

    def append(self, session_date: str, close: float, benchmark: float,
               volume: Optional[float], clean: bool) -> None:
        self.dates.append(session_date)
        self.closes.append(close)
        self.benchmarks.append(benchmark)
        self.volumes.append(volume)
        self.clean.append(clean)

    def __len__(self) -> int:
        return len(self.dates)


def _excess_return(history: SecurityHistory, index: int, window: int) -> Optional[float]:
    start = index - window
    if start < 0:
        return None
    stock = history.closes[index] / history.closes[start] - 1
    benchmark = history.benchmarks[index] / history.benchmarks[start] - 1
    return stock - benchmark


def build_features(history: SecurityHistory, index: int) -> Dict[str, Any]:
    """Features for one decision session, using sessions up to ``index`` only.

    ``index`` is the decision session. Every window ends there, so no value in
    the returned row can depend on a later bar.
    """
    if index < 0 or index >= len(history):
        raise IndexError("Session index is outside the archived history")

    window = history.closes[max(0, index - LONG_WINDOW):index + 1]
    benchmark_window = history.benchmarks[max(0, index - LONG_WINDOW):index + 1]
    stock_returns = _returns(history.closes[max(0, index - SHORT_WINDOW):index + 1])
    benchmark_returns = _returns(history.benchmarks[max(0, index - SHORT_WINDOW):index + 1])

    volatility = _stdev(stock_returns)
    benchmark_volatility = _stdev(benchmark_returns)
    annualised = volatility * math.sqrt(TRADING_SESSIONS_PER_YEAR) if volatility is not None else None

    high_window = history.closes[max(0, index - HIGH_WINDOW):index + 1]
    peak = max(high_window) if high_window else None
    drawdown = (history.closes[index] / peak - 1) if peak else None

    mean_window = history.closes[max(0, index - MEDIUM_WINDOW):index + 1]
    mean_close = sum(mean_window) / len(mean_window) if mean_window else None
    distance = (history.closes[index] / mean_close - 1) if mean_close else None

    recent_volumes = [value for value in history.volumes[max(0, index - VOLUME_RECENT + 1):index + 1]
                      if value is not None]
    base_volumes = [value for value in history.volumes[max(0, index - VOLUME_WINDOW):index + 1]
                    if value is not None]
    recent_median = _median(recent_volumes)
    base_median = _median(base_volumes)
    surge = (recent_median / base_median) if recent_median and base_median else None
    current_volume = history.volumes[index]
    log_volume = math.log10(current_volume) if current_volume and current_volume > 0 else None

    dispersion = None
    if stock_returns:
        dispersion = max(abs(value) for value in stock_returns)

    values: Dict[str, Optional[float]] = {
        "excess_return_5d": _excess_return(history, index, 5),
        "excess_return_21d": _excess_return(history, index, SHORT_WINDOW),
        "excess_return_63d": _excess_return(history, index, MEDIUM_WINDOW),
        "excess_return_126d": _excess_return(history, index, LONG_WINDOW),
        "volatility_21d": annualised,
        "volatility_ratio": (
            volatility / benchmark_volatility
            if volatility is not None and benchmark_volatility else None
        ),
        "drawdown_from_252d_high": drawdown,
        "distance_from_63d_mean": distance,
        "liquidity_surge": surge,
        "log_dollar_volume": log_volume,
        "return_dispersion_21d": dispersion,
    }
    missing = sorted(name for name in FEATURE_NAMES if values.get(name) is None)
    return {
        "securityId": history.security_id,
        "ticker": history.ticker,
        "sessionDate": history.dates[index],
        "featureVersion": FEATURE_VERSION,
        "policyVersion": POLICY_VERSION,
        "values": values,
        "missing": missing,
        "complete": not missing,
        "priorSessions": index,
        # Retained so a rebuilt row can be compared with the original.
        "close": history.closes[index],
        "benchmarkClose": history.benchmarks[index],
        "windowLength": len(window),
        "benchmarkWindowLength": len(benchmark_window),
    }


def session_cutoff(session_date: str) -> str:
    """The documented decision cutoff for a session, in UTC."""
    local = dt.datetime.combine(
        dt.date.fromisoformat(session_date), dt.time(16, 15), ZoneInfo("America/New_York")
    )
    return local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event_features(events: Sequence[Dict[str, Any]], session_date: str) -> Dict[str, Any]:
    """Insider and filing features, using only filings readable by the cutoff.

    Availability is enforced by ``feature_is_available``, so a filing accepted
    after the session's cutoff cannot reach the row even though its filing date
    may be the same calendar day.
    """
    cutoff = session_cutoff(session_date)
    visible = [
        event for event in events
        if feature_is_available(
            {"published_at": event.get("published_at"), "available_at": event.get("available_at")},
            cutoff,
        )
    ]
    session = dt.date.fromisoformat(session_date)

    def days_since(event_type: str) -> Optional[float]:
        dates = [
            dt.date.fromisoformat(event["event_date"])
            for event in visible
            if event.get("event_type") == event_type and event.get("event_date")
        ]
        usable = [day for day in dates if day <= session]
        if not usable:
            return None
        return float(min(MAX_DAYS_SINCE_EVENT, (session - max(usable)).days))

    def window_value(event_type: str, days: int) -> float:
        start = session - dt.timedelta(days=days)
        total = 0.0
        for event in visible:
            if event.get("event_type") != event_type or not event.get("event_date"):
                continue
            day = dt.date.fromisoformat(event["event_date"])
            if start <= day <= session:
                total += _finite(event.get("value")) or 0.0
        return total

    buys = window_value("insider_buy", 90)
    sells = window_value("insider_sell", 90)
    net = buys - sells
    material = sum(
        1 for event in visible
        if event.get("event_type") == "filing_event" and event.get("event_date")
        and (session - dt.timedelta(days=30)) <= dt.date.fromisoformat(event["event_date"]) <= session
    )
    return {
        "days_since_results": days_since("results"),
        "days_since_insider_buy": days_since("insider_buy"),
        # Signed log keeps a $200m sale and a $2m purchase on a comparable scale.
        "insider_net_value_90d": (
            math.copysign(math.log10(1 + abs(net)), net) if net else 0.0
        ),
        "material_filings_30d": float(material),
        "eventsVisible": len(visible),
        "cutoff": cutoff,
    }


def research_eligible(history: SecurityHistory, index: int) -> Dict[str, Any]:
    """Liquidity and identity screen for research rows.

    This is deliberately weaker than ``assess_investability``: the archive holds
    no point-in-time market value, so the $300 million floor cannot be applied
    and is reported as unavailable rather than silently passed.
    """
    reasons: List[str] = []
    close = history.closes[index]
    volume = history.volumes[index]
    if close < MIN_PRICE_USD:
        reasons.append(f"Close is below ${MIN_PRICE_USD:.0f}")
    if volume is None:
        reasons.append("Median dollar volume is unavailable")
    elif volume < MIN_MEDIAN_DOLLAR_VOLUME_20D_USD:
        reasons.append("20-session median dollar volume is below $5 million")
    if index < MIN_PRIOR_SESSIONS:
        reasons.append("Fewer than 126 prior trading sessions are available")
    if not history.clean[index]:
        reasons.append("Corporate-action history is unresolved")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "marketValueScreen": "unavailable",
        "policyVersion": POLICY_VERSION,
    }


class FeatureStore:
    """Streams archived history one security at a time."""

    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)

    def available(self) -> bool:
        return self.database.exists()

    def iter_histories(self, start: Optional[str] = None, end: Optional[str] = None,
                       tickers: Optional[Sequence[str]] = None) -> Iterator[SecurityHistory]:
        """Yield one history per security, sessions in ascending date order."""
        if not self.database.exists():
            return
        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        try:
            query = [
                """SELECT ticker, security_id, session_date, adjusted_close,
                          spy_adjusted_close, median_dollar_volume_20d, corporate_actions_clean
                   FROM swing_observations WHERE policy_version=?"""
            ]
            parameters: List[Any] = [POLICY_VERSION]
            if start:
                query.append("AND session_date >= ?")
                parameters.append(start)
            if end:
                query.append("AND session_date <= ?")
                parameters.append(end)
            if tickers:
                placeholders = ",".join("?" * len(tickers))
                query.append(f"AND ticker IN ({placeholders})")
                parameters.extend(ticker.upper() for ticker in tickers)
            query.append("ORDER BY ticker, session_date")
            try:
                rows = connection.execute(" ".join(query), parameters)
            except sqlite3.DatabaseError:
                return
            current: Optional[SecurityHistory] = None
            for row in rows:
                close = _positive(row["adjusted_close"])
                benchmark = _positive(row["spy_adjusted_close"])
                if close is None or benchmark is None:
                    continue
                if current is None or current.ticker != row["ticker"]:
                    if current is not None and len(current):
                        yield current
                    current = SecurityHistory(row["ticker"], str(row["security_id"]))
                current.append(
                    row["session_date"], close, benchmark,
                    _positive(row["median_dollar_volume_20d"]), bool(row["corporate_actions_clean"]),
                )
            if current is not None and len(current):
                yield current
        finally:
            connection.close()


def with_events(features: Dict[str, Any], events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge event features into a price feature row, recomputing completeness."""
    extra = event_features(events, features["sessionDate"])
    values = dict(features["values"])
    for name in EVENT_FEATURE_NAMES:
        values[name] = extra.get(name)
    names = tuple(PRICE_FEATURE_NAMES) + tuple(EVENT_FEATURE_NAMES)
    missing = sorted(name for name in names if values.get(name) is None)
    return {
        **features, "values": values, "missing": missing, "complete": not missing,
        "featureSet": "price+events", "eventsVisible": extra["eventsVisible"],
        "cutoff": extra["cutoff"],
    }


def feature_vector(row: Dict[str, Any], names: Sequence[str] = FEATURE_NAMES) -> Optional[List[float]]:
    """Ordered numeric vector, or None when any required feature is missing."""
    values = row.get("values") or {}
    vector = []
    for name in names:
        value = _finite(values.get(name))
        if value is None:
            return None
        vector.append(value)
    return vector
