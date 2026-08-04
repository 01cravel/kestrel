"""Versioned Phase 1 contract for Kestrel's investable Swing Radar.

This module deliberately contains policy and deterministic labelling only. It
does not download market history, fit a model or produce investment advice.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


POLICY_VERSION = "2026.08.02.1"

INVESTABLE_EXCHANGES = {"XNYS", "XNAS", "ARCX", "BATS"}
INVESTABLE_SECURITY_TYPES = {"common_stock", "adr"}
MIN_PRICE_USD = 2.0
MIN_MARKET_CAP_USD = 300_000_000.0
MIN_MEDIAN_DOLLAR_VOLUME_20D_USD = 5_000_000.0
MIN_PRIOR_SESSIONS = 126

PRIMARY_HORIZON_SESSIONS = 1
SECONDARY_HORIZON_SESSIONS = 5
PRIMARY_SWING_THRESHOLD = 0.10
SECONDARY_SWING_THRESHOLD = 0.15

EARLY_WATCH_MIN_PROBABILITY = 0.20
RESEARCH_ALERT_MIN_PROBABILITY = 0.35
DIRECTION_MIN_PROBABILITY = 0.65
MAX_DAILY_ALERTS = 5

PROMOTION_MIN_SESSIONS = 60
PROMOTION_MIN_PREDICTIONS = 200
PROMOTION_MIN_WATCHES = 40
PROMOTION_MIN_REALIZED_SWINGS = 15
PROMOTION_MIN_BRIER_SKILL = 0.10
PROMOTION_MAX_CALIBRATION_ERROR = 0.05
PROMOTION_MIN_DIRECTIONAL_ACCURACY = 0.60


def _finite_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def assess_investability(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Return an auditable point-in-time eligibility decision.

    Missing inputs produce ``unknown`` rather than silently excluding or
    including a security. Phase 2 is expected to store the returned reasons.
    """
    required = {
        "exchange_mic",
        "security_type",
        "active",
        "identity_clean",
        "corporate_actions_clean",
        "currency",
        "close",
        "market_cap",
        "median_dollar_volume_20d",
        "prior_sessions",
    }
    missing = sorted(field for field in required if row.get(field) is None)
    if missing:
        return {
            "eligible": None,
            "status": "unknown",
            "reasons": [f"Missing {field}" for field in missing],
            "policyVersion": POLICY_VERSION,
        }

    close = _finite_number(row.get("close"))
    market_cap = _finite_number(row.get("market_cap"))
    dollar_volume = _finite_number(row.get("median_dollar_volume_20d"))
    prior_sessions = _finite_number(row.get("prior_sessions"))
    invalid_numbers = [
        name
        for name, value in (
            ("close", close),
            ("market_cap", market_cap),
            ("median_dollar_volume_20d", dollar_volume),
            ("prior_sessions", prior_sessions),
        )
        if value is None
    ]
    if invalid_numbers:
        return {
            "eligible": None,
            "status": "unknown",
            "reasons": [f"Invalid {field}" for field in invalid_numbers],
            "policyVersion": POLICY_VERSION,
        }

    failures = []
    if str(row.get("exchange_mic", "")).upper() not in INVESTABLE_EXCHANGES:
        failures.append("Listing venue is outside the supported US exchanges")
    if str(row.get("security_type", "")).lower() not in INVESTABLE_SECURITY_TYPES:
        failures.append("Security is not a common stock or ADR")
    if row.get("active") is not True:
        failures.append("Security was not active at the cutoff")
    if row.get("identity_clean") is not True:
        failures.append("Security identity is unresolved")
    if row.get("corporate_actions_clean") is not True:
        failures.append("Corporate-action history is unresolved")
    if str(row.get("currency", "")).upper() != "USD":
        failures.append("Trading currency is not USD")
    if close is not None and close < MIN_PRICE_USD:
        failures.append(f"Close is below ${MIN_PRICE_USD:.0f}")
    if market_cap is not None and market_cap < MIN_MARKET_CAP_USD:
        failures.append("Market value is below $300 million")
    if dollar_volume is not None and dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME_20D_USD:
        failures.append("20-session median dollar volume is below $5 million")
    if prior_sessions is not None and prior_sessions < MIN_PRIOR_SESSIONS:
        failures.append("Fewer than 126 prior trading sessions are available")

    return {
        "eligible": not failures,
        "status": "eligible" if not failures else "ineligible",
        "reasons": failures,
        "policyVersion": POLICY_VERSION,
    }


