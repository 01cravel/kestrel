"""Fail-closed forward event radar with optional live SEC filing checks."""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
DEFAULT_WATCH_PATH = ROOT / "catalyst_watch.json"
STAGES = ("possible", "developing", "imminent", "confirmed")
EVIDENCE_STATUSES = {"verified", "provisional"}
MATERIAL_FORMS = {"8-K", "6-K", "SC 13D", "SC 13D/A", "SC TO-T", "SC TO-T/A", "PREM14A", "DEFA14A", "S-4", "425"}
LIVE_CACHE_SECONDS = 5 * 60
_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"savedAt": 0.0, "stamp": None, "payload": None}


def _iso(value: Any) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _source_is_valid(source: Any) -> bool:
    return isinstance(source, dict) and bool(source.get("name")) and str(source.get("url") or "").startswith("https://")


def _clean_case(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    symbol = str(raw.get("symbol") or "").strip().upper()
    current_stage = str(raw.get("currentStage") or "")
    timeline = raw.get("timeline")
    if not symbol or current_stage not in STAGES or not isinstance(timeline, list) or not timeline:
        return None

    cleaned_timeline: List[Dict[str, Any]] = []
    last_stage = -1
    for raw_item in timeline:
        if not isinstance(raw_item, dict):
            return None
        stage = str(raw_item.get("stage") or "")
        stage_index = STAGES.index(stage) if stage in STAGES else -1
        published = _iso(raw_item.get("publishedAt"))
        evidence_status = str(raw_item.get("evidenceStatus") or "")
        if (stage_index < last_stage or published is None or evidence_status not in EVIDENCE_STATUSES
                or not _source_is_valid(raw_item.get("source"))):
            return None
        last_stage = stage_index
        cleaned_timeline.append({
            "stage": stage,
            "publishedAt": raw_item["publishedAt"],
            "headline": str(raw_item.get("headline") or "Evidence update"),
            "detail": str(raw_item.get("detail") or ""),
            "evidenceStatus": evidence_status,
            "accessionNumber": raw_item.get("accessionNumber"),
            "source": dict(raw_item["source"]),
        })

    verified = [item for item in cleaned_timeline if item["evidenceStatus"] == "verified"]
    if not verified or verified[-1]["stage"] != current_stage:
        return None
    return {
        "id": str(raw.get("id") or symbol.lower()),
        "symbol": symbol,
        "name": str(raw.get("name") or symbol),
        "cik": str(raw.get("cik") or "").zfill(10),
        "category": str(raw.get("category") or "Event"),
        "currentStage": current_stage,
        "headline": str(raw.get("headline") or cleaned_timeline[-1]["headline"]),
        "plainEnglish": str(raw.get("plainEnglish") or ""),
        "whatWasKnowable": str(raw.get("whatWasKnowable") or ""),
        "whatWasNotKnowable": str(raw.get("whatWasNotKnowable") or ""),
        "marketAccess": str(raw.get("marketAccess") or ""),
        "monitorSince": raw.get("monitorSince"),
        "researchOnly": True,
        "firstPublicAt": verified[0]["publishedAt"],
        "lastVerifiedAt": verified[-1]["publishedAt"],
        "timeline": cleaned_timeline,
    }


def _load_cases(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "empty", "updatedAt": None, "cases": [], "invalidCases": 0}
    raw_cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(raw_cases, list):
        return {"status": "empty", "updatedAt": None, "cases": [], "invalidCases": 0}
    cases = [case for item in raw_cases if (case := _clean_case(item)) is not None]
    return {
        "status": "ready" if cases else "empty",
        "updatedAt": raw.get("updatedAt"),
        "cases": cases,
        "invalidCases": len(raw_cases) - len(cases),
    }


def _sec_url(cik: str, accession: str, primary_document: str) -> str:
    return "https://www.sec.gov/Archives/edgar/data/%s/%s/%s" % (
        int(cik), accession.replace("-", ""), primary_document,
    )


def _live_sec(case: Dict[str, Any], opener: Callable[..., Any] = urllib.request.urlopen) -> Dict[str, Any]:
    cik = case.get("cik")
    if not cik or not str(cik).isdigit():
        return {"status": "not_configured", "checkedAt": None, "newFilings": []}
    user_agent = os.environ.get("SEC_USER_AGENT", "Kestrel local catalyst watch research").strip()
    request = urllib.request.Request(
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        headers={"Accept": "application/json", "User-Agent": user_agent},
    )
    checked_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        with opener(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "unavailable", "checkedAt": checked_at, "newFilings": []}

    recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload, dict) else {}
    keys = ("form", "accessionNumber", "primaryDocument", "acceptanceDateTime")
    if not all(isinstance(recent.get(key), list) for key in keys):
        return {"status": "unavailable", "checkedAt": checked_at, "newFilings": []}
    known = {item.get("accessionNumber") for item in case.get("timeline", []) if item.get("accessionNumber")}
    thresholds = [value for value in (
        _iso(case.get("monitorSince")), _iso(case.get("lastVerifiedAt")),
    ) if value is not None]
    since = max(thresholds) if thresholds else None
    filings = []
    for form, accession, document, accepted in zip(*(recent[key] for key in keys)):
        accepted_at = _iso(accepted)
        if form not in MATERIAL_FORMS or accession in known or not accepted_at or (since and accepted_at < since):
            continue
        filings.append({
            "form": form, "accessionNumber": accession, "acceptedAt": accepted,
            "url": _sec_url(str(cik), accession, document),
            "autoEscalated": False,
        })
    filings.sort(key=lambda item: item["acceptedAt"], reverse=True)
    return {"status": "checked", "checkedAt": checked_at, "newFilings": filings[:5]}


def build_catalyst_watch(path: Path = DEFAULT_WATCH_PATH, live: bool = True,
                         opener: Callable[..., Any] = urllib.request.urlopen) -> Dict[str, Any]:
    loaded = _load_cases(Path(path))
    cases = loaded["cases"]
    if live:
        for case in cases:
            case["liveSec"] = _live_sec(case, opener)
    else:
        for case in cases:
            case["liveSec"] = {"status": "disabled", "checkedAt": None, "newFilings": []}
    counts = {stage: sum(1 for case in cases if case["currentStage"] == stage) for stage in STAGES}
    return {
        **loaded,
        "counts": counts,
        "stages": list(STAGES),
        "message": "Public evidence is escalated without predicting direction or trading automatically.",
        "feedCoverage": [
            "Live SEC material filings for tracked U.S. issuers",
            "Timestamped issuer, regulator and credible-news evidence stored in each case",
            "No automatic promotion from an unverified report",
        ],
        "researchOnly": True,
    }


def catalyst_watch_snapshot(path: Path = DEFAULT_WATCH_PATH) -> Dict[str, Any]:
    path = Path(path)
    stamp = path.stat().st_mtime_ns if path.exists() else None
    now = time.monotonic()
    with _CACHE_LOCK:
        if (_CACHE["payload"] is not None and _CACHE["stamp"] == stamp
                and now - float(_CACHE["savedAt"]) < LIVE_CACHE_SECONDS):
            return _CACHE["payload"]
    payload = build_catalyst_watch(path)
    with _CACHE_LOCK:
        _CACHE.update({"savedAt": now, "stamp": stamp, "payload": payload})
    return payload
