"""Machine-readable source hierarchy and confidence gates for Kestrel."""

from __future__ import annotations

from typing import Any, Dict, Iterable


POLICY_VERSION = "2026.08.08.1"

TIERS = [
    {
        "tier": 1,
        "name": "Authoritative",
        "meaning": "The account owner, regulator, exchange, central bank, government agency, or issuer filing.",
    },
    {
        "tier": 2,
        "name": "Institutional validated",
        "meaning": "Licensed data with transparent methodology, identifiers, timestamps, corrections, and quality controls.",
    },
    {
        "tier": 3,
        "name": "Provisional",
        "meaning": "Useful aggregators and public feeds that must be cross-checked before driving a high-confidence decision.",
    },
    {
        "tier": 4,
        "name": "Experimental",
        "meaning": "Alternative or model-derived signals that may support research but can never establish a fact by themselves.",
    },
]

SOURCE_AREAS = [
    {
        "id": "portfolio",
        "name": "Portfolio and cash",
        "truth": "Sarwa official statements and account records",
        "current": "Sarwa signed-in web snapshot with review-before-apply",
        "currentTier": 1,
        "target": "Daily read-only capture reconciled with the latest official monthly statement",
        "status": "connected",
        "url": "https://www.sarwa.co/",
    },
    {
        "id": "identity",
        "name": "Security identity",
        "truth": "Regulator identifiers plus FIGI, ISIN, exchange and currency",
        "current": "Persistent OpenFIGI mapping, share-class FIGI and SEC CIK with ambiguity checks",
        "currentTier": 2,
        "target": "Add ISIN, exchange MIC and local regulator identifiers as direct-market coverage expands",
        "status": "connected",
        "url": "https://www.openfigi.com/api/documentation",
    },
    {
        "id": "fundamentals_us",
        "name": "US company results",
        "truth": "SEC EDGAR filing and structured XBRL facts",
        "current": "SEC submissions, filing document and Company Facts API",
        "currentTier": 1,
        "target": "Broader filing coverage, restatement detection and issuer-release cross-check",
        "status": "connected",
        "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    },
    {
        "id": "fundamentals_global",
        "name": "International company results",
        "truth": "The issuer’s local regulator filing in its mandated electronic format",
        "current": "US ADR filings where available; otherwise aggregator data",
        "currentTier": 3,
        "target": "ESMA ESEF, FCA NSM and one verified local regulator pipeline per market",
        "status": "planned",
        "url": "https://www.esma.europa.eu/issuer-disclosure/electronic-reporting",
    },
    {
        "id": "prices",
        "name": "Prices and total returns",
        "truth": "Licensed consolidated or exchange-originated trades, closes and adjustments",
        "current": "Cost-controlled daily closes cross-checked between Yahoo and Finnhub; Databento pay-as-you-go official closes are an optional upgrade",
        "currentTier": 3,
        "target": "Nasdaq NLS+ official consolidated closes plus SIP data where needed, independently checked against Finnhub and Sarwa",
        "status": "cross_checked",
        "url": "https://www.nasdaqtrader.com/Trader.aspx?id=mddataproducts",
    },
    {
        "id": "corporate_actions",
        "name": "Corporate actions",
        "truth": "Exchange, issuer and validated institutional action records",
        "current": "Public split events, adjusted histories and unexplained-jump detection; paid point-in-time actions remain an optional upgrade",
        "currentTier": 3,
        "target": "DTCC and exchange announcements validated through point-in-time institutional corporate actions and adjustment factors",
        "status": "cross_checked",
        "url": "https://www.nasdaqtrader.com/Trader.aspx?id=DailyListPD",
    },
    {
        "id": "expectations",
        "name": "Analyst expectations",
        "truth": "Timestamped contributor-level estimates; opinions, never reported facts",
        "current": "Finnhub and FMP anonymous consensus; Benzinga named analyst, firm, target-change and accuracy adapter ready to connect",
        "currentTier": 3,
        "target": "Named Benzinga actions cross-checked against consensus, then LSEG I/B/E/S or FactSet point-in-time detail if its value justifies the cost",
        "status": "provisional",
        "url": "https://www.lseg.com/en/data-analytics/financial-data/company-data/ibes-estimates",
    },
    {
        "id": "company_guidance",
        "name": "Company guidance",
        "truth": "Company-issued guidance in SEC-filed earnings releases or a verified official investor-relations publication",
        "current": "On-demand SEC 8-K and 6-K release ingestion with exact acceptance cutoffs and fail-closed range comparison",
        "currentTier": 1,
        "target": "Archive verified issuer IR releases that are not furnished through EDGAR",
        "status": "connected",
        "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    },
    {
        "id": "manager_holdings",
        "name": "Proven-investor holdings",
        "truth": "SEC Form 13F filing and information table",
        "current": "Direct latest-versus-prior filing comparison for eight selected long-equity managers",
        "currentTier": 1,
        "target": "Broader manager validation, point-in-time outcome testing and international local-filing coverage",
        "status": "connected",
        "url": "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets",
    },
    {
        "id": "funds",
        "name": "ETF holdings and costs",
        "truth": "Issuer prospectus, issuer holdings and SEC Form N-PORT",
        "current": "Fund-level market metrics only",
        "currentTier": 3,
        "target": "Issuer daily holdings where offered, reconciled with SEC N-PORT and prospectus fees",
        "status": "planned",
        "url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets",
    },
    {
        "id": "macro",
        "name": "Rates, inflation and economy",
        "truth": "Original government agency and central-bank release with vintage date",
        "current": "Point-in-time FRED/ALFRED snapshots retaining Federal Reserve, BLS and BEA release vintages",
        "currentTier": 1,
        "target": "Validate regime-conditioned research over multiple cycles before allowing any capped model influence",
        "status": "connected",
        "url": "https://fred.stlouisfed.org/docs/api/fred/overview.html",
    },
    {
        "id": "risk_model",
        "name": "Portfolio risk model",
        "truth": "A reproducible model derived from point-in-time, corporate-action-adjusted returns",
        "current": "Simple concentration, beta and historical-return checks",
        "currentTier": 4,
        "target": "Shrinkage covariance, factor exposures, drawdown, stress scenarios and model-version audit trail",
        "status": "planned",
        "url": "https://www.econ.uzh.ch/en/people/researchers/ledoit/publications.html",
    },
]

GATES = {
    "highConfidence": [
        "Instrument identity, listing, currency and corporate-action state are resolved.",
        "The current price is fresh and confirmed by an independent source within tolerance.",
        "The latest official filing is present, current and free of material conflicts.",
        "Every critical metric carries its source, period, unit, currency and retrieval time.",
    ],
    "buy": [
        "Valuation uses official reported facts or a documented bridge from them.",
        "Expected growth is a range with disagreement and revision history, not one target.",
        "Liquidity, concentration, correlation and downside checks all pass.",
    ],
    "ultraBuy": [
        "All High-confidence and Buy gates pass.",
        "Institutional point-in-time estimates and validated corporate actions are connected.",
        "The proposed weight improves the whole portfolio under base and stressed assumptions.",
        "No unresolved source conflict, stale critical field or model warning remains.",
    ],
    "idealPortfolio": [
        "The investable universe is identity-clean and survivorship-bias controlled.",
        "Return and risk inputs are point-in-time and adjusted for splits, dividends and delistings.",
        "Estimation error is penalised; unstable weights are rejected.",
        "Every target weight has a reason, uncertainty range, capacity limit and stress result.",
    ],
}


def _count(data: Dict[str, Any], predicate: Any) -> int:
    return sum(1 for value in data.values() if isinstance(value, dict) and predicate(value))


def build_evidence_summary(
    data: Dict[str, Any],
    sarwa: Dict[str, Any] | None = None,
    identity: Dict[str, Any] | None = None,
    market: Dict[str, Any] | None = None,
    named_analysts: Dict[str, Any] | None = None,
    macro: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return a compact live summary used by the dashboard and rating gate."""
    values = data if isinstance(data, dict) else {}
    total = len(values)
    quote_ready = _count(values, lambda item: isinstance(item.get("quote"), dict) and bool(item["quote"].get("c")))
    filing_ready = _count(values, lambda item: isinstance(item.get("sec"), dict) and item["sec"].get("status") == "verified")
    estimate_ready = _count(
        values,
        lambda item: isinstance(item.get("analystIntelligence"), dict)
        and item["analystIntelligence"].get("status") in {"ready", "partial"},
    )
    error_free = _count(values, lambda item: not (item.get("errors") or []))
    portfolio_connected = bool(sarwa and sarwa.get("status") == "connected")
    identity_summary = identity if isinstance(identity, dict) else {}
    identity_resolved = int(identity_summary.get("ratingUniverseResolved") or 0)
    identity_total = int(identity_summary.get("ratingUniverseTotal") or 0)
    identity_clean = bool(identity_summary.get("ratingUniverseClean"))
    market_summary = market if isinstance(market, dict) else {}
    institutional_key = bool(market_summary.get("keyConfigured"))
    institutional_ready = int(market_summary.get("ratingReady") or 0)
    institutional_total = int(market_summary.get("ratedSymbols") or 0)
    institutional_clean = bool(market_summary.get("allRatingReady"))
    named_summary = named_analysts if isinstance(named_analysts, dict) else {}
    named_key = bool(named_summary.get("keyConfigured"))
    named_ready = int(named_summary.get("ratingReady") or 0)
    named_total = int(named_summary.get("ratedSymbols") or 0)
    macro_summary = macro if isinstance(macro, dict) else {}
    macro_ready = bool(macro_summary.get("ready"))

    authoritative_areas = int(filing_ready > 0) + int(portfolio_connected) + int(macro_ready)
    total_areas = len(SOURCE_AREAS)
    return {
        "version": POLICY_VERSION,
        "status": "guarded",
        "title": "Portfolio, identity and US filings connected",
        "summary": (
            "Sarwa holdings and SEC filings are authoritative, and instruments now have stable identities. "
            "Prices, corporate actions, international filings and analyst consensus still need stronger sources."
        ),
        "authoritativeAreas": authoritative_areas,
        "totalAreas": total_areas,
        "coverage": {
            "symbolsSeen": total,
            "freshQuotes": quote_ready,
            "verifiedFilings": filing_ready,
            "analystSeries": estimate_ready,
            "errorFreeSymbols": error_free,
            "portfolioConnected": portfolio_connected,
            "identityResolved": identity_resolved,
            "identityTotal": identity_total,
            "identityClean": identity_clean,
            "institutionalKeyConfigured": institutional_key,
            "institutionalPriceReady": institutional_ready,
            "institutionalPriceTotal": institutional_total,
            "institutionalMarketClean": institutional_clean,
            "marketMode": market_summary.get("mode") or "cost_controlled",
            "premiumRequired": bool(market_summary.get("premiumRequired")),
            "namedAnalystKeyConfigured": named_key,
            "namedAnalystReady": named_ready,
            "namedAnalystTotal": named_total,
            "macroConfigured": bool(macro_summary.get("keyConfigured")),
            "macroReady": macro_ready,
            "macroStatus": macro_summary.get("status") or "unavailable",
        },
        "ratingGate": {
            "maximumConfidence": "Medium",
            "ultraBuyEnabled": False,
            "reason": (
                "Ultra Buy is locked until institutional pricing, validated corporate actions, "
                "and point-in-time consensus estimates are connected."
            ),
        },
        "nextUpgrade": (
            "Resolve the remaining instrument identities before rating them."
            if identity_total and not identity_clean
            else "Resolve any remaining daily price or split-adjustment disagreements."
            if institutional_total and not institutional_clean
            else "Test the Benzinga named-ratings trial across the full portfolio before considering a paid plan."
            if not named_key
            else "Resolve named-analyst coverage or consensus disagreements."
            if named_total and named_ready < named_total
            else "Add pay-as-you-go official closes after creating a free Databento account; no subscription is required."
            if not institutional_key
            else "Add Morningstar independent fair value only if its measured benefit justifies the licence."
        ),
    }


def evidence_policy(
    data: Dict[str, Any],
    sarwa: Dict[str, Any] | None = None,
    identity: Dict[str, Any] | None = None,
    market: Dict[str, Any] | None = None,
    named_analysts: Dict[str, Any] | None = None,
    macro: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    areas = [dict(area) for area in SOURCE_AREAS]
    market_summary = market if isinstance(market, dict) else {}
    market_connected = bool(market_summary.get("allRatingReady"))
    institutional_connected = int(market_summary.get("institutionalVerified") or 0) > 0
    named_summary = named_analysts if isinstance(named_analysts, dict) else {}
    named_connected = bool(named_summary.get("allRatingReady"))
    for area in areas:
        if area["id"] in {"prices", "corporate_actions"} and market_connected:
            area["currentTier"] = 2 if institutional_connected else 3
            area["status"] = "connected" if institutional_connected else "cross_checked"
            area["current"] = (
                "Nasdaq NLS+ official consolidated closes delivered by Databento and independently cross-checked"
                if area["id"] == "prices" and institutional_connected
                else "Yahoo adjusted daily closes independently checked against Finnhub"
                if area["id"] == "prices"
                else "Point-in-time corporate actions and listing-matched adjustment factors delivered by Databento"
                if institutional_connected
                else "Public split events plus adjusted-history discontinuity checks"
            )
        if area["id"] == "expectations" and named_connected:
            area["currentTier"] = 2
            area["status"] = "connected"
            area["current"] = "Named analyst and firm actions, targets and accuracy records cross-checked against independent consensus"
        if area["id"] == "macro" and isinstance(macro, dict):
            area["status"] = "connected" if macro.get("ready") else macro.get("status") or "unavailable"
            area["current"] = (
                "Point-in-time FRED/ALFRED observations with original Federal Reserve, BLS and BEA vintages"
                if macro.get("ready") else "Macro connector is present but missing or stale evidence remains disabled"
            )
    return {
        **build_evidence_summary(data, sarwa, identity, market, named_analysts, macro),
        "principles": [
            "Facts outrank opinions; opinions outrank model guesses.",
            "Every critical value must retain source, period, unit, currency and retrieval time.",
            "Conflicts reduce confidence; missing data never counts as positive evidence.",
            "A model can transform evidence, but it can never promote its own output into a fact.",
            "Kestrel must withhold a rating when a critical gate fails.",
        ],
        "tiers": TIERS,
        "areas": areas,
        "gates": GATES,
    }
