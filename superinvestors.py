"""Direct SEC 13F intelligence for Kestrel's opportunity discovery.

13F records are authoritative facts about disclosed US-listed long holdings at a
quarter end. They are deliberately used to find research candidates, never as a
standalone Buy signal.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sec_data import SEC_USER_AGENT


ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".kestrel-superinvestors.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}"
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
SCHEMA_VERSION = 3
REFRESH_SECONDS = 24 * 60 * 60
DISCOVERY_LIMIT = 12
MAPPING_SHORTLIST = 40

# A deliberately mixed starting cohort. These managers are useful only where a
# disclosed long-equity portfolio meaningfully represents their strategy.
MANAGERS = (
    {"id": "berkshire", "name": "Berkshire Hathaway", "cik": "0001067983", "style": "Long-term quality and value"},
    {"id": "akre", "name": "Akre Capital", "cik": "0001112520", "style": "High-return compounders"},
    {"id": "fundsmith", "name": "Fundsmith", "cik": "0001868537", "style": "Durable global quality"},
    {"id": "pershing", "name": "Pershing Square", "cik": "0001336528", "style": "Concentrated value and change"},
    {"id": "himalaya", "name": "Himalaya Capital", "cik": "0001709323", "style": "Concentrated long-term value"},
    {"id": "dodge_cox", "name": "Dodge & Cox", "cik": "0000200217", "style": "Patient contrarian value"},
    {"id": "baillie_gifford", "name": "Baillie Gifford", "cik": "0001088875", "style": "Long-duration growth"},
    {"id": "polen", "name": "Polen Capital", "cik": "0001034524", "style": "Quality growth"},
)

_LOCK = threading.RLock()
_REQUEST_LOCK = threading.Lock()
_LAST_SEC_REQUEST = 0.0
_LAST_FIGI_REQUEST = 0.0
_STATE: Dict[str, Any] = {
    "status": "starting",
    "message": "Preparing direct SEC manager filings",
    "updatedAt": None,
    "lastSuccessfulAt": None,
    "managers": [],
    "ideas": [],
    "errors": [],
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str:
    for child in element.iter():
        if _local_name(child.tag) == name:
            return str(child.text or "").strip()
    return ""


def _number(value: Any) -> Optional[float]:
    try:
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def _sec_request(url: str, accept: str = "application/json") -> bytes:
    global _LAST_SEC_REQUEST
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_SEC_REQUEST
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                _LAST_SEC_REQUEST = time.monotonic()
                return response.read()
        except urllib.error.HTTPError as error:
            _LAST_SEC_REQUEST = time.monotonic()
            raise RuntimeError(f"SEC returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            _LAST_SEC_REQUEST = time.monotonic()
            raise RuntimeError("SEC manager filings were unavailable") from error


def _sec_json(url: str) -> Dict[str, Any]:
    try:
        payload = json.loads(_sec_request(url).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("SEC returned an unreadable filing record") from error
    if not isinstance(payload, dict):
        raise RuntimeError("SEC returned an unexpected filing record")
    return payload


def _filings(submissions: Dict[str, Any]) -> List[Dict[str, str]]:
    recent = submissions.get("filings", {}).get("recent", {})
    rows: List[Dict[str, str]] = []
    forms = recent.get("form") if isinstance(recent, dict) else []
    for index, form in enumerate(forms or []):
        if form != "13F-HR":
            continue
        try:
            rows.append({
                "accession": str(recent["accessionNumber"][index]),
                "filedAt": str(recent["filingDate"][index]),
                "periodEnd": str(recent["reportDate"][index]),
            })
        except (IndexError, KeyError, TypeError):
            continue
    return sorted(rows, key=lambda row: (row["periodEnd"], row["filedAt"]), reverse=True)


def _information_table_url(cik: str, accession: str) -> Tuple[str, str]:
    accession_plain = accession.replace("-", "")
    base = SEC_ARCHIVES_URL.format(cik=int(cik), accession=accession_plain)
    index = _sec_json(base + "/index.json")
    items = index.get("directory", {}).get("item", [])
    xml_names = []
    for item in items if isinstance(items, list) else []:
        name = str(item.get("name") or "")
        if name.lower().endswith(".xml") and name.lower() != "primary_doc.xml":
            xml_names.append(name)
    if not xml_names:
        raise RuntimeError("The SEC filing did not contain a readable holdings table")
    name = xml_names[0]
    return f"{base}/{name}", f"{base}/{accession}-index.html"


def _parse_holdings(payload: bytes) -> List[Dict[str, Any]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise RuntimeError("The SEC holdings table could not be read") from error
    holdings: List[Dict[str, Any]] = []
    for row in root.iter():
        if _local_name(row.tag) != "infoTable":
            continue
        put_call = _child_text(row, "putCall")
        shares = _number(_child_text(row, "sshPrnamt"))
        value_thousands = _number(_child_text(row, "value"))
        cusip = _child_text(row, "cusip").upper()
        if put_call or not cusip or not shares or shares <= 0 or value_thousands is None:
            continue
        holdings.append({
            "issuer": _child_text(row, "nameOfIssuer"),
            "class": _child_text(row, "titleOfClass"),
            "cusip": cusip,
            "shares": shares,
            # Current 13F XML reports this field in dollars. Only relative
            # portfolio weights are exposed to the decision layer.
            "value": value_thousands,
        })
    return holdings


def _consolidate_holdings(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Combine the same security reported through multiple included managers."""
    combined: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        holding = combined.setdefault(row["cusip"], {
            "issuer": row["issuer"],
            "class": row["class"],
            "cusip": row["cusip"],
            "shares": 0.0,
            "value": 0.0,
        })
        holding["shares"] += float(row["shares"])
        holding["value"] += float(row["value"])
    return list(combined.values())


