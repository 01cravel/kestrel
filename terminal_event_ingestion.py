"""Authoritative, append-only merger-term evidence for universe outcomes.

The collector deliberately ignores SEC item codes.  A filing is useful only
when its own text states complete, attributable transaction terms.  Parsed
records retain both evidence clocks and hashes of every raw input so a later
amendment can be appended without changing what Kestrel knew earlier.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

from company_guidance import html_to_text
from market_history import DEFAULT_DATABASE, MarketHistoryStore
from sec_data import sec_bytes, sec_identity


SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_ROOT = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
TERMINAL_FORMS = {"8-K", "8-K/A", "6-K", "6-K/A", "DEFM14A", "S-4", "S-4/A", "25-NSE"}
MAX_FILINGS = 12
MAX_DOCUMENTS = 16
REFRESH_SECONDS = 20 * 60 * 60
SCHEMA_VERSION = "authoritative-terminal-event-v1"

MONTHS = {
    name.lower(): number for number, name in enumerate(
        ("January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"), 1
    )
}
DATE_TOKEN = r"(?:20\d{2}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2})"
NUMBER = r"(?:\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"

EFFECTIVE_PATTERNS = (
    re.compile(rf"\b(?:effective date|effective on|became effective on|completed on|closed on)\s*(?::|was|is)?\s*(?P<date>{DATE_TOKEN})\b", re.I),
    re.compile(rf"\bmerger\s+(?:became effective|was completed|closed)\s+(?:on\s+)?(?P<date>{DATE_TOKEN})\b", re.I),
)
CASH_PATTERN = re.compile(
    rf"(?P<amount>{NUMBER})\s*(?P<currency>USD|U\.S\. dollars?|EUR|euros?|GBP|pounds? sterling|CAD|Canadian dollars?|JPY|Japanese yen)"
    rf"\s+(?:in cash\s+)?(?:for|per)\s+(?:each\s+)?share|"
    rf"(?P<currency_first>USD|U\.S\. dollars?|EUR|euros?|GBP|pounds? sterling|CAD|Canadian dollars?|JPY|Japanese yen)"
    rf"\s*(?P<amount_after>{NUMBER})\s+(?:in cash\s+)?(?:for|per)\s+(?:each\s+)?share",
    re.I,
)
STOCK_PATTERN = re.compile(
    rf"(?P<ratio>{NUMBER})\s+(?:shares?\s+of\s+[^.;]{{1,100}}?\s+)?shares?\s+(?:for|per)\s+(?:each\s+)?share",
    re.I,
)
SUCCESSOR_PATTERN = re.compile(
    r"\b(?:successor|surviving company|acquirer)\s+(?:stable\s+)?(?:security\s+)?(?:identity|identifier|SEC CIK)\s*(?::|is)?\s*"
    r"(?P<id>(?:FIGI|CIK):[A-Za-z0-9._-]+|\d{1,10})\b",
    re.I,
)
TARGET_PATTERN = re.compile(
    r"\b(?:target|subject company|issuer)\s+(?:stable\s+)?(?:security\s+)?(?:identity|identifier|SEC CIK)\s*(?::|is)?\s*"
    r"(?P<id>(?:FIGI|CIK):[A-Za-z0-9._-]+|\d{1,10})\b",
    re.I,
)
AMENDMENT_PATTERN = re.compile(
    r"\b(?:amends|amending|supersedes)\s+(?:and\s+supplements\s+)?(?:accession(?: number)?\s*)?"
    r"(?P<accession>\d{10}-\d{2}-\d{6})\b",
    re.I,
)
MERGER_NATURE = re.compile(r"\b(?:merger|acquisition|business combination)\b", re.I)
DELISTING_NATURE = re.compile(r"\bdelist(?:ing|ed)?\b", re.I)
CURRENCY_CODES = {
    "usd": "USD", "u.s. dollar": "USD", "u.s. dollars": "USD",
    "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "gbp": "GBP", "pound sterling": "GBP", "pounds sterling": "GBP",
    "cad": "CAD", "canadian dollar": "CAD", "canadian dollars": "CAD",
    "jpy": "JPY", "japanese yen": "JPY",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _utc(value: Any) -> Optional[str]:
    try:
        parsed = dt.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: str) -> Optional[str]:
    raw = value.strip()
    try:
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", raw):
            return dt.date.fromisoformat(raw).isoformat()
        name, day, year = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s+(20\d{2})", raw).groups()  # type: ignore[union-attr]
        return dt.date(int(year), MONTHS[name.lower()], int(day)).isoformat()
    except (AttributeError, KeyError, ValueError):
        return None


def _stable_id(value: Any) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    if raw.isdigit():
        return f"CIK:{int(raw)}"
    prefix, separator, identifier = raw.partition(":")
    if separator and prefix in {"FIGI", "CIK"} and identifier:
        return f"{prefix}:{int(identifier) if prefix == 'CIK' and identifier.isdigit() else identifier}"
    return None


def _number(value: str) -> Optional[float]:
    try:
        number = float(value.replace(",", ""))
    except (AttributeError, ValueError):
        return None
    return number if number >= 0 and number < float("inf") else None


def _single(matches: Iterable[Any]) -> Optional[Any]:
    values = list(matches)
    return values[0] if len(values) == 1 else None


def extract_terminal_terms(text: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Extract one complete term set, rejecting ambiguity instead of guessing."""
    source_url = str(evidence.get("sourceUrl") or "")
    source_kind = str(evidence.get("sourceKind") or "")
    parsed_url = urlparse(source_url)
    valid_sec = (source_kind == "sec_filing" and parsed_url.scheme == "https"
                 and (parsed_url.hostname or "").lower() in {"sec.gov", "www.sec.gov"}
                 and parsed_url.path.startswith("/Archives/edgar/data/"))
    valid_issuer = (source_kind == "official_issuer" and parsed_url.scheme == "https"
                    and evidence.get("issuerDomainVerified") is True)
    published = _utc(evidence.get("publishedAt"))
    available = _utc(evidence.get("availableAt"))
    retrieved = _utc(evidence.get("retrievedAt"))
    accession = str(evidence.get("accession") or (
        evidence.get("sourceRecordId") if source_kind == "official_issuer" else ""
    ) or "").strip()
    document_hashes = [str(value).lower() for value in evidence.get("rawDocumentHashes") or []]
    target = _stable_id(evidence.get("targetSecurityId"))
    expected_target = _stable_id(evidence.get("expectedTargetSecurityId"))
    base = {
        "schemaVersion": SCHEMA_VERSION, "sourceKind": source_kind,
        "sourceUrl": source_url, "accession": accession,
        "issuerDomainVerified": valid_issuer,
        "publishedAt": published, "availableAt": available, "retrievedAt": retrieved,
        "rawDocumentHashes": document_hashes,
    }
    if not (valid_sec or valid_issuer):
        return {**base, "status": "rejected", "reason": "Source authority was not verified."}
    if not published or not available or not retrieved or not (published <= available <= retrieved):
        return {**base, "status": "rejected", "reason": "Evidence clocks were missing or inconsistent."}
    if not accession or not document_hashes or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in document_hashes):
        return {**base, "status": "rejected", "reason": "Source record identity or raw hashes were incomplete."}
    if target != expected_target or not target:
        return {**base, "status": "rejected", "reason": "Target stable identity did not match the requested issuer."}

    normalized = re.sub(r"\s+", " ", text).strip()
    nature = "merger" if MERGER_NATURE.search(normalized) else (
        "delisting" if DELISTING_NATURE.search(normalized) else None
    )
    if not nature:
        return {**base, "status": "rejected", "reason": "The record did not explicitly identify a merger or delisting."}
    effective_dates = {_date(match.group("date")) for pattern in EFFECTIVE_PATTERNS for match in pattern.finditer(normalized)}
    effective_dates.discard(None)
    effective = _single(sorted(effective_dates))
    cash_terms = set()
    for match in CASH_PATTERN.finditer(normalized):
        amount = _number(match.group("amount") or match.group("amount_after"))
        currency = CURRENCY_CODES.get((match.group("currency") or match.group("currency_first") or "").lower())
        if amount is not None and amount > 0 and currency:
            cash_terms.add((amount, currency))
    stock_terms = {_number(match.group("ratio")) for match in STOCK_PATTERN.finditer(normalized)}
    stock_terms.discard(None)
    successors = {_stable_id(match.group("id")) for match in SUCCESSOR_PATTERN.finditer(normalized)}
    successors.discard(None)
    stated_targets = {_stable_id(match.group("id")) for match in TARGET_PATTERN.finditer(normalized)}
    stated_targets.discard(None)
    if stated_targets and stated_targets != {target}:
        return {**base, "status": "rejected", "reason": "Document target identity conflicted with filing attribution."}
    if not effective:
        return {**base, "status": "rejected", "reason": "A single explicit effective date was not present."}
    if len(cash_terms) > 1 or len(stock_terms) > 1 or len(successors) > 1:
        return {**base, "status": "rejected", "reason": "Transaction terms were ambiguous or conflicting within the record."}
    cash = _single(sorted(cash_terms))
    ratio = _single(sorted(stock_terms))
    successor = _single(sorted(successors))
    if not cash and ratio is None:
        return {**base, "status": "rejected", "reason": "Explicit per-share consideration was missing."}
    if ratio is not None and (ratio <= 0 or not successor):
        return {**base, "status": "rejected", "reason": "Stock consideration lacked a positive ratio or successor stable identity."}
    kind = "mixed" if cash and ratio is not None else "cash" if cash else "stock"
    consideration: Dict[str, Any] = {"kind": kind}
    if cash:
        consideration.update({"cashPerShare": cash[0], "currency": cash[1]})
    if ratio is not None:
        consideration.update({"sharesPerShare": ratio, "successorSecurityId": successor})
    supersedes = {match.group("accession") for match in AMENDMENT_PATTERN.finditer(normalized)}
    if len(supersedes) > 1:
        return {**base, "status": "rejected", "reason": "Amendment attribution was ambiguous."}
    detail = {
        **base, "targetSecurityId": target, "effectiveOn": effective,
        "consideration": consideration,
        "rawRecordHash": str(evidence.get("rawRecordHash") or "").lower(),
        "supersedesAccession": next(iter(supersedes), None),
    }
    if not re.fullmatch(r"[0-9a-f]{64}", detail["rawRecordHash"]):
        return {**base, "status": "rejected", "reason": "Raw filing record hash was missing."}
    return {"status": "accepted", "eventType": f"{nature}_{kind}", "detail": detail}


