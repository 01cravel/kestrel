"""Persistent, fail-closed security identities for Kestrel instruments."""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List

from sec_data import sec_identity


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-security-master.json"
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_SOURCE_URL = "https://www.openfigi.com/api/documentation"
OPENFIGI_BATCH_SIZE = 5
OPENFIGI_REQUEST_GAP_SECONDS = 2.5
CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
SCHEMA_VERSION = 1

FUND_SYMBOLS = {"SPY", "GMOI", "IEMG", "GLD"}
CRYPTO_SYMBOLS = {"BTC"}

_LOCK = threading.RLock()
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_STATE: Dict[str, Any] = {
    "status": "starting",
    "message": "Preparing permanent security identities",
    "updatedAt": None,
    "instruments": {},
}


def _asset_class(symbol: str) -> str:
    if symbol in CRYPTO_SYMBOLS:
        return "crypto"
    if symbol in FUND_SYMBOLS:
        return "fund"
    return "equity"


def _load_cache() -> None:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        instruments = payload.get("instruments")
        if payload.get("schemaVersion") != SCHEMA_VERSION or not isinstance(instruments, dict):
            return
        with _LOCK:
            _STATE["instruments"] = instruments
            _STATE["updatedAt"] = payload.get("updatedAt")
            _STATE["status"] = "cached"
            _STATE["message"] = "Showing saved identities while they are checked"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return


def _save_cache(instruments: Dict[str, Any], updated_at: int) -> None:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "updatedAt": updated_at,
        "instruments": instruments,
    }
    temporary_path = CACHE_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary_path.replace(CACHE_PATH)


