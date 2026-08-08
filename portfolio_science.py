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
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from price_history import historical_prices
from fund_lookthrough import fund_lookthrough_snapshot
from point_in_time_valuation import point_in_time_valuation_snapshot
from conservative_dcf import build_dcf_snapshot, official_treasury_10y
from universe_ledger import PROTOCOL_VERSION as UNIVERSE_PROTOCOL_VERSION


MODEL_VERSION = "portfolio-science-v7"
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
WALK_FORWARD_TRAIN_MONTHS = 36
WALK_FORWARD_TEST_MONTHS = 12
WALK_FORWARD_MIN_WINDOWS = 5
WALK_FORWARD_BOOTSTRAPS = 2_000

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


def _month_end(value: str) -> Optional[date]:
    try:
        year, month = (int(part) for part in value[:7].split("-"))
        if month == 12:
            return date(year + 1, 1, 1) - timedelta(days=1)
        return date(year, month + 1, 1) - timedelta(days=1)
    except (TypeError, ValueError):
        return None


def _protocol_failures(histories: Dict[str, Dict[str, Any]],
                       protocol: Optional[Dict[str, Any]]) -> List[str]:
    """Reject any historical test whose information set cannot be reconstructed.

    A current-ticker download is not a point-in-time research dataset.  Historical
    folds count only with a pre-declared universe, survivorship coverage and an
    availability timestamp on every price observation.  This deliberately makes
    the normal live snapshot fail closed until Kestrel has frozen prospective data.
    """
    if not protocol:
        return ["No pre-registered point-in-time test protocol was supplied"]
    failures = []
    if protocol.get("protocolVersion") != UNIVERSE_PROTOCOL_VERSION:
        failures.append("The protocol was not produced by the bitemporal universe ledger")
    if protocol.get("ledgerVerified") is not True:
        failures.append("The immutable universe snapshot did not pass its hash verification")
    snapshot_ids = protocol.get("snapshotIds") or []
    manifest_hashes = protocol.get("manifestHashes") or []
    if (not snapshot_ids or len(snapshot_ids) != len(manifest_hashes)
            or any(len(str(value)) != 64 for value in [*snapshot_ids, *manifest_hashes])):
        failures.append("The protocol lacks immutable snapshot and manifest hashes")
    expected_universe = sorted([*SYMBOLS, BENCHMARK_SYMBOL])
    if protocol.get("modelVersion") != MODEL_VERSION:
        failures.append("The protocol is not bound to this exact model version")
    if protocol.get("benchmark") != BENCHMARK_SYMBOL:
        failures.append("The benchmark is not the pre-declared VT global equity benchmark")
    if sorted(protocol.get("universe") or []) != expected_universe:
        failures.append("The tested universe does not match the pre-declared fixed universe")
    if protocol.get("survivorshipFree") is not True:
        failures.append("Inactive and delisted instruments are not explicitly retained")
    universe_records = protocol.get("universeRecords") or {}
    for symbol in expected_universe:
        record = universe_records.get(symbol) or {}
        if (not record.get("securityId") or record.get("membershipVerified") is not True
                or record.get("includedAtFreeze") is not True or record.get("outcomeComplete") is not True):
            failures.append(f"{symbol} lacks a frozen membership record or complete outcome path")
    if protocol.get("selectionPolicyFrozen") is not True or not protocol.get("frozenAt"):
        failures.append("The selection policy was not frozen before testing")
    if protocol.get("pointInTimePrices") is not True:
        failures.append("Price inputs are not declared point-in-time")
    if protocol.get("adjustmentPolicy") != "point_in_time_total_return":
        failures.append("Corporate-action adjustments are not point-in-time versioned")
    if not isinstance(protocol.get("lookthroughSnapshots"), list) or not protocol.get("lookthroughSnapshots"):
        failures.append("No point-in-time ETF look-through snapshots were supplied")
    cost_bps = _number(protocol.get("oneWayCostBps"))
    if cost_bps is None or cost_bps < 5:
        failures.append("The declared one-way trading cost is missing or below 5 bps")
    for symbol in expected_universe:
        points = (histories.get(symbol) or {}).get("points") or []
        if any(not point.get("availableAt") for point in points if isinstance(point, dict)):
            failures.append(f"{symbol} has observations without availability timestamps")
            continue
        for point in points:
            try:
                if date.fromisoformat(str(point["availableAt"])) < date.fromisoformat(str(point["date"])):
                    failures.append(f"{symbol} has an observation marked available before it existed")
                    break
            except (KeyError, TypeError, ValueError):
                failures.append(f"{symbol} has invalid point-in-time timestamps")
                break
    return failures