def ingest_terminal_record(record: Dict[str, Any], database: Path = DEFAULT_DATABASE) -> Dict[str, Any]:
    """Parse and append one already retrieved SEC or verified issuer record."""
    documents = record.get("documents") or []
    if not isinstance(documents, list) or not documents:
        return {"status": "rejected", "reason": "No raw documents were supplied.", "stored": 0}
    raw_documents: List[bytes] = []
    for document in documents:
        payload = document.get("content") if isinstance(document, dict) else None
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if not isinstance(payload, bytes):
            return {"status": "rejected", "reason": "A raw document was unreadable.", "stored": 0}
        raw_documents.append(payload)
    evidence = dict(record)
    evidence["rawDocumentHashes"] = [_sha256(payload) for payload in raw_documents]
    supplied_record_hash = str(record.get("rawRecordHash") or record.get("rawPackageRecord") or "").lower()
    evidence["rawRecordHash"] = supplied_record_hash if re.fullmatch(
        r"[0-9a-f]{64}", supplied_record_hash
    ) else _sha256(_canonical({
        key: value for key, value in record.items()
        if key not in {"documents", "retrievedAt", "issuerDomainVerified"}
    }).encode("utf-8"))
    parsed = extract_terminal_terms(" ".join(html_to_text(payload) for payload in raw_documents), evidence)
    if parsed.get("status") != "accepted":
        return {**parsed, "stored": 0}
    detail = parsed["detail"]
    ticker = str(record.get("ticker") or "").upper().strip()
    cik = str(record.get("cik") or "").lstrip("0")
    if not ticker or not cik or _stable_id(f"CIK:{cik}") != _stable_id(record.get("expectedTargetSecurityId")):
        return {"status": "rejected", "reason": "Ticker/CIK attribution was incomplete or mismatched.", "stored": 0}
    database = Path(database)
    connection = MarketHistoryStore(database).connect()
    try:
        prior_rows = connection.execute(
            "SELECT detail FROM issuer_events WHERE ticker=? AND event_type=? AND accession=?",
            (ticker, parsed["eventType"], detail["accession"]),
        ).fetchall()
        for prior_row in prior_rows:
            try:
                prior = json.loads(prior_row["detail"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if (prior.get("rawRecordHash") == detail["rawRecordHash"]
                    and prior.get("rawDocumentHashes") == detail["rawDocumentHashes"]):
                return {"status": "unchanged", "stored": 0,
                        "accession": detail["accession"], "eventType": parsed["eventType"]}
        cursor = connection.execute(
            """INSERT OR IGNORE INTO issuer_events
               (ticker, cik, event_type, event_date, published_at, available_at,
                value, detail, accession, source, retrieved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, cik, parsed["eventType"], detail["effectiveOn"], detail["publishedAt"],
             detail["availableAt"], detail["consideration"].get("cashPerShare"),
             _canonical(detail), detail["accession"],
             "SEC EDGAR authoritative terms" if detail["sourceKind"] == "sec_filing" else "Official issuer authoritative terms",
             detail["retrievedAt"]),
        )
        connection.commit()
        stored = cursor.rowcount
    except sqlite3.DatabaseError as error:
        return {"status": "failed", "reason": str(error), "stored": 0}
    finally:
        connection.close()
    return {"status": "stored" if stored else "unchanged", "stored": stored,
            "accession": detail["accession"], "eventType": parsed["eventType"]}


def _package_documents(index: Dict[str, Any]) -> Sequence[str]:
    items = ((index.get("directory") or {}).get("item") or [])
    names = []
    for item in items:
        name = str((item or {}).get("name") or "")
        lowered = name.lower()
        if (lowered.endswith((".htm", ".html", ".txt")) and not lowered.endswith("-index.html")
                and not any(token in lowered for token in ("xbrl", "schema", "cal.xml", "def.xml", "lab.xml", "pre.xml"))):
            names.append(name)
    return names[:MAX_DOCUMENTS]


def _recent_value(recent: Dict[str, Any], name: str, index: int) -> str:
    values = recent.get(name) or []
    return str(values[index] or "") if isinstance(values, list) and index < len(values) else ""


def refresh_sec_terminal_events(
    symbols: Iterable[str], database: Path = DEFAULT_DATABASE,
    fetcher: Callable[..., bytes] = sec_bytes,
    identity_provider: Callable[[str], Dict[str, Any]] = sec_identity,
    retrieved_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Discover and append explicit SEC terms for the daily evidence pass."""
    database = Path(database)
    if not database.exists():
        return {"status": "no-archive", "stored": 0, "rejected": 0, "failures": []}
    requested_retrieval = _utc(retrieved_at) if retrieved_at else None
    refresh_started = requested_retrieval or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if retrieved_at and not requested_retrieval:
        raise ValueError("Retrieval time must include a timezone")
    stored = rejected = 0
    failures: List[Dict[str, str]] = []
    for symbol in dict.fromkeys(str(value).upper() for value in symbols):
        checkpoint_key = f"terminal_event_refresh:{symbol}"
        with MarketHistoryStore(database).connect() as connection:
            checkpoint = connection.execute(
                "SELECT value FROM metadata WHERE key=?", (checkpoint_key,)
            ).fetchone()
        checkpoint_time = _utc(checkpoint[0]) if checkpoint else None
        if checkpoint_time:
            age = (dt.datetime.fromisoformat(refresh_started.replace("Z", "+00:00"))
                   - dt.datetime.fromisoformat(checkpoint_time.replace("Z", "+00:00"))).total_seconds()
            if 0 <= age < REFRESH_SECONDS:
                continue
        identity = identity_provider(symbol)
        if identity.get("status") != "verified" or not identity.get("cik"):
            failures.append({"symbol": symbol, "reason": "SEC identity unavailable"})
            continue
        cik = str(identity["cik"]).zfill(10)
        try:
            submissions_raw = fetcher(SUBMISSIONS_URL.format(cik=cik))
            submissions = json.loads(submissions_raw.decode("utf-8"))
        except (RuntimeError, ValueError, UnicodeDecodeError) as error:
            failures.append({"symbol": symbol, "reason": str(error)})
            continue
        recent = (submissions.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        seen = 0
        symbol_failed = False
        for index, form in enumerate(forms):
            if form not in TERMINAL_FORMS or seen >= MAX_FILINGS:
                continue
            seen += 1
            accession = _recent_value(recent, "accessionNumber", index)
            accepted = _recent_value(recent, "acceptanceDateTime", index)
            accepted = _utc(accepted.replace(" ", "T") + ("Z" if accepted and not re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", accepted) else ""))
            if not accession or not accepted:
                rejected += 1
                continue
            root = ARCHIVE_ROOT.format(cik=str(int(cik)), accession=accession.replace("-", ""))
            try:
                index_raw = fetcher(root + "index.json")
                package_index = json.loads(index_raw.decode("utf-8"))
                names = _package_documents(package_index)
                documents = [{"name": name, "content": fetcher(root + name)} for name in names]
            except (RuntimeError, ValueError, UnicodeDecodeError) as error:
                failures.append({"symbol": symbol, "accession": accession, "reason": str(error)})
                symbol_failed = True
                continue
            result = ingest_terminal_record({
                "ticker": symbol, "cik": str(int(cik)), "accession": accession,
                "sourceKind": "sec_filing", "sourceUrl": root,
                "publishedAt": accepted, "availableAt": accepted,
                # In production, retrieval time is assigned only after every
                # raw package document has actually arrived.
                "retrievedAt": requested_retrieval or dt.datetime.now(dt.timezone.utc).replace(
                    microsecond=0).isoformat().replace("+00:00", "Z"),
                "targetSecurityId": f"CIK:{int(cik)}", "expectedTargetSecurityId": f"CIK:{int(cik)}",
                "documents": documents,
                # The package index is the immutable SEC directory record;
                # document bytes are hashed separately above.
                "rawPackageRecord": _sha256(index_raw),
            }, database)
            stored += int(result.get("stored") or 0)
            rejected += result.get("status") == "rejected"
            if result.get("status") == "failed":
                failures.append({"symbol": symbol, "accession": accession,
                                 "reason": str(result.get("reason") or "storage failed")})
                symbol_failed = True
        if not symbol_failed:
            with MarketHistoryStore(database).connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES(?, ?)",
                    (checkpoint_key, requested_retrieval or dt.datetime.now(dt.timezone.utc).replace(
                        microsecond=0).isoformat().replace("+00:00", "Z")),
                )
                connection.commit()
    return {"status": "partial" if failures else "refreshed", "stored": stored,
            "rejected": rejected, "failures": failures}


def ingest_official_issuer_release(
    record: Dict[str, Any], issuer_domains: Iterable[str], database: Path = DEFAULT_DATABASE,
) -> Dict[str, Any]:
    """Append supplied issuer evidence only after exact allow-list verification."""
    host = (urlparse(str(record.get("sourceUrl") or "")).hostname or "").lower().rstrip(".")
    domains = {str(value).lower().strip().rstrip(".") for value in issuer_domains if value}
    verified = any(host == domain or host.endswith("." + domain) for domain in domains)
    return ingest_terminal_record({**record, "sourceKind": "official_issuer",
                                   "issuerDomainVerified": verified}, database)
