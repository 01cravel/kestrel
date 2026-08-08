"""Independent historical-price verification for point-in-time valuations.

Yahoo supplies the working price series.  This module deliberately uses a
separate, exchange-operated Nasdaq series and compares the split-normalized historical close on every
date used by the valuation model.  Missing data or disagreement fails closed.
"""

from __future__ import annotations

import json
import math
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional


SOURCE_NAME = "Nasdaq official historical close"
SOURCE_PAGE = "https://www.nasdaq.com/market-activity/stocks/{symbol}/historical"
SOURCE_API = "https://api.nasdaq.com/api/quote/{symbol}/historical"
AGREEMENT_TOLERANCE_PCT = 1.0
MATERIAL_DIFFERENCE_PCT = 3.0
MIN_MATCHED_DATES = 5
MIN_COVERAGE_PCT = 80.0


def _money(value: Any) -> Optional[float]:
    try:
        parsed = float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 and math.isfinite(parsed) else None


def parse_nasdaq_history(payload: Any) -> List[Dict[str, Any]]:
    """Parse Nasdaq's public historical table response into ascending closes."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = (((data or {}).get("tradesTable") or {}).get("rows") or [])
    parsed = []
    for row in rows:
        try:
            day = datetime.strptime(str(row.get("date")), "%m/%d/%Y").date()
        except (TypeError, ValueError):
            continue
        close = _money(row.get("close"))
        if close is not None:
            parsed.append({"date": day, "close": close})
    if not parsed:
        raise RuntimeError("Nasdaq returned no usable historical closes")
    return sorted(parsed, key=lambda item: item["date"])


def nasdaq_raw_prices(symbol: str, downloader: Callable[[str], str],
                      today: Optional[date] = None, years: int = 10) -> List[Dict[str, Any]]:
    current_day = today or date.today()
    start_day = current_day - timedelta(days=years * 366)
    query = urllib.parse.urlencode({
        "assetclass": "stocks", "fromdate": start_day.isoformat(),
        "todate": current_day.isoformat(), "limit": 5000,
    })
    url = f"{SOURCE_API.format(symbol=urllib.parse.quote(symbol))}?{query}"
    return parse_nasdaq_history(downloader(url))


def cross_check_prices(record: Dict[str, Any], independent: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare every price used by one valuation record with Nasdaq.

    Verification requires the current date, at least five matched dates, at
    least 80% coverage and every matched close within 1%.  That strict rule is
    intentional: a cross-check should detect problems, not average them away.
    """
    symbol = str(record.get("symbol") or "")
    checkpoints = list(record.get("history") or [])
    current = record.get("current") or {}
    if current.get("priceDate") and current.get("price") is not None:
        checkpoints.append({
            "priceDate": current.get("priceDate"), "price": current.get("price"),
            "kind": "current",
        })
    # A date can appear more than once when the EPS state changes on the same
    # market session; compare the source price only once.
    expected = {}
    for item in checkpoints:
        if item.get("priceDate") and item.get("price") is not None:
            expected[str(item["priceDate"])] = float(item["price"])
    independent_by_day = {row["date"].isoformat(): float(row["close"]) for row in independent}
    comparisons = []
    for day, primary in sorted(expected.items()):
        second = independent_by_day.get(day)
        if second is None:
            continue
        difference = abs(second - primary) / primary * 100 if primary > 0 else math.inf
        comparisons.append({
            "date": day, "workingClose": round(primary, 4),
            "independentClose": round(second, 4),
            "differencePct": round(difference, 3),
            "agrees": difference <= AGREEMENT_TOLERANCE_PCT,
        })
    total = len(expected)
    matched = len(comparisons)
    coverage = matched / total * 100 if total else 0.0
    current_day = str(current.get("priceDate") or "")
    current_matched = any(item["date"] == current_day for item in comparisons)
    all_agree = bool(comparisons) and all(item["agrees"] for item in comparisons)
    material_disagreements = sum(item["differencePct"] > MATERIAL_DIFFERENCE_PCT for item in comparisons)
    ready = (
        total >= MIN_MATCHED_DATES and matched >= MIN_MATCHED_DATES
        and coverage >= MIN_COVERAGE_PCT and current_matched
        and all_agree and material_disagreements == 0
    )
    if ready:
        status, message = "verified", f"Nasdaq agreed within 1% on all {matched} matched dates."
    elif material_disagreements:
        status, message = "disagreed", f"{material_disagreements} price differences exceeded 3%."
    elif not total:
        status, message = "unavailable", "There were no valuation price dates to verify."
    else:
        status, message = "partial", "Coverage or exact-date agreement was insufficient."
    return {
        "status": status, "ready": ready, "message": message,
        "source": SOURCE_NAME,
        "sourceUrl": SOURCE_PAGE.format(symbol=symbol.lower()),
        "workingSource": record.get("priceSource"),
        "tolerancePct": AGREEMENT_TOLERANCE_PCT,
        "datesRequired": total, "datesMatched": matched,
        "coveragePct": round(coverage, 1),
        "agreeingDates": sum(item["agrees"] for item in comparisons),
        "materialDisagreements": material_disagreements,
        "maximumDifferencePct": round(max((item["differencePct"] for item in comparisons), default=0.0), 3),
        "currentDateMatched": current_matched,
        "comparisons": comparisons,
    }
