"""Chronological validation and proper scoring rules.

Two jobs, kept apart from any model:

1. **Splitting.** Expanding walk-forward folds, with training rows purged when
   their outcome window overlaps the test window, plus an embargo gap at least
   as long as the horizon. Without purging, a row decided shortly before the
   test period would still be resolving inside it, and the score would flatter
   the model.
2. **Scoring.** Brier score, log loss, skill against a base rate, reliability
   bins, calibration slope and intercept, and confidence intervals from a block
   bootstrap clustered by decision date. Same-day predictions across securities
   are not independent, so resampling individual rows would understate the
   interval badly.

Hit rate is computed for readability but is never treated as sufficient.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


PROBABILITY_FLOOR = 1e-6
DEFAULT_OUTER_PERIODS = 5
DEFAULT_RELIABILITY_BINS = 10
DEFAULT_BOOTSTRAP_SAMPLES = 400
BOOTSTRAP_SEED = 20260804


def _clip(probability: float) -> float:
    return min(1 - PROBABILITY_FLOOR, max(PROBABILITY_FLOOR, probability))


# -- splitting ----------------------------------------------------------


def walk_forward_splits(dates: Sequence[str], horizon_sessions: int,
                        outer_periods: int = DEFAULT_OUTER_PERIODS,
                        min_train_sessions: Optional[int] = None) -> List[Dict[str, Any]]:
    """Expanding folds over unique sessions, with a purge and embargo gap.

    Sessions are divided into ``outer_periods + 1`` blocks. The first block is
    the initial training window and each later block becomes one test period, so
    the training window expands and every fold gets a comparable amount of test
    data. An embargo of at least one horizon separates train from test.

    Returns fold descriptions only. Applying them to rows is ``apply_split``,
    which enforces the purge on the training side.
    """
    unique = sorted(set(dates))
    if outer_periods < 1:
        raise ValueError("At least one outer test period is required")
    gap = max(1, horizon_sessions)
    available = len(unique) - gap * outer_periods
    block = available // (outer_periods + 1)
    if block < 1:
        return []
    if min_train_sessions is not None and block < min_train_sessions:
        return []

    folds: List[Dict[str, Any]] = []
    for period in range(outer_periods):
        train_end_index = block * (period + 1) + gap * period
        test_start_index = train_end_index + gap
        test_end_index = test_start_index + block
        if test_end_index > len(unique):
            break
        folds.append({
            "fold": len(folds) + 1,
            "trainStart": unique[0],
            "trainEnd": unique[train_end_index - 1],
            "testStart": unique[test_start_index],
            "testEnd": unique[test_end_index - 1],
            "embargoSessions": gap,
            "horizonSessions": horizon_sessions,
        })
    return folds


def apply_split(rows: Sequence[Dict[str, Any]], fold: Dict[str, Any],
                date_key: str = "sessionDate",
                exit_key: str = "exitDate") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split rows into train and test, purging overlapping outcome windows.

    A training row is dropped when its outcome is still resolving at or after
    the test period begins, even if its decision date sits safely earlier.
    """
    test = [row for row in rows if fold["testStart"] <= row[date_key] <= fold["testEnd"]]
    train = []
    purged = 0
    for row in rows:
        if row[date_key] > fold["trainEnd"]:
            continue
        exit_date = row.get(exit_key)
        if exit_date and exit_date >= fold["testStart"]:
            purged += 1
            continue
        train.append(row)
    fold["trainRows"] = len(train)
    fold["testRows"] = len(test)
    fold["purgedRows"] = purged
    return train, test


def leakage_violations(train: Sequence[Dict[str, Any]], test: Sequence[Dict[str, Any]],
                       date_key: str = "sessionDate", exit_key: str = "exitDate") -> List[str]:
    """Automated future-information check; must return empty before scoring."""
    if not train or not test:
        return []
    first_test = min(row[date_key] for row in test)
    violations = []
    for row in train:
        if row[date_key] >= first_test:
            violations.append(f"Training row {row.get('ticker')} {row[date_key]} is not before the test period")
        elif row.get(exit_key) and row[exit_key] >= first_test:
            violations.append(f"Training row {row.get('ticker')} {row[date_key]} resolves inside the test period")
    return violations[:20]


