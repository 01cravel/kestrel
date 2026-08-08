"""Transparent, conservative scenario DCF for direct portfolio companies.

This is an equity cash-flow model, not a price target.  It discounts a
conservative proxy for cash available to shareholders (operating cash flow
less productive-asset purchases) and shows three explicit scenarios.
"""

from __future__ import annotations

import math
import statistics
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


COMPANIES = ("TSM", "GOOGL", "AMZN", "ASML", "MELI", "ETN", "ISRG", "CEG")
MARKET_PROXY = "VTI"
FORECAST_YEARS = 5
RISK_FREE_FLOOR_PCT = 4.5
EQUITY_RISK_PREMIUM_PCT = 5.5
BASE_DISCOUNT_FLOOR_PCT = 10.5
MIN_BETA_MONTHS = 36
MIN_ANNUAL_CASHFLOW_POINTS = 3
MAX_BASE_GROWTH_PCT = 8.0
MAX_STRONG_GROWTH_PCT = 10.0
MAX_TERMINAL_SHARE_PCT = 80.0
TREASURY_SOURCE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"


def official_treasury_10y(today: Optional[date] = None) -> Dict[str, Any]:
    current_day = today or date.today()
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data=daily_treasury_yield_curve&field_tdr_date_value={current_day.year}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Kestrel valuation research"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            root = ET.fromstring(response.read())
        namespaces = {
            "a": "http://www.w3.org/2005/Atom",
            "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
            "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
        }
        values = []
        for entry in root.findall("a:entry", namespaces):
            properties = entry.find("a:content/m:properties", namespaces)
            if properties is None:
                continue
            day_node = properties.find("d:NEW_DATE", namespaces)
            yield_node = properties.find("d:BC_10YEAR", namespaces)
            if day_node is None or yield_node is None or not day_node.text or not yield_node.text:
                continue
            day = date.fromisoformat(day_node.text[:10])
            value = float(yield_node.text)
            if day <= current_day and value > 0:
                values.append((day, value))
        if not values:
            raise ValueError("No current 10-year Treasury observation")
        day, value = max(values)
        return {"ready": True, "valuePct": round(value, 3), "date": day.isoformat(), "source": "U.S. Treasury 10-year par yield", "sourceUrl": TREASURY_SOURCE}
    except (OSError, ValueError, ET.ParseError):
        return {"ready": False, "valuePct": RISK_FREE_FLOOR_PCT, "date": None, "source": "Conservative risk-free floor", "sourceUrl": TREASURY_SOURCE}


def _number(value: Any) -> Optional[float]:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _monthly_returns(history: Dict[str, Any]) -> Dict[str, float]:
    closes = {}
    for point in history.get("points") or []:
        close = _number(point.get("close")) if isinstance(point, dict) else None
        day = str(point.get("date") or "") if isinstance(point, dict) else ""
        if close and close > 0 and len(day) >= 7:
            closes[day[:7]] = close
    ordered = sorted(closes.items())
    return {
        month: close / ordered[index - 1][1] - 1
        for index, (month, close) in enumerate(ordered)
        if index and ordered[index - 1][1] > 0
    }


def estimate_beta(symbol_history: Dict[str, Any], market_history: Dict[str, Any]) -> Dict[str, Any]:
    stock, market = _monthly_returns(symbol_history), _monthly_returns(market_history)
    months = sorted(set(stock) & set(market))[-60:]
    if len(months) < MIN_BETA_MONTHS:
        return {"ready": False, "months": len(months), "raw": None, "used": None}
    xs, ys = [market[m] for m in months], [stock[m] for m in months]
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    variance = sum((value - mean_x) ** 2 for value in xs)
    covariance = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(len(months)))
    if variance <= 0:
        return {"ready": False, "months": len(months), "raw": None, "used": None}
    raw = covariance / variance
    used = min(1.6, max(0.8, raw))
    return {"ready": True, "months": len(months), "raw": round(raw, 3), "used": round(used, 3)}


