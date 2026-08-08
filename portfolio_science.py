"""Fail-closed scientific challenger for Kestrel's long-horizon portfolio.

This module does not declare a portfolio "optimal" from one noisy history.
It freezes the researched portfolio as Candidate 1, generates constrained
alternatives from conservative return estimates and a shrunk covariance
matrix, and then reports both the result and every reason it cannot yet be
promoted.  All calculations use data supplied to the function, which keeps the
research core deterministic and testable.
"""

from __future__ import annotations

import math
import random
import statistics
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from price_history import historical_prices
from fund_lookthrough import fund_lookthrough_snapshot
from point_in_time_valuation import point_in_time_valuation_snapshot
from conservative_dcf import build_dcf_snapshot, official_treasury_10y


MODEL_VERSION = "portfolio-science-v6"
DEFAULT_ITERATIONS = 20_000
RANDOM_SEED = 20260808
CACHE_SECONDS = 12 * 60 * 60

CANDIDATE_WEIGHTS: Dict[str, float] = {
    "VTI": 20, "AVUV": 8, "VEA": 7, "IEMG": 7, "AVDV": 5, "PAVE": 5,
    "TSM": 6, "GOOGL": 6, "AMZN": 5, "ASML": 5, "MELI": 5, "ETN": 4,
    "ISRG": 4, "CEG": 3, "IBIT": 8, "SGOV": 2,
}

GROUPS: Dict[str, str] = {
    "VTI": "foundation", "AVUV": "foundation", "VEA": "foundation",
    "IEMG": "foundation", "AVDV": "foundation", "PAVE": "foundation",
    "TSM": "companies", "GOOGL": "companies", "AMZN": "companies",
    "ASML": "companies", "MELI": "companies", "ETN": "companies",
    "ISRG": "companies", "CEG": "companies", "IBIT": "asymmetric",
    "SGOV": "reserve",
}

BOUNDS: Dict[str, Tuple[float, float]] = {
    "VTI": (15, 35), "AVUV": (2, 12), "VEA": (5, 20), "IEMG": (4, 15),
    "AVDV": (2, 10), "PAVE": (0, 8),
    "TSM": (0, 6), "GOOGL": (0, 6), "AMZN": (0, 6), "ASML": (0, 6),
    "MELI": (0, 6), "ETN": (0, 6), "ISRG": (0, 6), "CEG": (0, 6),
    "IBIT": (0, 8), "SGOV": (2, 12),
}

FOUNDATION = [symbol for symbol, group in GROUPS.items() if group == "foundation"]
COMPANIES = [symbol for symbol, group in GROUPS.items() if group == "companies"]
SYMBOLS = list(CANDIDATE_WEIGHTS)
BENCHMARK_SYMBOL = "VT"

_LOCK = threading.Lock()
_CACHE: Optional[Dict[str, Any]] = None


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _month_returns(history: Dict[str, Any]) -> Dict[str, float]:
    points: Dict[str, float] = {}
    for point in history.get("points") or []:
        if not isinstance(point, dict):
            continue
        close = _number(point.get("close"))
        date = str(point.get("date") or "")
        if close and close > 0 and len(date) >= 7:
            points[date[:7]] = close
    ordered = sorted(points.items())
    returns: Dict[str, float] = {}
    for index in range(1, len(ordered)):
        month, close = ordered[index]
        previous = ordered[index - 1][1]
        if previous > 0:
            returns[month] = close / previous - 1
    return returns


def _common_matrix(histories: Dict[str, Dict[str, Any]]) -> Tuple[List[str], Dict[str, List[float]]]:
    by_symbol = {symbol: _month_returns(histories.get(symbol) or {}) for symbol in SYMBOLS}
    benchmark_returns = _month_returns(histories.get(BENCHMARK_SYMBOL) or {})
    available = [set(values) for values in by_symbol.values() if values]
    if len(available) != len(SYMBOLS) or not benchmark_returns:
        return [], {symbol: [] for symbol in SYMBOLS}
    available.append(set(benchmark_returns))
    months = sorted(set.intersection(*available))
    return months, {symbol: [by_symbol[symbol][month] for month in months] for symbol in SYMBOLS}


def _covariance(matrix: Dict[str, List[float]], shrinkage: float = 0.5) -> Dict[str, Dict[str, float]]:
    means = {symbol: statistics.fmean(values) for symbol, values in matrix.items()}
    count = min((len(values) for values in matrix.values()), default=0)
    result = {symbol: {} for symbol in matrix}
    if count < 2:
        return result
    divisor = count - 1
    for left, left_values in matrix.items():
        for right, right_values in matrix.items():
            raw = sum(
                (left_values[index] - means[left]) * (right_values[index] - means[right])
                for index in range(count)
            ) / divisor
            # Shrink unstable cross-asset relationships toward zero while
            # retaining each asset's observed variance on the diagonal.
            result[left][right] = raw if left == right else raw * (1 - shrinkage)
    return result


