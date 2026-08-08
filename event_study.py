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


def persistence_check(database: Path = DEFAULT_DATABASE,
                      entries: Sequence[int] = ENTRY_OFFSETS,
                      exits: Sequence[int] = EXIT_OFFSETS,
                      min_events_each_half: int = 4) -> Dict[str, Any]:
    """Does a security's best-looking window keep working afterwards?

    For each security the events are split in time. The window that looked best
    in the earlier half is then measured in the later half. If per-security
    timing were real, that carried-forward choice would beat simply averaging
    every window. If it is noise, it will not.
    """
    events = collect_events(database)
    by_ticker: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        by_ticker.setdefault(event["ticker"], []).append(event)

    combinations = [
        (entry, exit_offset) for entry in entries for exit_offset in exits
        if exit_offset > entry
    ]
    carried: List[float] = []
    averages: List[float] = []
    for ticker, ticker_events in by_ticker.items():
        ordered = sorted(ticker_events, key=lambda event: event["reactionDate"])
        half = len(ordered) // 2
        if half < min_events_each_half or len(ordered) - half < min_events_each_half:
            continue
        early, late = ordered[:half], ordered[half:]

        def mean_for(sample: Sequence[Dict[str, Any]], entry: int, exit_offset: int) -> Optional[float]:
            values = []
            for event in sample:
                value = _excess(event["series"], event["reactionIndex"] + entry,
                                event["reactionIndex"] + exit_offset)
                if value is not None:
                    values.append(value)
            return statistics.mean(values) if values else None

        scored = [
            (mean_for(early, entry, exit_offset), entry, exit_offset)
            for entry, exit_offset in combinations
        ]
        scored = [row for row in scored if row[0] is not None]
        if not scored:
            continue
        _, best_entry, best_exit = max(scored, key=lambda row: row[0])
        forward = mean_for(late, best_entry, best_exit)
        every = [mean_for(late, entry, exit_offset) for entry, exit_offset in combinations]
        every = [value for value in every if value is not None]
        if forward is None or not every:
            continue
        carried.append(forward)
        averages.append(statistics.mean(every))

    if not carried:
        return {"status": "insufficient", "securities": 0}
    differences = [forward - every for forward, every in zip(carried, averages)]
    advantage = statistics.mean(differences)
    interval = block_bootstrap_interval(
        [{"sessionDate": str(index), "value": value} for index, value in enumerate(differences)],
        lambda sample: statistics.mean(row["value"] for row in sample) if sample else None,
    )
    beat_rate = sum(1 for value in differences if value > 0) / len(differences)
    # A sign test: with this many securities, a genuine effect would push the
    # win rate clearly past half rather than sitting on it.
    error = (0.25 / len(differences)) ** 0.5
    convincing = bool(
        interval.get("lower95") is not None and interval["lower95"] > 0
        and beat_rate - 0.5 > 2 * error
    )
    return {
        "status": "measured",
        "securities": len(carried),
        "carriedForwardMean": round(statistics.mean(carried), 3),
        "allWindowMean": round(statistics.mean(averages), 3),
        "advantage": round(advantage, 3),
        "advantageLower95": interval.get("lower95"),
        "advantageUpper95": interval.get("upper95"),
        "beatChanceRate": round(beat_rate, 4),
        "coinFlipRate": 0.5,
        "verdict": (
            "The best-looking window carried forward by more than chance."
            if convincing else
            "The best-looking window did not carry forward. Choosing a timing per "
            "security is fitting noise: it wins about as often as a coin."
        ),
    }


def _daily_excess(rows: Sequence[Tuple[str, float, float]], index: int) -> Optional[float]:
    """One session's benchmark-relative move, as a percentage."""
    if index <= 0 or index >= len(rows):
        return None
    stock = rows[index][1] / rows[index - 1][1] - 1
    benchmark = rows[index][2] / rows[index - 1][2] - 1
    return (stock - benchmark) * 100


def move_timing(database: Path = DEFAULT_DATABASE, sessions_after: int = 5,
                events: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Where in the week the movement actually lands, per security.

    This is a question about size, not direction, and size is far more stable
    than edge. Knowing that most of a week's movement arrives in one session
    tells a holder when they are exposed, without implying a trade.
    """
    events = collect_events(database) if events is None else events
    per_ticker: Dict[str, List[List[float]]] = {}
    for event in events:
        rows = event["series"]
        reaction = event["reactionIndex"]
        moves = []
        for step in range(sessions_after):
            value = _daily_excess(rows, reaction + step)
            if value is None:
                break
            moves.append(abs(value))
        if len(moves) == sessions_after:
            per_ticker.setdefault(event["ticker"], []).append(moves)

    timings: Dict[str, Dict[str, Any]] = {}
    for ticker, samples in per_ticker.items():
        if len(samples) < 3:
            continue
        reaction_day = statistics.mean(sample[0] for sample in samples)
        rest = statistics.mean(sum(sample[1:]) for sample in samples)
        total = reaction_day + rest
        if not total:
            continue
        other_days = statistics.mean(
            statistics.mean(sample[1:]) for sample in samples if len(sample) > 1
        )
        timings[ticker] = {
            "events": len(samples),
            "reactionDayMove": round(reaction_day, 2),
            "otherDayMove": round(other_days, 2),
            "reactionShareOfWeek": round(reaction_day / total, 4),
            "timesAnOrdinaryDay": round(reaction_day / other_days, 1) if other_days else None,
        }
    return timings
