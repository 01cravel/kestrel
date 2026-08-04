"""Measured returns for every entry and exit timing around results.

The question is empirical: buy the day before and sell the day after, or wait?
This measures every combination against the benchmark, over every confirmed
announcement in the archive.

Three habits keep the answer honest.

**Session zero is the reaction session** — the first session able to respond to
the filing. Entering at offset −1 means buying at the last close before the news
is public; exiting at 0 means selling into the reaction. Any window that spans
zero is holding through the announcement.

**The average is reported beside the spread and the win rate.** Around results
the distribution is bimodal: a mean of +1% can be a coin flip between +20% and
−18%, which is a completely different proposition from a steady +1%.

**Every window is reported, not the best one.** Searching a grid and quoting the
winner is how noise gets published. The grid is small and fixed in advance, the
count of windows tested is stated, and confidence intervals resample whole
announcement dates because results cluster in the same fortnight each quarter.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from outcome_source import DEFAULT_DATABASE
from swing_radar_policy import INVESTABLE_SECURITY_TYPES, POLICY_VERSION
from validation import block_bootstrap_interval


STUDY_VERSION = "2026.08.1"
# Offsets are trading sessions from the reaction session (0).
ENTRY_OFFSETS = (-5, -3, -1, 0)
EXIT_OFFSETS = (0, 1, 2, 5, 10)
MIN_EVENTS = 100
# A declared round-trip cost. Any edge smaller than this is not an edge.
ROUND_TRIP_COST_PERCENT = 0.20


def _load_series(connection: sqlite3.Connection) -> Dict[str, List[Tuple[str, float, float]]]:
    placeholders = ",".join("?" * len(INVESTABLE_SECURITY_TYPES))
    rows = connection.execute(
        f"""SELECT ticker, session_date, adjusted_close, spy_adjusted_close
            FROM swing_observations
            WHERE policy_version=? AND ticker!='SPY'
              AND security_type IN ({placeholders})
              AND corporate_actions_clean=1
            ORDER BY ticker, session_date""",
        (POLICY_VERSION, *sorted(INVESTABLE_SECURITY_TYPES)),
    )
    series: Dict[str, List[Tuple[str, float, float]]] = {}
    for ticker, date, close, benchmark in rows:
        if close and benchmark:
            series.setdefault(ticker, []).append((date, float(close), float(benchmark)))
    return series


def _load_reaction_dates(connection: sqlite3.Connection) -> Dict[str, List[str]]:
    """Announcement dates, mapped to the session that could first respond."""
    events: Dict[str, List[str]] = {}
    for ticker, event_date in connection.execute(
        "SELECT ticker, event_date FROM issuer_events WHERE event_type='results'"
    ):
        events.setdefault(ticker, []).append(event_date)
    return events


def collect_events(database: Path = DEFAULT_DATABASE) -> List[Dict[str, Any]]:
    """One record per announcement, with the index of its reaction session."""
    database = Path(database)
    if not database.exists():
        return []
    connection = sqlite3.connect(str(database))
    try:
        series = _load_series(connection)
        announcements = _load_reaction_dates(connection)
    except sqlite3.DatabaseError:
        return []
    finally:
        connection.close()

    events: List[Dict[str, Any]] = []
    for ticker, dates in announcements.items():
        rows = series.get(ticker)
        if not rows:
            continue
        index_of = {row[0]: position for position, row in enumerate(rows)}
        session_dates = [row[0] for row in rows]
        for announced in sorted(set(dates)):
            # An announcement predating the archive has no reaction inside it.
            # Without this guard every such filing collapses onto the first
            # archived session and is measured as if the market reacted then.
            if announced <= session_dates[0]:
                continue
            # The filing lands after the close, so the reaction is the first
            # session strictly after the announcement date.
            later = [date for date in session_dates if date > announced]
            if not later:
                continue
            reaction = later[0]
            events.append({
                "ticker": ticker,
                "announcedOn": announced,
                "reactionDate": reaction,
                "reactionIndex": index_of[reaction],
                "series": rows,
            })
    return events


def _excess(rows: Sequence[Tuple[str, float, float]], entry: int, exit_index: int) -> Optional[float]:
    if entry < 0 or exit_index >= len(rows) or entry >= exit_index:
        return None
    stock = rows[exit_index][1] / rows[entry][1] - 1
    benchmark = rows[exit_index][2] / rows[entry][2] - 1
    return (stock - benchmark) * 100


def window_results(events: Sequence[Dict[str, Any]], entry_offset: int,
                   exit_offset: int) -> Dict[str, Any]:
    """Measure one entry/exit timing across every announcement."""
    returns: List[Dict[str, Any]] = []
    for event in events:
        rows = event["series"]
        entry = event["reactionIndex"] + entry_offset
        exit_index = event["reactionIndex"] + exit_offset
        value = _excess(rows, entry, exit_index)
        if value is None:
            continue
        returns.append({
            "excess": value,
            "sessionDate": event["reactionDate"],
            "ticker": event["ticker"],
        })
    if len(returns) < MIN_EVENTS:
        return {"entryOffset": entry_offset, "exitOffset": exit_offset,
                "events": len(returns), "sufficient": False}

    values = [row["excess"] for row in returns]
    ordered = sorted(values)
    mean = statistics.mean(values)
    net = mean - ROUND_TRIP_COST_PERCENT

    def average(sample: Sequence[Dict[str, Any]]) -> Optional[float]:
        if not sample:
            return None
        return statistics.mean(row["excess"] for row in sample)

    interval = block_bootstrap_interval(returns, average, date_key="sessionDate")
    return {
        "entryOffset": entry_offset,
        "exitOffset": exit_offset,
        "holdsThroughAnnouncement": entry_offset < 0 <= exit_offset,
        "sessionsHeld": exit_offset - entry_offset,
        "events": len(returns),
        "sufficient": True,
        "meanExcess": round(mean, 3),
        "medianExcess": round(statistics.median(values), 3),
        "netOfCosts": round(net, 3),
        "winRate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "spread": round(statistics.pstdev(values), 3),
        "worst": round(ordered[0], 2),
        "best": round(ordered[-1], 2),
        "lower95": interval.get("lower95"),
        "upper95": interval.get("upper95"),
        "beatsCosts": bool(
            interval.get("lower95") is not None
            and interval["lower95"] > ROUND_TRIP_COST_PERCENT
        ),
    }


def run_study(database: Path = DEFAULT_DATABASE,
              entries: Sequence[int] = ENTRY_OFFSETS,
              exits: Sequence[int] = EXIT_OFFSETS) -> Dict[str, Any]:
    """Every declared window, reported together."""
    events = collect_events(database)
    if not events:
        return {"status": "empty", "windows": [],
                "message": "No archived announcements with price history."}

    windows = [
        window_results(events, entry, exit_offset)
        for entry in entries for exit_offset in exits
        if exit_offset > entry
    ]
    scored = [window for window in windows if window.get("sufficient")]
    survivors = [window for window in scored if window["beatsCosts"]]
    return {
        "status": "ready",
        "studyVersion": STUDY_VERSION,
        "announcements": len(events),
        "securities": len({event["ticker"] for event in events}),
        "windowsTested": len(scored),
        "windows": sorted(scored, key=lambda window: -(window["meanExcess"] or 0)),
        "survivingWindows": len(survivors),
        "costAssumption": (
            f"A round trip is charged {ROUND_TRIP_COST_PERCENT}% before any window counts."
        ),
        "multipleComparisons": (
            f"{len(scored)} windows were measured. With that many, the best-looking one is "
            "expected to look good by chance alone, so a single winner proves nothing on its own."
        ),
        "limitation": (
            "One market regime of roughly two years, measured in sample, with no slippage, "
            "spread, borrow cost or tax. Real trading would keep less than these figures show."
        ),
    }