def _annual_cashflow_per_share(record: Dict[str, Any]) -> List[Tuple[int, float]]:
    by_year = {}
    for item in record.get("history") or []:
        try:
            year = int(str(item.get("knownOn"))[:4])
            cash = float(item.get("freeCashFlow"))
            shares = float(item.get("tradedShares"))
        except (TypeError, ValueError):
            continue
        if cash > 0 and shares > 0:
            by_year[year] = (str(item.get("knownOn")), cash / shares)
    return [(year, by_year[year][1]) for year in sorted(by_year)]


def _growth_anchor(annual: List[Tuple[int, float]]) -> float:
    changes = []
    for (prior_year, prior), (year, value) in zip(annual, annual[1:]):
        years = year - prior_year
        if years > 0 and prior > 0 and value > 0:
            growth = (value / prior) ** (1 / years) - 1
            changes.append(min(0.5, max(-0.5, growth)))
    median = statistics.median(changes[-5:]) * 100 if changes else 0.0
    return round(min(MAX_BASE_GROWTH_PCT, max(0.0, median)), 2)


def discounted_value(start_fcf_per_share: float, growth_pct: float,
                     discount_pct: float, terminal_growth_pct: float,
                     years: int = FORECAST_YEARS) -> Dict[str, float]:
    growth, discount, terminal_growth = growth_pct / 100, discount_pct / 100, terminal_growth_pct / 100
    if start_fcf_per_share <= 0 or discount <= terminal_growth:
        raise ValueError("DCF assumptions were not economically valid")
    present_value, cash = 0.0, start_fcf_per_share
    for year in range(1, years + 1):
        cash *= 1 + growth
        present_value += cash / ((1 + discount) ** year)
    terminal = cash * (1 + terminal_growth) / (discount - terminal_growth)
    terminal_present = terminal / ((1 + discount) ** years)
    total = present_value + terminal_present
    return {
        "value": round(total, 2),
        "forecastCashValue": round(present_value, 2),
        "terminalValue": round(terminal_present, 2),
        "terminalSharePct": round(terminal_present / total * 100, 1),
    }