def _robust_means(matrix: Dict[str, List[float]]) -> Dict[str, float]:
    sample = {symbol: statistics.fmean(values) * 12 for symbol, values in matrix.items()}
    broad = [sample[symbol] for symbol in ("VTI", "VEA", "IEMG") if symbol in sample]
    equilibrium = statistics.median(broad) if broad else 0.06
    means: Dict[str, float] = {}
    for symbol in SYMBOLS:
        if symbol == "SGOV":
            means[symbol] = sample.get(symbol, equilibrium)
        elif symbol == "IBIT":
            means[symbol] = equilibrium * 0.9 + sample.get(symbol, equilibrium) * 0.1
        else:
            # Ninety per cent of a company or fund's historical alpha is
            # discarded. This is deliberately hostile to return chasing.
            means[symbol] = equilibrium * 0.9 + sample.get(symbol, equilibrium) * 0.1
    return means


def _portfolio_returns(weights: Dict[str, float], matrix: Dict[str, List[float]]) -> List[float]:
    count = min((len(values) for values in matrix.values()), default=0)
    return [
        sum((weights.get(symbol, 0) / 100) * matrix[symbol][index] for symbol in SYMBOLS)
        for index in range(count)
    ]


def _metrics(weights: Dict[str, float], matrix: Dict[str, List[float]]) -> Dict[str, Optional[float]]:
    returns = _portfolio_returns(weights, matrix)
    if not returns:
        return {"annualReturn": None, "annualVolatility": None, "maxDrawdown": None,
                "worstTwoYear": None, "bestTwoYear": None, "monthlyCvar95": None}
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        wealth *= 1 + value
        peak = max(peak, wealth)
        max_drawdown = min(max_drawdown, wealth / peak - 1)
    annual_return = wealth ** (12 / len(returns)) - 1 if wealth > 0 else -1.0
    volatility = statistics.stdev(returns) * math.sqrt(12) if len(returns) > 1 else 0.0
    rolling = []
    for start in range(0, len(returns) - 23):
        outcome = math.prod(1 + value for value in returns[start:start + 24]) - 1
        rolling.append(outcome)
    tail_count = max(1, math.ceil(len(returns) * 0.05))
    cvar = statistics.fmean(sorted(returns)[:tail_count])
    return {
        "annualReturn": round(annual_return * 100, 2),
        "annualVolatility": round(volatility * 100, 2),
        "maxDrawdown": round(max_drawdown * 100, 2),
        "worstTwoYear": round(min(rolling) * 100, 2) if rolling else None,
        "bestTwoYear": round(max(rolling) * 100, 2) if rolling else None,
        "monthlyCvar95": round(cvar * 100, 2),
    }


def _variance(weights: Dict[str, float], covariance: Dict[str, Dict[str, float]]) -> float:
    return sum(
        weights.get(left, 0) / 100 * weights.get(right, 0) / 100 * covariance[left][right]
        for left in SYMBOLS for right in SYMBOLS
    )


def _utility(weights: Dict[str, float], means: Dict[str, float],
             covariance: Dict[str, Dict[str, float]]) -> float:
    expected = sum(weights.get(symbol, 0) / 100 * means[symbol] for symbol in SYMBOLS)
    # A low risk-aversion coefficient represents Luke's 8/10 appetite while
    # still penalising portfolios that manufacture return through concentration.
    return expected - 0.625 * max(0.0, _variance(weights, covariance))


def _allocate_group(symbols: List[str], total: float, rng: random.Random) -> Optional[Dict[str, float]]:
    minimum = sum(BOUNDS[symbol][0] for symbol in symbols)
    maximum = sum(BOUNDS[symbol][1] for symbol in symbols)
    if total < minimum or total > maximum:
        return None
    allocation = {symbol: BOUNDS[symbol][0] for symbol in symbols}
    remaining = total - minimum
    open_symbols = list(symbols)
    while remaining > 1e-9 and open_symbols:
        draws = {symbol: rng.gammavariate(1.6, 1.0) for symbol in open_symbols}
        draw_total = sum(draws.values()) or 1.0
        distributed = 0.0
        next_open = []
        for symbol in open_symbols:
            room = BOUNDS[symbol][1] - allocation[symbol]
            addition = min(room, remaining * draws[symbol] / draw_total)
            allocation[symbol] += addition
            distributed += addition
            if room - addition > 1e-9:
                next_open.append(symbol)
        if distributed <= 1e-12:
            break
        remaining -= distributed
        open_symbols = next_open
    if remaining > 1e-6:
        return None
    return allocation


