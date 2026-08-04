"""Independent matured outcomes for Kestrel's prediction journals.

A journal must never grade itself. Every outcome here comes from the local
market-history archive, which stores corporate-action-adjusted closes beside the
matching SPY close and a per-session cleanliness flag. A prediction is graded
only when that archive independently covers the entry session, the exit session
and the whole path between them.

Returns are benchmark-relative and assume a realistic entry: Kestrel decides
using the close of the decision session, so the position is entered at the next
session's close, never at the price the decision was based on.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from swing_radar_policy import POLICY_VERSION


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / ".kestrel-data" / "market-history" / "market-history.sqlite3"

# Entry happens one session after the decision, never at the decision price.
ENTRY_DELAY_SESSIONS = 1
# A matured exit may sit at most this far past the target date before the
# outcome is abandoned rather than stretched onto an unrelated session.
MAX_EXIT_SLIP_DAYS = 15
# Declared round-trip cost band. A benchmark-relative result inside this band is
# neutral, not a win. This is a cost floor, not a calibrated volatility band.
COST_BAND_PERCENT = 0.5

STATUS_MATURED = "matured"
STATUS_PENDING = "pending"
STATUS_UNAVAILABLE = "unavailable"


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed > 0 else None


def _date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


class OutcomeSource:
    """Read-only view of the adjusted archive, used to mature predictions."""

    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)
        self._series: Dict[str, List[Tuple[str, float, float, bool]]] = {}
        self._extent: Optional[Tuple[Optional[str], Optional[str]]] = None
        self._stamp: Optional[float] = None

    # -- archive access -------------------------------------------------

    def _refresh(self) -> None:
        """Drop cached prices when the archive gains new sessions."""
        try:
            stamp = self.database.stat().st_mtime
        except OSError:
            stamp = None
        if stamp != self._stamp:
            self._stamp = stamp
            self._series.clear()
            self._extent = None

    def _connect(self) -> Optional[sqlite3.Connection]:
        if not self.database.exists():
            return None
        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        return connection

    def available(self) -> bool:
        return self.coverage()["status"] == "ready"

    def coverage(self) -> Dict[str, Any]:
        """Report what the archive can actually grade, in plain fields."""
        self._refresh()
        if self._extent is None:
            connection = self._connect()
            if connection is None:
                self._extent = (None, None)
            else:
                try:
                    row = connection.execute(
                        """SELECT MIN(session_date), MAX(session_date) FROM swing_observations
                           WHERE policy_version=?""", (POLICY_VERSION,)
                    ).fetchone()
                    self._extent = (row[0], row[1]) if row else (None, None)
                except sqlite3.DatabaseError:
                    self._extent = (None, None)
                finally:
                    connection.close()
        first, last = self._extent
        return {
            "status": "ready" if first and last else "empty",
            "database": str(self.database),
            "firstSession": first,
            "lastSession": last,
            "policyVersion": POLICY_VERSION,
        }

    def _load(self, symbol: str) -> List[Tuple[str, float, float, bool]]:
        """Adjusted close, matching SPY close and cleanliness, oldest first."""
        self._refresh()
        symbol = symbol.upper()
        if symbol in self._series:
            return self._series[symbol]
        series: List[Tuple[str, float, float, bool]] = []
        connection = self._connect()
        if connection is not None:
            try:
                rows = connection.execute(
                    """SELECT session_date, adjusted_close, spy_adjusted_close, corporate_actions_clean
                       FROM swing_observations WHERE ticker=? AND policy_version=?
                       ORDER BY session_date""", (symbol, POLICY_VERSION)
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = []
            finally:
                connection.close()
            for row in rows:
                close = _number(row["adjusted_close"])
                benchmark = _number(row["spy_adjusted_close"])
                if close is None or benchmark is None:
                    continue
                series.append((row["session_date"], close, benchmark, bool(row["corporate_actions_clean"])))
        self._series[symbol] = series
        return series

    # -- outcome measurement --------------------------------------------

    def outcome(self, symbol: str, decision_date: Any, horizon_days: int) -> Dict[str, Any]:
        """Mature one prediction over ``horizon_days`` calendar days.

        Always returns a status. ``pending`` means the archive has not reached
        the exit session yet; ``unavailable`` means Kestrel cannot honestly
        grade this prediction at all and must not guess.
        """
        start = _date(decision_date)
        if not start:
            return {"status": STATUS_UNAVAILABLE, "reason": "Unreadable decision date"}
        series = self._load(symbol)
        if not series:
            return {"status": STATUS_UNAVAILABLE, "reason": "No archived sessions for this security"}

        after_decision = [point for point in series if point[0] > start.isoformat()]
        if len(after_decision) < ENTRY_DELAY_SESSIONS:
            return {"status": STATUS_PENDING, "reason": "Entry session not archived yet"}
        entry = after_decision[ENTRY_DELAY_SESSIONS - 1]

        target = (start + dt.timedelta(days=horizon_days)).isoformat()
        limit = (start + dt.timedelta(days=horizon_days + MAX_EXIT_SLIP_DAYS)).isoformat()
        held = [point for point in series if entry[0] <= point[0] <= limit]
        exits = [point for point in held if point[0] >= target]
        if not exits:
            last_session = series[-1][0]
            if last_session < target:
                return {"status": STATUS_PENDING, "reason": "Archive has not reached the exit date"}
            return {"status": STATUS_UNAVAILABLE, "reason": "No traded session near the exit date"}
        exit_point = exits[0]
        path = [point for point in held if point[0] <= exit_point[0]]

        if not all(point[3] for point in path):
            return {"status": STATUS_UNAVAILABLE, "reason": "Unresolved corporate action inside the holding period"}

        stock_return = (exit_point[1] / entry[1] - 1) * 100
        benchmark_return = (exit_point[2] / entry[2] - 1) * 100
        excess = stock_return - benchmark_return
        trough = min(point[1] for point in path)
        drawdown = (trough / entry[1] - 1) * 100
        relative_trough = min(
            (point[1] / entry[1]) / (point[2] / entry[2]) - 1 for point in path
        ) * 100
        return {
            "status": STATUS_MATURED,
            "entryDate": entry[0],
            "exitDate": exit_point[0],
            "sessionsHeld": len(path) - 1,
            "stockReturn": round(stock_return, 2),
            "benchmarkReturn": round(benchmark_return, 2),
            "excessReturn": round(excess, 2),
            "maxDrawdown": round(drawdown, 2),
            "maxRelativeDrawdown": round(relative_trough, 2),
            "verdict": verdict(excess),
            "source": "archive",
        }


def verdict(excess_return: Optional[float]) -> Optional[str]:
    """Classify a benchmark-relative result against the declared cost band."""
    if excess_return is None:
        return None
    if excess_return > COST_BAND_PERCENT:
        return "outperformed"
    if excess_return < -COST_BAND_PERCENT:
        return "underperformed"
    return "neutral"


_SHARED: Optional[OutcomeSource] = None


def shared_source() -> OutcomeSource:
    """One cached reader per process; the archive is append-only in practice."""
    global _SHARED
    if _SHARED is None:
        _SHARED = OutcomeSource()
    return _SHARED


def reset_shared_source() -> None:
    global _SHARED
    _SHARED = None
