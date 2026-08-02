"""Point-in-time outcome journal for manager-disclosed equity ideas."""

from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / ".kestrel-investor-history.json"
MODEL_VERSION = "2026.08.1"
REVIEW_DAYS = (90, 180, 365)
MINIMUM_VALIDATED_IDEAS = 10
_LOCK = threading.Lock()


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed == parsed and parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _load() -> List[Dict[str, Any]]:
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _save(records: List[Dict[str, Any]]) -> None:
    temporary = HISTORY_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(HISTORY_PATH)


def record_investor_ideas(rows: List[Dict[str, Any]], benchmark_price: Any) -> Dict[str, Any]:
    """Save the original public idea and add today's unbiased price observation."""
    today = dt.date.today().isoformat()
    benchmark = _number(benchmark_price)
    if not benchmark:
        raise ValueError("A verified SPY price is required")

    clean: List[Dict[str, Any]] = []
    for row in rows[:100]:
        symbol = str(row.get("symbol") or "").upper()
        price = _number(row.get("price"))
        managers = row.get("managers")
        if not symbol or not price or not isinstance(managers, list):
            continue
        for manager in managers[:25]:
            manager_id = str(manager.get("id") or "")
            action = str(manager.get("action") or "")
            period_end = _date(manager.get("periodEnd") or row.get("periodEnd"))
            if not manager_id or not period_end or action not in {"New", "Increased", "Held", "Reduced"}:
                continue
            clean.append({
                "managerId": manager_id,
                "managerName": str(manager.get("name") or manager_id)[:120],
                "symbol": symbol,
                "periodEnd": period_end.isoformat(),
                "filedAt": str(manager.get("filedAt") or ""),
                "action": action,
                "portfolioWeight": _number(manager.get("portfolioWeight")),
                "observation": {"date": today, "price": price, "benchmarkPrice": benchmark},
            })

    with _LOCK:
        records = _load()
        by_key = {
            (str(item.get("managerId")), str(item.get("symbol")), str(item.get("periodEnd"))): item
            for item in records
        }
        for row in clean:
            key = (row["managerId"], row["symbol"], row["periodEnd"])
            record = by_key.get(key)
            if not record:
                record = {
                    **{name: value for name, value in row.items() if name != "observation"},
                    "recordedAt": today,
                    "modelVersion": MODEL_VERSION,
                    "observations": [],
                }
                records.append(record)
                by_key[key] = record
            observations = [item for item in record.get("observations", []) if item.get("date") != today]
            observations.append(row["observation"])
            observations.sort(key=lambda item: str(item.get("date") or ""))
            record["observations"] = observations

        cutoff = dt.date.today() - dt.timedelta(days=8 * 366)
        records = [row for row in records if _date(row.get("recordedAt")) and _date(row.get("recordedAt")) >= cutoff]
        _save(records)
        return investor_calibration_summary(records)


def _outcome(record: Dict[str, Any], days: int) -> Optional[Dict[str, float]]:
    observations = sorted(record.get("observations") or [], key=lambda row: str(row.get("date") or ""))
    if not observations:
        return None
    start = observations[0]
    start_date = _date(start.get("date"))
    start_price = _number(start.get("price"))
    start_benchmark = _number(start.get("benchmarkPrice"))
    if not start_date or not start_price or not start_benchmark:
        return None
    target = start_date + dt.timedelta(days=days)
    candidates = [
        row for row in observations
        if _date(row.get("date")) and target <= _date(row.get("date")) <= target + dt.timedelta(days=30)
    ]
    if not candidates:
        return None
    finish = min(candidates, key=lambda row: _date(row.get("date")))
    finish_price = _number(finish.get("price"))
    finish_benchmark = _number(finish.get("benchmarkPrice"))
    if not finish_price or not finish_benchmark:
        return None
    stock_return = (finish_price / start_price - 1) * 100
    benchmark_return = (finish_benchmark / start_benchmark - 1) * 100
    return {
        "stockReturn": round(stock_return, 2),
        "benchmarkReturn": round(benchmark_return, 2),
        "excessReturn": round(stock_return - benchmark_return, 2),
    }


def investor_calibration_summary(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if records is None:
        with _LOCK:
            records = _load()
    managers: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if record.get("action") not in {"New", "Increased"}:
            continue
        bucket = managers.setdefault(str(record.get("managerId")), {
            "id": str(record.get("managerId")),
            "name": str(record.get("managerName") or record.get("managerId")),
            "ideasRecorded": 0,
            "outcomes": {str(days): [] for days in REVIEW_DAYS},
        })
        bucket["ideasRecorded"] += 1
        for days in REVIEW_DAYS:
            outcome = _outcome(record, days)
            if outcome:
                bucket["outcomes"][str(days)].append(outcome)

    public_managers = []
    for manager in managers.values():
        year = manager["outcomes"]["365"]
        average_excess = round(sum(item["excessReturn"] for item in year) / len(year), 2) if year else None
        hit_rate = round(sum(item["excessReturn"] > 0 for item in year) / len(year) * 100, 1) if year else None
        public_managers.append({
            "id": manager["id"],
            "name": manager["name"],
            "ideasRecorded": manager["ideasRecorded"],
            "matured90": len(manager["outcomes"]["90"]),
            "matured180": len(manager["outcomes"]["180"]),
            "matured365": len(year),
            "averageExcessReturn365": average_excess,
            "hitRate365": hit_rate,
            "validated": len(year) >= MINIMUM_VALIDATED_IDEAS,
        })
    public_managers.sort(key=lambda item: (-item["matured365"], item["name"]))
    return {
        "modelVersion": MODEL_VERSION,
        "status": "validated" if any(item["validated"] for item in public_managers) else "building",
        "ideasRecorded": sum(item["ideasRecorded"] for item in public_managers),
        "minimumValidatedIdeas": MINIMUM_VALIDATED_IDEAS,
        "managers": public_managers,
        "method": "New and increased 13F positions measured from the first Kestrel observation against SPY after 90, 180 and 365 days.",
    }
