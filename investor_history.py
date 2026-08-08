"""Append-only outcome journal for manager-disclosed equity ideas.

Ideas and their daily observations are appended and never rewritten or pruned.
Manager skill is judged only on outcomes the adjusted market-history archive can
verify independently; observation snapshots recorded by Kestrel itself remain
visible as provisional and never count toward validation.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from outcome_source import STATUS_MATURED, shared_source, verdict


ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / ".kestrel-investor-history.json"
MODEL_VERSION = "2026.08.2"
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
            observations = list(record.get("observations") or [])
            if any(item.get("date") == today for item in observations):
                continue
            observations.append(row["observation"])
            observations.sort(key=lambda item: str(item.get("date") or ""))
            record["observations"] = observations

        _save(records)
        return investor_calibration_summary(records)


def _outcome(record: Dict[str, Any], days: int) -> Optional[Dict[str, Any]]:
    """Prefer the independent archive; fall back to Kestrel's own snapshots.

    A snapshot-based result is returned so nothing disappears from view, but it
    carries ``source: "journal-snapshot"`` and is excluded from validation
    because its prices are unadjusted and Kestrel recorded them itself.
    """
    observations = sorted(record.get("observations") or [], key=lambda row: str(row.get("date") or ""))
    if not observations:
        return None
    first_date = _date(observations[0].get("date"))
    symbol = str(record.get("symbol") or "")
    if first_date and symbol:
        archived = shared_source().outcome(symbol, first_date, days)
        if archived["status"] == STATUS_MATURED:
            return {
                "stockReturn": archived["stockReturn"],
                "benchmarkReturn": archived["benchmarkReturn"],
                "excessReturn": archived["excessReturn"],
                "maxDrawdown": archived["maxDrawdown"],
                "verdict": archived["verdict"],
                "source": "archive",
            }

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
        "maxDrawdown": None,
        "verdict": verdict(stock_return - benchmark_return),
        "source": "journal-snapshot",
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

    def verified(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [row for row in rows if row.get("source") == "archive"]

    public_managers = []
    for manager in managers.values():
        year = verified(manager["outcomes"]["365"])
        provisional = len(manager["outcomes"]["365"]) - len(year)
        decided = [item for item in year if item.get("verdict") != "neutral"]
        average_excess = round(sum(item["excessReturn"] for item in year) / len(year), 2) if year else None
        hit_rate = round(sum(item["excessReturn"] > 0 for item in decided) / len(decided) * 100, 1) if decided else None
        public_managers.append({
            "id": manager["id"],
            "name": manager["name"],
            "ideasRecorded": manager["ideasRecorded"],
            "matured90": len(verified(manager["outcomes"]["90"])),
            "matured180": len(verified(manager["outcomes"]["180"])),
            "matured365": len(year),
            "provisional365": provisional,
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
        "outcomeSource": shared_source().coverage(),
        "journal": "append-only; ideas and observations are never rewritten or pruned",
        "method": (
            "New and increased 13F positions measured against SPY after 90, 180 and 365 days "
            "using archived split- and dividend-adjusted closes, entered one session after the "
            "first Kestrel observation."
        ),
        "limitations": (
            "Only archive-verified outcomes count toward validation. Results shown as "
            "provisional came from Kestrel's own unadjusted snapshots and prove nothing."
        ),
    }