def _openfigi(jobs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    global _LAST_REQUEST
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST
        if elapsed < OPENFIGI_REQUEST_GAP_SECONDS:
            time.sleep(OPENFIGI_REQUEST_GAP_SECONDS - elapsed)
        request = urllib.request.Request(
            OPENFIGI_URL,
            data=json.dumps(jobs).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Kestrel local portfolio dashboard",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                _LAST_REQUEST = time.monotonic()
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            _LAST_REQUEST = time.monotonic()
            raise RuntimeError(f"OpenFIGI returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
            _LAST_REQUEST = time.monotonic()
            raise RuntimeError("OpenFIGI identity data was unavailable") from error
    if not isinstance(payload, list) or len(payload) != len(jobs):
        raise RuntimeError("OpenFIGI returned an unexpected identity response")
    return payload


def _fresh(record: Any, now: int) -> bool:
    if not isinstance(record, dict):
        return False
    resolved_at = int(record.get("resolvedAt") or 0)
    return record.get("status") in {"resolved", "partial"} and now - resolved_at < CACHE_MAX_AGE_SECONDS


def _eligible_candidates(symbol: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = result.get("data") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return []
    candidates = [
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("ticker") or "").upper() == symbol
        and row.get("exchCode") == "US"
        and row.get("marketSector") == "Equity"
    ]
    if symbol in FUND_SYMBOLS:
        return [
            row for row in candidates
            if row.get("securityType") == "ETP" or row.get("securityType2") == "Mutual Fund"
        ]
    return [
        row for row in candidates
        if row.get("securityType") != "ETP" and row.get("securityType2") != "Mutual Fund"
    ]


def _crypto_record(symbol: str, now: int) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "name": "Bitcoin",
        "status": "partial",
        "assetClass": "crypto",
        "listing": {"market": "global", "exchangeCode": None, "currency": "USD"},
        "identifiers": {"figi": None, "compositeFigi": None, "shareClassFigi": None, "cik": None, "dti": None},
        "candidateCount": 0,
        "message": "Bitcoin is canonical, but its ISO 24165 Digital Token Identifier is not connected yet.",
        "sources": [{
            "name": "ISO 24165 Digital Token Identifier standard",
            "tier": 1,
            "url": "https://www.iso.org/standard/85546.html",
            "status": "identifier pending",
        }],
        "resolvedAt": now,
    }


def _build_record(symbol: str, result: Dict[str, Any], now: int) -> Dict[str, Any]:
    candidates = _eligible_candidates(symbol, result)
    asset_class = _asset_class(symbol)
    base: Dict[str, Any] = {
        "symbol": symbol,
        "status": "unresolved",
        "assetClass": asset_class,
        "listing": {"market": "US", "exchangeCode": "US", "currency": "USD"},
        "identifiers": {"figi": None, "compositeFigi": None, "shareClassFigi": None, "cik": None},
        "candidateCount": len(candidates),
        "sources": [{
            "name": "OpenFIGI v3 mapping",
            "tier": 2,
            "url": OPENFIGI_SOURCE_URL,
            "retrievedAt": now,
        }],
        "resolvedAt": now,
    }
    if len(candidates) != 1:
        base["status"] = "ambiguous" if len(candidates) > 1 else "unresolved"
        base["message"] = (
            "More than one exact US identity matched; Kestrel refused to guess."
            if len(candidates) > 1
            else "No exact US identity matched; Kestrel refused to guess."
        )
        return base

    match = candidates[0]
    base.update({
        "name": match.get("name"),
        "securityType": match.get("securityType2") or match.get("securityType"),
        "openFigiSecurityType": match.get("securityType"),
        "identifiers": {
            "figi": match.get("figi"),
            "compositeFigi": match.get("compositeFIGI"),
            "shareClassFigi": match.get("shareClassFIGI"),
            "cik": None,
        },
    })

    regulator = None
    if asset_class == "equity":
        try:
            regulator = sec_identity(symbol)
        except RuntimeError:
            regulator = {"status": "error"}
        if regulator.get("status") == "verified":
            base["identifiers"]["cik"] = regulator.get("cik")
            base["sources"].append({
                "name": regulator.get("source"),
                "tier": 1,
                "url": regulator.get("sourceUrl"),
                "retrievedAt": now,
            })

    regulator_ready = asset_class == "fund" or bool(base["identifiers"].get("cik"))
    base["status"] = "resolved" if regulator_ready else "partial"
    base["message"] = (
        "Exact US instrument and regulator identity resolved."
        if regulator_ready and asset_class == "equity"
        else "Exact US fund identity resolved; fund filings require the separate N-PORT layer."
        if regulator_ready
        else "Instrument identity resolved, but a matching SEC regulator identity was not available."
    )
    return base


def _summary(instruments: Dict[str, Any]) -> Dict[str, Any]:
    total = len(instruments)
    resolved = sum(record.get("status") == "resolved" for record in instruments.values())
    partial = sum(record.get("status") == "partial" for record in instruments.values())
    ambiguous = sum(record.get("status") == "ambiguous" for record in instruments.values())
    unresolved = sum(record.get("status") == "unresolved" for record in instruments.values())
    rated = [record for record in instruments.values() if record.get("assetClass") != "crypto"]
    rated_resolved = sum(record.get("status") == "resolved" for record in rated)
    return {
        "total": total,
        "resolved": resolved,
        "partial": partial,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
        "ratingUniverseTotal": len(rated),
        "ratingUniverseResolved": rated_resolved,
        "ratingUniverseClean": bool(rated) and rated_resolved == len(rated),
    }


def security_master_snapshot(symbols: Iterable[str] | None = None) -> Dict[str, Any]:
    with _LOCK:
        records = dict(_STATE["instruments"])
        status = _STATE["status"]
        message = _STATE["message"]
        updated_at = _STATE["updatedAt"]
    if symbols is not None:
        wanted = {str(symbol).upper() for symbol in symbols}
        records = {symbol: record for symbol, record in records.items() if symbol in wanted}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "message": message,
        "updatedAt": updated_at,
        "summary": _summary(records),
        "instruments": records,
    }


def refresh_security_master(symbols: Iterable[str], force: bool = False) -> Dict[str, Any]:
    normalized = list(dict.fromkeys(str(symbol).upper() for symbol in symbols if symbol))
    now = int(time.time())
    with _LOCK:
        existing = dict(_STATE["instruments"])
        _STATE["status"] = "refreshing"
        _STATE["message"] = "Checking stable identifiers, share classes and regulator records"

    records: Dict[str, Any] = {}
    pending: List[str] = []
    for symbol in normalized:
        if symbol in CRYPTO_SYMBOLS:
            records[symbol] = existing.get(symbol) if not force and _fresh(existing.get(symbol), now) else _crypto_record(symbol, now)
        elif not force and _fresh(existing.get(symbol), now):
            records[symbol] = existing[symbol]
        else:
            pending.append(symbol)

    errors: List[str] = []
    for offset in range(0, len(pending), OPENFIGI_BATCH_SIZE):
        batch = pending[offset:offset + OPENFIGI_BATCH_SIZE]
        jobs = [
            {"idType": "TICKER", "idValue": symbol, "exchCode": "US", "marketSecDes": "Equity"}
            for symbol in batch
        ]
        try:
            results = _openfigi(jobs)
            for symbol, result in zip(batch, results):
                records[symbol] = _build_record(symbol, result, now)
        except RuntimeError as error:
            errors.append(str(error))
            for symbol in batch:
                records[symbol] = existing.get(symbol, {
                    "symbol": symbol,
                    "status": "unresolved",
                    "assetClass": _asset_class(symbol),
                    "message": "Identity source unavailable; no identity was guessed.",
                    "resolvedAt": now,
                })

    ordered = {symbol: records[symbol] for symbol in normalized if symbol in records}
    updated_at = int(time.time())
    summary = _summary(ordered)
    final_status = "ready" if not errors else "partial"
    message = (
        f"{summary['ratingUniverseResolved']} of {summary['ratingUniverseTotal']} rated instruments have clean identities"
        if not errors
        else "Some identity checks failed; last known identities were preserved"
    )
    with _LOCK:
        _STATE.update({
            "status": final_status,
            "message": message,
            "updatedAt": updated_at,
            "instruments": ordered,
        })
        try:
            _save_cache(ordered, updated_at)
        except OSError:
            _STATE["status"] = "partial"
            _STATE["message"] = "Identities resolved, but the local security master could not be saved"
    return security_master_snapshot(normalized)


_load_cache()