def _lookthrough_at(protocol: Dict[str, Any], cutoff: date) -> Optional[Dict[str, Any]]:
    eligible = []
    for snapshot in protocol.get("lookthroughSnapshots") or []:
        try:
            as_of = date.fromisoformat(str(snapshot.get("asOf")))
            available = date.fromisoformat(str(snapshot.get("availableAt")))
        except (TypeError, ValueError):
            continue
        if as_of <= available <= cutoff and snapshot.get("complete") is True:
            eligible.append((available, snapshot))
    if not eligible:
        return None
    available, snapshot = max(eligible, key=lambda item: item[0])
    if (cutoff - available).days > 120:
        return None
    return snapshot


def _point_in_time_returns(history: Dict[str, Any], cutoff: str) -> Dict[str, float]:
    """Return only observations that were available by the fold decision date."""
    cutoff_date = date.fromisoformat(cutoff)
    points: Dict[str, float] = {}
    for point in history.get("points") or []:
        try:
            observed = date.fromisoformat(str(point.get("date")))
            available = date.fromisoformat(str(point.get("availableAt")))
            close = float(point.get("close"))
        except (TypeError, ValueError):
            continue
        if close > 0 and observed <= cutoff_date and available <= cutoff_date:
            points[observed.isoformat()[:7]] = close
    ordered = sorted(points.items())
    return {
        month: close / ordered[index - 1][1] - 1
        for index, (month, close) in enumerate(ordered)
        if index and ordered[index - 1][1] > 0
    }


def _path_metrics(returns: List[float]) -> Dict[str, Optional[float]]:
    if not returns:
        return {"annualReturn": None, "maxDrawdown": None}
    wealth = peak = 1.0
    drawdown = 0.0
    for value in returns:
        wealth *= 1 + value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1)
    annual = wealth ** (12 / len(returns)) - 1 if wealth > 0 else -1.0
    return {"annualReturn": round(annual * 100, 2), "maxDrawdown": round(drawdown * 100, 2)}


def _information_ratio(left: List[float], right: List[float]) -> Optional[float]:
    differences = [a - b for a, b in zip(left, right)]
    if len(differences) < 2:
        return None
    tracking_error = statistics.stdev(differences)
    if tracking_error <= 1e-12:
        return None
    return round(statistics.fmean(differences) / tracking_error * math.sqrt(12), 2)


def _window_bootstrap(windows: List[Dict[str, Any]], comparison: str) -> Dict[str, Any]:
    if len(windows) < WALK_FORWARD_MIN_WINDOWS:
        return {"samples": 0, "low": None, "high": None, "method": "Independent-window bootstrap"}
    rng = random.Random(RANDOM_SEED + (1 if comparison == "candidate" else 2))
    outcomes = []
    key = f"{comparison}NetReturn"
    for _ in range(WALK_FORWARD_BOOTSTRAPS):
        sample = [windows[rng.randrange(len(windows))] for _ in windows]
        outcomes.append(statistics.fmean(item["challengerNetReturn"] - item[key] for item in sample))
    outcomes.sort()
    return {
        "samples": WALK_FORWARD_BOOTSTRAPS,
        "low": round(outcomes[int(0.025 * (len(outcomes) - 1))], 2),
        "high": round(outcomes[int(0.975 * (len(outcomes) - 1))], 2),
        "method": "95% interval from resampling whole, non-overlapping test windows",
    }