def _manager_filings(manager: Dict[str, str]) -> Dict[str, Any]:
    submissions = _sec_json(SEC_SUBMISSIONS_URL.format(cik=manager["cik"]))
    filings = _filings(submissions)
    if len(filings) < 2:
        raise RuntimeError("Two comparable 13F quarters were not available")
    current_meta, prior_meta = filings[0], filings[1]
    current_url, current_index = _information_table_url(manager["cik"], current_meta["accession"])
    prior_url, _ = _information_table_url(manager["cik"], prior_meta["accession"])
    current = _consolidate_holdings(_parse_holdings(_sec_request(current_url, "application/xml,text/xml")))
    prior = _consolidate_holdings(_parse_holdings(_sec_request(prior_url, "application/xml,text/xml")))
    if not current:
        raise RuntimeError("The latest filing did not contain disclosed long holdings")
    return {
        **manager,
        "status": "ready",
        "periodEnd": current_meta["periodEnd"],
        "priorPeriodEnd": prior_meta["periodEnd"],
        "filedAt": current_meta["filedAt"],
        "filingUrl": current_index,
        "holdings": current,
        "priorHoldings": prior,
    }


def _change_label(current: float, prior: Optional[float]) -> Tuple[str, Optional[float]]:
    if prior is None or prior <= 0:
        return "New", None
    change = ((current - prior) / prior) * 100
    if change >= 10:
        return "Increased", change
    if change <= -10:
        return "Reduced", change
    return "Held", change


def _aggregate(manager_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}
    for manager in manager_rows:
        total_value = sum(float(row["value"]) for row in manager["holdings"])
        prior = {row["cusip"]: row for row in manager["priorHoldings"]}
        for holding in manager["holdings"]:
            prior_holding = prior.get(holding["cusip"])
            action, change = _change_label(holding["shares"], prior_holding.get("shares") if prior_holding else None)
            manager_position = {
                "id": manager["id"],
                "name": manager["name"],
                "style": manager["style"],
                "action": action,
                "changePercent": round(change, 1) if change is not None else None,
                "portfolioWeight": round((holding["value"] / total_value) * 100, 2) if total_value else None,
                "periodEnd": manager["periodEnd"],
                "filedAt": manager["filedAt"],
                "filingUrl": manager["filingUrl"],
            }
            idea = aggregated.setdefault(holding["cusip"], {
                "cusip": holding["cusip"],
                "issuer": holding["issuer"],
                "class": holding["class"],
                "managers": [],
            })
            idea["managers"].append(manager_position)
    results = []
    for idea in aggregated.values():
        managers = sorted(
            idea["managers"],
            key=lambda item: (item["action"] not in {"New", "Increased"}, -(item["portfolioWeight"] or 0)),
        )
        active = sum(item["action"] in {"New", "Increased"} for item in managers)
        highest = max((item["portfolioWeight"] or 0) for item in managers)
        results.append({
            **idea,
            "managers": managers,
            "ownerCount": len(managers),
            "activeBuyerCount": active,
            "highestConviction": round(highest, 2),
        })
    # No opaque composite: fresh buying, independent agreement, then disclosed
    # portfolio conviction decide which filings are investigated first.
    return sorted(
        results,
        key=lambda item: (-item["activeBuyerCount"], -item["ownerCount"], -item["highestConviction"], item["issuer"]),
    )