def build_company_dcf(symbol: str, cashflow_record: Dict[str, Any],
                      symbol_history: Dict[str, Any], market_history: Dict[str, Any],
                      risk_free_pct: float = RISK_FREE_FLOOR_PCT) -> Dict[str, Any]:
    current = cashflow_record.get("current") or {}
    current_cash, shares, price = (
        _number(current.get("freeCashFlow")),
        _number(current.get("tradedShares")),
        _number(current.get("price")),
    )
    annual = _annual_cashflow_per_share(cashflow_record)
    beta = estimate_beta(symbol_history, market_history)
    base = {
        "symbol": symbol, "method": "Five-year equity cash-flow DCF with a perpetual-growth terminal value",
        "source": "SEC as-filed cash flow and split-normalized market history",
        "beta": beta, "annualCashFlowPoints": len(annual), "forecastYears": FORECAST_YEARS,
    }
    if not current_cash or current_cash <= 0 or not shares or shares <= 0 or not price or price <= 0:
        return {
            **base, "status": "unavailable", "ready": False, "currentPrice": price,
            "message": "Current free cash flow is not positive, so a conventional DCF would manufacture a result.",
        }
    if len(annual) < MIN_ANNUAL_CASHFLOW_POINTS:
        return {
            **base, "status": "limited", "ready": False, "currentPrice": price,
            "message": "There are too few standalone annual cash-flow observations to set a defensible starting point.",
        }
    if not beta.get("ready"):
        return {
            **base, "status": "limited", "ready": False, "currentPrice": price,
            "message": "There is too little common market history to estimate a conservative discount rate.",
        }

    current_per_share = current_cash / shares
    recent = [value for _, value in annual[-3:]]
    normalized_per_share = min(current_per_share, statistics.median(recent))
    base_growth = _growth_anchor(annual)
    risk_free_used = max(RISK_FREE_FLOOR_PCT, risk_free_pct)
    base_discount = max(BASE_DISCOUNT_FLOOR_PCT, risk_free_used + beta["used"] * EQUITY_RISK_PREMIUM_PCT)
    assumptions = [
        ("downside", "Downside", normalized_per_share * 0.8, max(-5.0, min(0.0, base_growth - 6.0)), base_discount + 2.0, 1.5),
        ("base", "Conservative base", normalized_per_share, base_growth, base_discount, 2.0),
        ("strong", "Strong execution", normalized_per_share, min(MAX_STRONG_GROWTH_PCT, base_growth + 3.0), max(9.5, base_discount - 1.0), 2.5),
    ]
    scenarios = []
    for scenario_id, name, start, growth, discount, terminal_growth in assumptions:
        result = discounted_value(start, growth, discount, terminal_growth)
        scenarios.append({
            "id": scenario_id, "name": name,
            "startFcfPerShare": round(start, 4), "growthPct": round(growth, 2),
            "discountPct": round(discount, 2), "terminalGrowthPct": terminal_growth,
            **result, "versusPricePct": round((result["value"] / price - 1) * 100, 1),
        })
    base_case = next(item for item in scenarios if item["id"] == "base")
    ready = base_case["terminalSharePct"] <= MAX_TERMINAL_SHARE_PCT
    return {
        **base, "status": "verified" if ready else "limited", "ready": ready,
        "currentPrice": round(price, 2), "currentFcfPerShare": round(current_per_share, 4),
        "normalizedFcfPerShare": round(normalized_per_share, 4),
        "baseGrowthPct": base_growth, "baseDiscountPct": round(base_discount, 2),
        "riskFreeUsedPct": round(risk_free_used, 3),
        "scenarios": scenarios,
        "rangeLow": scenarios[0]["value"], "rangeHigh": scenarios[-1]["value"],
        "message": (
            "The model passed its history, discount-rate and terminal-value checks."
            if ready else "Too much of the result comes from the terminal value, so confidence remains limited."
        ),
    }


def build_dcf_snapshot(cashflow: Dict[str, Any], histories: Dict[str, Dict[str, Any]],
                       risk_free: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    records = cashflow.get("companies") or {}
    risk_free_evidence = risk_free or {
        "ready": False, "valuePct": RISK_FREE_FLOOR_PCT, "date": None,
        "source": "Conservative risk-free floor", "sourceUrl": TREASURY_SOURCE,
    }
    companies = {
        symbol: build_company_dcf(
            symbol, records.get(symbol) or {}, histories.get(symbol) or {}, histories.get(MARKET_PROXY) or {},
            risk_free_pct=float(risk_free_evidence.get("valuePct") or RISK_FREE_FLOOR_PCT),
        )
        for symbol in COMPANIES
    }
    ready = sum(bool(record.get("ready")) for record in companies.values())
    return {
        "status": "complete" if ready == len(COMPANIES) else "incomplete",
        "complete": ready == len(COMPANIES), "companiesReady": ready,
        "companiesTotal": len(COMPANIES), "companies": companies,
        "method": "Five-year levered cash-flow scenarios; market beta sets a floored cost of equity; terminal growth never exceeds 2.5%",
        "assumptions": {
            "riskFreeFloorPct": RISK_FREE_FLOOR_PCT,
            "equityRiskPremiumPct": EQUITY_RISK_PREMIUM_PCT,
            "baseDiscountFloorPct": BASE_DISCOUNT_FLOOR_PCT,
            "terminalGrowthRangePct": [1.5, 2.5],
            "baseGrowthCapPct": MAX_BASE_GROWTH_PCT,
            "strongGrowthCapPct": MAX_STRONG_GROWTH_PCT,
        },
        "riskFreeEvidence": risk_free_evidence,
        "warning": "These are sensitivity ranges, not price targets or probabilities. Small assumption changes can materially alter DCF values.",
    }
