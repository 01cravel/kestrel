"""Point-in-time US macro evidence from FRED and ALFRED.

The module asks ALFRED for the observation set visible on one calendar-day
cutoff.  It never substitutes today's revised history for a historical query.
The resulting regime is descriptive context only: it cannot promote a company,
portfolio or rating and it fails closed when any required series is absent or
stale.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


MODEL_VERSION = "macro-regime-v1"
CACHE_VERSION = 1
CACHE_SECONDS = 12 * 60 * 60
DEFAULT_API_BASE = "https://api.stlouisfed.org/fred"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent / ".kestrel-macro-cache.json"

# These definitions are intentionally fixed and auditable. FRED distributes
# each series, while the named agency and release remain the original evidence.
SERIES: Dict[str, Dict[str, Any]] = {
    "DGS2": {
        "name": "2-year Treasury constant-maturity yield",
        "agency": "Board of Governors of the Federal Reserve System",
        "release": "H.15 Selected Interest Rates",
        "frequency": "daily",
        "units": "percent",
        "maxVintageAgeDays": 7,
        "maxObservationAgeDays": 10,
        "sourceUrl": "https://fred.stlouisfed.org/series/DGS2",
    },
    "DGS10": {
        "name": "10-year Treasury constant-maturity yield",
        "agency": "Board of Governors of the Federal Reserve System",
        "release": "H.15 Selected Interest Rates",
        "frequency": "daily",
        "units": "percent",
        "maxVintageAgeDays": 7,
        "maxObservationAgeDays": 10,
        "sourceUrl": "https://fred.stlouisfed.org/series/DGS10",
    },
    "CPIAUCSL": {
        "name": "Consumer Price Index for All Urban Consumers: All Items",
        "agency": "U.S. Bureau of Labor Statistics",
        "release": "Consumer Price Index",
        "frequency": "monthly",
        "units": "index 1982-1984=100, seasonally adjusted",
        "maxVintageAgeDays": 45,
        "maxObservationAgeDays": 75,
        "sourceUrl": "https://fred.stlouisfed.org/series/CPIAUCSL",
    },
    "UNRATE": {
        "name": "Unemployment Rate",
        "agency": "U.S. Bureau of Labor Statistics",
        "release": "Employment Situation",
        "frequency": "monthly",
        "units": "percent, seasonally adjusted",
        "maxVintageAgeDays": 45,
        "maxObservationAgeDays": 75,
        "sourceUrl": "https://fred.stlouisfed.org/series/UNRATE",
    },
    "GDPC1": {
        "name": "Real Gross Domestic Product",
        "agency": "U.S. Bureau of Economic Analysis",
        "release": "Gross Domestic Product",
        "frequency": "quarterly",
        "units": "billions of chained dollars, seasonally adjusted annual rate",
        "maxVintageAgeDays": 120,
        "maxObservationAgeDays": 240,
        "sourceUrl": "https://fred.stlouisfed.org/series/GDPC1",
    },
}


def _day(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _observations(rows: Sequence[Dict[str, Any]], cutoff: dt.date) -> List[Dict[str, Any]]:
    usable = []
    for row in rows:
        observed, value = _day(row.get("date")), _number(row.get("value"))
        if observed and observed <= cutoff and value is not None:
            usable.append({"date": observed, "value": value})
    return sorted(usable, key=lambda row: row["date"])


def _latest_vintage(values: Sequence[Any], cutoff: dt.date) -> Optional[dt.date]:
    dates = [_day(value) for value in values]
    return max((value for value in dates if value and value <= cutoff), default=None)


def _series_record(series_id: str, rows: Sequence[Dict[str, Any]], vintages: Sequence[Any],
                   cutoff: dt.date) -> Dict[str, Any]:
    definition = SERIES[series_id]
    values = _observations(rows, cutoff)
    vintage = _latest_vintage(vintages, cutoff)
    latest = values[-1] if values else None
    stale_reasons = []
    if not vintage or (cutoff - vintage).days > definition["maxVintageAgeDays"]:
        stale_reasons.append("release_vintage")
    if not latest or (cutoff - latest["date"]).days > definition["maxObservationAgeDays"]:
        stale_reasons.append("observation")
    return {
        "seriesId": series_id,
        "name": definition["name"],
        "originalAgency": definition["agency"],
        "release": definition["release"],
        "frequency": definition["frequency"],
        "units": definition["units"],
        "sourceUrl": definition["sourceUrl"],
        "requestedVintageDate": cutoff.isoformat(),
        "latestSeriesVintageDate": vintage.isoformat() if vintage else None,
        "observationDate": latest["date"].isoformat() if latest else None,
        "value": latest["value"] if latest else None,
        "stale": bool(stale_reasons),
        "staleReasons": stale_reasons,
        "missing": not bool(latest) or not bool(vintage),
        "_values": values,
    }


def _pct_change(current: float, prior: float) -> Optional[float]:
    return (current / prior - 1) * 100 if prior > 0 else None


def _months_before(day: dt.date, months: int) -> dt.date:
    index = day.year * 12 + day.month - 1 - months
    return dt.date(index // 12, index % 12 + 1, 1)


def _month_value(values: Sequence[Dict[str, Any]], latest: dt.date, months: int) -> Optional[float]:
    target = _months_before(latest, months)
    return next((row["value"] for row in values if row["date"] == target), None)


def build_macro_regime(as_of: dt.date, observations: Dict[str, Sequence[Dict[str, Any]]],
                       vintage_dates: Dict[str, Sequence[Any]],
                       fetched_at: Optional[str] = None) -> Dict[str, Any]:
    """Build a deterministic, point-in-time regime from supplied ALFRED rows."""
    evidence = {
        series_id: _series_record(
            series_id, observations.get(series_id) or [],
            vintage_dates.get(series_id) or [], as_of,
        )
        for series_id in SERIES
    }
    missing = sorted(series_id for series_id, row in evidence.items() if row["missing"])
    stale = sorted(series_id for series_id, row in evidence.items() if row["stale"])

    cpi = evidence["CPIAUCSL"]["_values"]
    unemployment = evidence["UNRATE"]["_values"]
    gdp = evidence["GDPC1"]["_values"]
    cpi_latest = cpi[-1] if cpi else None
    cpi_prior_year = _month_value(cpi, cpi_latest["date"], 12) if cpi_latest else None
    cpi_three_month = _month_value(cpi, cpi_latest["date"], 3) if cpi_latest else None
    cpi_fifteen_month = _month_value(cpi, cpi_latest["date"], 15) if cpi_latest else None
    inflation_yoy = (
        _pct_change(cpi_latest["value"], cpi_prior_year)
        if cpi_latest and cpi_prior_year is not None else None
    )
    earlier_inflation = (
        _pct_change(cpi_three_month, cpi_fifteen_month)
        if cpi_three_month is not None and cpi_fifteen_month is not None else None
    )
    unemployment_latest = unemployment[-1] if unemployment else None
    unemployment_prior = (
        _month_value(unemployment, unemployment_latest["date"], 3)
        if unemployment_latest else None
    )
    unemployment_change = (
        unemployment_latest["value"] - unemployment_prior
        if unemployment_latest and unemployment_prior is not None else None
    )
    gdp_latest = gdp[-1] if gdp else None
    gdp_prior = _month_value(gdp, gdp_latest["date"], 3) if gdp_latest else None
    growth_qoq = (
        ((gdp_latest["value"] / gdp_prior) ** 4 - 1) * 100
        if gdp_latest and gdp_prior is not None and gdp_prior > 0 else None
    )
    two_year = evidence["DGS2"]["value"]
    ten_year = evidence["DGS10"]["value"]
    same_yield_day = evidence["DGS2"]["observationDate"] == evidence["DGS10"]["observationDate"]
    curve = (
        ten_year - two_year
        if same_yield_day and ten_year is not None and two_year is not None else None
    )

    derived = {
        "headlineInflationYoY": round(inflation_yoy, 2) if inflation_yoy is not None else None,
        "inflationThreeMonthDirection": (
            round(inflation_yoy - earlier_inflation, 2)
            if inflation_yoy is not None and earlier_inflation is not None else None
        ),
        "unemploymentThreeMonthChange": (
            round(unemployment_change, 2) if unemployment_change is not None else None
        ),
        "realGdpQoqAnnualized": round(growth_qoq, 2) if growth_qoq is not None else None,
        "tenYearMinusTwoYear": round(curve, 2) if curve is not None else None,
    }
    derived_missing = sorted(key for key, value in derived.items() if value is None)
    complete = not missing and not stale and not derived_missing

    growth_signal = (
        "contracting" if growth_qoq is not None and growth_qoq < 0
        else "expanding" if growth_qoq is not None and growth_qoq > 0
        else "unclear"
    )
    inflation_signal = (
        "elevated" if inflation_yoy is not None and inflation_yoy >= 3
        else "low" if inflation_yoy is not None and inflation_yoy < 1
        else "moderate" if inflation_yoy is not None
        else "unclear"
    )
    labor_signal = (
        "weakening" if unemployment_change is not None and unemployment_change >= 0.3
        else "improving" if unemployment_change is not None and unemployment_change <= -0.3
        else "stable" if unemployment_change is not None
        else "unclear"
    )
    rates_signal = "inverted" if curve is not None and curve < 0 else "upward_sloping" if curve is not None else "unclear"
    label = "unavailable"
    if complete:
        label = (
            "downturn_risk" if growth_signal == "contracting" and labor_signal == "weakening"
            else "inflationary_expansion" if growth_signal == "expanding" and inflation_signal == "elevated"
            else "expansion" if growth_signal == "expanding"
            else "mixed"
        )

    public_evidence = {
        series_id: {key: value for key, value in row.items() if key != "_values"}
        for series_id, row in evidence.items()
    }
    problems = []
    if missing:
        problems.append("Required point-in-time series were missing: " + ", ".join(missing))
    if stale:
        problems.append("Required series vintages were stale: " + ", ".join(stale))
    if derived_missing:
        problems.append("Required regime calculations were unavailable: " + ", ".join(derived_missing))
    return {
        "version": MODEL_VERSION,
        "status": "ready" if complete else "unavailable" if missing else "stale" if stale else "partial",
        "ready": complete,
        "asOf": as_of.isoformat(),
        "cutoffConvention": "End of calendar day; do not use for intraday decisions",
        "fetchedAt": fetched_at,
        "source": "FRED/ALFRED distribution of original-agency releases",
        "apiDocumentation": "https://fred.stlouisfed.org/docs/api/fred/series_observations.html",
        "decisionUse": "Research context and regime-stratified validation only",
        "ratingImpact": "none",
        "regime": {
            "label": label,
            "growth": growth_signal,
            "inflation": inflation_signal,
            "labor": labor_signal,
            "yieldCurve": rates_signal,
        },
        "derived": derived,
        "evidence": public_evidence,
        "missingSeries": missing,
        "staleSeries": stale,
        "missingDerived": derived_missing,
        "errors": problems,
    }


def _cache_path(value: Optional[Path]) -> Path:
    configured = os.environ.get("KESTREL_MACRO_CACHE_PATH", "").strip()
    return value or (Path(configured) if configured else DEFAULT_CACHE_PATH)


def _read_cache(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if payload.get("version") == CACHE_VERSION and isinstance(payload.get("entries"), dict) else {"version": CACHE_VERSION, "entries": {}}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"version": CACHE_VERSION, "entries": {}}


def _write_cache(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _download_json(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Kestrel point-in-time macro research"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("FRED returned an invalid response")
    return payload


def _request(base: str, endpoint: str, params: Dict[str, str], api_key: str,
             downloader: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    query = {**params, "api_key": api_key, "file_type": "json"}
    return downloader(base.rstrip("/") + "/" + endpoint + "?" + urllib.parse.urlencode(query))


def _stale_cached(snapshot: Dict[str, Any], message: str, *, key_configured: bool) -> Dict[str, Any]:
    result = json.loads(json.dumps(snapshot))
    result["status"] = "stale"
    result["ready"] = False
    result["cache"] = {"hit": True, "stale": True}
    result["keyConfigured"] = key_configured
    result["errors"] = list(result.get("errors") or []) + [message]
    result["ratingImpact"] = "none"
    result["regime"] = {**(result.get("regime") or {}), "label": "unavailable"}
    return result


def macro_regime_snapshot(as_of: Optional[dt.date] = None, *, api_key: Optional[str] = None,
                          cache_path: Optional[Path] = None,
                          downloader: Optional[Callable[[str], Dict[str, Any]]] = None,
                          now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """Fetch or reuse a cached point-in-time macro snapshot, failing closed."""
    current_time = now or dt.datetime.now(dt.timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=dt.timezone.utc)
    cutoff = as_of or current_time.date()
    if cutoff > current_time.date():
        return {
            "version": MODEL_VERSION, "status": "unavailable", "ready": False,
            "asOf": cutoff.isoformat(), "keyConfigured": bool(api_key or os.environ.get("FRED_API_KEY")),
            "decisionUse": "Research context and regime-stratified validation only",
            "ratingImpact": "none", "regime": {"label": "unavailable"},
            "missingSeries": list(SERIES), "staleSeries": [],
            "errors": ["A future macro cutoff is not allowed."],
        }

    path = _cache_path(cache_path)
    cache = _read_cache(path)
    cached = cache["entries"].get(cutoff.isoformat())
    if isinstance(cached, dict) and isinstance(cached.get("snapshot"), dict):
        fetched = current_time
        try:
            fetched = dt.datetime.fromisoformat(str(cached.get("fetchedAt")))
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
        # A snapshot first fetched during its own calendar day is refreshed at
        # least once later; only a snapshot fetched after its cutoff is final.
        immutable = bool(cached["snapshot"].get("ready")) and cutoff < fetched.date()
        if immutable or (current_time - fetched).total_seconds() <= CACHE_SECONDS:
            result = json.loads(json.dumps(cached["snapshot"]))
            result["cache"] = {"hit": True, "stale": False}
            result["keyConfigured"] = bool(api_key or os.environ.get("FRED_API_KEY"))
            return result

    key = (api_key if api_key is not None else os.environ.get("FRED_API_KEY", "")).strip()
    if not key:
        if cached:
            return _stale_cached(
                cached["snapshot"],
                "FRED_API_KEY is not configured; cached macro evidence was not treated as current.",
                key_configured=False,
            )
        return {
            "version": MODEL_VERSION, "status": "unavailable", "ready": False,
            "asOf": cutoff.isoformat(), "keyConfigured": False,
            "decisionUse": "Research context and regime-stratified validation only",
            "ratingImpact": "none", "regime": {"label": "unavailable"},
            "missingSeries": list(SERIES), "staleSeries": [],
            "errors": ["FRED_API_KEY is not configured."], "cache": {"hit": False, "stale": False},
        }

    base = os.environ.get("FRED_API_BASE_URL", DEFAULT_API_BASE).strip() or DEFAULT_API_BASE
    if not base.startswith("https://"):
        return {
            "version": MODEL_VERSION, "status": "unavailable", "ready": False,
            "asOf": cutoff.isoformat(), "keyConfigured": True,
            "decisionUse": "Research context and regime-stratified validation only",
            "ratingImpact": "none", "regime": {"label": "unavailable"},
            "missingSeries": list(SERIES), "staleSeries": [],
            "errors": ["FRED_API_BASE_URL must use HTTPS."], "cache": {"hit": False, "stale": False},
        }
    fetch = downloader or _download_json
    observations: Dict[str, Sequence[Dict[str, Any]]] = {}
    vintages: Dict[str, Sequence[Any]] = {}
    start = cutoff - dt.timedelta(days=550)
    try:
        for series_id in SERIES:
            observation_payload = _request(base, "series/observations", {
                "series_id": series_id,
                "realtime_start": cutoff.isoformat(),
                "realtime_end": cutoff.isoformat(),
                "observation_start": start.isoformat(),
                "observation_end": cutoff.isoformat(),
                "output_type": "1",
                "sort_order": "asc",
            }, key, fetch)
            vintage_payload = _request(base, "series/vintagedates", {
                "series_id": series_id,
                "realtime_end": cutoff.isoformat(),
                "sort_order": "desc",
                "limit": "1",
            }, key, fetch)
            observations[series_id] = observation_payload.get("observations") or []
            vintages[series_id] = vintage_payload.get("vintage_dates") or []
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, urllib.error.URLError,
            urllib.error.HTTPError, TimeoutError, socket.timeout, json.JSONDecodeError):
        if cached:
            return _stale_cached(
                cached["snapshot"],
                "FRED/ALFRED refresh failed; cached macro evidence was retained but disabled.",
                key_configured=True,
            )
        return {
            "version": MODEL_VERSION, "status": "unavailable", "ready": False,
            "asOf": cutoff.isoformat(), "keyConfigured": True,
            "decisionUse": "Research context and regime-stratified validation only",
            "ratingImpact": "none", "regime": {"label": "unavailable"},
            "missingSeries": list(SERIES), "staleSeries": [],
            "errors": ["FRED/ALFRED data was unavailable."], "cache": {"hit": False, "stale": False},
        }

    fetched_at = current_time.isoformat()
    snapshot = build_macro_regime(cutoff, observations, vintages, fetched_at=fetched_at)
    snapshot["keyConfigured"] = True
    snapshot["cache"] = {"hit": False, "stale": False}
    cache["entries"][cutoff.isoformat()] = {"fetchedAt": fetched_at, "snapshot": snapshot}
    try:
        _write_cache(path, cache)
    except OSError:
        snapshot["errors"] = list(snapshot.get("errors") or []) + ["Macro cache could not be written."]
    return snapshot
