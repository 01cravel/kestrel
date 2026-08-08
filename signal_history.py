"""Append-only signal journal graded against independent adjusted returns.

Two rules hold this file together:

1. A prediction is written once and never altered. A repeat submission for the
   same day, security and model version is refused, not overwritten, and nothing
   is ever pruned by age.
2. Kestrel does not grade its own homework. Outcomes come from the adjusted
   market-history archive through ``outcome_source``, are measured against SPY
   after a realistic entry delay, and stay uncounted when the archive cannot
   support them honestly.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from outcome_source import COST_BAND_PERCENT, STATUS_MATURED, STATUS_PENDING, shared_source


ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / ".kestrel-signal-history.json"
MODEL_VERSION = "2026.08.1"
VALID_ACTIONS = {"Hold", "Sell", "Buy", "Ultra Buy"}
VALID_CONFIDENCE = {"Low", "Medium", "High"}
REVIEW_DAYS = (30, 90, 180)
HEADLINE_HORIZON = 30
BULLISH_ACTIONS = {"Buy", "Ultra Buy"}
GRADED_ACTIONS = BULLISH_ACTIONS | {"Sell"}
_LOCK = threading.Lock()


def _load() -> List[Dict[str, Any]]:
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _save(records: List[Dict[str, Any]]) -> None:
    temporary_path = HISTORY_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(records), encoding="utf-8")
    temporary_path.replace(HISTORY_PATH)


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else None
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def record_signals(rows: List[Dict[str, Any]], evidence_timestamp: Any) -> Dict[str, Any]:
    """Append today's predictions. Existing records are never rewritten."""
    today = dt.date.today().isoformat()
    recorded_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    clean = []
    for row in rows[:250]:
        symbol = str(row.get("symbol", "")).upper()
        action = str(row.get("action", ""))
        confidence = str(row.get("confidence", ""))
        price = _number(row.get("price"))
        if not symbol.isalnum() or action not in VALID_ACTIONS or confidence not in VALID_CONFIDENCE or not price:
            continue
        clean.append({
            "date": today,
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "score": _number(row.get("score")),
            "price": price,
            "owned": bool(row.get("owned")),
            "reason": str(row.get("reason", ""))[:500],
            "evidenceTimestamp": evidence_timestamp,
            "modelVersion": MODEL_VERSION,
            "recordedAt": recorded_at,
        })

    with _LOCK:
        records = _load()
        existing = {(row.get("date"), row.get("symbol"), row.get("modelVersion")) for row in records}
        appended = 0
        for row in clean:
            key = (row["date"], row["symbol"], row["modelVersion"])
            if key in existing:
                continue
            existing.add(key)
            records.append(row)
            appended += 1
        records.sort(key=lambda row: (row.get("date", ""), row.get("symbol", "")))
        if appended:
            _save(records)
        summary = calibration_summary(records)
        summary["predictionsAppended"] = appended
        summary["duplicatesRefused"] = len(clean) - appended
        return summary


def _matured_outcomes(records: List[Dict[str, Any]], horizon_days: int) -> Dict[str, List[Dict[str, Any]]]:
    """Grade every actionable prediction at one horizon, keeping the misses visible."""
    source = shared_source()
    matured: List[Dict[str, Any]] = []
    pending = 0
    ungradeable = 0
    for row in records:
        if row.get("action") not in GRADED_ACTIONS:
            continue
        outcome = source.outcome(str(row.get("symbol")), row.get("date"), horizon_days)
        if outcome["status"] == STATUS_MATURED:
            bullish = row.get("action") in BULLISH_ACTIONS
            excess = outcome["excessReturn"]
            if outcome["verdict"] == "neutral":
                correct = None
            else:
                correct = excess > 0 if bullish else excess < 0
            matured.append({**row, **outcome, "correct": correct})
        elif outcome["status"] == STATUS_PENDING:
            pending += 1
        else:
            ungradeable += 1
    return {"matured": matured, "pending": pending, "ungradeable": ungradeable}


def _rate(rows: List[Dict[str, Any]]) -> Optional[float]:
    decided = [row for row in rows if row.get("correct") is not None]
    if not decided:
        return None
    return round(sum(bool(row["correct"]) for row in decided) / len(decided) * 100, 1)


def _average(values: List[Optional[float]]) -> Optional[float]:
    usable = [value for value in values if value is not None]
    return round(sum(usable) / len(usable), 2) if usable else None


def calibration_summary(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if records is None:
        with _LOCK:
            records = _load()

    source = shared_source()
    coverage = source.coverage()
    horizons: Dict[str, Any] = {}
    for days in REVIEW_DAYS:
        graded = _matured_outcomes(records, days)
        matured = graded["matured"]
        horizons[str(days)] = {
            "maturedSignals": len(matured),
            "awaitingOutcome": graded["pending"],
            "notGradeable": graded["ungradeable"],
            "hitRate": _rate(matured),
            "highConfidenceHitRate": _rate([row for row in matured if row.get("confidence") == "High"]),
            "neutralResults": sum(1 for row in matured if row.get("verdict") == "neutral"),
            "averageExcessReturn": _average([row.get("excessReturn") for row in matured]),
            "averageBuyDrawdown": _average([
                row.get("maxDrawdown") for row in matured if row.get("action") in BULLISH_ACTIONS
            ]),
        }

    headline = horizons[str(HEADLINE_HORIZON)]
    actionable = [row for row in records if row.get("action") in GRADED_ACTIONS]
    recorded_dates = sorted({row.get("date") for row in records if row.get("date")})
    first_review = None
    if actionable:
        first_date = min((_date(row.get("date")) for row in actionable if _date(row.get("date"))), default=None)
        if first_date:
            first_review = (first_date + dt.timedelta(days=HEADLINE_HORIZON)).isoformat()

    return {
        "modelVersion": MODEL_VERSION,
        "recordedDays": len(recorded_dates),
        "signalsRecorded": len(records),
        "actionableSignals": len(actionable),
        "maturedSignals": headline["maturedSignals"],
        "hitRate": headline["hitRate"],
        "highConfidenceHitRate": headline["highConfidenceHitRate"],
        "averageBuyDrawdown": headline["averageBuyDrawdown"],
        "averageExcessReturn": headline["averageExcessReturn"],
        "firstReviewDate": first_review,
        "horizons": horizons,
        "outcomeSource": coverage,
        "costBandPercent": COST_BAND_PERCENT,
        "journal": "append-only; predictions are never rewritten, replaced or pruned",
        "method": (
            "Benchmark-relative total return against SPY, measured from the archived "
            "split- and dividend-adjusted close one session after each decision. "
            "Results inside the declared cost band count as neither a hit nor a miss."
        ),
        "limitations": (
            "Hit rate is a diagnostic, not a calibration result. Confidence describes "
            "evidence completeness and is not a forecast probability."
            if coverage["status"] == "ready" else
            "No outcomes can be graded yet: the adjusted market-history archive is empty, "
            "so Kestrel reports no result rather than grading itself."
        ),
    }
