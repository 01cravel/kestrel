"""Confirmed earnings-announcement dates from SEC filings, and honest projections.

A company announces results by filing an 8-K carrying item 2.02, *Results of
Operations and Financial Condition*. Those filings are authoritative, free, and
carry an acceptance timestamp, so Kestrel can say exactly when results became
public rather than inferring it from a price move. Inferring the date from the
reaction is unreliable: a large move near a reporting window may belong to some
other news entirely.

What the SEC cannot give is the *next* date, which companies pre-announce
through investor relations rather than through EDGAR. This module therefore
separates two things and never blurs them:

* **confirmed** — a filing that exists, with its accession number and timestamp;
* **projected** — an arithmetic estimate from the historical cadence, presented
  as a window with its own error, never as a known date.

A projection is a scheduling expectation. It is not a forecast of the result,
and nothing here says anything about direction.
"""

from __future__ import annotations

import datetime as dt
import statistics
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from outcome_source import DEFAULT_DATABASE
from sec_data import _sec_json, sec_identity


EARNINGS_ITEM = "2.02"
RADAR_HORIZON_DAYS = 14
RADAR_CACHE_SECONDS = 12 * 60 * 60
_RADAR_LOCK = threading.Lock()
_RADAR_CACHE: Dict[str, Any] = {}
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
# US markets close at 16:00 New York time; results filed after that are read by
# the market on the following session.
MARKET_CLOSE_HOUR_UTC = 20
MIN_HISTORY_FOR_PROJECTION = 4
# Quarterly reporters also file results-related 8-Ks between quarters — guidance
# updates, pre-announcements — and a missed detection leaves a double-length
# gap. Only gaps that plausibly represent one reporting period define cadence.
QUARTERLY_GAP_BAND = (70, 110)
MIN_GAPS_FOR_CADENCE = 3
# Companies whose gaps vary more than this do not have a projectable cadence.
MAX_CADENCE_SPREAD_DAYS = 28
MIN_WINDOW_HALF_WIDTH_DAYS = 4
MAX_WINDOW_HALF_WIDTH_DAYS = 14


def _interquartile_range(values: Sequence[int]) -> int:
    """Robust spread; ignores the one-off gap that would widen a window absurdly."""
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    lower = ordered[:midpoint]
    upper = ordered[midpoint + 1:] if len(ordered) % 2 else ordered[midpoint:]
    if not lower or not upper:
        return max(ordered) - min(ordered)
    return int(statistics.median(upper) - statistics.median(lower))


def _parse_date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def confirmed_announcements(symbol: str, limit: int = 12) -> Dict[str, Any]:
    """Every 8-K item 2.02 filing Kestrel can verify, newest first."""
    identity = sec_identity(symbol)
    if identity.get("status") != "verified":
        return {"status": "unavailable", "symbol": symbol.upper(),
                "reason": "No SEC identity for this ticker", "announcements": []}
    cik = identity["cik"]
    try:
        payload = _sec_json(SUBMISSIONS_URL.format(cik=cik))
    except RuntimeError as error:
        return {"status": "unavailable", "symbol": symbol.upper(),
                "reason": str(error), "announcements": []}

    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    announcements: List[Dict[str, Any]] = []
    for index, form in enumerate(forms):
        if form != "8-K":
            continue
        items = str((recent.get("items") or [""] * len(forms))[index] or "")
        if EARNINGS_ITEM not in [entry.strip() for entry in items.split(",")]:
            continue
        filing_date = _parse_date((recent.get("filingDate") or [])[index])
        if not filing_date:
            continue
        accepted = str((recent.get("acceptanceDateTime") or [""] * len(forms))[index] or "")
        after_close = _after_close(accepted)
        accession = str((recent.get("accessionNumber") or [""] * len(forms))[index] or "")
        announcements.append({
            "announcedOn": filing_date.isoformat(),
            "acceptedAt": accepted,
            "afterMarketClose": after_close,
            "marketReactionDate": (
                _next_weekday(filing_date).isoformat() if after_close else filing_date.isoformat()
            ),
            "reportPeriod": _parse_date((recent.get("reportDate") or [""] * len(forms))[index]),
            "accession": accession,
            "sourceUrl": FILING_INDEX_URL.format(
                cik=str(int(cik)), accession=accession.replace("-", "")
            ),
            "source": "SEC EDGAR 8-K item 2.02",
        })
        if len(announcements) >= limit:
            break

    for entry in announcements:
        period = entry.get("reportPeriod")
        entry["reportPeriod"] = period.isoformat() if isinstance(period, dt.date) else None
    return {
        "status": "verified" if announcements else "none-found",
        "symbol": identity["symbol"],
        "name": identity.get("name"),
        "cik": cik,
        "announcements": announcements,
        "source": "SEC EDGAR",
        "sourceUrl": SUBMISSIONS_URL.format(cik=cik),
    }