def label_forward_return(
    stock_start: Any,
    stock_end: Any,
    benchmark_start: Any,
    benchmark_end: Any,
    *,
    horizon_sessions: int = PRIMARY_HORIZON_SESSIONS,
    data_clean: bool = True,
) -> Dict[str, Any]:
    """Create a benchmark-relative swing label from adjusted closes."""
    values = tuple(
        _finite_number(value)
        for value in (stock_start, stock_end, benchmark_start, benchmark_end)
    )
    threshold = {
        PRIMARY_HORIZON_SESSIONS: PRIMARY_SWING_THRESHOLD,
        SECONDARY_HORIZON_SESSIONS: SECONDARY_SWING_THRESHOLD,
    }.get(horizon_sessions)
    if threshold is None:
        raise ValueError("Only the versioned 1- and 5-session horizons are supported")
    if not data_clean or any(value is None or value <= 0 for value in values):
        return {
            "labelStatus": "quarantined",
            "reason": "Adjusted closes or corporate-action checks are incomplete",
            "policyVersion": POLICY_VERSION,
        }

    stock_start_n, stock_end_n, benchmark_start_n, benchmark_end_n = values
    stock_return = stock_end_n / stock_start_n - 1
    benchmark_return = benchmark_end_n / benchmark_start_n - 1
    excess_return = stock_return - benchmark_return
    is_swing = abs(excess_return) >= threshold
    return {
        "labelStatus": "ready",
        "horizonSessions": horizon_sessions,
        "threshold": threshold,
        "stockReturn": stock_return,
        "benchmarkReturn": benchmark_return,
        "excessReturn": excess_return,
        "isSwing": is_swing,
        "direction": "up" if is_swing and excess_return > 0 else "down" if is_swing else "none",
        "policyVersion": POLICY_VERSION,
    }


def feature_is_available(feature: Mapping[str, Any], cutoff: str) -> bool:
    """Enforce the two timestamps required to prevent point-in-time leakage.

    ISO-8601 timestamps are lexically comparable only after normalisation. Phase
    2 must supply UTC ``YYYY-MM-DDTHH:MM:SSZ`` strings.
    """
    published_at = feature.get("published_at")
    available_at = feature.get("available_at")
    return bool(
        isinstance(published_at, str)
        and isinstance(available_at, str)
        and published_at.endswith("Z")
        and available_at.endswith("Z")
        and published_at <= cutoff
        and available_at <= cutoff
    )


def promotion_failures(metrics: Mapping[str, Any]) -> Sequence[str]:
    """List failed shadow-to-visible research-alert promotion gates."""
    failures = []

    minimums = (
        ("trading_sessions", PROMOTION_MIN_SESSIONS, "Fewer than 60 shadow trading sessions"),
        ("matured_predictions", PROMOTION_MIN_PREDICTIONS, "Fewer than 200 matured predictions"),
        ("matured_watches", PROMOTION_MIN_WATCHES, "Fewer than 40 matured Early watches"),
        ("realized_swings", PROMOTION_MIN_REALIZED_SWINGS, "Fewer than 15 realised big swings"),
    )
    for key, minimum, message in minimums:
        value = _finite_number(metrics.get(key))
        if value is None or value < minimum:
            failures.append(message)

    brier_skill = _finite_number(metrics.get("brier_skill"))
    if brier_skill is None or brier_skill < PROMOTION_MIN_BRIER_SKILL:
        failures.append("Brier skill is below 10% versus the rolling base rate")
    calibration_error = _finite_number(metrics.get("calibration_error"))
    if calibration_error is None or calibration_error > PROMOTION_MAX_CALIBRATION_ERROR:
        failures.append("Calibration error exceeds 5 percentage points")

    alert_precision = _finite_number(metrics.get("alert_precision"))
    base_rate = _finite_number(metrics.get("base_rate"))
    lower_bound = _finite_number(metrics.get("alert_precision_lower_95"))
    if alert_precision is None or base_rate is None or alert_precision < 2 * base_rate:
        failures.append("Alert precision is less than twice the point-in-time base rate")
    if lower_bound is None or base_rate is None or lower_bound <= base_rate:
        failures.append("Alert precision's 95% lower bound does not beat the base rate")

    directional_accuracy = _finite_number(metrics.get("directional_accuracy"))
    if directional_accuracy is None or directional_accuracy < PROMOTION_MIN_DIRECTIONAL_ACCURACY:
        failures.append("Directional accuracy is below 60% where direction was stated")

    if metrics.get("critical_incident") is not False:
        failures.append("A critical incident is present or has not been reviewed")
    if metrics.get("risk_review_accepted") is not True:
        failures.append("Worst loss, false alerts and missing data have not been accepted by Luke")
    return failures


def alert_status(
    probability: Any,
    peer_base_rate: Any,
    *,
    model_promoted: bool,
    evidence_clean: bool,
) -> str:
    """Map calibrated probabilities to the visible non-trading research state."""
    chance = _finite_number(probability)
    base_rate = _finite_number(peer_base_rate)
    if chance is None or base_rate is None or not evidence_clean:
        return "abstain"
    if model_promoted and chance >= RESEARCH_ALERT_MIN_PROBABILITY and chance >= 2 * base_rate:
        return "research_alert"
    if chance >= EARLY_WATCH_MIN_PROBABILITY and chance >= 2 * base_rate:
        return "early_watch"
    return "abstain"
