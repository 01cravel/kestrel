"""Monitoring for the things that quietly break a working model.

A model can pass every promotion gate and then degrade because the world moved,
a source changed shape, or the securities it sees stopped resembling the ones it
learned from. This module reports that drift in plain terms.

Nothing here blocks or promotes anything. It produces the monthly model-risk
review the roadmap requires, and names each problem as a model-risk event that
needs a documented resolution.
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from feature_store import FEATURE_NAMES
from learning_dataset import build_dataset
from outcome_source import DEFAULT_DATABASE, OutcomeSource
from shadow_journal import _load as load_shadow
from validation import expected_calibration_error, reliability_bins


# A standardised shift beyond this counts as material drift worth explaining.
DRIFT_WARNING = 0.5
DRIFT_SERIOUS = 1.0
RECENT_SESSIONS = 21


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _stdev(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def feature_drift(rows: Sequence[Dict[str, Any]],
                  recent_sessions: int = RECENT_SESSIONS) -> List[Dict[str, Any]]:
    """Compare the newest sessions with everything before them, per feature."""
    dates = sorted({row["sessionDate"] for row in rows})
    if len(dates) <= recent_sessions:
        return []
    boundary = dates[-recent_sessions]
    baseline = [row for row in rows if row["sessionDate"] < boundary]
    recent = [row for row in rows if row["sessionDate"] >= boundary]
    if not baseline or not recent:
        return []

    report = []
    for name in FEATURE_NAMES:
        old = [row["features"][name] for row in baseline if row["features"].get(name) is not None]
        new = [row["features"][name] for row in recent if row["features"].get(name) is not None]
        old_mean, new_mean = _mean(old), _mean(new)
        deviation = _stdev(old)
        if old_mean is None or new_mean is None or deviation is None:
            report.append({"feature": name, "shift": None, "severity": "unknown"})
            continue
        # A constant feature has a standard deviation of rounding error only.
        # Dividing one rounding error by another invents drift that is not there.
        if deviation <= max(abs(old_mean), 1.0) * 1e-9:
            report.append({
                "feature": name, "baselineMean": round(old_mean, 6),
                "recentMean": round(new_mean, 6), "shift": None, "severity": "constant",
            })
            continue
        shift = (new_mean - old_mean) / deviation
        severity = (
            "serious" if abs(shift) >= DRIFT_SERIOUS else
            "watch" if abs(shift) >= DRIFT_WARNING else "stable"
        )
        report.append({
            "feature": name,
            "baselineMean": round(old_mean, 6),
            "recentMean": round(new_mean, 6),
            "shift": round(shift, 3),
            "severity": severity,
        })
    report.sort(key=lambda item: -(abs(item["shift"]) if item["shift"] is not None else 0))
    return report


def prediction_drift(model_id: str, recent_sessions: int = RECENT_SESSIONS,
                     path: Optional[Path] = None) -> Dict[str, Any]:
    """Has the model started saying something different from what it used to?"""
    records = [row for row in load_shadow(path) if row.get("modelId") == model_id]
    dates = sorted({row["sessionDate"] for row in records})
    if len(dates) <= recent_sessions:
        return {"status": "insufficient", "sessions": len(dates)}
    boundary = dates[-recent_sessions]
    baseline = [row["probability"] for row in records if row["sessionDate"] < boundary]
    recent = [row["probability"] for row in records if row["sessionDate"] >= boundary]
    baseline_mean, recent_mean = _mean(baseline), _mean(recent)
    deviation = _stdev(baseline)
    shift = ((recent_mean - baseline_mean) / deviation) if deviation and recent_mean is not None else None
    return {
        "status": "measured",
        "baselineMean": round(baseline_mean, 4) if baseline_mean is not None else None,
        "recentMean": round(recent_mean, 4) if recent_mean is not None else None,
        "shift": round(shift, 3) if shift is not None else None,
        "severity": (
            "unknown" if shift is None else
            "serious" if abs(shift) >= DRIFT_SERIOUS else
            "watch" if abs(shift) >= DRIFT_WARNING else "stable"
        ),
    }


def model_risk_report(model_id: str = "big-move-logistic", horizon: int = 5,
                      database: Path = DEFAULT_DATABASE,
                      shadow_path: Optional[Path] = None) -> Dict[str, Any]:
    """The monthly review: coverage, drift, calibration, outcomes and exceptions."""
    coverage = OutcomeSource(database).coverage()
    rows = build_dataset(horizon, database=database)
    drift = feature_drift(rows)
    predictions = prediction_drift(model_id, path=shadow_path)

    shadow_records = [row for row in load_shadow(shadow_path) if row.get("modelId") == model_id]
    from shadow_journal import _matured

    graded = _matured(shadow_records, threshold=0.15) if shadow_records else []
    matured = [row for row in graded if row.get("outcomeStatus") == "matured"]
    probabilities = [row["probability"] for row in matured]
    outcomes = [1 if row.get("realisedSwing") else 0 for row in matured]

    events: List[str] = []
    for item in drift:
        if item.get("severity") == "serious":
            events.append(f"Feature {item['feature']} has shifted materially since training")
    if predictions.get("severity") == "serious":
        events.append("The model's average stated probability has shifted materially")
    if coverage["status"] != "ready":
        events.append("The adjusted market-history archive is unavailable")
    calibration_error = expected_calibration_error(probabilities, outcomes) if matured else None
    if calibration_error is not None and calibration_error > 0.05:
        events.append(f"Calibration error is {calibration_error:.3f}, above the 5 point limit")

    return {
        "modelId": model_id,
        "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archive": coverage,
        "researchRows": len(rows),
        "featureDrift": drift,
        "predictionDrift": predictions,
        "maturedShadowPredictions": len(matured),
        "awaitingOutcome": len(graded) - len(matured),
        "calibrationError": round(calibration_error, 4) if calibration_error is not None else None,
        "reliability": reliability_bins(probabilities, outcomes) if matured else [],
        "modelRiskEvents": events,
        "status": "attention" if events else "stable",
        "action": (
            "Each event above needs a documented resolution before the model advances."
            if events else
            "No model-risk event detected in this period."
        ),
    }
