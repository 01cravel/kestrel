"""Compute the weekly "could move sharply" list from evidence, not by hand.

The previous watchlist carried numbers a person typed in. This computes every
figure from the archive and from SEC filings, and each candidate can be traced
back to the sessions and filings that produced it.

The headline chance is a **conditional base rate**, not a forecast. It answers a
question with a checkable answer: across the whole archive, when a security was
in this state — a results announcement due inside the week, this volatility
regime, this jump history — how often did the next five sessions actually
deliver a benchmark-relative move of ten percent or more? A model that claimed
to know *this* week would need to have passed the promotion gates, and none has.

Direction is never stated. Kestrel can measure how often something moves; which
way it moves at a scheduled announcement is not knowable in advance, and the
sample of past reactions is far too small to imply it.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from earnings_calendar import project_from_dates, reaction_history
from outcome_source import DEFAULT_DATABASE
from swing_radar_policy import INVESTABLE_SECURITY_TYPES, POLICY_VERSION


RADAR_VERSION = "2026.08.1"
JUMP_THRESHOLD = 0.10          # benchmark-relative move that counts as a jump
HORIZON_SESSIONS = 5           # one trading week
LOOKBACK_SESSIONS = 252
VOLATILITY_WINDOW = 21
VOLUME_RECENT = 5
VOLUME_BASE = 60
MIN_HISTORY_SESSIONS = 150
SHORTLIST = 12
DISPLAY = 5
# A cohort smaller than this cannot support a rate worth showing.
MIN_COHORT = 200


def _series(connection: sqlite3.Connection, ticker: str) -> List[Tuple[str, float, float, Optional[float]]]:
    rows = connection.execute(
        """SELECT session_date, adjusted_close, spy_adjusted_close, median_dollar_volume_20d
           FROM swing_observations WHERE ticker=? AND policy_version=?
           ORDER BY session_date""", (ticker, POLICY_VERSION)
    ).fetchall()
    return [
        (row[0], float(row[1]), float(row[2]), float(row[3]) if row[3] else None)
        for row in rows if row[1] and row[2]
    ]


def _forward_jump(series: Sequence[Tuple[str, float, float, Optional[float]]],
                  index: int) -> Optional[bool]:
    """Did the five sessions after ``index`` deliver a ten percent relative move?"""
    exit_index = index + HORIZON_SESSIONS
    if exit_index >= len(series):
        return None
    stock = series[exit_index][1] / series[index][1] - 1
    benchmark = series[exit_index][2] / series[index][2] - 1
    return abs(stock - benchmark) >= JUMP_THRESHOLD


def _volatility(series: Sequence[Tuple[str, float, float, Optional[float]]],
                index: int) -> Optional[float]:
    window = series[max(0, index - VOLATILITY_WINDOW):index + 1]
    if len(window) < 10:
        return None
    returns = [window[i][1] / window[i - 1][1] - 1 for i in range(1, len(window))]
    return statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else None


def _volume_build(series: Sequence[Tuple[str, float, float, Optional[float]]],
                  index: int) -> Optional[float]:
    recent = [row[3] for row in series[max(0, index - VOLUME_RECENT + 1):index + 1] if row[3]]
    base = [row[3] for row in series[max(0, index - VOLUME_BASE):index + 1] if row[3]]
    if not recent or len(base) < 20:
        return None
    return statistics.median(recent) / statistics.median(base)


def _volatility_bucket(volatility: Optional[float]) -> str:
    if volatility is None:
        return "unknown"
    if volatility < 0.35:
        return "calm"
    if volatility < 0.60:
        return "normal"
    if volatility < 0.95:
        return "lively"
    return "wild"


class RadarArchive:
    """Loads every security once, then answers cohort questions from memory."""

    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)
        self.series: Dict[str, List[Tuple[str, float, float, Optional[float]]]] = {}
        self.results_dates: Dict[str, set] = {}
        self._cohorts: Optional[Dict[Tuple[bool, str], List[int]]] = None

    def load(self, min_sessions: int = MIN_HISTORY_SESSIONS) -> "RadarArchive":
        if not self.database.exists():
            return self
        connection = sqlite3.connect(str(self.database))
        try:
            # Leveraged and inverse funds are violent by construction, so an
            # unfiltered list is nothing but them. The investability policy
            # already answers this: ordinary shares and ADRs only.
            placeholders = ",".join("?" * len(INVESTABLE_SECURITY_TYPES))
            tickers = [
                row[0] for row in connection.execute(
                    f"""SELECT ticker FROM swing_observations
                        WHERE ticker!='SPY' AND policy_version=?
                          AND security_type IN ({placeholders})
                        GROUP BY ticker HAVING COUNT(*) >= ?""",
                    (POLICY_VERSION, *sorted(INVESTABLE_SECURITY_TYPES), min_sessions)
                )
            ]
            for ticker in tickers:
                series = _series(connection, ticker)
                if len(series) >= min_sessions:
                    self.series[ticker] = series
            for row in connection.execute(
                "SELECT ticker, event_date FROM issuer_events WHERE event_type='results'"
            ):
                self.results_dates.setdefault(row[0], set()).add(row[1])
        except sqlite3.DatabaseError:
            # An archive without the derived tables is empty, not broken.
            self.series.clear()
        finally:
            connection.close()
        return self

    def _build_cohorts(self) -> None:
        """One pass over every session, tallied by state.

        Volatility is computed incrementally rather than re-derived per session:
        a naive scan recomputes the same rolling window millions of times and
        turns a seconds-long job into a minutes-long one.
        """
        if self._cohorts is not None:
            return
        tally: Dict[Tuple[bool, str], List[int]] = {}
        for ticker, series in self.series.items():
            announcements = self.results_dates.get(ticker, set())
            returns = [None] + [
                series[i][1] / series[i - 1][1] - 1 for i in range(1, len(series))
            ]
            for index in range(VOLATILITY_WINDOW, len(series) - HORIZON_SESSIONS):
                window = [value for value in returns[index - VOLATILITY_WINDOW + 1:index + 1]
                          if value is not None]
                if len(window) < 10:
                    continue
                bucket = _volatility_bucket(statistics.pstdev(window) * math.sqrt(252))
                dates = {series[step][0] for step in range(index + 1, index + HORIZON_SESSIONS + 1)}
                results_due = bool(dates & announcements)
                outcome = _forward_jump(series, index)
                if outcome is None:
                    continue
                counts = tally.setdefault((results_due, bucket), [0, 0])
                counts[0] += 1
                counts[1] += 1 if outcome else 0
        self._cohorts = tally

    def cohort_rate(self, *, results_due: bool, bucket: str) -> Dict[str, Any]:
        """Historic jump frequency for every session matching this state.

        A session counts as results-due when a confirmed announcement lands
        inside the following week — exactly the situation a candidate is in.
        """
        self._build_cohorts()
        matches, jumps = (self._cohorts or {}).get((results_due, bucket), (0, 0))
        rate = (jumps / matches) if matches else None
        return {
            "cohortSessions": matches,
            "jumps": jumps,
            "rate": round(rate, 4) if rate is not None else None,
            "sufficient": matches >= MIN_COHORT,
            "definition": (
                f"Sessions in the {bucket} volatility band with"
                f"{'' if results_due else ' no'} scheduled results in the next week."
            ),
        }

    def own_jump_rate(self, ticker: str) -> Dict[str, Any]:
        """How often this security itself has jumped, over the last year."""
        series = self.series.get(ticker) or []
        window = series[-(LOOKBACK_SESSIONS + HORIZON_SESSIONS):]
        outcomes = [
            _forward_jump(window, index) for index in range(len(window) - HORIZON_SESSIONS)
        ]
        usable = [outcome for outcome in outcomes if outcome is not None]
        if not usable:
            return {"sessions": 0, "jumps": 0, "rate": None}
        return {
            "sessions": len(usable),
            "jumps": sum(usable),
            "rate": round(sum(usable) / len(usable), 4),
        }


def _blend(cohort: Dict[str, Any], own: Dict[str, Any]) -> Optional[float]:
    """Combine the large cohort rate with the security's own record.

    The cohort supplies a stable prior from thousands of sessions; the security's
    own year adds what is specific to it. The own-rate is weighted by how much
    evidence it carries, so a quiet name cannot swing the answer on a handful of
    observations.
    """
    if cohort["rate"] is None:
        return own["rate"]
    if own["rate"] is None:
        return cohort["rate"]
    weight = min(0.5, own["sessions"] / (own["sessions"] + 250))
    return round(cohort["rate"] * (1 - weight) + own["rate"] * weight, 4)


def build_candidates(database: Path = DEFAULT_DATABASE,
                     today: Optional[dt.date] = None,
                     archive: Optional[RadarArchive] = None) -> Dict[str, Any]:
    """Rank securities by the measured chance of a sharp move this week."""
    today = today or dt.date.today()
    archive = archive or RadarArchive(database).load()
    if not archive.series:
        return {"status": "empty", "candidates": [],
                "message": "The archive holds no securities with enough history."}

    cohort_cache: Dict[Tuple[bool, str], Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    for ticker, series in archive.series.items():
        index = len(series) - 1
        volatility = _volatility(series, index)
        bucket = _volatility_bucket(volatility)
        if bucket == "unknown":
            continue
        known = sorted(
            dt.date.fromisoformat(value) for value in archive.results_dates.get(ticker, set())
        )
        context = project_from_dates(known, today)
        window = context.get("projection") or {}
        # Due this week: the projected date lands inside the coming seven days,
        # or the window is already open around today.
        results_due = bool(window) and (
            0 <= window.get("daysAway", 99) <= 7
            or (window.get("windowIsOpen") and not window.get("overdue"))
        )
        key = (results_due, bucket)
        if key not in cohort_cache:
            cohort_cache[key] = archive.cohort_rate(results_due=results_due, bucket=bucket)
        cohort = cohort_cache[key]
        own = archive.own_jump_rate(ticker)
        chance = _blend(cohort, own)
        if chance is None:
            continue
        rows.append({
            "symbol": ticker,
            "asOf": series[index][0],
            "jumpChance10": chance,
            "cohort": cohort,
            "ownRecord": own,
            "annualisedVolatility": round(volatility, 3) if volatility else None,
            "volatilityBand": bucket,
            "volumeBuild": round(_volume_build(series, index) or 0, 3) or None,
            "resultsDue": results_due,
            "resultsExpected": window.get("expectedDate"),
            "resultsWindow": (
                [window.get("windowStart"), window.get("windowEnd")] if window else None
            ),
            "resultsPrecision": window.get("precision"),
            "calendarStatus": context.get("status"),
        })

    rows.sort(key=lambda row: -row["jumpChance10"])
    shortlist = rows[:SHORTLIST]
    for row in shortlist:
        row["reactionHistory"] = reaction_history(row["symbol"], database, today)
    return {
        "status": "ready",
        "radarVersion": RADAR_VERSION,
        "policyVersion": POLICY_VERSION,
        "asOf": today.isoformat(),
        "securitiesConsidered": len(rows),
        "candidates": shortlist[:DISPLAY],
        "target": f"A benchmark-relative move of {int(JUMP_THRESHOLD * 100)}% or more within one trading week.",
        "chanceMethod": (
            "A measured base rate, not a prediction. Every archived session in the same "
            "volatility band and the same scheduled-results state is counted, and the share "
            "that produced the move is reported, blended with this security's own record."
        ),
        "directionPolicy": (
            "No direction is stated. Kestrel can measure how often a security moves sharply; "
            "which way it moves at a scheduled announcement is not knowable in advance."
        ),
    }


def freeze_weekly_list(path: Path = Path(__file__).resolve().parent / "swing_watchlist.json",
                       database: Path = DEFAULT_DATABASE,
                       today: Optional[dt.date] = None,
                       archive: Optional["RadarArchive"] = None) -> Dict[str, Any]:
    """Write this week's list once and never revise it.

    The value of a shadow list is that it was fixed before the outcome existed.
    If a list for this week is already frozen, it is left exactly as it was.
    """
    today = today or dt.date.today()
    week_ending = (today + dt.timedelta(days=(4 - today.weekday()) % 7)).isoformat()
    path = Path(path)
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = None
    if isinstance(existing, dict) and existing.get("weekEnding") == week_ending:
        return {**existing, "status": "already-frozen",
                "message": "This week's list was already frozen and has not been changed."}

    result = build_candidates(database=database, today=today, archive=archive)
    if result.get("status") != "ready":
        return result
    payload = {
        **result,
        "title": "Could move sharply this week",
        "weekEnding": week_ending,
        "frozenAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidates": [
            {**candidate, "rank": position}
            for position, candidate in enumerate(result["candidates"], 1)
        ],
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return payload
