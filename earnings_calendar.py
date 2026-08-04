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
from typing import Any, Dict, List, Optional

from sec_data import _sec_json, sec_identity


EARNINGS_ITEM = "2.02"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
# US markets close at 16:00 New York time; results filed after that are read by
# the market on the following session.
MARKET_CLOSE_HOUR_UTC = 20
MIN_HISTORY_FOR_PROJECTION = 4


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

    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    typical = statistics.median(gaps)
    last = dates[-1]
    expected = last + dt.timedelta(days=int(typical))
    earliest = last + dt.timedelta(days=min(gaps))
    latest = last + dt.timedelta(days=max(gaps))
    days_away = (expected - today).days

    return {
        "status": "projected",
        "symbol": history["symbol"],
        "name": history.get("name"),
        "lastConfirmed": last.isoformat(),
        "lastConfirmedSource": history["announcements"][0]["sourceUrl"],
        "confirmedAnnouncements": len(dates),
        "typicalGapDays": int(typical),
        "observedGapDays": sorted(gaps),
        "projection": {
            "expectedDate": expected.isoformat(),
            "windowStart": earliest.isoformat(),
            "windowEnd": latest.isoformat(),
            "daysAway": days_away,
            "windowIsOpen": earliest <= today <= latest,
        },
        "confidence": (
            "The date is estimated from the spacing of past filings. Companies announce "
            "the real date through investor relations, which EDGAR does not carry, so treat "
            "this as a window rather than a diary entry."
        ),
        "limitation": "A projected date says nothing about the result or its direction.",
        "source": "SEC EDGAR 8-K item 2.02",
    }


def earnings_context(symbol: str, today: Optional[dt.date] = None) -> Dict[str, Any]:
    """Plain answer to: is this security near a scheduled results event?"""
    today = today or dt.date.today()
    projection = next_expected(symbol, today)
    if projection.get("status") != "projected":
        return {**projection, "flag": "unknown",
                "plainEnglish": "Kestrel cannot tell whether results are due."}
    window = projection["projection"]
    days = window["daysAway"]
    if window["windowIsOpen"]:
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