# -- scoring ------------------------------------------------------------


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> Optional[float]:
    if not probabilities or len(probabilities) != len(outcomes):
        return None
    return sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(outcomes)


def log_loss(probabilities: Sequence[float], outcomes: Sequence[int]) -> Optional[float]:
    if not probabilities or len(probabilities) != len(outcomes):
        return None
    total = 0.0
    for probability, outcome in zip(probabilities, outcomes):
        clipped = _clip(probability)
        total += -(outcome * math.log(clipped) + (1 - outcome) * math.log(1 - clipped))
    return total / len(outcomes)


def brier_skill(probabilities: Sequence[float], outcomes: Sequence[int],
                reference: Optional[float] = None) -> Optional[float]:
    """Skill against a constant base-rate forecast. Positive means better."""
    score = brier_score(probabilities, outcomes)
    if score is None:
        return None
    rate = reference if reference is not None else (sum(outcomes) / len(outcomes))
    baseline = brier_score([rate] * len(outcomes), outcomes)
    if not baseline:
        return None
    return 1 - (score / baseline)


def reliability_bins(probabilities: Sequence[float], outcomes: Sequence[int],
                     bins: int = DEFAULT_RELIABILITY_BINS) -> List[Dict[str, Any]]:
    buckets: List[Dict[str, Any]] = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        selected = [
            (probability, outcome) for probability, outcome in zip(probabilities, outcomes)
            if (low <= probability < high) or (index == bins - 1 and probability == 1.0)
        ]
        if not selected:
            buckets.append({"bin": index + 1, "from": round(low, 2), "to": round(high, 2), "count": 0,
                            "forecast": None, "observed": None})
            continue
        forecast = sum(item[0] for item in selected) / len(selected)
        observed = sum(item[1] for item in selected) / len(selected)
        buckets.append({
            "bin": index + 1, "from": round(low, 2), "to": round(high, 2),
            "count": len(selected), "forecast": round(forecast, 4), "observed": round(observed, 4),
        })
    return buckets


def expected_calibration_error(probabilities: Sequence[float], outcomes: Sequence[int],
                               bins: int = DEFAULT_RELIABILITY_BINS) -> Optional[float]:
    if not probabilities:
        return None
    total = 0.0
    for bucket in reliability_bins(probabilities, outcomes, bins):
        if not bucket["count"]:
            continue
        total += (bucket["count"] / len(probabilities)) * abs(bucket["forecast"] - bucket["observed"])
    return total


def calibration_slope_intercept(probabilities: Sequence[float],
                                outcomes: Sequence[int]) -> Dict[str, Optional[float]]:
    """Logistic recalibration fit: outcome ~ intercept + slope * logit(p).

    A slope near 1 with an intercept near 0 means the stated probabilities can
    be taken at face value. A slope below 1 means overconfidence.
    """
    points = []
    for probability, outcome in zip(probabilities, outcomes):
        clipped = _clip(probability)
        points.append((math.log(clipped / (1 - clipped)), outcome))
    if len(points) < 10 or len({outcome for _, outcome in points}) < 2:
        return {"slope": None, "intercept": None, "samples": len(points)}

    intercept, slope = 0.0, 1.0
    for _ in range(200):
        gradient_intercept = gradient_slope = 0.0
        hessian_ii = hessian_is = hessian_ss = 0.0
        for logit, outcome in points:
            prediction = 1 / (1 + math.exp(-max(-30.0, min(30.0, intercept + slope * logit))))
            error = prediction - outcome
            weight = max(prediction * (1 - prediction), 1e-9)
            gradient_intercept += error
            gradient_slope += error * logit
            hessian_ii += weight
            hessian_is += weight * logit
            hessian_ss += weight * logit * logit
        determinant = hessian_ii * hessian_ss - hessian_is * hessian_is
        if abs(determinant) < 1e-12:
            break
        step_intercept = (hessian_ss * gradient_intercept - hessian_is * gradient_slope) / determinant
        step_slope = (hessian_ii * gradient_slope - hessian_is * gradient_intercept) / determinant
        intercept -= step_intercept
        slope -= step_slope
        if abs(step_intercept) < 1e-8 and abs(step_slope) < 1e-8:
            break
    return {"slope": round(slope, 4), "intercept": round(intercept, 4), "samples": len(points)}


