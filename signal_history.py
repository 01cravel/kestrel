"""Point-in-time signal journal and simple calibration summaries."""

from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / ".kestrel-signal-history.json"
MODEL_VERSION = "2026.07.1"
VALID_ACTIONS = {"Hold", "Sell", "Buy", "Ultra Buy"}
VALID_CONFIDENCE = {"Low", "Medium", "High"}
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


def record_signals(rows: List[Dict[str, Any]], evidence_timestamp: Any) -> Dict[str, Any]:
    today = dt.date.today().isoformat()
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
        })

    with _LOCK:
        records = _load()
        replacement_keys = {(row["date"], row["symbol"], row["modelVersion"]) for row in clean}
        records = [
            row for row in records
            if (row.get("date"), row.get("symbol"), row.get("modelVersion")) not in replacement_keys
        ]
        records.extend(clean)
        cutoff = dt.date.today() - dt.timedelta(days=8 * 366)
        records = [row for row in records if _date(row.get("date")) and _date(row.get("date")) >= cutoff]
        records.sort(key=lambda row: (row.get("date", ""), row.get("symbol", "")))
        _save(records)
        return calibration_summary(records)


def _date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def calibration_summary(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if records is None:
        with _LOCK:
            records = _load()
    by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for row in records:
        by_symbol.setdefault(str(row.get("symbol")), []).append(row)
    for rows in by_symbol.values():
        rows.sort(key=lambda row: row.get("date", ""))

    outcomes = []
    for row in records:
        if row.get("action") not in {"Buy", "Ultra Buy", "Sell"}:
            continue
        start_date = _date(row.get("date"))
        start_price = _number(row.get("price"))
        if not start_date or not start_price:
            continue
        target_date = start_date + dt.timedelta(days=30)
        candidates = []
        for future in by_symbol.get(str(row.get("symbol")), []):
            future_date = _date(future.get("date"))
            if future_date and target_date <= future_date <= target_date + dt.timedelta(days=15):
                candidates.append((future_date, future))
        if not candidates:
            continue
        _, future = min(candidates, key=lambda item: item[0])
        future_price = _number(future.get("price"))
        if not future_price:
            continue
        change = (future_price - start_price) / start_price * 100
        correct = change > 0 if row.get("action") in {"Buy", "Ultra Buy"} else change < 0
        period_prices = [
            _number(point.get("price")) for point in by_symbol.get(str(row.get("symbol")), [])
            if _date(point.get("date")) and start_date <= _date(point.get("date")) <= target_date
        ]
        period_prices = [price for price in period_prices if price is not None]
        drawdown = ((min(period_prices) - start_price) / start_price * 100) if period_prices else None
        outcomes.append({**row, "return": change, "correct": correct, "drawdown": drawdown})

    actionable = [row for row in records if row.get("action") in {"Buy", "Ultra Buy", "Sell"}]
    recorded_dates = sorted({row.get("date") for row in records if row.get("date")})
    high_outcomes = [row for row in outcomes if row.get("confidence") == "High"]
    buy_outcomes = [row for row in outcomes if row.get("action") in {"Buy", "Ultra Buy"}]
    first_review = None
    if actionable:
        first_date = min((_date(row.get("date")) for row in actionable), default=None)
        if first_date:
            first_review = (first_date + dt.timedelta(days=30)).isoformat()

    def hit_rate(rows: List[Dict[str, Any]]) -> Optional[float]:
        return round(sum(bool(row.get("correct")) for row in rows) / len(rows) * 100, 1) if rows else None

    average_drawdown = None
    drawdowns = [_number(row.get("drawdown")) for row in buy_outcomes]
    drawdowns = [value for value in drawdowns if value is not None]
    if drawdowns:
        average_drawdown = round(sum(drawdowns) / len(drawdowns), 1)

    return {
        "modelVersion": MODEL_VERSION,
        "recordedDays": len(recorded_dates),
        "signalsRecorded": len(records),
        "actionableSignals": len(actionable),
        "maturedSignals": len(outcomes),
        "hitRate": hit_rate(outcomes),
        "highConfidenceHitRate": hit_rate(high_outcomes),
        "averageBuyDrawdown": average_drawdown,
        "firstReviewDate": first_review,
        "method": "30-day directional check using point-in-time daily snapshots",
    }