def walk_forward_evaluation(histories: Dict[str, Dict[str, Any]],
                            protocol: Optional[Dict[str, Any]],
                            iterations: int = DEFAULT_ITERATIONS) -> Dict[str, Any]:
    """Evaluate newly fitted challengers on sealed, non-overlapping future years."""
    failures = _protocol_failures(histories, protocol)
    months, full_matrix = _common_matrix(histories)
    base = {
        "status": "blocked", "eligible": False, "windows": [], "windowCount": 0,
        "minimumWindows": WALK_FORWARD_MIN_WINDOWS, "trainingMonths": WALK_FORWARD_TRAIN_MONTHS,
        "testMonths": WALK_FORWARD_TEST_MONTHS, "benchmark": BENCHMARK_SYMBOL,
        "failures": failures, "candidateWins": 0, "benchmarkWins": 0,
        "uncertainty": {"versusCandidate": _window_bootstrap([], "candidate"),
                        "versusBenchmark": _window_bootstrap([], "benchmark")},
    }
    if failures or len(months) < WALK_FORWARD_TRAIN_MONTHS + WALK_FORWARD_TEST_MONTHS:
        if not failures:
            base["failures"] = ["Not enough common history for one sealed test window"]
        return base

    try:
        frozen_at = date.fromisoformat(str(protocol["frozenAt"]))
    except (TypeError, ValueError):
        base["failures"] = ["The protocol freeze date is invalid"]
        return base
    first_test_index = next((
        index for index in range(WALK_FORWARD_TRAIN_MONTHS, len(months))
        if date.fromisoformat(f"{months[index]}-01") > frozen_at
    ), None)
    if first_test_index is None:
        base["failures"] = ["No outcome month exists after the protocol was frozen"]
        return base

    cost_rate = float(protocol["oneWayCostBps"]) / 10_000
    windows: List[Dict[str, Any]] = []
    challenger_path: List[float] = []
    candidate_path: List[float] = []
    benchmark_path: List[float] = []
    fold_failures: List[str] = []
    for test_start in range(first_test_index,
                            len(months) - WALK_FORWARD_TEST_MONTHS + 1,
                            WALK_FORWARD_TEST_MONTHS):
        train_months = months[:test_start]
        test_months = months[test_start:test_start + WALK_FORWARD_TEST_MONTHS]
        cutoff_month = train_months[-1]
        cutoff = _month_end(cutoff_month)
        if cutoff is None:
            continue
        cutoff_iso = cutoff.isoformat()
        fold_lookthrough = _lookthrough_at(protocol, cutoff)
        if fold_lookthrough is None:
            fold_failures.append(f"No complete ETF look-through was available at the {cutoff_month} cutoff")
            continue
        available = {
            symbol: _point_in_time_returns(histories[symbol], cutoff_iso)
            for symbol in [*SYMBOLS, BENCHMARK_SYMBOL]
        }
        if any(any(month not in available[symbol] for month in train_months)
               for symbol in [*SYMBOLS, BENCHMARK_SYMBOL]):
            continue
        train_matrix = {symbol: [available[symbol][month] for month in train_months] for symbol in SYMBOLS}
        challenger, _ = _search(train_matrix, max(100, iterations), fold_lookthrough)
        test_matrix = {symbol: [full_matrix[symbol][months.index(month)] for month in test_months]
                       for symbol in SYMBOLS}
        challenger_returns = _portfolio_returns(challenger, test_matrix)
        candidate_returns = _portfolio_returns(CANDIDATE_WEIGHTS, test_matrix)
        benchmark_monthly = _month_returns(histories[BENCHMARK_SYMBOL])
        benchmark_returns = [benchmark_monthly[month] for month in test_months]
        turnover = sum(abs(challenger[symbol] - CANDIDATE_WEIGHTS[symbol]) for symbol in SYMBOLS) / 200
        challenger_returns[0] = (1 + challenger_returns[0]) * (1 - turnover * cost_rate) - 1
        benchmark_returns[0] = (1 + benchmark_returns[0]) * (1 - cost_rate) - 1
        compound = lambda values: (math.prod(1 + value for value in values) - 1) * 100
        challenger_net = compound(challenger_returns)
        candidate_net = compound(candidate_returns)
        benchmark_net = compound(benchmark_returns)
        windows.append({
            "trainedThrough": cutoff_month, "from": test_months[0], "through": test_months[-1],
            "challengerNetReturn": round(challenger_net, 2),
            "candidateNetReturn": round(candidate_net, 2),
            "benchmarkNetReturn": round(benchmark_net, 2),
            "versusCandidate": round(challenger_net - candidate_net, 2),
            "versusBenchmark": round(challenger_net - benchmark_net, 2),
            "turnoverPercent": round(turnover * 100, 2),
            "weights": challenger,
        })
        challenger_path.extend(challenger_returns)
        candidate_path.extend(candidate_returns)
        benchmark_path.extend(benchmark_returns)

    base["windows"] = windows
    base["windowCount"] = len(windows)
    base["candidateWins"] = sum(item["versusCandidate"] > 0 for item in windows)
    base["benchmarkWins"] = sum(item["versusBenchmark"] > 0 for item in windows)
    base["uncertainty"] = {
        "versusCandidate": _window_bootstrap(windows, "candidate"),
        "versusBenchmark": _window_bootstrap(windows, "benchmark"),
    }
    base["metrics"] = {
        "challenger": {**_path_metrics(challenger_path),
                       "informationRatioVsBenchmark": _information_ratio(challenger_path, benchmark_path),
                       "informationRatioVsCandidate": _information_ratio(challenger_path, candidate_path)},
        "candidate": _path_metrics(candidate_path),
        "benchmark": _path_metrics(benchmark_path),
    }
    candidate_interval = base["uncertainty"]["versusCandidate"]
    benchmark_interval = base["uncertainty"]["versusBenchmark"]
    enough = len(windows) >= WALK_FORWARD_MIN_WINDOWS
    required_wins = math.ceil(len(windows) * 0.8) if enough else WALK_FORWARD_MIN_WINDOWS
    evidence_strong = bool(
        enough
        and not fold_failures
        and base["candidateWins"] >= required_wins
        and base["benchmarkWins"] >= required_wins
        and candidate_interval["low"] is not None and candidate_interval["low"] > 0
        and benchmark_interval["low"] is not None and benchmark_interval["low"] > 0
        and (base["metrics"]["challenger"]["informationRatioVsBenchmark"] or 0) > 0
    )
    base["eligible"] = evidence_strong
    base["status"] = "passed" if evidence_strong else "blocked" if fold_failures else "insufficient_evidence"
    if fold_failures:
        base["failures"] = fold_failures
    elif not enough:
        base["failures"] = [f"Only {len(windows)} of {WALK_FORWARD_MIN_WINDOWS} independent windows are available"]
    elif not evidence_strong:
        base["failures"] = ["Net outperformance is not consistent and its 95% intervals do not both exclude zero"]
    return base


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
                              dcf_risk_free: Optional[Dict[str, Any]] = None,
                              walk_forward_protocol: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    walk_forward = walk_forward_evaluation(
        histories, walk_forward_protocol, iterations=min(iterations, 2_000)
    )
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
        {"id": "equity_valuation", "name": "Balance-sheet-vetted equity valuation",
         "passed": bool(dcf.get("equityEvidenceComplete")), "detail": (
             f'{dcf.get("equityCompaniesReady", 0)} of {dcf.get("companiesTotal", 8)} companies have complete cash, debt, lease, minority-interest and net-borrowing evidence'
         )},
        {"id": "walk_forward", "name": "Challenger wins unseen walk-forward periods",
         "passed": bool(walk_forward.get("eligible")), "detail": (
             f'{walk_forward.get("windowCount", 0)} of {walk_forward.get("minimumWindows", WALK_FORWARD_MIN_WINDOWS)} '
             + f'independent windows; {walk_forward.get("candidateWins", 0)} wins versus Candidate 1; '
             + f'{walk_forward.get("benchmarkWins", 0)} wins versus VT'
         )},
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
        "walkForward": walk_forward,
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
                               iterations: int = DEFAULT_ITERATIONS,
                               walk_forward_protocol: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    global _CACHE
    now = int(time.time())
    with _LOCK:
        if (provider is None and walk_forward_protocol is None and not force and _CACHE
                and now - int(_CACHE.get("generatedAt") or 0) < CACHE_SECONDS):
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
            dcf_risk_free=dcf_risk_free, walk_forward_protocol=walk_forward_protocol,
        )
        payload["errors"] = errors
        if errors:
            payload["status"] = "data_incomplete"
            payload["title"] = "Candidate 1 remains frozen"
            payload["message"] = "Some histories were unavailable, so no challenger can be promoted."
        if provider is None and walk_forward_protocol is None:
            _CACHE = dict(payload)
        return payload