def _after_close(accepted: str) -> Optional[bool]:
    """SEC acceptance timestamps are Eastern; treat 16:00 as the boundary."""
    try:
        stamp = dt.datetime.fromisoformat(accepted.replace("Z", ""))
    except (TypeError, ValueError):
        return None
    return stamp.hour >= 16


def _next_weekday(day: dt.date) -> dt.date:
    following = day + dt.timedelta(days=1)
    while following.weekday() >= 5:
        following += dt.timedelta(days=1)
    return following


def next_expected(symbol: str, today: Optional[dt.date] = None) -> Dict[str, Any]:
    """Project the next announcement window from the confirmed cadence.

    The projection is arithmetic on past spacing. It carries the observed spread
    as an explicit window and is never described as a confirmed date.
    """
    today = today or dt.date.today()
    history = confirmed_announcements(symbol)
    if history["status"] != "verified":
        return {**history, "projection": None}

    dates = sorted(_parse_date(entry["announcedOn"]) for entry in history["announcements"])
    dates = [day for day in dates if day]
    if len(dates) < MIN_HISTORY_FOR_PROJECTION:
        return {
            "status": "insufficient-history", "symbol": history["symbol"],
            "confirmedAnnouncements": len(dates), "projection": None,
            "message": "Too few confirmed announcements to project a cadence.",
        }

    all_gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    low, high = QUARTERLY_GAP_BAND
    gaps = [gap for gap in all_gaps if low <= gap <= high]
    if len(gaps) < MIN_GAPS_FOR_CADENCE:
        return {
            "status": "irregular-cadence", "symbol": history["symbol"],
            "confirmedAnnouncements": len(dates), "observedGapDays": sorted(all_gaps),
            "projection": None,
            "message": "This company does not file results on a regular cadence, so no date is projected.",
        }

    spread = _interquartile_range(gaps)
    if spread > MAX_CADENCE_SPREAD_DAYS:
        return {
            "status": "irregular-cadence", "symbol": history["symbol"],
            "confirmedAnnouncements": len(dates), "observedGapDays": sorted(all_gaps),
            "cadenceSpreadDays": spread, "projection": None,
            "message": (
                f"Reporting gaps vary by {spread} days, too irregular to project a date honestly."
            ),
        }

    typical = statistics.median(gaps)
    last = dates[-1]
    expected = last + dt.timedelta(days=int(typical))
    half_width = min(MAX_WINDOW_HALF_WIDTH_DAYS,
                     max(MIN_WINDOW_HALF_WIDTH_DAYS, int(round(spread / 2)) + 2))
    earliest = expected - dt.timedelta(days=half_width)
    latest = expected + dt.timedelta(days=half_width)
    days_away = (expected - today).days

    return {
        "status": "projected",
        "symbol": history["symbol"],
        "name": history.get("name"),
        "lastConfirmed": last.isoformat(),
        "lastConfirmedSource": history["announcements"][0]["sourceUrl"],
        "confirmedAnnouncements": len(dates),
        "typicalGapDays": int(typical),
        "cadenceSpreadDays": spread,
        "observedGapDays": sorted(gaps),
        "projection": {
            "expectedDate": expected.isoformat(),
            "windowStart": earliest.isoformat(),
            "windowEnd": latest.isoformat(),
            "windowHalfWidthDays": half_width,
            "daysAway": days_away,
            "windowIsOpen": earliest <= today <= latest,
            "overdue": today > latest,
            "precision": (
                "firm" if half_width <= 5 else "approximate" if half_width <= 9 else "wide"
            ),
        },
        "confidence": (
            "The date is estimated from the spacing of past filings. Companies announce "
            "the real date through investor relations, which EDGAR does not carry, so treat "
            "this as a window rather than a diary entry."
        ),
        "limitation": "A projected date says nothing about the result or its direction.",
        "source": "SEC EDGAR 8-K item 2.02",
    }


