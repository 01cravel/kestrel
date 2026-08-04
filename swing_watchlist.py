"""Frozen, pre-event shadow predictions for Kestrel's Swing Radar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parent
DEFAULT_WATCHLIST = ROOT / "swing_watchlist.json"


def swing_watchlist_snapshot(path: Path = DEFAULT_WATCHLIST) -> Dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "empty",
            "candidates": [],
            "message": "No shadow predictions have been frozen yet.",
        }
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return {
            "status": "invalid",
            "candidates": [],
            "message": "The shadow prediction file is invalid.",
        }
    if any(
        not isinstance(candidate, dict)
        or not isinstance(candidate.get("jumpChance10"), (int, float))
        or not 0 <= float(candidate["jumpChance10"]) <= 1
        for candidate in candidates
    ):
        return {
            "status": "invalid",
            "candidates": [],
            "message": "A shadow percentage is missing or outside the valid range.",
        }
    if any(
        not isinstance(candidate.get("setupSignalsPassed"), int)
        or not isinstance(candidate.get("setupSignalsTotal"), int)
        or not 0 <= candidate["setupSignalsPassed"] <= candidate["setupSignalsTotal"]
        for candidate in candidates
        if "setupSignalsPassed" in candidate or "setupSignalsTotal" in candidate
    ):
        return {
            "status": "invalid",
            "candidates": [],
            "message": "A setup-strength score is missing or outside the valid range.",
        }
    payload["candidateCount"] = len(candidates)
    payload["message"] = (
        "Frozen before the events. Outcomes will be added later without rewriting the prediction."
    )
    return payload