def _openfigi(jobs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    global _LAST_FIGI_REQUEST
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_FIGI_REQUEST
        if elapsed < 2.5:
            time.sleep(2.5 - elapsed)
        request = urllib.request.Request(
            OPENFIGI_URL,
            data=json.dumps(jobs).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Kestrel local portfolio dashboard"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                _LAST_FIGI_REQUEST = time.monotonic()
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            _LAST_FIGI_REQUEST = time.monotonic()
            raise RuntimeError(f"OpenFIGI returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
            _LAST_FIGI_REQUEST = time.monotonic()
            raise RuntimeError("CUSIP-to-ticker mapping was unavailable") from error
    if not isinstance(payload, list) or len(payload) != len(jobs):
        raise RuntimeError("OpenFIGI returned an unexpected mapping response")
    return payload


def _resolve_symbols(ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    shortlisted = ideas[:MAPPING_SHORTLIST]
    resolved: Dict[str, Dict[str, Any]] = {}
    for offset in range(0, len(shortlisted), 5):
        batch = shortlisted[offset:offset + 5]
        jobs = [{"idType": "ID_CUSIP", "idValue": idea["cusip"], "marketSecDes": "Equity"} for idea in batch]
        results = _openfigi(jobs)
        for idea, result in zip(batch, results):
            rows = result.get("data") if isinstance(result, dict) else None
            candidates = [
                row for row in (rows or [])
                if isinstance(row, dict)
                and row.get("marketSector") == "Equity"
                and row.get("exchCode") == "US"
                and row.get("ticker")
            ]
            tickers = {str(row["ticker"]).upper() for row in candidates}
            if len(tickers) != 1:
                continue
            ticker = next(iter(tickers))
            match = next(row for row in candidates if str(row["ticker"]).upper() == ticker)
            resolved[idea["cusip"]] = {
                "symbol": ticker,
                "name": match.get("name") or idea["issuer"],
                "figi": match.get("figi"),
                "shareClassFigi": match.get("shareClassFIGI"),
            }
    mapped = [{**idea, **resolved[idea["cusip"]]} for idea in shortlisted if idea["cusip"] in resolved]
    return _deduplicate_companies(mapped)[:DISCOVERY_LIMIT]


def _company_key(idea: Dict[str, Any]) -> str:
    """Return a conservative company identity for separately listed share classes."""
    raw = str(idea.get("issuer") or idea.get("name") or idea.get("symbol") or "").upper()
    words = re.sub(r"[^A-Z0-9]+", " ", raw).split()
    while words and words[-1] in {"INC", "CORP", "CORPORATION", "PLC", "LTD", "LIMITED", "CO", "COMPANY"}:
        words.pop()
    return " ".join(words) or str(idea.get("symbol") or idea.get("cusip") or "")


def _deduplicate_companies(ideas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge multiple quoted share classes into one research candidate.

    Managers remain independent votes. If a manager owns two classes, their
    disclosed weights are combined and the freshest positive action is retained.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for idea in ideas:
        grouped.setdefault(_company_key(idea), []).append(idea)

    action_priority = {"New": 4, "Increased": 3, "Held": 2, "Reduced": 1}
    merged: List[Dict[str, Any]] = []
    for company_key, classes in grouped.items():
        primary = max(
            classes,
            key=lambda item: (
                int(item.get("ownerCount") or 0),
                str(item.get("symbol") or "") == "GOOGL",
                int(item.get("activeBuyerCount") or 0),
                float(item.get("highestConviction") or 0),
            ),
        )
        managers_by_id: Dict[str, Dict[str, Any]] = {}
        for share_class in classes:
            for manager in share_class.get("managers") or []:
                manager_id = str(manager.get("id") or manager.get("name") or "")
                existing = managers_by_id.get(manager_id)
                if not existing:
                    managers_by_id[manager_id] = {**manager}
                    continue
                existing["portfolioWeight"] = round(
                    float(existing.get("portfolioWeight") or 0) + float(manager.get("portfolioWeight") or 0), 2
                )
                if action_priority.get(str(manager.get("action")), 0) > action_priority.get(str(existing.get("action")), 0):
                    existing["action"] = manager.get("action")
                existing["changePercent"] = None

        managers = sorted(
            managers_by_id.values(),
            key=lambda item: (item.get("action") not in {"New", "Increased"}, -float(item.get("portfolioWeight") or 0)),
        )
        share_classes = sorted({str(item.get("symbol") or "") for item in classes if item.get("symbol")})
        active = sum(item.get("action") in {"New", "Increased"} for item in managers)
        merged.append({
            **primary,
            "companyKey": company_key,
            "shareClasses": share_classes,
            "managers": managers,
            "ownerCount": len(managers),
            "activeBuyerCount": active,
            "highestConviction": round(max((float(item.get("portfolioWeight") or 0) for item in managers), default=0), 2),
        })

    return sorted(
        merged,
        key=lambda item: (-item["activeBuyerCount"], -item["ownerCount"], -item["highestConviction"], item["issuer"]),
    )


def _public_manager(manager: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in manager.items() if key not in {"holdings", "priorHoldings"}}


def _load_cache() -> None:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            return
        with _LOCK:
            _STATE.update({
                "status": payload.get("status") or "cached",
                "message": payload.get("message") or "Showing saved SEC manager filings",
                "updatedAt": payload.get("updatedAt"),
                "lastSuccessfulAt": payload.get("lastSuccessfulAt"),
                "managers": payload.get("managers") or [],
                "ideas": payload.get("ideas") or [],
                "errors": payload.get("errors") or [],
            })
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return


def _save_cache() -> None:
    with _LOCK:
        payload = {"schemaVersion": SCHEMA_VERSION, **_STATE}
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def superinvestor_snapshot() -> Dict[str, Any]:
    with _LOCK:
        managers = list(_STATE["managers"])
        ideas = list(_STATE["ideas"])
        errors = list(_STATE["errors"])
        status = _STATE["status"]
        message = _STATE["message"]
        updated_at = _STATE["updatedAt"]
        successful_at = _STATE["lastSuccessfulAt"]
    periods = sorted({manager.get("periodEnd") for manager in managers if manager.get("periodEnd")}, reverse=True)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "message": message,
        "updatedAt": updated_at,
        "lastSuccessfulAt": successful_at,
        "source": "SEC EDGAR Form 13F filings",
        "sourceUrl": "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets",
        "method": "Fresh disclosed buying first, then independent manager agreement, then portfolio conviction. Share classes are merged before ranking.",
        "managerValidation": {
            "status": "building",
            "rule": "Manager skill is measured only from point-in-time ideas saved by Kestrel versus SPY after 90, 180 and 365 days.",
            "minimum": "No manager receives extra trust until at least 10 independent ideas have a full 365-day result.",
        },
        "limitations": "Quarterly US-listed long positions only. Filings may arrive up to 45 days late and omit shorts, hedges and non-US listings.",
        "latestPeriodEnd": periods[0] if periods else None,
        "managerCount": len(managers),
        "managers": managers,
        "ideas": ideas,
        "errors": errors,
    }


def refresh_superinvestors(force: bool = False) -> Dict[str, Any]:
    now = int(time.time())
    with _LOCK:
        last_success = int(_STATE.get("lastSuccessfulAt") or 0)
        if not force and _STATE["ideas"] and now - last_success < REFRESH_SECONDS:
            return superinvestor_snapshot()
        _STATE["status"] = "refreshing"
        _STATE["message"] = "Reading the latest and previous SEC filings for the tracked managers"

    ready: List[Dict[str, Any]] = []
    errors: List[str] = []
    for manager in MANAGERS:
        try:
            ready.append(_manager_filings(manager))
        except RuntimeError as error:
            errors.append(f"{manager['name']}: {error}")

    ideas: List[Dict[str, Any]] = []
    if ready:
        try:
            ideas = _resolve_symbols(_aggregate(ready))
        except RuntimeError as error:
            errors.append(str(error))

    updated_at = int(time.time())
    with _LOCK:
        if ready and ideas:
            _STATE.update({
                "status": "ready" if not errors else "partial",
                "message": f"{len(ready)} managers checked; {len(ideas)} disclosed ideas resolved for research",
                "updatedAt": updated_at,
                "lastSuccessfulAt": updated_at,
                "managers": [_public_manager(manager) for manager in ready],
                "ideas": ideas,
                "errors": errors,
            })
        else:
            _STATE.update({
                "status": "error",
                "message": "SEC manager intelligence could not be refreshed; no filing was treated as a signal",
                "updatedAt": updated_at,
                "errors": errors or ["No verified manager ideas were available"],
            })
        try:
            _save_cache()
        except OSError:
            _STATE["status"] = "partial"
            _STATE["message"] = "SEC manager filings were read, but the local cache could not be saved"
    return superinvestor_snapshot()


_load_cache()