def block_bootstrap_interval(rows: Sequence[Dict[str, Any]],
                             statistic: Callable[[Sequence[Dict[str, Any]]], Optional[float]],
                             date_key: str = "sessionDate",
                             samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
                             seed: int = BOOTSTRAP_SEED) -> Dict[str, Optional[float]]:
    """95% interval, resampling whole decision dates rather than single rows."""
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_date.setdefault(row[date_key], []).append(row)
    dates = sorted(by_date)
    if len(dates) < 3:
        return {"lower95": None, "upper95": None, "samples": 0, "clusters": len(dates)}

    generator = random.Random(seed)
    estimates: List[float] = []
    for _ in range(samples):
        drawn: List[Dict[str, Any]] = []
        for _ in range(len(dates)):
            drawn.extend(by_date[dates[generator.randrange(len(dates))]])
        value = statistic(drawn)
        if value is not None and math.isfinite(value):
            estimates.append(value)
    if len(estimates) < 20:
        return {"lower95": None, "upper95": None, "samples": len(estimates), "clusters": len(dates)}
    estimates.sort()
    lower = estimates[int(0.025 * (len(estimates) - 1))]
    upper = estimates[int(0.975 * (len(estimates) - 1))]
    return {
        "lower95": round(lower, 4), "upper95": round(upper, 4),
        "samples": len(estimates), "clusters": len(dates),
    }


def score_predictions(rows: Sequence[Dict[str, Any]], probability_key: str = "probability",
                      label_key: str = "label", reference_rate: Optional[float] = None,
                      date_key: str = "sessionDate") -> Dict[str, Any]:
    """Full scorecard for one set of matured probabilistic predictions."""
    probabilities = [float(row[probability_key]) for row in rows]
    outcomes = [int(row[label_key]) for row in rows]
    if not rows:
        return {"count": 0, "brier": None, "logLoss": None, "brierSkill": None,
                "baseRate": None, "hitRate": None, "calibration": {"slope": None, "intercept": None},
                "expectedCalibrationError": None, "reliability": [], "brierSkillInterval": None}

    observed_rate = sum(outcomes) / len(outcomes)
    reference = reference_rate if reference_rate is not None else observed_rate

    def skill(sample: Sequence[Dict[str, Any]]) -> Optional[float]:
        return brier_skill(
            [float(row[probability_key]) for row in sample],
            [int(row[label_key]) for row in sample],
            reference,
        )

    return {
        "count": len(rows),
        "baseRate": round(observed_rate, 4),
        "referenceRate": round(reference, 4),
        "brier": round(brier_score(probabilities, outcomes), 6),
        "logLoss": round(log_loss(probabilities, outcomes), 6),
        "brierSkill": round(brier_skill(probabilities, outcomes, reference), 4),
        "brierSkillInterval": block_bootstrap_interval(rows, skill, date_key=date_key),
        "hitRate": round(
            sum((probability >= 0.5) == bool(outcome) for probability, outcome in zip(probabilities, outcomes))
            / len(outcomes), 4),
        "calibration": calibration_slope_intercept(probabilities, outcomes),
        "expectedCalibrationError": round(expected_calibration_error(probabilities, outcomes), 4),
        "reliability": reliability_bins(probabilities, outcomes),
        "note": "Hit rate is a diagnostic only; promotion depends on proper scores and calibration.",
    }
