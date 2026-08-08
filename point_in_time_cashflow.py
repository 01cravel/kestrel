"""As-filed free-cash-flow valuation for Kestrel's direct companies.

The calculation uses only SEC facts filed by each observation date:
operating cash flow less purchases of property, plant and equipment.  It then
compares market value / free cash flow with the company's own prior history.
"""

from __future__ import annotations

import math
import statistics
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple


ALLOWED_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "6-K"}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
MIN_HISTORY_POINTS = 5
ADR_RATIOS = {"TSM": 5.0}
CFO_TAGS = (
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
)
CAPEX_TAGS = (
    ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
    ("us-gaap", "PaymentsToAcquireProductiveAssets"),
    ("us-gaap", "PaymentsForAdditionsToPropertyPlantAndEquipment"),
    ("ifrs-full", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"),
    ("ifrs-full", "PurchaseOfPropertyPlantAndEquipment"),
)
SHARE_TAGS = (
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
)


def _parse_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _duration(row: Dict[str, Any]) -> Optional[int]:
    start, end = _parse_date(row.get("start")), _parse_date(row.get("end"))
    return (end - start).days if start and end else None


def _eligible_flows(entries: Iterable[Dict[str, Any]], as_of: date) -> List[Dict[str, Any]]:
    result = []
    for row in entries:
        filed, end, duration = _parse_date(row.get("filed")), _parse_date(row.get("end")), _duration(row)
        try:
            value = float(row.get("val"))
        except (TypeError, ValueError):
            continue
        if (
            row.get("form") in ALLOWED_FORMS and filed and filed <= as_of and end
            and duration is not None and 20 <= duration <= 430 and math.isfinite(value)
        ):
            result.append({**row, "val": value, "_filed": filed, "_end": end, "_duration": duration})
    return result


def ttm_flow_as_of(entries: Iterable[Dict[str, Any]], as_of: date) -> Optional[Dict[str, Any]]:
    """Reconstruct a trailing flow from annual and comparable YTD filings."""
    rows = _eligible_flows(entries, as_of)
    annuals = [row for row in rows if row["form"] in ANNUAL_FORMS and 300 <= row["_duration"] <= 430]
    if not annuals:
        return None
    annual = max(annuals, key=lambda row: (row["_end"], row["_filed"]))
    result = {
        "value": annual["val"], "periodEnd": annual["end"], "filed": annual["filed"],
        "form": annual["form"], "accession": annual.get("accn"),
        "method": "Latest as-filed annual amount",
    }
    interims = [
        row for row in rows if row["form"] not in ANNUAL_FORMS
        and row["_end"] > annual["_end"] and row["_duration"] <= 300
    ]
    if not interims:
        return result
    latest_end = max(row["_end"] for row in interims)
    latest_filed = max(row["_filed"] for row in interims if row["_end"] == latest_end)
    accessions = {
        row.get("accn") for row in interims
        if row["_end"] == latest_end and row["_filed"] == latest_filed
    }
    filing_rows = [row for row in rows if row.get("accn") in accessions]
    current_candidates = [row for row in filing_rows if row["_end"] == latest_end and row["_duration"] <= 300]
    if not current_candidates:
        return result
    current = max(current_candidates, key=lambda row: row["_duration"])
    prior_candidates = [
        row for row in filing_rows
        if 300 <= (current["_end"] - row["_end"]).days <= 430
        and abs(row["_duration"] - current["_duration"]) <= 35
    ]
    if not prior_candidates:
        return result
    prior = min(prior_candidates, key=lambda row: abs((current["_end"] - row["_end"]).days - 365))
    return {
        "value": annual["val"] + current["val"] - prior["val"],
        "periodEnd": current["end"], "filed": current["filed"],
        "form": current["form"], "accession": current.get("accn"),
        "method": "As-filed annual plus current YTD minus prior comparable YTD",
    }


def _facts(payload: Dict[str, Any], tags: Tuple[Tuple[str, str], ...],
           units: Tuple[str, ...]) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    facts = payload.get("facts") or {}
    for unit in units:
        candidates = []
        for tag_index, (taxonomy, tag) in enumerate(tags):
            concept = (facts.get(taxonomy) or {}).get(tag) or {}
            available = concept.get("units") or {}
            rows = available.get(unit)
            if isinstance(rows, list) and rows:
                usable = [row for row in rows if isinstance(row, dict)]
                latest = max((str(row.get("filed") or "") for row in usable), default="")
                candidates.append((latest, -tag_index, usable, f"{taxonomy}:{tag}"))
        if candidates:
            _, _, rows, source_tag = max(candidates, key=lambda item: (item[0], item[1]))
            return rows, unit, source_tag
    return [], None, None


def _shares_as_of(entries: Iterable[Dict[str, Any]], as_of: date) -> Optional[Dict[str, Any]]:
    candidates = []
    for row in entries:
        filed, end = _parse_date(row.get("filed")), _parse_date(row.get("end"))
        try:
            value = float(row.get("val"))
        except (TypeError, ValueError):
            continue
        if row.get("form") in ALLOWED_FORMS and filed and filed <= as_of and end and value > 0:
            candidates.append({**row, "val": value, "_filed": filed, "_end": end})
    if not candidates:
        return None
    row = max(candidates, key=lambda item: (item["_end"], item["_filed"]))
    return {"value": row["val"], "filed": row["filed"], "end": row["end"], "accession": row.get("accn")}


def _on_or_after(prices: List[Dict[str, Any]], day: date) -> Optional[Dict[str, Any]]:
    return next((row for row in prices if day <= row["date"] <= day + timedelta(days=7)), None)


def _on_or_before(values: Dict[date, float], day: date) -> Optional[float]:
    for offset in range(8):
        value = values.get(day - timedelta(days=offset))
        if value is not None:
            return value
    return None


def _percentile(values: List[float], target: float) -> float:
    below, equal = sum(v < target for v in values), sum(v == target for v in values)
    return (below + 0.5 * equal) / len(values) if values else 0.5


def build_company_cashflow(symbol: str, cik: str, companyfacts: Dict[str, Any],
                           prices: List[Dict[str, Any]], fx_rates: Dict[date, float],
                           today: Optional[date] = None) -> Dict[str, Any]:
    current_day = today or date.today()
    cfo, currency, cfo_tag = _facts(companyfacts, CFO_TAGS, ("USD", "EUR", "TWD"))
    capex, capex_currency, capex_tag = _facts(companyfacts, CAPEX_TAGS, (currency,) if currency else ())
    shares, _, share_tag = _facts(companyfacts, SHARE_TAGS, ("shares",))
    base = {
        "symbol": symbol, "source": "SEC EDGAR Company Facts",
        "sourceUrl": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        "currency": currency, "cfoTag": cfo_tag, "capexTag": capex_tag,
        "shareTag": share_tag, "definition": "Operating cash flow minus productive-asset purchases, normally property and equipment",
    }
    if not cfo or not capex or not shares or currency != capex_currency:
        return {**base, "status": "unavailable", "ready": False, "message": "Comparable operating cash flow, capital investment or share facts were missing."}

    def observation(as_of: date, price: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        operating, investment, share_count = ttm_flow_as_of(cfo, as_of), ttm_flow_as_of(capex, as_of), _shares_as_of(shares, as_of)
        if not operating or not investment or not share_count:
            return None
        free_cash_flow = operating["value"] - abs(investment["value"])
        if currency == "EUR":
            fx = _on_or_before(fx_rates, price["date"])
            if fx is None:
                return None
            free_cash_flow *= fx
        elif currency != "USD":
            return None
        traded_shares = (
            share_count["value"] / ADR_RATIOS.get(symbol, 1.0)
            * float(price.get("shareFactor") or 1.0)
        )
        market_value = price["close"] * traded_shares
        if market_value <= 0:
            return None
        multiple = market_value / free_cash_flow if free_cash_flow > 0 else None
        filed_day = max(_parse_date(operating["filed"]), _parse_date(investment["filed"]), _parse_date(share_count["filed"]))
        return {
            "knownOn": as_of.isoformat(), "priceDate": price["date"].isoformat(),
            "price": round(price["close"], 4), "filed": filed_day.isoformat(),
            "operatingCashFlow": round(operating["value"], 2),
            "capitalInvestment": round(abs(investment["value"]), 2),
            "freeCashFlow": round(free_cash_flow, 2), "tradedShares": round(traded_shares),
            "priceToFcf": round(multiple, 2) if multiple else None,
            "fcfYield": round(100 / multiple, 2) if multiple else None,
            "positiveFreeCashFlow": free_cash_flow > 0,
            "shareFactor": round(float(price.get("shareFactor") or 1.0), 6),
            "method": operating["method"],
        }

    latest_price = prices[-1] if prices else None
    if not latest_price:
        return {**base, "status": "unavailable", "ready": False, "message": "Current price evidence was missing."}
    filing_days = sorted({
        day for row in [*cfo, *capex, *shares]
        if (day := _parse_date(row.get("filed"))) and day <= current_day
    })
    cutoff = current_day - timedelta(days=10 * 366)
    history = []
    for filing_day in (day for day in filing_days if day >= cutoff):
        price = _on_or_after(prices, filing_day)
        item = observation(filing_day, price) if price else None
        # Very low but still positive free cash flow can create a large, real
        # multiple. Keep it visible rather than making an expensive period
        # disappear from the company's own comparison set.
        if item and item["priceToFcf"] is not None and 0 < item["priceToFcf"] <= 1000:
            history.append(item)
    history = list({(row["knownOn"], row["freeCashFlow"], row["tradedShares"]): row for row in history}.values())
    current = observation(current_day, latest_price)
    if not current:
        return {**base, "status": "unavailable", "ready": False, "history": history, "message": "Current free cash flow could not be reconstructed in the traded share currency."}
    prior = [row["priceToFcf"] for row in history if row["priceDate"] != current["priceDate"]]
    enough_history = len(prior) >= MIN_HISTORY_POINTS
    rank = _percentile(prior, current["priceToFcf"]) if enough_history and current["priceToFcf"] is not None else None
    filing_age = (current_day - _parse_date(current["filed"])).days
    price_age = (current_day - latest_price["date"]).days
    fresh = filing_age <= 450 and price_age <= 7
    verdict = "Not enough history"
    if rank is not None:
        verdict = "Cheaper than usual" if rank <= 0.25 else "Within its own range" if rank <= 0.75 else "More expensive than usual"
    current["filingAgeDays"], current["priceAgeDays"] = filing_age, price_age
    positive_current = bool(current.get("positiveFreeCashFlow"))
    ready = fresh and enough_history and positive_current
    return {
        **base, "status": "verified" if ready else "partial",
        "ready": ready,
        "message": (
            "As-filed cash generation was compared with the company's own valuation history."
            if positive_current else
            "Capital investment currently exceeds operating cash generation, so a positive free-cash-flow yield is not meaningful."
        ),
        "current": current, "history": history,
        "comparison": {
            "observations": len(prior),
            "medianPriceToFcf": round(statistics.median(prior), 2) if prior else None,
            "percentile": round(rank * 100, 1) if rank is not None else None,
            "verdict": verdict,
        },
    }
