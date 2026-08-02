"""Private, read-only Sarwa snapshot staging and reconciliation."""

from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / ".kestrel-sarwa-sync.json"
BACKUP_PATH = ROOT / ".kestrel-sarwa-sync-backup.json"
TEMP_PATH = ROOT / ".kestrel-sarwa-sync.tmp"
STATE_LOCK = threading.Lock()
ALLOWED_SOURCES = {"sarwa_web", "sarwa_statement"}


def _empty_state() -> Dict[str, Any]:
    return {
        "lastSuccessfulSync": None,
        "lastSource": None,
        "lastAccountTypes": [],
        "lastHoldingCount": None,
        "pending": None,
        "history": [],
    }


def _load_unlocked() -> Dict[str, Any]:
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {**_empty_state(), **payload} if isinstance(payload, dict) else _empty_state()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return _empty_state()


def _save_unlocked(payload: Dict[str, Any]) -> None:
    if STATE_PATH.exists():
        try:
            BACKUP_PATH.write_text(STATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass
    TEMP_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    TEMP_PATH.replace(STATE_PATH)


def _number(value: Any, label: str, allow_zero: bool = False) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{label} must be a finite number")
    if parsed < 0 or (not allow_zero and parsed == 0):
        raise ValueError(f"{label} must be positive")
    return parsed


def _clean_snapshot(raw_snapshot: Any, allowed_symbols: Iterable[str]) -> Dict[str, Any]:
    if not isinstance(raw_snapshot, dict):
        raise ValueError("Sarwa snapshot must be an object")
    source = str(raw_snapshot.get("source") or "").strip()
    if source not in ALLOWED_SOURCES:
        raise ValueError("Sarwa snapshot source must be the web account or an official statement")

    allowed = set(allowed_symbols)
    raw_positions = raw_snapshot.get("positions")
    if not isinstance(raw_positions, dict) or not raw_positions:
        raise ValueError("Sarwa snapshot did not contain any positions")

    positions: Dict[str, Dict[str, Any]] = {}
    unsupported: List[str] = []
    for raw_symbol, raw_position in raw_positions.items():
        symbol = str(raw_symbol).strip().upper()
        if not isinstance(raw_position, dict):
            raise ValueError(f"{symbol or 'A position'} has an invalid shape")
        if symbol not in allowed:
            unsupported.append(symbol)
            continue
        shares = _number(raw_position.get("shares"), f"{symbol} shares")
        raw_cost = raw_position.get("cost")
        cost = _number(raw_cost, f"{symbol} average cost") if raw_cost not in (None, "") else None
        raw_market_value = raw_position.get("marketValue")
        market_value = _number(raw_market_value, f"{symbol} market value", allow_zero=True) if raw_market_value not in (None, "") else None
        positions[symbol] = {
            "shares": round(shares, 8),
            "cost": round(cost, 8) if cost is not None else None,
            "marketValue": round(market_value, 2) if market_value is not None else None,
        }

    account_types = raw_snapshot.get("accountTypes") or []
    if not isinstance(account_types, list):
        raise ValueError("Sarwa account types must be a list")
    account_types = sorted({str(value).strip() for value in account_types if str(value).strip()})
    currency = str(raw_snapshot.get("currency") or "USD").strip().upper()
    if len(currency) != 3:
        raise ValueError("Sarwa snapshot currency must use a three-letter code")
    cash_value = raw_snapshot.get("cash")
    cash = _number(cash_value, "Sarwa cash", allow_zero=True) if cash_value not in (None, "") else None
    account_value_raw = raw_snapshot.get("accountValue")
    account_value = _number(account_value_raw, "Sarwa account value", allow_zero=True) if account_value_raw not in (None, "") else None

    return {
        "source": source,
        "capturedAt": int(raw_snapshot.get("capturedAt") or time.time()),
        "accountTypes": account_types,
        "currency": currency,
        "cash": round(cash, 2) if cash is not None else None,
        "accountValue": round(account_value, 2) if account_value is not None else None,
        "positions": positions,
        "unsupportedSymbols": sorted(set(unsupported)),
    }


def _different(left: Any, right: Any, tolerance: float) -> bool:
    if left is None and right is None:
        return False
    if left is None or right is None:
        return True
    return abs(float(left) - float(right)) > tolerance


def _reconcile(snapshot: Dict[str, Any], current_positions: Dict[str, Any]) -> Dict[str, Any]:
    incoming = snapshot["positions"]
    added = []
    removed = []
    changed = []
    unchanged = 0

    for symbol in sorted(set(current_positions) | set(incoming)):
        current = current_positions.get(symbol)
        next_position = incoming.get(symbol)
        if current is None and next_position is not None:
            added.append({"symbol": symbol, "shares": next_position["shares"], "cost": next_position.get("cost")})
            continue
        if next_position is None and current is not None:
            removed.append({"symbol": symbol, "shares": current.get("shares"), "cost": current.get("cost")})
            continue
        shares_changed = _different(current.get("shares"), next_position.get("shares"), 0.000001)
        cost_changed = _different(current.get("cost"), next_position.get("cost"), 0.01)
        if shares_changed or cost_changed:
            changed.append({
                "symbol": symbol,
                "sharesFrom": current.get("shares"),
                "sharesTo": next_position.get("shares"),
                "costFrom": current.get("cost"),
                "costTo": next_position.get("cost"),
            })
        else:
            unchanged += 1

    warnings = []
    if snapshot["unsupportedSymbols"]:
        warnings.append("Some Sarwa symbols are not yet supported by Kestrel.")
    if not incoming:
        warnings.append("No supported positions were found.")
    reported_value = snapshot.get("accountValue")
    visible_values = [position.get("marketValue") for position in incoming.values()]
    if reported_value is not None and visible_values and all(value is not None for value in visible_values):
        calculated = sum(visible_values) + (snapshot.get("cash") or 0)
        difference = abs(calculated - reported_value)
        if reported_value and difference / reported_value > 0.01:
            warnings.append("Visible positions and cash do not match Sarwa’s reported account value.")

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "warningCount": len(warnings),
        "warnings": warnings,
        "requiresReview": bool(added or removed or changed or warnings),
    }


