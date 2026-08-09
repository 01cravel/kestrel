"""Deterministic, fail-closed selection from a frozen universe snapshot.

The long-term portfolio originally began with eight companies chosen by hand.
This module makes the next candidate auditable: it reads only evidence retained
inside one immutable universe snapshot, rejects incomplete identities and
conflicting filings, ranks sufficiently covered companies, and records exactly
which frozen evidence produced the result.  It never promotes the candidate;
the existing valuation, risk and walk-forward gates retain that authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SELECTION_VERSION = "frozen-universe-company-selection-v1"
COMPANY_SLOTS = 8
COMPANY_WEIGHTS = (6.0, 6.0, 5.0, 5.0, 5.0, 4.0, 4.0, 3.0)
FOUNDATION_WEIGHTS = {
    "VTI": 20.0, "AVUV": 8.0, "VEA": 7.0,
    "IEMG": 7.0, "AVDV": 5.0, "PAVE": 5.0,
}
OTHER_WEIGHTS = {"IBIT": 8.0, "SGOV": 2.0}
NON_COMPANIES = {*FOUNDATION_WEIGHTS, *OTHER_WEIGHTS, "SPY", "VT", "GLD", "BTC", "GMOI"}
MINIMUM_DESCRIPTORS = 6


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _first(mapping: Dict[str, Any], names: Iterable[str]) -> Optional[float]:
    for name in names:
        value = _number(mapping.get(name))
        if value is not None:
            return value
    return None


def _percentiles(rows: Sequence[Dict[str, Any]], key: str, reverse: bool = False) -> Dict[str, float]:
    available = sorted(
        ((row["symbol"], row.get(key)) for row in rows if _number(row.get(key)) is not None),
        key=lambda item: (float(item[1]), item[0]),
        reverse=reverse,
    )
    if not available:
        return {}
    if len(available) == 1:
        return {available[0][0]: 50.0}
    return {
        symbol: index / (len(available) - 1) * 100.0
        for index, (symbol, _value) in enumerate(available)
    }


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return sum(present) / len(present) if present else None


def _parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default
    return parsed


def _blocked(reason: str, frozen: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": "blocked",
        "selectionVersion": SELECTION_VERSION,
        "reason": reason,
        "snapshotId": (frozen or {}).get("snapshotId"),
        "manifestHash": (frozen or {}).get("manifestHash"),
        "selected": [],
        "weights": {},
        "promotionReady": False,
    }


def select_frozen_candidate(frozen: Dict[str, Any]) -> Dict[str, Any]:
    """Select eight companies using only one verified frozen information set."""
    if not isinstance(frozen, dict) or frozen.get("status") != "verified":
        return _blocked("No cryptographically verified frozen universe is available.", frozen)
    manifest = frozen.get("manifest") or {}
    controls = manifest.get("controls") or {}
    if controls.get("selectionPolicyFrozen") is not True:
        return _blocked("The universe selection policy was not frozen before scoring.", frozen)

    evidence_by_symbol: Dict[str, Dict[str, Any]] = {}
    evidence_hashes: Dict[str, str] = {}
    for row in frozen.get("evidence") or []:
        if row.get("category") != "live_symbol_evidence":
            continue
        symbol = str(row.get("record_key") or row.get("recordKey") or "").upper()
        payload = _parse_json(row.get("payload_json") or row.get("payload"), {})
        if symbol and isinstance(payload, dict):
            evidence_by_symbol[symbol] = payload
            evidence_hashes[symbol] = str(row.get("payload_hash") or row.get("payloadHash") or "")

    eligible: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, str]] = []
    for member in frozen.get("members") or []:
        symbol = str(member.get("ticker") or "").upper()
        if symbol in NON_COMPANIES:
            continue
        verified = bool(member.get("included") and member.get("active")
                        and member.get("identity_clean") and member.get("membership_verified"))
        if not verified:
            exclusions.append({"symbol": symbol, "reason": "identity or listing membership is incomplete"})
            continue
        payload = evidence_by_symbol.get(symbol)
        if not payload:
            exclusions.append({"symbol": symbol, "reason": "no frozen company evidence"})
            continue
        if _number((payload.get("sec") or {}).get("conflictCount")) not in {None, 0.0}:
            exclusions.append({"symbol": symbol, "reason": "official filing evidence conflicts"})
            continue
        quote = payload.get("quote") or {}
        metrics = payload.get("metrics") or {}
        price = _number(quote.get("c"))
        if price is None or price <= 0:
            exclusions.append({"symbol": symbol, "reason": "no positive price at the cutoff"})
            continue
        pe = _first(metrics, ("peTTM", "peNormalizedAnnual"))
        book = _first(metrics, ("pbQuarterly", "pbAnnual"))
        roe = _first(metrics, ("roeTTM", "roeRfy"))
        margin = _first(metrics, ("netProfitMarginTTM", "netProfitMarginAnnual"))
        leverage = _first(metrics, ("totalDebt/totalEquityQuarterly", "totalDebt/totalEquityAnnual"))
        six_month = _first(metrics, ("26WeekPriceReturnDaily",))
        one_year = _first(metrics, ("52WeekPriceReturnDaily",))
        volatility = _first(metrics, ("3MonthADReturnStd",))
        descriptors = [pe, book, roe, margin, leverage, six_month, one_year, volatility]
        coverage = sum(value is not None for value in descriptors)
        if coverage < MINIMUM_DESCRIPTORS:
            exclusions.append({"symbol": symbol, "reason": f"only {coverage} of 8 required descriptors"})
            continue
        profile = payload.get("profile") or {}
        eligible.append({
            "symbol": symbol,
            "securityId": member.get("security_id") or member.get("securityId"),
            "name": str(profile.get("name") or symbol),
            "sector": str(profile.get("finnhubIndustry") or "Unclassified"),
            "price": price,
            "pe": pe if pe and pe > 0 else None,
            "book": book if book and book > 0 else None,
            "roe": roe,
            "margin": margin,
            "leverage": leverage,
            "sixMonth": six_month,
            "oneYear": one_year,
            "volatility": volatility if volatility and volatility > 0 else None,
            "coverage": coverage,
            "evidenceHash": evidence_hashes.get(symbol),
        })

    if len(eligible) < COMPANY_SLOTS:
        result = _blocked(
            f"Only {len(eligible)} companies have complete enough frozen evidence; {COMPANY_SLOTS} are required.",
            frozen,
        )
        result.update({"eligibleCount": len(eligible), "excluded": exclusions})
        return result

    value_pe = _percentiles(eligible, "pe", reverse=True)
    value_book = _percentiles(eligible, "book", reverse=True)
    quality_roe = _percentiles(eligible, "roe")
    quality_margin = _percentiles(eligible, "margin")
    quality_leverage = _percentiles(eligible, "leverage", reverse=True)
    momentum_six = _percentiles(eligible, "sixMonth")
    momentum_year = _percentiles(eligible, "oneYear")
    volatility = _percentiles(eligible, "volatility", reverse=True)

    for row in eligible:
        symbol = row["symbol"]
        value = _mean((value_pe.get(symbol), value_book.get(symbol)))
        quality = _mean((quality_roe.get(symbol), quality_margin.get(symbol), quality_leverage.get(symbol)))
        momentum = _mean((momentum_six.get(symbol), momentum_year.get(symbol), volatility.get(symbol)))
        score = _mean((value, quality, momentum))
        row.update({
            "score": round(score or 0.0, 2),
            "valueScore": round(value or 0.0, 2),
            "qualityScore": round(quality or 0.0, 2),
            "momentumScore": round(momentum or 0.0, 2),
        })

    ranked = sorted(eligible, key=lambda row: (-row["score"], row["symbol"]))
    selected = ranked[:COMPANY_SLOTS]
    for row, weight in zip(selected, COMPANY_WEIGHTS):
        row["weight"] = weight
        row["reason"] = (
            f"Ranked {row['score']:.1f}/100 across price, business quality and recent direction "
            f"using {row['coverage']} of 8 frozen descriptors."
        )
    weights = {**FOUNDATION_WEIGHTS, **{row["symbol"]: row["weight"] for row in selected}, **OTHER_WEIGHTS}
    selection_record = {
        "selectionVersion": SELECTION_VERSION,
        "snapshotId": frozen.get("snapshotId"),
        "manifestHash": frozen.get("manifestHash"),
        "cutoffUtc": frozen.get("cutoffUtc"),
        "weights": weights,
        "selected": [{key: row.get(key) for key in (
            "symbol", "securityId", "name", "sector", "weight", "score", "valueScore",
            "qualityScore", "momentumScore", "coverage", "evidenceHash", "reason",
        )} for row in selected],
    }
    return {
        "status": "selected",
        **selection_record,
        "candidateHash": _digest(selection_record),
        "eligibleCount": len(eligible),
        "excluded": exclusions,
        "promotionReady": False,
        "message": "A new research candidate was selected from frozen evidence; existing promotion gates still apply.",
    }


def candidate_from_latest(latest: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(latest, dict) or latest.get("status") != "ready":
        return _blocked("The universe ledger has not frozen a usable market snapshot yet.")
    return select_frozen_candidate(latest.get("latest") or {})
