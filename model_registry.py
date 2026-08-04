"""Append-only model inventory and experiment registry.

Model risk management needs two records that cannot be quietly edited:

* the **inventory** — what each model is for, who approved it, what it may
  influence, and which version to roll back to;
* the **experiment registry** — every comparison that was run, including the
  ones that failed. A registry that only records successes is a marketing
  document, not evidence.

Both are JSON files of immutable entries. Nothing is updated in place: a change
of approval status appends a new entry that supersedes the previous one, and the
history stays readable.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
INVENTORY_PATH = ROOT / ".kestrel-model-inventory.json"
EXPERIMENTS_PATH = ROOT / ".kestrel-experiments.json"

APPROVAL_STATES = {"research", "shadow", "approved", "retired", "rolled-back"}
_LOCK = threading.Lock()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _append(path: Path, entry: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        entries = _load(path)
        entry = {**entry, "sequence": len(entries) + 1}
        entry["entryHash"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode("utf-8")
        ).hexdigest()
        entries.append(entry)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
        return entry


def register_model(model_id: str, purpose: str, family: str, version: str,
                   inputs: List[str], intended_use: str, limitations: str,
                   approval: str = "research", owner: str = "Luke",
                   rollback_version: Optional[str] = None,
                   influence_cap: float = 0.0,
                   path: Optional[Path] = None) -> Dict[str, Any]:
    """Append an inventory entry. Later entries supersede earlier ones."""
    path = path or INVENTORY_PATH
    if approval not in APPROVAL_STATES:
        raise ValueError(f"Approval state must be one of {sorted(APPROVAL_STATES)}")
    return _append(path, {
        "recordedAt": _now(),
        "modelId": model_id,
        "purpose": purpose,
        "family": family,
        "version": version,
        "owner": owner,
        "inputs": list(inputs),
        "intendedUse": intended_use,
        "limitations": limitations,
        "approval": approval,
        "rollbackVersion": rollback_version,
        "influenceCap": influence_cap,
    })


def current_models(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Latest entry per model, newest first."""
    path = path or INVENTORY_PATH
    latest: Dict[str, Dict[str, Any]] = {}
    for entry in _load(path):
        latest[str(entry.get("modelId"))] = entry
    return sorted(latest.values(), key=lambda entry: entry.get("recordedAt", ""), reverse=True)


def model_history(model_id: str, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return [entry for entry in _load(path or INVENTORY_PATH) if entry.get("modelId") == model_id]


def register_experiment(name: str, question: str, horizon_sessions: int,
                        champion: Dict[str, Any], challenger: Dict[str, Any],
                        folds: List[Dict[str, Any]], verdict: str,
                        gate_failures: List[str], dataset: Dict[str, Any],
                        notes: str = "", path: Optional[Path] = None) -> Dict[str, Any]:
    """Record one comparison, whatever its result."""
    return _append(path or EXPERIMENTS_PATH, {
        "recordedAt": _now(),
        "name": name,
        "question": question,
        "horizonSessions": horizon_sessions,
        "champion": champion,
        "challenger": challenger,
        "folds": folds,
        "verdict": verdict,
        "gateFailures": list(gate_failures),
        "dataset": dataset,
        "notes": notes,
    })


def experiments(limit: Optional[int] = None, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    entries = sorted(_load(path or EXPERIMENTS_PATH), key=lambda entry: entry.get("recordedAt", ""), reverse=True)
    return entries[:limit] if limit else entries


def registry_summary(inventory_path: Optional[Path] = None,
                     experiments_path: Optional[Path] = None) -> Dict[str, Any]:
    models = current_models(inventory_path)
    runs = experiments(path=experiments_path)
    promoted = [model for model in models if model.get("approval") == "approved"]
    return {
        "models": len(models),
        "approvedModels": len(promoted),
        "shadowModels": len([model for model in models if model.get("approval") == "shadow"]),
        "experiments": len(runs),
        "passedExperiments": len([run for run in runs if run.get("verdict") == "passed"]),
        "lastExperimentAt": runs[0]["recordedAt"] if runs else None,
        "liveInfluence": (
            "No model influences a live recommendation."
            if not promoted else
            f"{len(promoted)} approved model(s) with a capped, reversible contribution."
        ),
        "registers": "append-only; approval changes add a superseding entry rather than editing history",
    }