def reaction_history(symbol: str, database: Optional[Path] = None,
                     today: Optional[dt.date] = None) -> Dict[str, Any]:
    """How large past results reactions were, measured against the benchmark.

    Reactions come from the archive's adjusted closes on the session the market
    could first respond to each confirmed filing. Magnitude is reported, not
    direction: with a handful of events, the sign carries no information, and
    presenting it as if it did would be the most misleading thing here.
    """
    database = Path(database) if database else DEFAULT_DATABASE
    history = confirmed_announcements(symbol)
    if history["status"] != "verified" or not Path(database).exists():
        return {"status": "unavailable", "symbol": symbol.upper(), "reactions": [],
                "reason": "No confirmed filings or no price archive"}

    reaction_dates = {entry["marketReactionDate"] for entry in history["announcements"]}
    moves = _session_moves(database, symbol.upper())
    if not moves:
        return {"status": "unavailable", "symbol": symbol.upper(), "reactions": [],
                "reason": "The archive holds no sessions for this security"}

    reactions = [
        {"date": date, "excessReturn": round(excess, 2)}
        for date, excess in sorted(moves.items()) if date in reaction_dates
    ]
    ordinary = [abs(excess) for date, excess in moves.items() if date not in reaction_dates]
    if not reactions:
        return {"status": "no-overlap", "symbol": symbol.upper(), "reactions": [],
                "reason": "No confirmed announcement falls inside the archived period"}

    magnitudes = sorted(abs(entry["excessReturn"]) for entry in reactions)
    typical = statistics.median(magnitudes)
    ordinary_typical = statistics.median(ordinary) if ordinary else None
    return {
        "status": "measured",
        "symbol": symbol.upper(),
        "eventsMeasured": len(reactions),
        "typicalReactionPercent": round(typical, 2),
        "smallestPercent": round(magnitudes[0], 2),
        "largestPercent": round(magnitudes[-1], 2),
        "ordinaryNightPercent": round(ordinary_typical, 2) if ordinary_typical else None,
        "multipleOfOrdinaryNight": (
            round(typical / ordinary_typical, 1) if ordinary_typical else None
        ),
        "reactions": reactions,
        "basis": "Benchmark-relative move on the first session able to respond to each filing.",
        "limitation": (
            f"{len(reactions)} events is far too few to read anything into direction. "
            "Only the size of the move is reported."
        ),
    }


def _session_moves(database: Path, symbol: str) -> Dict[str, float]:
    """Benchmark-relative one-session moves for a security, keyed by date."""
    import sqlite3

    try:
        connection = sqlite3.connect(str(database))
    except sqlite3.DatabaseError:
        return {}
    try:
        def series(ticker: str):
            return [
                (row[0], row[1]) for row in connection.execute(
                    "SELECT session_date, close FROM daily_bars WHERE ticker=? ORDER BY session_date",
                    (ticker,),
                ) if row[1]
            ]
        stock = series(symbol)
        benchmark = dict(series("SPY"))
    except sqlite3.DatabaseError:
        return {}
    finally:
        connection.close()

    moves: Dict[str, float] = {}
    for (previous_date, previous_close), (date, close) in zip(stock, stock[1:]):
        if previous_date in benchmark and date in benchmark and previous_close:
            stock_move = (close / previous_close - 1) * 100
            benchmark_move = (benchmark[date] / benchmark[previous_date] - 1) * 100
            moves[date] = stock_move - benchmark_move
    return moves


