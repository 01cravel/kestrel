"""Append-only shadow predictions and the promotion metrics they produce.

A challenger that passes chronological validation has still only been tested on
history. Before it may influence anything it must run live, daily, without being
shown — predicting forward, then being graded by the same independent archive
that grades Kestrel's own signals.

This module stores those forward predictions immutably and turns matured ones
into the metrics mapping ``swing_radar_policy.promotion_failures`` expects, so
the promotion gates are evaluated against real recorded behaviour rather than
hand-supplied numbers.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from outcome_source import STATUS_MATURED, STATUS_PENDING, shared_source
from swing_radar_policy import (
    DIRECTION_MIN_PROBABILITY,
    MAX_DAILY_ALERTS,
    POLICY_VERSION,
    alert_status,
    promotion_failures,
)


ROOT = Path(__file__).resolve().parent
SHADOW_PATH = ROOT / ".kestrel-shadow-journal.json"
_LOCK = threading.Lock()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _save(path: Path, records: List[Dict[str, Any]]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def record_shadow_predictions(model_id: str, model_version: str, session_date: str,
                              predictions: Sequence[Dict[str, Any]],
                              horizon_sessions: int,
                              base_rates: Optional[Dict[str, float]] = None,
                              path: Optional[Path] = None) -> Dict[str, Any]:
    """Freeze one session of forward predictions. Nothing is ever rewritten."""
    path = path or SHADOW_PATH
    base_rates = base_rates or {}
    recorded_at = _now()
    clean: List[Dict[str, Any]] = []
    for prediction in predictions:
        symbol = str(prediction.get("symbol") or "").upper()
        probability = prediction.get("probability")
        try:
            probability = float(probability)
        except (TypeError, ValueError):
            continue
        if not symbol or not 0.0 <= probability <= 1.0:
            continue
        peer_rate = base_rates.get(symbol, base_rates.get("__default__"))
        status = alert_status(
            probability, peer_rate,
            model_promoted=False,  # A shadow model is never promoted by definition.
            evidence_clean=bool(prediction.get("evidenceClean", True)),
        )
        direction = prediction.get("direction")
        direction_probability = prediction.get("directionProbability")
        stated_direction = None
        if direction in {"up", "down"} and direction_probability is not None:
            try:
                if float(direction_probability) >= DIRECTION_MIN_PROBABILITY:
                    stated_direction = direction
            except (TypeError, ValueError):
                stated_direction = None
        clean.append({
            "modelId": model_id,
            "modelVersion": model_version,
            "policyVersion": POLICY_VERSION,
            "sessionDate": session_date,
            "symbol": symbol,
            "probability": probability,
            "peerBaseRate": peer_rate,
            "alertStatus": status,
            "direction": stated_direction,
            "directionProbability": direction_probability,
            "horizonSessions": horizon_sessions,
            "evidenceClean": bool(prediction.get("evidenceClean", True)),
            "recordedAt": recorded_at,
        })

    alerts = [row for row in clean if row["alertStatus"] in {"early_watch", "research_alert"}]
    if len(alerts) > MAX_DAILY_ALERTS:
        keep = {id(row) for row in sorted(alerts, key=lambda row: -row["probability"])[:MAX_DAILY_ALERTS]}
        for row in alerts:
            if id(row) not in keep:
                row["alertStatus"] = "abstain"
                row["alertSuppressed"] = "Daily alert budget reached"

    with _LOCK:
        records = _load(path)
        existing = {(row.get("modelId"), row.get("sessionDate"), row.get("symbol")) for row in records}
        appended = 0
        for row in clean:
            key = (row["modelId"], row["sessionDate"], row["symbol"])
            if key in existing:
                continue
            existing.add(key)
            row["predictionHash"] = hashlib.sha256(
                json.dumps(row, sort_keys=True).encode("utf-8")
            ).hexdigest()
            records.append(row)
            appended += 1
        if appended:
            _save(path, records)
    return {
        "sessionDate": session_date,
        "modelId": model_id,
        "predictionsAppended": appended,
        "duplicatesRefused": len(clean) - appended,
        "alerts": len([row for row in clean if row["alertStatus"] != "abstain"]),
        "alertBudget": MAX_DAILY_ALERTS,
    }


def _matured(records: Sequence[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """Grade shadow predictions using the same independent archive."""
    source = shared_source()
    graded: List[Dict[str, Any]] = []
    for row in records:
        horizon_days = max(1, int(round(int(row.get("horizonSessions") or 5) * 7 / 5)))
        outcome = source.outcome(str(row.get("symbol")), row.get("sessionDate"), horizon_days)
        if outcome["status"] != STATUS_MATURED:
            graded.append({**row, "outcomeStatus": outcome["status"]})
            continue
        excess = outcome["excessReturn"] / 100.0
        graded.append({
            **row,
            "outcomeStatus": STATUS_MATURED,
            "excessReturn": outcome["excessReturn"],
            "realisedSwing": abs(excess) >= threshold,
            "realisedDirection": "up" if excess > 0 else "down",
            "exitDate": outcome["exitDate"],
        })
    return graded


def promotion_metrics(model_id: str, threshold: float = 0.15,
                      risk_review_accepted: bool = False,
                      critical_incident: Optional[bool] = None,
                      path: Optional[Path] = None) -> Dict[str, Any]:
    """Build the metrics mapping the promotion gates consume, then run them."""
    records = [row for row in _load(path or SHADOW_PATH) if row.get("modelId") == model_id]
    graded = _matured(records, threshold)
    matured = [row for row in graded if row.get("outcomeStatus") == STATUS_MATURED]
    pending = len([row for row in graded if row.get("outcomeStatus") == STATUS_PENDING])

    sessions = {row["sessionDate"] for row in records}
    watches = [row for row in matured if row.get("alertStatus") in {"early_watch", "research_alert"}]
    realised = [row for row in matured if row.get("realisedSwing")]
    alert_hits = [row for row in watches if row.get("realisedSwing")]
    directional = [row for row in matured if row.get("direction")]
    directional_hits = [row for row in directional if row["direction"] == row.get("realisedDirection")]

    observed_rate = (len(realised) / len(matured)) if matured else None
    from validation import block_bootstrap_interval, brier_skill

    probabilities = [row["probability"] for row in matured]
    outcomes = [1 if row.get("realisedSwing") else 0 for row in matured]
    skill = brier_skill(probabilities, outcomes, observed_rate) if matured else None

    def precision(sample: Sequence[Dict[str, Any]]) -> Optional[float]:
        selected = [row for row in sample if row.get("alertStatus") in {"early_watch", "research_alert"}]
        if not selected:
            return None
        return sum(1 for row in selected if row.get("realisedSwing")) / len(selected)

    interval = block_bootstrap_interval(matured, precision, date_key="sessionDate") if watches else {}
    metrics = {
        "trading_sessions": len(sessions),
        "matured_predictions": len(matured),
        "matured_watches": len(watches),
        "realized_swings": len(realised),
        "brier_skill": skill,
        "calibration_error": _calibration_error(probabilities, outcomes),
        "alert_precision": (len(alert_hits) / len(watches)) if watches else None,
        "alert_precision_lower_95": interval.get("lower95"),
        "base_rate": observed_rate,
        "directional_accuracy": (len(directional_hits) / len(directional)) if directional else None,
        "critical_incident": critical_incident,
        "risk_review_accepted": risk_review_accepted,
    }
    failures = promotion_failures(metrics)
    return {
        "modelId": model_id,
        "metrics": metrics,
        "awaitingOutcome": pending,
        "gateFailures": list(failures),
        "promotable": not failures,
        "decision": (
            "Every promotion gate passes. Promotion still requires Luke's explicit approval "
            "and starts at a capped, reversible influence."
            if not failures else
            f"{len(failures)} promotion gate(s) fail. The model stays in shadow."
        ),
        "policyVersion": POLICY_VERSION,
    }


def _calibration_error(probabilities: Sequence[float], outcomes: Sequence[int]) -> Optional[float]:
    from validation import expected_calibration_error
    return expected_calibration_error(probabilities, outcomes) if probabilities else None


def shadow_summary(path: Optional[Path] = None) -> Dict[str, Any]:
    records = _load(path or SHADOW_PATH)
    models = sorted({str(row.get("modelId")) for row in records})
    sessions = sorted({str(row.get("sessionDate")) for row in records})
    return {
        "models": models,
        "predictions": len(records),
        "sessions": len(sessions),
        "firstSession": sessions[0] if sessions else None,
        "lastSession": sessions[-1] if sessions else None,
        "journal": "append-only; a shadow prediction is hashed at write time and never rewritten",
        "visibility": "Shadow predictions never appear as actions and never change a displayed rating.",
    }
