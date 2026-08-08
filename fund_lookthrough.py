"""Official, fail-closed ETF holdings look-through for Candidate 1.

The calculation deliberately uses issuer-published holdings only.  If an
issuer feed disappears, is stale, or cannot be parsed, the affected fund is
reported as missing and the science gate remains closed.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import threading
import time
import urllib.request
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional


EQUITY_FUNDS = ("VTI", "AVUV", "VEA", "IEMG", "AVDV", "PAVE")
MAX_AGE_DAYS = 75
CACHE_SECONDS = 24 * 60 * 60

FUND_SOURCES = {
    "VTI": "https://investor.vanguard.com/vmf/api/VTI/portfolio-holding/stock.json?start=1&count=20000&asOfType=daily",
    "VEA": "https://investor.vanguard.com/vmf/api/VEA/portfolio-holding/stock.json?start=1&count=20000&asOfType=daily",
    "AVUV": "https://www.avantisinvestors.com/avantis-investments/avantis-us-small-cap-value-etf/trading-details/",
    "AVDV": "https://www.avantisinvestors.com/avantis-investments/avantis-international-small-cap-value-etf/trading-details/",
    "IEMG": "https://www.ishares.com/us/products/244050/ishares-core-msci-emerging-markets-etf/latest-holdings.csv",
    "PAVE": "https://www.globalxetfs.com/funds/pave?download_full_holdings=true",
}

DIRECT_COMPANIES = {
    "TSM": {"tickers": {"TSM", "2330"}, "names": ("TAIWAN SEMICONDUCTOR",)},
    "GOOGL": {"tickers": {"GOOGL", "GOOG"}, "names": ("ALPHABET INC",)},
    "AMZN": {"tickers": {"AMZN"}, "names": ("AMAZON.COM", "AMAZON COM")},
    "ASML": {"tickers": {"ASML", "ASML NA"}, "names": ("ASML HOLDING",)},
    "MELI": {"tickers": {"MELI"}, "names": ("MERCADOLIBRE",)},
    "ETN": {"tickers": {"ETN"}, "names": ("EATON CORP",)},
    "ISRG": {"tickers": {"ISRG"}, "names": ("INTUITIVE SURGICAL",)},
    "CEG": {"tickers": {"CEG"}, "names": ("CONSTELLATION ENERGY",)},
}

_LOCK = threading.Lock()
_CACHE: Optional[Dict[str, Any]] = None


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Kestrel/1.0 portfolio research (issuer holdings)",
        "Accept": "application/json,text/csv,text/plain,text/html",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def _weight(value: Any) -> Optional[float]:
    try:
        parsed = float(str(value).replace("%", "").replace(",", "").strip())
        return parsed if math.isfinite(parsed) and parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def _holding(ticker: Any, name: Any, weight: Any) -> Optional[Dict[str, Any]]:
    parsed = _weight(weight)
    if parsed is None:
        return None
    return {
        "ticker": str(ticker or "").strip().upper(),
        "name": str(name or "").strip(),
        "weight": parsed,
    }


def _parse_vanguard(text: str) -> Dict[str, Any]:
    payload = json.loads(text)
    rows = payload.get("fund", {}).get("entity") or []
    holdings = [
        item for row in rows
        if (item := _holding(row.get("ticker"), row.get("longName"), row.get("percentWeight")))
    ]
    return {"asOf": str(payload.get("asOfDate") or "")[:10], "holdings": holdings}


def _parse_avantis(text: str) -> Dict[str, Any]:
    date_match = re.search(r'etfHoldingsAsOfDate:"([^"]+)"', text)
    start = text.find("etfHoldings:[")
    if start < 0:
        raise ValueError("Avantis holdings list was not found")
    end = text.find("],sectors:", start)
    if end < 0:
        end = text.find("],sector", start)
    block = text[start:end if end > start else len(text)]
    pattern = re.compile(
        r'\{name:"((?:\\.|[^"])*)",ticker:"((?:\\.|[^"])*)"[^{}]*?weight:"([^"]+)"'
    )
    holdings = []
    for name, ticker, weight in pattern.findall(block):
        item = _holding(ticker, name.replace(r'\"', '"'), weight)
        if item:
            holdings.append(item)
    as_of = ""
    if date_match:
        as_of = datetime.strptime(date_match.group(1), "%m/%d/%Y").date().isoformat()
    return {"asOf": as_of, "holdings": holdings}


def _parse_ishares(text: str) -> Dict[str, Any]:
    date_match = re.search(r'Fund Holdings as of,"?([^"\r\n]+)', text)
    rows = list(csv.reader(io.StringIO(text)))
    header_index = next((index for index, row in enumerate(rows) if row and row[0] == "Ticker"), -1)
    if header_index < 0:
        raise ValueError("iShares holdings header was not found")
    headers = rows[header_index]
    holdings = []
    for values in rows[header_index + 1:]:
        if len(values) < len(headers):
            continue
        row = dict(zip(headers, values))
        item = _holding(row.get("Ticker"), row.get("Name"), row.get("Weight (%)"))
        if item:
            holdings.append(item)
    as_of = ""
    if date_match:
        as_of = datetime.strptime(date_match.group(1).strip(), "%b %d, %Y").date().isoformat()
    return {"asOf": as_of, "holdings": holdings}


def _parse_global_x(text: str, downloader: Callable[[str], str]) -> Dict[str, Any]:
    match = re.search(r'https://assets\.globalxetfs\.com/funds/holdings/pave_full-holdings_[0-9]+\.csv', text)
    if not match:
        raise ValueError("Global X official holdings download was not found")
    csv_text = downloader(match.group(0))
    date_match = re.search(r'Fund Holdings Data as of ([0-9/]+)', csv_text)
    rows = list(csv.reader(io.StringIO(csv_text)))
    header_index = next((index for index, row in enumerate(rows) if row and row[0] == "% of Net Assets"), -1)
    if header_index < 0:
        raise ValueError("Global X holdings header was not found")
    holdings = []
    for values in rows[header_index + 1:]:
        if len(values) < 3:
            continue
        item = _holding(values[1], values[2], values[0])
        if item:
            holdings.append(item)
    as_of = ""
    if date_match:
        as_of = datetime.strptime(date_match.group(1), "%m/%d/%Y").date().isoformat()
    return {"asOf": as_of, "holdings": holdings, "downloadUrl": match.group(0)}


def _canonical_company(holding: Dict[str, Any]) -> Optional[str]:
    ticker = str(holding.get("ticker") or "").upper()
    name = str(holding.get("name") or "").upper()
    for symbol, aliases in DIRECT_COMPANIES.items():
        if ticker in aliases["tickers"] or any(alias in name for alias in aliases["names"]):
            return symbol
    return None


def calculate_lookthrough(weights: Dict[str, float], funds: Dict[str, Dict[str, Any]],
                          today: Optional[date] = None) -> Dict[str, Any]:
    current_date = today or date.today()
    direct = {symbol: float(weights.get(symbol, 0)) for symbol in DIRECT_COMPANIES}
    hidden = {symbol: 0.0 for symbol in DIRECT_COMPANIES}
    fund_overlaps = {fund: {symbol: 0.0 for symbol in DIRECT_COMPANIES} for fund in EQUITY_FUNDS}
    source_rows = []
    for fund in EQUITY_FUNDS:
        record = funds.get(fund) or {}
        holdings = record.get("holdings") or []
        as_of = str(record.get("asOf") or "")
        try:
            age = (current_date - date.fromisoformat(as_of)).days
        except ValueError:
            age = None
        total_weight = sum(float(item.get("weight") or 0) for item in holdings)
        ready = bool(holdings) and age is not None and 0 <= age <= MAX_AGE_DAYS and 95 <= total_weight <= 105
        source_rows.append({
            "symbol": fund, "asOf": as_of or None, "ageDays": age,
            "holdings": len(holdings), "reportedWeight": round(total_weight, 2),
            "ready": ready, "source": FUND_SOURCES[fund], "error": record.get("error"),
        })
        if not ready:
            continue
        fund_weight = float(weights.get(fund, 0))
        for holding in holdings:
            symbol = _canonical_company(holding)
            if symbol:
                holding_weight = float(holding["weight"])
                hidden[symbol] += fund_weight * holding_weight / 100
                fund_overlaps[fund][symbol] += holding_weight

    exposures = sorted(({
        "symbol": symbol,
        "direct": round(direct[symbol], 2),
        "insideFunds": round(hidden[symbol], 2),
        "effective": round(direct[symbol] + hidden[symbol], 2),
    } for symbol in DIRECT_COMPANIES), key=lambda item: item["effective"], reverse=True)
    ready_count = sum(bool(item["ready"]) for item in source_rows)
    return {
        "status": "complete" if ready_count == len(EQUITY_FUNDS) else "incomplete",
        "complete": ready_count == len(EQUITY_FUNDS),
        "fundsReady": ready_count,
        "fundsTotal": len(EQUITY_FUNDS),
        "maxAgeDays": MAX_AGE_DAYS,
        "sources": source_rows,
        "exposures": exposures,
        "fundOverlaps": {
            fund: {symbol: round(value, 4) for symbol, value in overlaps.items() if value > 0}
            for fund, overlaps in fund_overlaps.items()
        },
        "note": "Effective exposure adds direct shares to the same company held inside the six equity ETFs.",
    }


def fetch_fund_holdings(downloader: Callable[[str], str] = _download) -> Dict[str, Dict[str, Any]]:
    parsers = {
        "VTI": lambda text: _parse_vanguard(text),
        "VEA": lambda text: _parse_vanguard(text),
        "AVUV": lambda text: _parse_avantis(text),
        "AVDV": lambda text: _parse_avantis(text),
        "IEMG": lambda text: _parse_ishares(text),
        "PAVE": lambda text: _parse_global_x(text, downloader),
    }
    records: Dict[str, Dict[str, Any]] = {}
    for fund in EQUITY_FUNDS:
        try:
            records[fund] = parsers[fund](downloader(FUND_SOURCES[fund]))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            records[fund] = {"asOf": None, "holdings": [], "error": str(error)}
    return records


def fund_lookthrough_snapshot(weights: Dict[str, float], force: bool = False,
                              downloader: Callable[[str], str] = _download) -> Dict[str, Any]:
    global _CACHE
    now = int(time.time())
    with _LOCK:
        if downloader is _download and not force and _CACHE and now - int(_CACHE.get("generatedAt") or 0) < CACHE_SECONDS:
            return dict(_CACHE)
        payload = calculate_lookthrough(weights, fetch_fund_holdings(downloader))
        payload["generatedAt"] = now
        if downloader is _download:
            _CACHE = dict(payload)
        return payload