def earnings_radar(symbols: Sequence[str], database: Optional[Path] = None,
                   today: Optional[dt.date] = None,
                   horizon_days: int = RADAR_HORIZON_DAYS) -> Dict[str, Any]:
    """Every scheduled results event due within the horizon, across a universe.

    Cached, because each symbol costs one rate-limited SEC request. Securities
    Kestrel cannot resolve are listed rather than silently dropped: a missing
    calendar entry is not the same as no event.
    """
    today = today or dt.date.today()
    cache_key = (tuple(sorted({symbol.upper() for symbol in symbols})), today.isoformat(), horizon_days)
    with _RADAR_LOCK:
        cached = _RADAR_CACHE.get("payload")
        if cached and _RADAR_CACHE.get("key") == cache_key and \
                time.time() - _RADAR_CACHE.get("savedAt", 0) < RADAR_CACHE_SECONDS:
            return cached

    upcoming: List[Dict[str, Any]] = []
    unresolved: List[str] = []
    for symbol in sorted({symbol.upper() for symbol in symbols}):
        try:
            context = earnings_context(symbol, today)
        except RuntimeError:
            unresolved.append(symbol)
            continue
        if context.get("status") != "projected":
            unresolved.append(symbol)
            continue
        window = context["projection"]
        if window.get("overdue") or not (
            window["windowIsOpen"] or 0 <= window["daysAway"] <= horizon_days
        ):
            continue
        upcoming.append({
            "symbol": symbol,
            "name": context.get("name"),
            "expectedDate": window["expectedDate"],
            "windowStart": window["windowStart"],
            "windowEnd": window["windowEnd"],
            "daysAway": window["daysAway"],
            "windowIsOpen": window["windowIsOpen"],
            "windowHalfWidthDays": window["windowHalfWidthDays"],
            "flag": context["flag"],
            "lastConfirmed": context["lastConfirmed"],
            "sourceUrl": context["lastConfirmedSource"],
            "reaction": reaction_history(symbol, database, today),
        })
    upcoming.sort(key=lambda entry: (entry["expectedDate"], entry["symbol"]))

    payload = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asOf": today.isoformat(),
        "horizonDays": horizon_days,
        "events": upcoming,
        "unresolved": unresolved,
        "source": "SEC EDGAR 8-K item 2.02",
        "limitation": (
            "Dates are projected from each company's filing cadence, not from an announced "
            "diary. Sizes are historical; direction is not stated and is not knowable."
        ),
    }
    with _RADAR_LOCK:
        _RADAR_CACHE.update({"key": cache_key, "payload": payload, "savedAt": time.time()})
    return payload


def earnings_context(symbol: str, today: Optional[dt.date] = None) -> Dict[str, Any]:
    """Plain answer to: is this security near a scheduled results event?"""
    today = today or dt.date.today()
    projection = next_expected(symbol, today)
    if projection.get("status") != "projected":
        return {**projection, "flag": "unknown",
                "plainEnglish": "Kestrel cannot tell whether results are due."}
    window = projection["projection"]
    days = window["daysAway"]
    if window.get("overdue"):
        flag, message = "overdue", (
            f"Results were expected around {window['expectedDate']} and have not been filed. "
            "The cadence may have changed, or the date was announced differently."
        )
    elif window["windowIsOpen"]:
        flag, message = "window-open", (
            f"Results are due around {window['expectedDate']} and the window is open now "
            f"({window['windowStart']} to {window['windowEnd']}). Treat any position as "
            "exposed to a scheduled event with an unknowable outcome."
        )
    elif 0 <= days <= 14:
        flag, message = "approaching", (
            f"Results are expected around {window['expectedDate']}, about {days} days away."
        )
    else:
        flag, message = "clear", (
            f"No results expected soon; the next is estimated around {window['expectedDate']}."
        )
    return {**projection, "flag": flag, "plainEnglish": message}
