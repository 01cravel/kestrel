"""Fail-closed company guidance evidence from issuer publications.

The public entry points deliberately separate collection, extraction and
comparison.  SEC acceptance time is the publication cutoff for filed exhibits;
an official IR release must supply its own publication timestamp.  Nothing in
this module changes a rating or relaxes a valuation or portfolio-risk gate.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import math
import re
import time
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from sec_data import sec_bytes, sec_identity


SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_ROOT = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
GUIDANCE_FORMS = {"8-K", "6-K"}
GUIDANCE_ITEMS = {"2.02", "7.01", "8.01"}
MAX_FILINGS = 8

METRICS = {
    "revenue": ("revenue", "revenues", "net sales"),
    "adjusted_eps": ("adjusted diluted eps", "adjusted eps", "non-gaap diluted eps"),
    "diluted_eps": ("diluted eps", "diluted earnings per share"),
    "adjusted_operating_income": ("adjusted operating income",),
    "operating_income": ("operating income",),
    "free_cash_flow": ("free cash flow",),
    "capital_expenditure": ("capital expenditures", "capital expenditure", "capex"),
    "gross_margin": ("gross margin",),
    "operating_margin": ("operating margin",),
}

PERIOD_PATTERNS = (
    re.compile(r"(?:full[ -]?year|fiscal year|fy)\s*(20\d{2})", re.I),
    re.compile(r"(first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter(?:\s+of)?\s*(20\d{2})", re.I),
    re.compile(r"q([1-4])\s*(20\d{2})", re.I),
)
MULTIPLIERS = {"thousand": 1_000.0, "million": 1_000_000.0, "billion": 1_000_000_000.0}
CURRENCY_SYMBOLS = {"$": None, "€": "EUR", "£": "GBP", "¥": None}
DEFINITION_QUALIFIERS = ("adjusted", "non-gaap", "organic", "constant currency")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(payload: bytes | str) -> str:
    """Return deterministic visible text without adding inferred structure."""
    raw = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    parser = _Text()
    try:
        parser.feed(raw)
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _iso_timestamp(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _period(sentence: str) -> Optional[Dict[str, str]]:
    match = PERIOD_PATTERNS[0].search(sentence)
    if match:
        year = match.group(1)
        return {"type": "fiscal_year", "label": f"FY {year}", "year": year}
    for pattern in PERIOD_PATTERNS[1:]:
        match = pattern.search(sentence)
        if not match:
            continue
        quarter = match.group(1).lower()
        quarter = {"first": "1", "1st": "1", "second": "2", "2nd": "2",
                   "third": "3", "3rd": "3", "fourth": "4", "4th": "4"}.get(quarter, quarter)
        year = match.group(2)
        return {"type": "fiscal_quarter", "label": f"Q{quarter} {year}",
                "year": year, "quarter": quarter}
    return None


def _metric(sentence: str) -> Optional[Tuple[str, str]]:
    lowered = sentence.lower()
    # Specific adjusted definitions must win over their unadjusted substring.
    for metric, aliases in METRICS.items():
        for alias in aliases:
            match = re.search(rf"\b{re.escape(alias)}\b", lowered)
            if match:
                prefix = lowered[max(0, match.start() - 24):match.start()].strip()
                if any(prefix.endswith(qualifier) for qualifier in DEFINITION_QUALIFIERS):
                    return None
                return metric, alias
    return None


NUMBER = r"(?:\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"


def _value_pattern(prefix: str) -> str:
    return (rf"(?P<{prefix}symbol>[$€£¥])?\s*(?P<{prefix}number>{NUMBER})\s*"
            rf"(?P<{prefix}scale>thousand|million|billion)?\s*"
            rf"(?P<{prefix}percent>%|percent)?\s*"
            rf"(?P<{prefix}code>USD|EUR|GBP|JPY|CAD|CHF|TWD)?")


RANGE = re.compile(rf"{_value_pattern('low')}\s*(?:to|through|[-–—])\s*{_value_pattern('high')}", re.I)
MIDPOINT = re.compile(rf"\bmidpoint(?:\s+of|\s+is)?\s*{_value_pattern('mid')}", re.I)


def _value(match: re.Match[str], prefix: str, sentence: str) -> Optional[Dict[str, Any]]:
    try:
        number = float(match.group(prefix + "number").replace(",", ""))
    except (AttributeError, ValueError):
        return None
    scale = (match.group(prefix + "scale") or "").lower() or None
    percent = bool(match.group(prefix + "percent"))
    symbol = match.group(prefix + "symbol")
    code = (match.group(prefix + "code") or "").upper() or None
    currency = CURRENCY_SYMBOLS.get(symbol) or code
    if percent:
        return {"value": number, "unit": "percent", "currency": None, "scale": None}
    if scale:
        number *= MULTIPLIERS[scale]
    # Currency codes elsewhere in the same short statement may qualify both bounds.
    if not currency:
        present = {item.upper() for item in re.findall(r"\b(?:USD|EUR|GBP|JPY|CAD|CHF|TWD)\b", sentence, re.I)}
        if len(present) == 1:
            currency = present.pop()
    return {"value": number, "unit": "currency" if currency or symbol else "number",
            "currency": currency, "scale": scale}


def extract_guidance(text: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only explicit metric-period ranges from issuer evidence.

    A midpoint is never calculated.  Ambiguous currency, unit, period, source or
    publication time makes the row ineligible rather than guessed.
    """
    published_at = _iso_timestamp(evidence.get("publishedAt"))
    source_kind = evidence.get("sourceKind")
    source_url = str(evidence.get("sourceUrl") or "")
    source = urlparse(source_url)
    valid_sec = (source_kind == "sec_filing" and source.scheme == "https"
                 and (source.hostname or "").lower() in {"sec.gov", "www.sec.gov"}
                 and source.path.startswith("/Archives/edgar/data/"))
    valid_source = valid_sec or (
        source_kind == "official_ir" and urlparse(source_url).scheme == "https"
        and bool(evidence.get("issuerDomainVerified"))
    )
    base = {
        "sourceKind": source_kind, "sourceUrl": source_url,
        "sourceRecordId": evidence.get("sourceRecordId"), "publishedAt": published_at,
        "retrievedAt": evidence.get("retrievedAt"), "accession": evidence.get("accession"),
        "contentHash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    if not valid_source or not published_at or not source_url:
        return {"status": "rejected", "reason": "Issuer source, exact publication time or URL was not verified.",
                "observations": [], **base}

    observations: List[Dict[str, Any]] = []
    rejected: List[str] = []
    sentences = re.split(r"(?<=[.;])\s+|\s+[•|]\s+", re.sub(r"\s+", " ", text))
    for sentence in sentences:
        metric = _metric(sentence)
        if not metric or not re.search(r"\b(expect|expects|forecast|forecasts|guidance|outlook|project|projects|anticipate|anticipates)\b", sentence, re.I):
            continue
        period = _period(sentence)
        match = RANGE.search(sentence)
        if not period or not match:
            rejected.append(sentence[:240])
            continue
        low, high = _value(match, "low", sentence), _value(match, "high", sentence)
        if not low or not high or low["unit"] != high["unit"] or low["value"] > high["value"]:
            rejected.append(sentence[:240])
            continue
        if low["currency"] != high["currency"]:
            # A currency sign on only the first bound conventionally applies to
            # the range, but that is an inference. Fail closed.
            rejected.append(sentence[:240])
            continue
        metric_id, definition = metric
        if low["unit"] == "currency" and not low["currency"]:
            rejected.append(sentence[:240])
            continue
        management_midpoint = None
        midpoint_match = MIDPOINT.search(sentence)
        if midpoint_match:
            midpoint = _value(midpoint_match, "mid", sentence)
            if (not midpoint or midpoint["unit"] != low["unit"]
                    or midpoint["currency"] != low["currency"]
                    or not low["value"] <= midpoint["value"] <= high["value"]):
                rejected.append(sentence[:240])
                continue
            management_midpoint = midpoint["value"]
        observations.append({
            **base, "metric": metric_id, "definition": definition,
            "period": period, "low": low["value"], "high": high["value"],
            "unit": low["unit"], "currency": low["currency"],
            "managementMidpoint": management_midpoint, "midpointInferred": False,
            "originalText": sentence.strip(), "status": "verified",
        })

    # Conflicting duplicate facts in one publication invalidate that exact key.
    grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for row in observations:
        grouped.setdefault(comparability_key(row), []).append(row)
    conflicts = {key for key, rows in grouped.items()
                 if len({(row["low"], row["high"]) for row in rows}) > 1}
    clean = [row for row in observations if comparability_key(row) not in conflicts]
    return {
        "status": "verified" if clean else "conflict" if conflicts else "no-explicit-guidance",
        "observations": clean, "rejectedStatements": rejected,
        "conflictCount": len(conflicts), **base,
    }


def official_ir_guidance(payload: bytes | str, source_url: str, published_at: str,
                         issuer_domains: Iterable[str],
                         retrieved_at: Optional[str] = None) -> Dict[str, Any]:
    """Ingest a supplied official IR release after exact domain verification.

    Discovery is intentionally separate: callers must obtain the release from
    an issuer-owned IR page and pass the issuer's allow-listed domains.  This
    prevents a search result or syndicated copy from becoming Tier 1 evidence.
    """
    parsed_url = urlparse(source_url)
    hostname = (parsed_url.hostname or "").lower().rstrip(".")
    domains = {str(domain).lower().strip().rstrip(".") for domain in issuer_domains if domain}
    verified = parsed_url.scheme == "https" and any(
        hostname == domain or hostname.endswith("." + domain) for domain in domains
    )
    evidence = {
        "sourceKind": "official_ir", "sourceUrl": source_url,
        "sourceRecordId": source_url, "issuerDomainVerified": verified,
        "publishedAt": published_at,
        "retrievedAt": retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return extract_guidance(html_to_text(payload), evidence)


def comparability_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    period = row.get("period") or {}
    return (row.get("metric"), row.get("definition"), period.get("type"),
            period.get("year"), period.get("quarter"), row.get("unit"), row.get("currency"))


def _comparable(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return bool(left and right and comparability_key(left) == comparability_key(right))


def _range(row: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    try:
        low, high = float(row.get("low")), float(row.get("high"))
    except (TypeError, ValueError):
        return None
    return (low, high) if math.isfinite(low) and math.isfinite(high) and low <= high else None


def compare_guidance(latest: Dict[str, Any], previous: Optional[Dict[str, Any]] = None,
                     actual: Optional[Dict[str, Any]] = None,
                     consensus: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compare only exact metric/definition/period/unit/currency matches."""
    result: Dict[str, Any] = {"previous": None, "actual": None, "consensus": None}
    latest_range = _range(latest)
    if previous:
        if (_comparable(latest, previous) and previous.get("publishedAt")
                and latest.get("publishedAt") and previous["publishedAt"] < latest["publishedAt"]
                and latest_range and _range(previous)):
            old = _range(previous)
            new = latest_range
            if old == new:
                change = "reiterated"
            elif new[0] >= old[0] and new[1] > old[1]:
                change = "raised"
            elif new[0] < old[0] and new[1] <= old[1]:
                change = "lowered"
            elif new[0] > old[0] and new[1] <= old[1]:
                change = "narrowed"
            elif new[0] <= old[0] and new[1] > old[1]:
                change = "widened"
            else:
                change = "changed"
            result["previous"] = {"status": "comparable", "change": change,
                                  "oldRange": list(old), "newRange": list(new)}
        else:
            result["previous"] = {"status": "not-comparable", "reason": "Metric, definition, period, unit, currency or publication order differs."}
    for label, row in (("actual", actual), ("consensus", consensus)):
        if not row:
            continue
        published = row.get("publishedAt")
        correct_time = bool(
            published and latest.get("publishedAt") and
            (published > latest["publishedAt"] if label == "actual" else published <= latest["publishedAt"])
        )
        if not _comparable(latest, row) or row.get("value") is None or not correct_time:
            timing = "later" if label == "actual" else "available by the guidance cutoff"
            result[label] = {"status": "not-comparable", "reason":
                             f"Metric, definition, period, unit or currency differs, or the evidence was not {timing}."}
            continue
        try:
            value = float(row["value"])
        except (TypeError, ValueError):
            value = float("nan")
        if not math.isfinite(value) or not latest_range:
            result[label] = {"status": "not-comparable", "reason": "The comparison value or guidance range was invalid."}
            continue
        position = "above" if value > latest_range[1] else "below" if value < latest_range[0] else "within"
        result[label] = {"status": "comparable", "position": position, "value": value}
    return result


def _display_value(value: float, row: Dict[str, Any]) -> str:
    if row.get("unit") == "percent":
        return f"{value:g}%"
    code = f" {row['currency']}" if row.get("currency") else ""
    return f"{value:g}{code}"


def plain_english(row: Dict[str, Any], comparisons: Optional[Dict[str, Any]] = None) -> str:
    period = (row.get("period") or {}).get("label") or "the stated period"
    words = row.get("definition") or str(row.get("metric") or "metric").replace("_", " ")
    sentence = (f"Management guided {period} {words} to "
                f"{_display_value(row['low'], row)}–{_display_value(row['high'], row)}.")
    previous = (comparisons or {}).get("previous") or {}
    if previous.get("status") == "comparable":
        sentence += f" That {previous['change']} the previous comparable range."
    actual = (comparisons or {}).get("actual") or {}
    if actual.get("status") == "comparable":
        sentence += f" The later actual result was {actual['position']} the range."
    consensus = (comparisons or {}).get("consensus") or {}
    if consensus.get("status") == "comparable":
        sentence += f" Comparable analyst consensus was {consensus['position']} the range."
    return sentence


def build_guidance_view(observations: Sequence[Dict[str, Any]],
                        actuals: Sequence[Dict[str, Any]] = (),
                        consensus: Sequence[Dict[str, Any]] = (),
                        cutoff: Optional[str] = None) -> Dict[str, Any]:
    cutoff_time = _iso_timestamp(cutoff) if cutoff else None
    if cutoff and not cutoff_time:
        raise ValueError("Guidance cutoff must be a timezone-bearing ISO timestamp")
    eligible = [row for row in observations if row.get("status") == "verified"
                and row.get("publishedAt") and (not cutoff_time or row["publishedAt"] <= cutoff_time)]
    publications: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for row in eligible:
        publications.setdefault((row["publishedAt"], *comparability_key(row)), []).append(row)
    publication_conflicts = {
        key for key, rows in publications.items()
        if len({(row.get("low"), row.get("high")) for row in rows}) > 1
    }
    # The same release can appear both on the filing cover and as EX-99. Keep
    # one identical fact; remove the entire publication key if the copies differ.
    deduplicated: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for row in eligible:
        publication_key = (row["publishedAt"], *comparability_key(row))
        if publication_key not in publication_conflicts:
            deduplicated[(publication_key, row.get("low"), row.get("high"))] = row
    eligible = list(deduplicated.values())
    groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for row in eligible:
        groups.setdefault(comparability_key(row), []).append(row)
    entries = []
    for rows in groups.values():
        rows.sort(key=lambda row: row["publishedAt"], reverse=True)
        latest, previous = rows[0], rows[1] if len(rows) > 1 else None
        matching_actuals = [item for item in actuals if _comparable(latest, item)
                            and item.get("publishedAt", "") > latest["publishedAt"]]
        matching_consensus = [item for item in consensus if _comparable(latest, item)
                              and item.get("publishedAt", "") <= latest["publishedAt"]]
        actual = min(matching_actuals, key=lambda item: item["publishedAt"], default=None)
        estimate = max(matching_consensus, key=lambda item: item["publishedAt"], default=None)
        comparisons = compare_guidance(latest, previous, actual, estimate)
        entries.append({"latest": latest, "comparisons": comparisons,
                        "summary": plain_english(latest, comparisons)})
    entries.sort(key=lambda item: item["latest"]["publishedAt"], reverse=True)
    return {
        "status": "ready" if entries else "conflict" if publication_conflicts else "unavailable",
        "conflictCount": len(publication_conflicts), "cutoff": cutoff_time,
        "entries": entries,
        "ratingImpact": "none",
        "gatePolicy": "Guidance informs the thesis but never overrides valuation, evidence-quality, liquidity, concentration or portfolio-risk gates.",
        "message": (entries[0]["summary"] if entries else
                    "No conflict-free, explicit company guidance was available at this cutoff."),
    }


def sec_guidance_evidence(symbol: str, cutoff: Optional[str] = None,
                          max_filings: int = MAX_FILINGS) -> Dict[str, Any]:
    """Collect and parse recent issuer releases furnished through EDGAR."""
    if cutoff and not _iso_timestamp(cutoff):
        raise ValueError("Guidance cutoff must be a timezone-bearing ISO timestamp")
    identity = sec_identity(symbol)
    if identity.get("status") != "verified":
        return {"status": "unavailable", "symbol": symbol.upper(), "observations": [],
                "reason": "No SEC issuer identity was verified."}
    try:
        submissions = json.loads(sec_bytes(SUBMISSIONS_URL.format(cik=identity["cik"])).decode("utf-8"))
    except (RuntimeError, ValueError):
        return {"status": "unavailable", "symbol": symbol.upper(), "observations": [],
                "reason": "SEC submissions were unavailable."}
    recent = (submissions.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    observations: List[Dict[str, Any]] = []
    evidence_log: List[Dict[str, Any]] = []
    cutoff_time = _iso_timestamp(cutoff) if cutoff else None
    used = 0

    def at(name: str, index: int) -> Any:
        values = recent.get(name) or []
        return values[index] if index < len(values) else None

    for index, form in enumerate(forms):
        if form not in GUIDANCE_FORMS or used >= max_filings:
            continue
        items = {part.strip() for part in str(at("items", index) or "").split(",")}
        if form == "8-K" and not (items & GUIDANCE_ITEMS):
            continue
        accepted = _iso_timestamp(at("acceptanceDateTime", index))
        if not accepted or (cutoff_time and accepted > cutoff_time):
            continue
        accession = str(at("accessionNumber", index) or "")
        primary = str(at("primaryDocument", index) or "")
        if not accession or not primary:
            continue
        used += 1
        root = ARCHIVE_ROOT.format(cik=int(identity["cik"]), accession=accession.replace("-", ""))
        # SEC index.json is an official directory of the filing package. Earnings
        # releases are usually EX-99 HTML exhibits, not the primary 8-K cover.
        # Stay inside this exact accession directory and never follow off-site links.
        document_names = [primary.split("/")[-1]]
        try:
            index_payload = json.loads(sec_bytes(root + "index.json").decode("utf-8"))
            items = ((index_payload.get("directory") or {}).get("item") or [])
            exhibit_names = [
                str(item.get("name")) for item in items if isinstance(item, dict)
                and re.search(r"\.(?:html?|txt)$", str(item.get("name") or ""), re.I)
                and re.search(r"(?:ex(?:hibit)?[-_]?99|99[-_.])", str(item.get("name") or ""), re.I)
                and "/" not in str(item.get("name") or "") and ".." not in str(item.get("name") or "")
            ]
            document_names.extend(exhibit_names[:4])
        except (RuntimeError, ValueError):
            pass
        for document_name in dict.fromkeys(document_names):
            url = root + document_name
            try:
                text = html_to_text(sec_bytes(url, accept="text/html"))
            except RuntimeError:
                evidence_log.append({"accession": accession, "status": "unavailable", "sourceUrl": url})
                continue
            evidence = {
                "sourceKind": "sec_filing", "sourceUrl": url,
                "sourceRecordId": f"{accession}:{document_name}",
                "accession": accession, "publishedAt": accepted,
                "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            parsed = extract_guidance(text, evidence)
            observations.extend(parsed["observations"])
            evidence_log.append({"accession": accession, "publishedAt": accepted,
                                 "status": parsed["status"], "sourceUrl": url,
                                 "observations": len(parsed["observations"])})
    view = build_guidance_view(observations, cutoff=cutoff)
    return {**view, "symbol": identity["symbol"], "name": identity.get("name"),
            "observations": observations, "evidence": evidence_log,
            "source": "SEC EDGAR issuer filings", "retrievedAt": int(time.time())}