def _random_portfolio(rng: random.Random) -> Optional[Dict[str, float]]:
    company_total = rng.uniform(20, 40)
    asymmetric_total = rng.uniform(0, 8)
    reserve_total = rng.uniform(2, 12)
    foundation_total = 100 - company_total - asymmetric_total - reserve_total
    if not 45 <= foundation_total <= 70:
        return None
    foundation = _allocate_group(FOUNDATION, foundation_total, rng)
    companies = _allocate_group(COMPANIES, company_total, rng)
    if foundation is None or companies is None:
        return None
    return {
        **foundation, **companies,
        "IBIT": asymmetric_total,
        "SGOV": reserve_total,
    }


def _effective_company_exposure(weights: Dict[str, float], lookthrough: Optional[Dict[str, Any]]) -> Dict[str, float]:
    overlaps = (lookthrough or {}).get("fundOverlaps") or {}
    return {
        symbol: weights.get(symbol, 0) + sum(
            weights.get(fund, 0) * float(fund_overlaps.get(symbol, 0)) / 100
            for fund, fund_overlaps in overlaps.items()
        )
        for symbol in COMPANIES
    }


def _search(matrix: Dict[str, List[float]], iterations: int,
            lookthrough: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, float], int]:
    covariance = _covariance(matrix)
    means = _robust_means(matrix)
    rng = random.Random(RANDOM_SEED)
    best = dict(CANDIDATE_WEIGHTS)
    best_score = _utility(best, means, covariance)
    tested = 1
    attempts = 0
    while tested < iterations and attempts < iterations * 4:
        attempts += 1
        candidate = _random_portfolio(rng)
        if candidate is None:
            continue
        if lookthrough and max(_effective_company_exposure(candidate, lookthrough).values(), default=0) > 8:
            continue
        tested += 1
        score = _utility(candidate, means, covariance)
        if score > best_score:
            best, best_score = candidate, score
    return {symbol: round(best[symbol], 2) for symbol in SYMBOLS}, tested


def _bootstrap(weights: Dict[str, float], matrix: Dict[str, List[float]], samples: int = 1_000) -> Dict[str, Any]:
    returns = _portfolio_returns(weights, matrix)
    if len(returns) < 24:
        return {"samples": 0, "status": "insufficient_history"}
    rng = random.Random(RANDOM_SEED + int(sum(weights.values()) * 10))
    outcomes = []
    block = 3
    for _ in range(samples):
        path: List[float] = []
        while len(path) < 24:
            start = rng.randrange(len(returns))
            path.extend(returns[(start + offset) % len(returns)] for offset in range(block))
        outcomes.append(math.prod(1 + value for value in path[:24]) - 1)
    outcomes.sort()
    percentile = lambda fraction: outcomes[min(len(outcomes) - 1, int((len(outcomes) - 1) * fraction))]
    return {
        "samples": samples,
        "status": "research_only",
        "medianTwoYear": round(percentile(0.5) * 100, 2),
        "p10TwoYear": round(percentile(0.1) * 100, 2),
        "p05TwoYear": round(percentile(0.05) * 100, 2),
        "lossProbability": round(sum(value < 0 for value in outcomes) / samples * 100, 1),
        "method": "Three-month block bootstrap of the common adjusted monthly history",
    }


def _benchmark_metrics(histories: Dict[str, Dict[str, Any]], months: List[str]) -> Dict[str, Any]:
    returns = _month_returns(histories.get(BENCHMARK_SYMBOL) or {})
    ordered = [returns[month] for month in months if month in returns]
    matrix = {symbol: ordered for symbol in SYMBOLS}
    weights = {symbol: 0.0 for symbol in SYMBOLS}
    weights["VTI"] = 100.0
    metrics = _metrics(weights, matrix)
    metrics["label"] = "VT global equity benchmark"
    metrics["symbol"] = BENCHMARK_SYMBOL
    return metrics


