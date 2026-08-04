"""Leakage-safe research dataset joining point-in-time features to outcomes.

The roadmap keeps three questions apart. This module supplies the two that a
model may answer from archived market data:

* **big move** — will the absolute benchmark-relative move over the horizon
  cross the policy threshold, regardless of sign;
* **direction** — will the benchmark-relative move be positive beyond the
  declared cost band.

Investment-worthiness is a constrained portfolio decision and is deliberately
not modelled here.

Every row pairs features ending at session ``D`` with an outcome measured from
the session *after* ``D`` to the horizon end, so the entry price is never the
price the decision was based on. Rows whose outcome window is incomplete, or
whose corporate-action history is unresolved anywhere in that window, are
dropped rather than guessed.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from feature_store import (
    EVENT_FEATURE_NAMES,
    FEATURE_NAMES,
    FEATURE_VERSION,
    FeatureStore,
    SecurityHistory,
    build_features,
    feature_vector,
    research_eligible,
    with_events,
)
from outcome_source import COST_BAND_PERCENT, DEFAULT_DATABASE
from swing_radar_policy import POLICY_VERSION


DATASET_VERSION = "2026.08.1"

# Horizons in trading sessions, with the absolute benchmark-relative move that
# counts as a big move at each. The short horizons mirror the swing policy.
HORIZON_THRESHOLDS: Dict[int, float] = {1: 0.10, 5: 0.15, 21: 0.20}
DIRECTION_BAND = COST_BAND_PERCENT / 100.0
ENTRY_DELAY_SESSIONS = 1


def horizon_threshold(horizon: int) -> float:
    try:
        return HORIZON_THRESHOLDS[horizon]
    except KeyError:
        raise ValueError(f"No declared big-move threshold for a {horizon}-session horizon") from None


def _outcome(history: SecurityHistory, index: int, horizon: int) -> Optional[Dict[str, float]]:
    """Benchmark-relative outcome from the entry session to the horizon end."""
    entry = index + ENTRY_DELAY_SESSIONS
    exit_index = entry + horizon
    if exit_index >= len(history):
        return None
    if not all(history.clean[position] for position in range(index, exit_index + 1)):
        return None
    stock = history.closes[exit_index] / history.closes[entry] - 1
    benchmark = history.benchmarks[exit_index] / history.benchmarks[entry] - 1
    path = history.closes[entry:exit_index + 1]
    trough = min(path) / history.closes[entry] - 1
    return {
        "excessReturn": stock - benchmark,
        "stockReturn": stock,
        "benchmarkReturn": benchmark,
        "maxDrawdown": trough,
        "entryDate": history.dates[entry],
        "exitDate": history.dates[exit_index],
    }


def build_rows(history: SecurityHistory, horizon: int,
               require_complete: bool = True,
               events: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Labelled rows for one security at one horizon.

    When ``events`` is supplied the row carries the insider and filing features
    as well, and the vector spans both families.
    """
    names = (tuple(FEATURE_NAMES) + tuple(EVENT_FEATURE_NAMES)) if events is not None else FEATURE_NAMES
    threshold = horizon_threshold(horizon)
    rows: List[Dict[str, Any]] = []
    for index in range(len(history)):
        eligibility = research_eligible(history, index)
        if not eligibility["eligible"]:
            continue
        outcome = _outcome(history, index, horizon)
        if outcome is None:
            continue
        features = build_features(history, index)
        if events is not None:
            features = with_events(features, events)
        if require_complete and not features["complete"]:
            continue
        vector = feature_vector(features, names)
        if vector is None:
            continue
        excess = outcome["excessReturn"]
        rows.append({
            "datasetVersion": DATASET_VERSION,
            "featureVersion": FEATURE_VERSION,
            "policyVersion": POLICY_VERSION,
            "securityId": history.security_id,
            "ticker": history.ticker,
            "sessionDate": history.dates[index],
            "entryDate": outcome["entryDate"],
            "exitDate": outcome["exitDate"],
            "horizonSessions": horizon,
            "features": features["values"],
            "featureSet": features.get("featureSet", "price"),
            "vector": vector,
            "excessReturn": excess,
            "maxDrawdown": outcome["maxDrawdown"],
            "bigMove": 1 if abs(excess) >= threshold else 0,
            "up": 1 if excess > DIRECTION_BAND else 0,
            "neutral": 1 if abs(excess) <= DIRECTION_BAND else 0,
        })
    return rows


def build_dataset(horizon: int, database: Path = DEFAULT_DATABASE,
                  start: Optional[str] = None, end: Optional[str] = None,
                  tickers: Optional[Sequence[str]] = None,
                  exclude_benchmark: bool = True,
                  include_events: bool = False) -> List[Dict[str, Any]]:
    """Assemble the full research set, sorted chronologically.

    ``include_events`` restricts the set to issuers whose SEC filings have been
    ingested, so every row carries the same evidence and the comparison stays
    like for like.
    """
    store = FeatureStore(database)
    rows: List[Dict[str, Any]] = []
    for history in store.iter_histories(start=start, end=end, tickers=tickers):
        if exclude_benchmark and history.ticker == "SPY":
            continue
        events = None
        if include_events:
            from sec_events import load_events
            events = load_events(history.ticker, database)
            if not events:
                continue
        rows.extend(build_rows(history, horizon, events=events))
    rows.sort(key=lambda row: (row["sessionDate"], row["ticker"]))
    return rows


def dataset_summary(rows: Sequence[Dict[str, Any]], horizon: int) -> Dict[str, Any]:
    """Plain description of what the research set actually contains."""
    dates = sorted({row["sessionDate"] for row in rows})
    securities = {row["securityId"] for row in rows}
    big_moves = sum(row["bigMove"] for row in rows)
    ups = sum(row["up"] for row in rows)
    neutrals = sum(row["neutral"] for row in rows)
    return {
        "datasetVersion": DATASET_VERSION,
        "featureVersion": FEATURE_VERSION,
        "horizonSessions": horizon,
        "bigMoveThreshold": horizon_threshold(horizon),
        "directionBand": DIRECTION_BAND,
        "rows": len(rows),
        "securities": len(securities),
        "sessions": len(dates),
        "firstSession": dates[0] if dates else None,
        "lastSession": dates[-1] if dates else None,
        "bigMoveRate": round(big_moves / len(rows), 4) if rows else None,
        "upRate": round(ups / len(rows), 4) if rows else None,
        "neutralRate": round(neutrals / len(rows), 4) if rows else None,
        "features": list(FEATURE_NAMES),
        "entryConvention": "Enter at the close one session after the decision session.",
    }


def base_rate(rows: Sequence[Dict[str, Any]], label: str = "bigMove") -> Optional[float]:
    return (sum(row[label] for row in rows) / len(rows)) if rows else None


def subset_vectors(rows: Iterable[Dict[str, Any]], names: Sequence[str]) -> List[Dict[str, Any]]:
    """Copy rows with vectors rebuilt over a feature subset, for ablation."""
    rebuilt: List[Dict[str, Any]] = []
    for row in rows:
        values = row.get("features") or {}
        vector: List[float] = []
        usable = True
        for name in names:
            value = values.get(name)
            if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                usable = False
                break
            vector.append(float(value))
        if usable:
            rebuilt.append({**row, "vector": vector})
    return rebuilt
