"""Small, conservative SEC EDGAR verification client for Kestrel."""

from __future__ import annotations

import datetime as dt
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple


SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Kestrel/0.1 admin@kestrel.local",
).strip()
SEC_REQUEST_GAP_SECONDS = 0.2
SEC_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "Revenue",
)
NET_INCOME_TAGS = ("NetIncomeLoss", "ProfitLoss")
EQUITY_TAGS = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "Equity",
)

_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_TICKER_MAP: Optional[Dict[str, Dict[str, Any]]] = None


def _sec_json(url: str) -> Any:
    global _LAST_REQUEST
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST
        if elapsed < SEC_REQUEST_GAP_SECONDS:
            time.sleep(SEC_REQUEST_GAP_SECONDS - elapsed)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": SEC_USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                _LAST_REQUEST = time.monotonic()
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            _LAST_REQUEST = time.monotonic()
            raise RuntimeError(f"SEC returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as error:
            _LAST_REQUEST = time.monotonic()
            raise RuntimeError("SEC filing data was unavailable") from error


def _ticker_map() -> Dict[str, Dict[str, Any]]:
    global _TICKER_MAP
    if _TICKER_MAP is not None:
        return _TICKER_MAP
    payload = _sec_json("https://www.sec.gov/files/company_tickers.json")
    if not isinstance(payload, dict):
        raise RuntimeError("SEC ticker directory was unavailable")
    _TICKER_MAP = {
        str(item.get("ticker", "")).upper(): item
        for item in payload.values()
        if isinstance(item, dict) and item.get("ticker")
    }
    return _TICKER_MAP


def sec_identity(symbol: str) -> Dict[str, Any]:
    """Return the SEC's compact company identity for a ticker."""
    company = _ticker_map().get(symbol.upper())
    if not company:
        return {
            "status": "unavailable",
            "symbol": symbol.upper(),
            "source": "SEC company ticker directory",
            "sourceUrl": "https://www.sec.gov/files/company_tickers.json",
        }
    return {
        "status": "verified",
        "symbol": str(company.get("ticker") or symbol).upper(),
        "name": company.get("title"),
        "cik": f"{int(company['cik_str']):010d}",
        "source": "SEC company ticker directory",
        "sourceUrl": "https://www.sec.gov/files/company_tickers.json",
    }


def _latest_filing(submissions: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for index, form in enumerate(forms):
        if form not in SEC_FORMS:
            continue
        try:
            return {
                "form": form,
                "filed": recent["filingDate"][index],
                "periodEnd": recent["reportDate"][index],
                "accession": recent["accessionNumber"][index],
                "document": recent["primaryDocument"][index],
            }
        except (IndexError, KeyError):
            continue
    return None


def _filing_url(cik: str, filing: Dict[str, Any]) -> str:
    accession = str(filing["accession"]).replace("-", "")
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession}/{filing['document']}"
    )