def analyze_portfolio_science(histories: Dict[str, Dict[str, Any]],
                              iterations: int = DEFAULT_ITERATIONS,
                              lookthrough: Optional[Dict[str, Any]] = None,
                              fundamentals: Optional[Dict[str, Any]] = None,
                              dcf_risk_free: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    months, matrix = _common_matrix(histories)
    coverage = []
    for symbol in [*SYMBOLS, BENCHMARK_SYMBOL]:
        history = histories.get(symbol) or {}
        returns = _month_returns(history)
        coverage.append({
            "symbol": symbol,
            "months": len(returns),
            "from": min(returns) if returns else None,
            "through": max(returns) if returns else None,
            "source": history.get("source"),
            "method": history.get("method"),
            "ready": len(returns) >= 36,
        })

    enough_matrix = len(months) >= 24 and all(matrix.values())
    challenger = dict(CANDIDATE_WEIGHTS)
    tested = 0
    if enough_matrix:
        challenger, tested = _search(matrix, max(100, iterations), lookthrough)

    candidate_metrics = _metrics(CANDIDATE_WEIGHTS, matrix) if enough_matrix else _metrics({}, {})
    challenger_metrics = _metrics(challenger, matrix) if enough_matrix else _metrics({}, {})
    turnover = sum(abs(challenger[symbol] - CANDIDATE_WEIGHTS[symbol]) for symbol in SYMBOLS) / 2
    estimated_cost = turnover / 100 * 0.001

    effective_exposures = _effective_company_exposure(CANDIDATE_WEIGHTS, lookthrough)
    lookthrough_complete = bool((lookthrough or {}).get("complete"))
    concentration_ready = bool(effective_exposures) and max(effective_exposures.values(), default=100) <= 8
    fundamental_price_total = (fundamentals or {}).get("priceChecksTotal", 8)
    fundamental_price_ready = (fundamentals or {}).get("priceChecksReady")
    if fundamental_price_ready is None:
        fundamental_price_ready = fundamental_price_total if (fundamentals or {}).get("priceCrossCheckReady") else 0
    fundamental_cashflow = (fundamentals or {}).get("cashFlow") or {}
    dcf = build_dcf_snapshot(fundamental_cashflow, histories, risk_free=dcf_risk_free)
    gates = [
        {"id": "price_coverage", "name": "At least three years for every holding",
         "passed": all(item["ready"] for item in coverage if item["symbol"] != BENCHMARK_SYMBOL)},
        {"id": "common_history", "name": "At least ten years of common history",
         "passed": len(months) >= 120},
        {"id": "adjusted_returns", "name": "Corporate-action-adjusted return histories",
         "passed": all("adjusted" in str(item.get("method") or "").lower() for item in coverage)},
        {"id": "lookthrough", "name": "Official ETF holdings counted through to underlying companies",
         "passed": lookthrough_complete, "detail": (
             f'{(lookthrough or {}).get("fundsReady", 0)} of {(lookthrough or {}).get("fundsTotal", 6)} equity ETFs verified'
         )},
        {"id": "effective_concentration", "name": "No effective company exposure above 8%",
         "passed": lookthrough_complete and concentration_ready},
        {"id": "point_in_time", "name": "Point-in-time fundamentals and valuations",
         "passed": bool((fundamentals or {}).get("complete")), "detail": (
             f'{(fundamentals or {}).get("companiesReady", 0)} of {(fundamentals or {}).get("companiesTotal", 8)} as-filed histories; '
             + f'{fundamental_cashflow.get("companiesReady", 0)} of {fundamental_cashflow.get("companiesTotal", 8)} cash-flow histories; '
             + f'{fundamental_price_ready} of {fundamental_price_total} Nasdaq prices'
         )},
        {"id": "dcf", "name": "Conservative cash-flow valuation range",
         "passed": bool(dcf.get("complete")), "detail": (
             f'{dcf.get("companiesReady", 0)} of {dcf.get("companiesTotal", 8)} companies passed at least one DCF view; '
             + f'{dcf.get("reportedCompaniesReady", 0)} reported and {dcf.get("normalizedCompaniesReady", 0)} normalized'
         )},
        {"id": "investment_split", "name": "Maintenance versus growth investment evidence",
         "passed": bool(dcf.get("investmentEvidenceComplete")), "detail": (
             f'{dcf.get("investmentCompaniesReady", 0)} of {dcf.get("companiesTotal", 8)} companies have dated issuer evidence and a depreciation cross-check'
         )},
        {"id": "walk_forward", "name": "Challenger wins unseen walk-forward periods",
         "passed": False},
        {"id": "costs", "name": "Turnover and estimated trading cost included",
         "passed": True},
    ]
    passed = sum(bool(gate["passed"]) for gate in gates)
    promotion_ready = passed == len(gates)

    changes = sorted([
        {"symbol": symbol, "candidate": CANDIDATE_WEIGHTS[symbol], "challenger": challenger[symbol],
         "change": round(challenger[symbol] - CANDIDATE_WEIGHTS[symbol], 2)}
        for symbol in SYMBOLS
    ], key=lambda item: abs(item["change"]), reverse=True)

    return {
        "modelVersion": MODEL_VERSION,
        "status": "promotion_ready" if promotion_ready else "research_only",
        "title": "Scientific challenger" if promotion_ready else "Candidate 1 remains frozen",
        "message": (
            "Every evidence and validation gate passed."
            if promotion_ready else
            "The engine can challenge the weights, but missing evidence prevents it from replacing Candidate 1."
        ),
        "objective": "Maximise robust expected two-year wealth within an 8/10 risk budget",
        "candidate": {"name": "Candidate 1", "weights": CANDIDATE_WEIGHTS,
                      "metrics": candidate_metrics, "bootstrap": _bootstrap(CANDIDATE_WEIGHTS, matrix)},
        "challenger": {"name": "Research challenger", "weights": challenger,
                       "metrics": challenger_metrics, "bootstrap": _bootstrap(challenger, matrix),
                       "changes": changes, "promotionReady": promotion_ready},
        "benchmark": _benchmark_metrics(histories, months),
        "research": {
            "portfoliosTested": tested,
            "commonMonths": len(months),
            "commonFrom": months[0] if months else None,
            "commonThrough": months[-1] if months else None,
            "covariance": "Sample covariance with 50% cross-asset shrinkage",
            "returnForecast": "90% common market prior; 10% historical asset return",
            "riskPreference": "Low penalty consistent with an 8/10 appetite; hard concentration ceilings remain",
            "turnoverPercent": round(turnover, 2),
            "estimatedTradingCostPercent": round(estimated_cost * 100, 3),
            "warning": "Historical and bootstrap results describe the supplied sample; they are not forecasts.",
        },
        "gates": {"passed": passed, "total": len(gates), "items": gates},
        "lookthrough": lookthrough or {
            "status": "not_supplied", "complete": False, "fundsReady": 0,
            "fundsTotal": 6, "sources": [], "exposures": [],
        },
        "fundamentals": fundamentals or {
            "status": "not_supplied", "complete": False, "companiesReady": 0,
            "companiesTotal": 8, "companies": {},
            "cashFlow": {"status": "not_supplied", "complete": False,
                         "companiesReady": 0, "companiesTotal": 8, "companies": {}},
        },
        "dcf": dcf,
        "coverage": coverage,
        "constraints": {
            "foundation": "45–70%", "companies": "20–40%", "directCompany": "0–6%",
            "effectiveCompany": "0–8% including ETF overlap",
            "bitcoin": "0–8%", "reserve": "2–12%", "leverage": "0%",
        },
        "generatedAt": int(time.time()),
    }


def _fetch_history(symbol: str) -> Dict[str, Any]:
    return historical_prices(symbol, "all", request_institutional=False)


def portfolio_science_snapshot(force: bool = False,
                               provider: Optional[Callable[[str], Dict[str, Any]]] = None,
                               iterations: int = DEFAULT_ITERATIONS) -> Dict[str, Any]:
    global _CACHE
    now = int(time.time())
    with _LOCK:
        if provider is None and not force and _CACHE and now - int(_CACHE.get("generatedAt") or 0) < CACHE_SECONDS:
            return dict(_CACHE)
        fetch = provider or _fetch_history
        histories: Dict[str, Dict[str, Any]] = {}
        errors: Dict[str, str] = {}
        for symbol in [*SYMBOLS, BENCHMARK_SYMBOL]:
            try:
                histories[symbol] = fetch(symbol)
            except (RuntimeError, ValueError, TypeError, KeyError) as error:
                histories[symbol] = {}
                errors[symbol] = str(error)
        lookthrough = fund_lookthrough_snapshot(CANDIDATE_WEIGHTS) if provider is None else None
        fundamentals = point_in_time_valuation_snapshot() if provider is None else None
        dcf_risk_free = official_treasury_10y() if provider is None else None
        payload = analyze_portfolio_science(
            histories, iterations=iterations, lookthrough=lookthrough, fundamentals=fundamentals,
            dcf_risk_free=dcf_risk_free,
        )
        payload["errors"] = errors
        if errors:
            payload["status"] = "data_incomplete"
            payload["title"] = "Candidate 1 remains frozen"
            payload["message"] = "Some histories were unavailable, so no challenger can be promoted."
        if provider is None:
            _CACHE = dict(payload)
        return payload
