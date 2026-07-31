"""Analyst estimate snapshots and consensus targets for Kestrel."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any, Dict, List, Optional

from price_history import FMP_KEY, fmp_json


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else None
    except (TypeError, ValueError):
        return None


def _nearest_estimate(estimates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    today = dt.date.today()
    candidates = []
    for estimate in estimates:
        try:
            fiscal_date = dt.date.fromisoformat(str(estimate.get("date", ""))[:10])
        except ValueError:
            continue
        if fiscal_date >= today - dt.timedelta(days=45):
            candidates.append((fiscal_date, estimate))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def _revision(current: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
    comparable = [
        snapshot for snapshot in history
        if snapshot.get("fiscalDate") == current.get("fiscalDate")
        and snapshot.get("capturedDate") != current.get("capturedDate")
    ]
    if not comparable:
        return {"status": "baseline", "message": "Today establishes the estimate baseline."}
    prior = comparable[-1]

    def change(name: str) -> Optional[float]:
        latest_value = _number(current.get(name))
        prior_value = _number(prior.get(name))
        if latest_value is None or prior_value in (None, 0):
            return None
        return round((latest_value - prior_value) / abs(prior_value) * 100, 2)

    eps_change = change("epsAverage")
    revenue_change = change("revenueAverage")
    changes = [value for value in (eps_change, revenue_change) if value is not None]
    direction = "unchanged"
    if changes and sum(changes) / len(changes) >= 1:
        direction = "up"
    elif changes and sum(changes) / len(changes) <= -1:
        direction = "down"
    return {
        "status": "compared",
        "direction": direction,
        "epsChangePercent": eps_change,
        "revenueChangePercent": revenue_change,
        "priorCapturedDate": prior.get("capturedDate"),
    }


def fetch_analyst_intelligence(
    symbol: str,
    previous_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    fetched_at = int(time.time())
    if not FMP_KEY:
        return {
            "status": "error",
            "message": "An FMP API key is required for estimate tracking.",
            "fetchedAt": fetched_at,
        }
    try:
        estimates = fmp_json(
            "analyst-estimates",
            {"symbol": symbol, "period": "annual", "page": "0", "limit": "10"},
        )
        targets = fmp_json("price-target-consensus", {"symbol": symbol})
        estimate = _nearest_estimate(estimates if isinstance(estimates, list) else [])
        target = targets[0] if isinstance(targets, list) and targets else {}
        history = list(previous_history or [])[-30:]
        snapshot = None
        revision = {"status": "unavailable", "message": "No current analyst estimate was returned."}
        if estimate:
            snapshot = {
                "capturedDate": dt.date.today().isoformat(),
                "fiscalDate": str(estimate.get("date", ""))[:10],
                "epsAverage": _number(estimate.get("epsAvg")),
                "epsLow": _number(estimate.get("epsLow")),
                "epsHigh": _number(estimate.get("epsHigh")),
                "revenueAverage": _number(estimate.get("revenueAvg")),
                "revenueLow": _number(estimate.get("revenueLow")),
                "revenueHigh": _number(estimate.get("revenueHigh")),
                "epsAnalysts": int(_number(estimate.get("numAnalystsEps")) or 0),
                "revenueAnalysts": int(_number(estimate.get("numAnalystsRevenue")) or 0),
            }
            revision = _revision(snapshot, history)
            history = [item for item in history if item.get("capturedDate") != snapshot["capturedDate"]]
            history.append(snapshot)

        return {
            "status": "ready" if snapshot or target else "partial",
            "estimate": snapshot,
            "estimateRevision": revision,
            "estimateHistory": history,
            "priceTarget": {
                "low": _number(target.get("targetLow")),
                "median": _number(target.get("targetMedian")),
                "consensus": _number(target.get("targetConsensus")),
                "high": _number(target.get("targetHigh")),
            } if target else None,
            "source": "Financial Modeling Prep analyst consensus",
            "fetchedAt": fetched_at,
        }
    except RuntimeError as error:
        return {
            "status": "error",
            "message": str(error),
            "estimateHistory": list(previous_history or [])[-30:],
            "fetchedAt": fetched_at,
        }