def _parse_date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _concept_entries(
    facts: Dict[str, Any],
    tags: Iterable[str],
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    for taxonomy in ("us-gaap", "ifrs-full"):
        concepts = facts.get(taxonomy, {})
        for tag in tags:
            concept = concepts.get(tag)
            if not isinstance(concept, dict):
                continue
            units = concept.get("units", {})
            if not isinstance(units, dict) or not units:
                continue
            preferred_units = ["USD", "EUR", "GBP", "JPY", "CAD", "CHF"]
            unit = next((name for name in preferred_units if name in units), None)
            if unit is None:
                unit = max(units, key=lambda name: len(units.get(name, [])))
            entries = [entry for entry in units.get(unit, []) if isinstance(entry, dict)]
            if entries:
                return entries, unit, tag
    return [], None, None


def _duration_days(entry: Dict[str, Any]) -> Optional[int]:
    start = _parse_date(entry.get("start"))
    end = _parse_date(entry.get("end"))
    return (end - start).days if start and end else None


def _select_period(
    entries: List[Dict[str, Any]],
    filing: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    annual = filing["form"] in ANNUAL_FORMS
    target_days = 365 if annual else 91
    minimum_days, maximum_days = ((300, 430) if annual else (60, 125))
    candidates = []
    for entry in entries:
        duration = _duration_days(entry)
        end = _parse_date(entry.get("end"))
        if (
            entry.get("form") not in SEC_FORMS
            or duration is None
            or not minimum_days <= duration <= maximum_days
            or end is None
        ):
            continue
        candidates.append((entry, end, duration))
    if not candidates:
        return None, None

    accession = filing.get("accession")
    same_filing = [item for item in candidates if item[0].get("accn") == accession]
    pool = same_filing or candidates
    latest_end = max(item[1] for item in pool)
    same_end = [item for item in pool if item[1] == latest_end]
    current, current_end, current_days = min(
        same_end,
        key=lambda item: (abs(item[2] - target_days), str(item[0].get("filed", ""))),
    )

    prior_candidates = []
    for entry, end, duration in candidates:
        distance = (current_end - end).days
        if 300 <= distance <= 430 and abs(duration - current_days) <= 35:
            prior_candidates.append((entry, abs(distance - 364), abs(duration - current_days)))
    prior = min(prior_candidates, key=lambda item: (item[1], item[2]))[0] if prior_candidates else None
    return current, prior


def _select_matching_period(
    entries: List[Dict[str, Any]],
    reference: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not reference:
        return None
    exact = [
        entry for entry in entries
        if entry.get("start") == reference.get("start")
        and entry.get("end") == reference.get("end")
        and entry.get("form") in SEC_FORMS
    ]
    if not exact:
        return None
    return max(exact, key=lambda entry: str(entry.get("filed", "")))


def _latest_instant(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [
        entry for entry in entries
        if entry.get("form") in SEC_FORMS and _parse_date(entry.get("end"))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: (str(entry.get("end", "")), str(entry.get("filed", ""))))


def _number(entry: Optional[Dict[str, Any]]) -> Optional[float]:
    if not entry:
        return None
    try:
        value = float(entry.get("val"))
        return value if value == value else None
    except (TypeError, ValueError):
        return None


def _percent_change(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior in (None, 0):
        return None
    return ((current - prior) / abs(prior)) * 100


def _market_number(metrics: Dict[str, Any], *names: str) -> Optional[float]:
    for name in names:
        try:
            value = float(metrics.get(name))
            if value == value:
                return value
        except (TypeError, ValueError):
            continue
    return None


def _agreement(
    label: str,
    official_value: Optional[float],
    market_value: Optional[float],
    tolerance: float,
) -> Optional[Dict[str, Any]]:
    if official_value is None or market_value is None:
        return None
    difference = abs(official_value - market_value)
    return {
        "label": label,
        "status": "agrees" if difference <= tolerance else "review",
        "officialValue": round(official_value, 2),
        "marketValue": round(market_value, 2),
        "difference": round(difference, 2),
    }


def verify_with_sec(symbol: str, market_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact filing verification record; never return full SEC payloads."""
    verified_at = int(time.time())
    try:
        company = _ticker_map().get(symbol.upper())
        if not company:
            return {
                "status": "unavailable",
                "message": "No matching SEC filer was found for this symbol.",
                "verifiedAt": verified_at,
            }

        cik = f"{int(company['cik_str']):010d}"
        submissions = _sec_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        filing = _latest_filing(submissions)
        if not filing:
            return {
                "status": "unavailable",
                "message": "No recent annual or quarterly SEC filing was found.",
                "cik": cik,
                "verifiedAt": verified_at,
            }

        company_facts = _sec_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        facts = company_facts.get("facts", {}) if isinstance(company_facts, dict) else {}
        revenue_entries, currency, revenue_tag = _concept_entries(facts, REVENUE_TAGS)
        income_entries, income_currency, income_tag = _concept_entries(facts, NET_INCOME_TAGS)
        equity_entries, equity_currency, equity_tag = _concept_entries(facts, EQUITY_TAGS)

        current_revenue_entry, prior_revenue_entry = _select_period(revenue_entries, filing)
        current_income_entry = _select_matching_period(income_entries, current_revenue_entry)
        if current_income_entry is None:
            current_income_entry, _ = _select_period(income_entries, filing)
        latest_equity_entry = _latest_instant(equity_entries)

        revenue = _number(current_revenue_entry)
        prior_revenue = _number(prior_revenue_entry)
        net_income = _number(current_income_entry)
        equity = _number(latest_equity_entry)
        revenue_growth = _percent_change(revenue, prior_revenue)
        profit_margin = (net_income / revenue * 100) if revenue not in (None, 0) and net_income is not None else None

        filed_date = _parse_date(filing.get("filed"))
        age_days = (dt.date.today() - filed_date).days if filed_date else None
        annual = filing["form"] in ANNUAL_FORMS
        fresh = age_days is not None and age_days <= (450 if annual else 200)
        coverage = sum(value is not None for value in (revenue, net_income, equity))

        checks = [
            _agreement(
                "Revenue growth",
                revenue_growth,
                _market_number(market_metrics, "revenueGrowthTTMYoy", "revenueGrowth3Y"),
                15,
            ),
            _agreement(
                "Profit margin",
                profit_margin,
                _market_number(market_metrics, "netProfitMarginTTM"),
                8,
            ),
        ]
        checks = [check for check in checks if check is not None]
        conflicts = sum(check["status"] == "review" for check in checks)
        agreements = sum(check["status"] == "agrees" for check in checks)
        status = "verified" if fresh and coverage >= 2 else "partial"

        return {
            "status": status,
            "message": (
                "Official filing found and core figures extracted."
                if status == "verified"
                else "Official filing found, but the available facts are incomplete or old."
            ),
            "companyName": company.get("title"),
            "cik": cik,
            "filing": {
                **filing,
                "url": _filing_url(cik, filing),
                "ageDays": age_days,
            },
            "facts": {
                "currency": currency or income_currency or equity_currency,
                "revenue": revenue,
                "priorRevenue": prior_revenue,
                "revenueGrowth": round(revenue_growth, 2) if revenue_growth is not None else None,
                "netIncome": net_income,
                "profitMargin": round(profit_margin, 2) if profit_margin is not None else None,
                "equity": equity,
                "periodStart": current_revenue_entry.get("start") if current_revenue_entry else None,
                "periodEnd": current_revenue_entry.get("end") if current_revenue_entry else filing.get("periodEnd"),
                "tags": {
                    "revenue": revenue_tag,
                    "netIncome": income_tag,
                    "equity": equity_tag,
                },
            },
            "checks": checks,
            "agreementCount": agreements,
            "conflictCount": conflicts,
            "ratingReady": status == "verified" and agreements >= 1 and conflicts == 0,
            "verifiedAt": verified_at,
            "source": "U.S. SEC EDGAR",
        }
    except RuntimeError as error:
        return {
            "status": "error",
            "message": str(error),
            "verifiedAt": verified_at,
        }