def stage_snapshot(raw_snapshot: Any, current_positions: Dict[str, Any], allowed_symbols: Iterable[str]) -> Dict[str, Any]:
    snapshot = _clean_snapshot(raw_snapshot, allowed_symbols)
    for symbol, position in snapshot["positions"].items():
        current = current_positions.get(symbol)
        if position.get("cost") is None and isinstance(current, dict) and current.get("cost") is not None:
            position["cost"] = current.get("cost")
    reconciliation = _reconcile(snapshot, current_positions)
    pending = {
        "snapshot": snapshot,
        "reconciliation": reconciliation,
        "stagedAt": int(time.time()),
        "canApply": not reconciliation["warnings"] and bool(snapshot["positions"]),
    }
    with STATE_LOCK:
        state = _load_unlocked()
        state["pending"] = pending
        _save_unlocked(state)
    return pending


def connection_status(current_holding_count: int) -> Dict[str, Any]:
    with STATE_LOCK:
        state = _load_unlocked()
    pending = state.get("pending")
    if pending:
        status = "review_required"
    elif state.get("lastSuccessfulSync"):
        status = "connected"
    else:
        status = "not_connected"
    return {
        "status": status,
        "mode": "read_only",
        "lastSuccessfulSync": state.get("lastSuccessfulSync"),
        "lastSource": state.get("lastSource"),
        "lastAccountTypes": state.get("lastAccountTypes") or [],
        "lastHoldingCount": state.get("lastHoldingCount"),
        "currentHoldingCount": current_holding_count,
        "pending": pending,
    }


def pending_positions() -> Dict[str, Dict[str, Any]]:
    with STATE_LOCK:
        state = _load_unlocked()
    pending = state.get("pending")
    if not pending:
        raise ValueError("There is no Sarwa snapshot waiting for review")
    if not pending.get("canApply"):
        raise ValueError("The Sarwa snapshot has unresolved warnings")
    return {
        symbol: {"shares": position["shares"], "cost": position.get("cost")}
        for symbol, position in pending["snapshot"]["positions"].items()
    }


def mark_applied() -> Dict[str, Any]:
    with STATE_LOCK:
        state = _load_unlocked()
        pending = state.get("pending")
        if not pending:
            raise ValueError("There is no Sarwa snapshot waiting for review")
        snapshot = pending["snapshot"]
        now = int(time.time())
        state["lastSuccessfulSync"] = now
        state["lastSource"] = snapshot.get("source")
        state["lastAccountTypes"] = snapshot.get("accountTypes") or []
        state["lastHoldingCount"] = len(snapshot.get("positions") or {})
        history = list(state.get("history") or [])
        history.append({
            "syncedAt": now,
            "capturedAt": snapshot.get("capturedAt"),
            "source": snapshot.get("source"),
            "holdingCount": len(snapshot.get("positions") or {}),
            "reconciliation": pending.get("reconciliation"),
        })
        state["history"] = history[-90:]
        state["pending"] = None
        _save_unlocked(state)
    return state


def discard_pending() -> None:
    with STATE_LOCK:
        state = _load_unlocked()
        state["pending"] = None
        _save_unlocked(state)
