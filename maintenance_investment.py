"""Dated evidence and conservative maintenance-versus-growth sensitivities.

The issuer usually does not publish an audited maintenance-capex number.  This
module therefore refuses to manufacture one.  It keeps reported capex as the
downside case and only opens a sensitivity band when (a) a dated issuer filing
explicitly describes capacity/growth investment and (b) point-in-time PP&E
depreciation is available as a cross-check.  Depreciation is an accounting
allocation, not an estimate of maintenance spending.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional


METHOD_SOURCE_URL = "https://pages.stern.nyu.edu/~adamodar/podcasts/cfspr23/session12slides.pdf"
ACCOUNTING_SOURCE_URL = "https://www.ifrs.org/issued-standards/list-of-standards/ias-16-property-plant-and-equipment/"


# Paraphrases are intentionally short.  The linked filings are the evidence.
# Each record may only be used on or after publicOn.
ISSUER_EVIDENCE: Dict[str, Dict[str, Any]] = {
    "TSM": {
        "publicOn": "2026-04-17",
        "source": "TSMC 2025 Form 20-F",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm",
        "finding": "TSMC says it is expanding manufacturing capacity and upgrading technology to meet forecast demand.",
        "quality": "moderate",
    },
    "GOOGL": {
        "publicOn": "2026-02-05",
        "source": "Alphabet 2025 Form 10-K",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm",
        "finding": "Alphabet says property investment provides capacity for growth, especially AI technical infrastructure.",
        "quality": "moderate",
    },
    "AMZN": {
        "publicOn": "2026-02-06",
        "source": "Amazon 2025 Form 10-K",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm",
        "finding": "Amazon says most technology-infrastructure spending supports AWS growth and adds fulfillment capacity.",
        "quality": "moderate",
    },
    "ASML": {
        "publicOn": "2026-02-25",
        "source": "ASML 2025 Form 20-F",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/937966/000162828026011378/asml-20251231.htm",
        "finding": "ASML says it is preparing capacity and its supply chain for a multi-year growth ramp.",
        "quality": "moderate",
    },
    "MELI": {
        "publicOn": "2026-02-25",
        "source": "MercadoLibre 2025 Form 10-K",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1099590/000109959026000006/meli-20251231.htm",
        "finding": "MercadoLibre identifies investment in technology and added logistics-network capacity.",
        "quality": "moderate",
    },
    "ETN": {
        "publicOn": "2026-02-26",
        "source": "Eaton 2025 Form 10-K",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000007/etn-20251231.htm",
        "finding": "Eaton says planned capital spending will expand production capacity for anticipated growth.",
        "quality": "moderate",
    },
    "ISRG": {
        "publicOn": "2026-02-03",
        "source": "Intuitive Surgical 2025 Form 10-K",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1035267/000103526726000010/isrg-20251231.htm",
        "finding": "Intuitive says a significant portion builds facilities that expand manufacturing and commercial capacity.",
        "quality": "moderate",
    },
    "CEG": {
        "publicOn": "2026-02-24",
        "source": "Constellation Energy 2025 Form 10-K",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1868275/000186827526000032/ceg-20251231.htm",
        "finding": "The filing describes mixed reliability, regulatory and growth projects but does not support a company-wide split.",
        "quality": "insufficient",
    },
}


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def evidence_as_of(symbol: str, cutoff: Any) -> Optional[Dict[str, Any]]:
    evidence = ISSUER_EVIDENCE.get(symbol)
    cutoff_day = _date(cutoff)
    public_day = _date((evidence or {}).get("publicOn"))
    if not evidence or not cutoff_day or not public_day or public_day > cutoff_day:
        return None
    return dict(evidence)


def investment_sensitivity(symbol: str, current: Dict[str, Any]) -> Dict[str, Any]:
    """Return a range, never a claimed maintenance-capex point estimate."""
    capex = _number(current.get("capitalInvestment"))
    depreciation = _number(current.get("depreciation"))
    operating_cash = _number(current.get("operatingCashFlow"))
    evidence = evidence_as_of(symbol, current.get("knownOn"))
    base = {
        "method": "Reported capex downside; dated issuer growth evidence plus PP&E depreciation cross-check for the sensitivity band",
        "evidence": evidence,
        "methodSourceUrl": METHOD_SOURCE_URL,
        "accountingSourceUrl": ACCOUNTING_SOURCE_URL,
        "reportedCapitalInvestment": capex,
        "depreciationCrossCheck": depreciation,
        "operatingCashFlow": operating_cash,
    }
    if capex is None or operating_cash is None:
        return {**base, "ready": False, "status": "missing", "message": "Current operating cash flow or productive-asset spending is missing."}
    if not evidence:
        return {**base, "ready": False, "status": "not_public", "message": "No qualifying issuer evidence was public by this cutoff."}
    if evidence.get("quality") != "moderate":
        return {**base, "ready": False, "status": "insufficient", "message": "The issuer evidence does not support a company-wide maintenance/growth split."}
    if depreciation is None or depreciation <= 0:
        return {**base, "ready": False, "status": "missing", "message": "Point-in-time PP&E depreciation is missing, so there is no accounting cross-check."}

    # Only the excess above the depreciation cross-check can be treated as
    # possible growth spending.  The whole amount remains maintenance in the
    # downside case.  The midpoint is a labelled sensitivity, not an estimate.
    possible_growth = max(0.0, capex - depreciation)
    scenarios = []
    for scenario_id, name, growth_share in (
        ("downside", "Downside", 0.0),
        ("base", "Conservative base", 0.5),
        ("strong", "Strong execution", 1.0),
    ):
        growth = possible_growth * growth_share
        maintenance = capex - growth
        scenarios.append({
            "id": scenario_id,
            "name": name,
            "maintenanceInvestment": round(maintenance, 2),
            "growthInvestment": round(growth, 2),
            "ownerCash": round(operating_cash - maintenance, 2),
            "growthShareOfPossiblePct": round(growth_share * 100),
        })
    return {
        **base,
        "ready": True,
        "status": "bounded",
        "possibleGrowthInvestment": round(possible_growth, 2),
        "maintenanceRange": [round(depreciation if depreciation < capex else capex, 2), round(capex, 2)],
        "growthRange": [0.0, round(possible_growth, 2)],
        "scenarios": scenarios,
        "message": "Issuer evidence supports a growth sensitivity, but does not quantify the split; depreciation is only a cross-check.",
    }
