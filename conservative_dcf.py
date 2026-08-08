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

from maintenance_investment import investment_sensitivity


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
FCFE_METHOD_SOURCE = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/AppldCF/derivn/ch11deriv.html"
ENTERPRISE_BRIDGE_SOURCE = "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation"


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


def _annual_net_borrowing_per_share(record: Dict[str, Any]) -> List[Tuple[int, float]]:
    by_year = {}
    for item in record.get("history") or []:
        financing = item.get("financingEvidence") or {}
        try:
            year = int(str(item.get("knownOn"))[:4])
            borrowing = float(item.get("netBorrowing"))
            shares = float(item.get("tradedShares"))
        except (TypeError, ValueError):
            continue
        if financing.get("ready") and shares > 0:
            by_year[year] = (str(item.get("knownOn")), borrowing / shares)
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
    investment = investment_sensitivity(symbol, current)
    financing = current.get("financingEvidence") or {
        "ready": False,
        "message": "Point-in-time cash, debt, leases, minority interests and net borrowing were not supplied.",
    }
    base = {
        "symbol": symbol, "method": "Five-year equity cash-flow DCF with a perpetual-growth terminal value",
        "source": "SEC as-filed cash flow and split-normalized market history",
        "beta": beta, "annualCashFlowPoints": len(annual), "forecastYears": FORECAST_YEARS,
        "investmentModel": investment,
        "financingEvidence": financing,
    }
    if not shares or shares <= 0 or not price or price <= 0:
        return {
            **base, "status": "unavailable", "ready": False, "currentPrice": price,
            "message": "Current share or price evidence is missing, so no per-share DCF can be built.",
        }
    if (current_cash is None or current_cash <= 0) and not investment.get("ready"):
        return {
            **base, "status": "unavailable", "ready": False, "currentPrice": round(price, 2),
            "message": "Reported free cash flow is not positive and no qualifying investment split can support an owner-cash sensitivity.",
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

    base_growth = _growth_anchor(annual)
    risk_free_used = max(RISK_FREE_FLOOR_PCT, risk_free_pct)
    base_discount = max(BASE_DISCOUNT_FLOOR_PCT, risk_free_used + beta["used"] * EQUITY_RISK_PREMIUM_PCT)
    scenario_terms = {
        "downside": ("Downside", max(-5.0, min(0.0, base_growth - 6.0)), base_discount + 2.0, 1.5),
        "base": ("Conservative base", base_growth, base_discount, 2.0),
        "strong": ("Strong execution", min(MAX_STRONG_GROWTH_PCT, base_growth + 3.0), max(9.5, base_discount - 1.0), 2.5),
    }

    def view(starts: Dict[str, float], label: str, points: int) -> Dict[str, Any]:
        scenarios = []
        for scenario_id in ("downside", "base", "strong"):
            start = starts.get(scenario_id)
            if start is None or start <= 0:
                continue
            name, growth, discount, terminal_growth = scenario_terms[scenario_id]
            result = discounted_value(start, growth, discount, terminal_growth)
            scenarios.append({
                "id": scenario_id, "name": name,
                "startFcfPerShare": round(start, 4), "growthPct": round(growth, 2),
                "discountPct": round(discount, 2), "terminalGrowthPct": terminal_growth,
                **result, "versusPricePct": round((result["value"] / price - 1) * 100, 1),
            })
        base_case = next((item for item in scenarios if item["id"] == "base"), None)
        ready = bool(base_case) and points >= MIN_ANNUAL_CASHFLOW_POINTS and base_case["terminalSharePct"] <= MAX_TERMINAL_SHARE_PCT
        values = [item["value"] for item in scenarios]
        return {
            "label": label, "ready": ready, "historyPoints": points,
            "scenarios": scenarios, "rangeLow": min(values) if values else None,
            "rangeHigh": max(values) if values else None,
            "message": (
                "The view passed history and terminal-value checks."
                if ready else "Positive starting cash, three annual observations and the terminal-value check are required."
            ),
        }

    reported_recent = [value for _, value in annual[-3:]]
    reported_start = None
    if current_cash is not None and current_cash > 0 and reported_recent:
        reported_start = min(current_cash / shares, statistics.median(reported_recent))
    reported_view = view(
        {key: reported_start * (0.8 if key == "downside" else 1.0) for key in scenario_terms}
        if reported_start else {},
        "Reported operating cash flow less all productive-asset spending",
        len(annual),
    )

    owner_starts: Dict[str, float] = {}
    if investment.get("ready"):
        current_by_id = {item["id"]: item for item in investment.get("scenarios") or []}
        # Current issuer evidence must never be projected backward into an old
        # cutoff.  Historical reported FCF only supplies the observation gate
        # and a conservative cap on today's normalized starting cash.
        history_cap = statistics.median(reported_recent) if reported_recent else None
        for scenario_id in ("downside", "base", "strong"):
            owner_cash = _number((current_by_id.get(scenario_id) or {}).get("ownerCash"))
            if owner_cash and owner_cash > 0 and history_cap:
                start = min(owner_cash / shares, history_cap)
                owner_starts[scenario_id] = start * (0.8 if scenario_id == "downside" else 1.0)
    owner_history_points = len(annual)
    owner_view = view(owner_starts, "Normalized owner cash with a bounded maintenance/growth sensitivity", owner_history_points)

    borrowing_history = _annual_net_borrowing_per_share(cashflow_record)
    normalized_net_borrowing = None
    fcfe_starts: Dict[str, float] = {}
    if financing.get("ready") and len(borrowing_history) >= MIN_ANNUAL_CASHFLOW_POINTS:
        # A positive borrowing run-rate cannot be assumed to recur forever
        # without a forecast leverage policy.  Historical repayments count;
        # historical debt issuance is shown but receives no valuation credit.
        normalized_net_borrowing = min(0.0, statistics.median(value for _, value in borrowing_history[-3:]))
        for scenario_id, start in owner_starts.items():
            adjusted = start + normalized_net_borrowing
            if adjusted > 0:
                fcfe_starts[scenario_id] = adjusted
    fcfe_view = view(
        fcfe_starts,
        "Balance-sheet-vetted FCFE: owner cash plus normalized net borrowing",
        len(borrowing_history),
    )
    fcfe_view.update({
        "ready": bool(fcfe_view.get("ready")) and bool(financing.get("ready")),
        "netBorrowingHistoryPoints": len(borrowing_history),
        "normalizedNetBorrowingPerShare": round(normalized_net_borrowing, 4)
        if normalized_net_borrowing is not None else None,
        "positiveBorrowingCreditCappedAtZero": True,
        "balanceSheetClaimsAppliedToFcfe": False,
        "methodSourceUrl": FCFE_METHOD_SOURCE,
        "bridgeSourceUrl": ENTERPRISE_BRIDGE_SOURCE,
        "message": (
            "Direct FCFE already reflects debt cash flows, so cash, debt, leases and minority claims are evidence checks and are not subtracted again."
            if fcfe_starts and financing.get("ready") else
            "Three dated net-borrowing observations and complete same-period financing claims are required."
        ),
    })
    selected = owner_view if owner_view["ready"] else reported_view
    ready = bool(selected["ready"])
    return {
        **base, "status": "verified" if ready else "limited", "ready": ready,
        "reportedReady": reported_view["ready"], "normalizedReady": owner_view["ready"],
        "equityReady": fcfe_view["ready"],
        "currentPrice": round(price, 2),
        "currentFcfPerShare": round(current_cash / shares, 4) if current_cash is not None else None,
        "baseGrowthPct": base_growth, "baseDiscountPct": round(base_discount, 2),
        "riskFreeUsedPct": round(risk_free_used, 3),
        "reportedView": reported_view, "ownerCashView": owner_view, "fcfeView": fcfe_view,
        "selectedView": "ownerCash" if owner_view["ready"] else "reported",
        "scenarios": selected["scenarios"],
        "rangeLow": selected["rangeLow"], "rangeHigh": selected["rangeHigh"],
        "message": (
            "A dated, bounded owner-cash view passed the evidence checks."
            if owner_view["ready"] else
            "The reported all-capex view passed; the maintenance/growth distinction remains evidence-limited."
            if reported_view["ready"] else
            "No cash-flow view passed every history, market and terminal-value check."
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
    reported_ready = sum(bool(record.get("reportedReady")) for record in companies.values())
    normalized_ready = sum(bool(record.get("normalizedReady")) for record in companies.values())
    investment_ready = sum(bool((record.get("investmentModel") or {}).get("ready")) for record in companies.values())
    equity_ready = sum(bool(record.get("equityReady")) for record in companies.values())
    return {
        "status": "complete" if ready == len(COMPANIES) else "incomplete",
        "complete": ready == len(COMPANIES), "companiesReady": ready,
        "reportedCompaniesReady": reported_ready,
        "normalizedCompaniesReady": normalized_ready,
        "investmentCompaniesReady": investment_ready,
        "investmentEvidenceComplete": investment_ready == len(COMPANIES),
        "equityCompaniesReady": equity_ready,
        "equityEvidenceComplete": equity_ready == len(COMPANIES),
        "companiesTotal": len(COMPANIES), "companies": companies,
        "method": "Reported all-capex DCF and bounded owner-cash sensitivity preserved; a separate direct-FCFE view adds normalized net borrowing only when same-period financing evidence is complete",
        "assumptions": {
            "riskFreeFloorPct": RISK_FREE_FLOOR_PCT,
            "equityRiskPremiumPct": EQUITY_RISK_PREMIUM_PCT,
            "baseDiscountFloorPct": BASE_DISCOUNT_FLOOR_PCT,
            "terminalGrowthRangePct": [1.5, 2.5],
            "baseGrowthCapPct": MAX_BASE_GROWTH_PCT,
            "strongGrowthCapPct": MAX_STRONG_GROWTH_PCT,
        },
        "riskFreeEvidence": risk_free_evidence,
        "warning": "Depreciation is only a cross-check. Direct FCFE is not reduced again by cash, debt, leases or minority claims; doing so would double count financing. Positive future borrowing receives no value credit.",
    }
