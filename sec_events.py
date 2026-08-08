"""Insider dealing and material filing events, straight from SEC EDGAR.

Two free evidence families the price archive cannot contain.

**Form 4 — insider transactions.** The signal people mean by "insider buying"
is a director or officer choosing to buy shares on the open market with their
own money. That is transaction code ``P``. It is a small minority of Form 4
activity: most filings are awards (``A``), option exercises (``M``) and shares
surrendered to cover tax (``F``), which say nothing about conviction because
the insider never chose to transact. Mixing them together is the single most
common way insider data is misread, so they are separated here and the routine
codes are never counted as buying.

Sales get the same care. A disposal under a pre-arranged 10b5-1 plan was
scheduled months earlier and carries little information; the filing declares
this, so Kestrel records it rather than treating every sale as a warning.

**8-K — material events.** The item numbers say what kind of event occurred:
results, a material agreement, an executive change, a restructuring. These come
free with the submissions index, needing no extra request.

Every record keeps the filing date *and* the acceptance timestamp, so a feature
built from it can prove it was knowable at the decision cutoff.
"""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ElementTree
from typing import Any, Dict, List, Optional, Sequence

from sec_data import sec_bytes, sec_identity


SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

# Transaction codes that represent a deliberate open-market decision.
OPEN_MARKET_BUY = "P"
OPEN_MARKET_SELL = "S"
# Codes where the insider did not choose to transact at that price.
ROUTINE_CODES = {
    "A": "Grant or award",
    "M": "Option or derivative exercise",
    "F": "Shares surrendered to cover tax",
    "G": "Gift",
    "C": "Conversion of a derivative",
    "D": "Disposition to the issuer",
    "I": "Discretionary transaction",
}

EIGHT_K_ITEMS = {
    "1.01": "Material agreement entered",
    "1.02": "Material agreement terminated",
    "1.03": "Bankruptcy or receivership",
    "2.01": "Assets acquired or disposed",
    "2.02": "Results of operations",
    "2.03": "Material financial obligation",
    "2.04": "Obligation accelerated",
    "2.05": "Costs from exit or disposal",
    "2.06": "Material impairment",
    "3.01": "Delisting or listing-rule failure",
    "3.02": "Unregistered equity sale",
    "4.01": "Auditor changed",
    "4.02": "Prior statements not reliable",
    "5.01": "Change in control",
    "5.02": "Director or officer change",
    "5.07": "Shareholder vote results",
    "7.01": "Regulation FD disclosure",
    "8.01": "Other material event",
    "9.01": "Financial statements and exhibits",
}
# Items that rarely carry new information on their own.
ROUTINE_ITEMS = {"9.01", "5.07"}

INSIDER_WINDOWS = (30, 90, 180)
DEFAULT_FORM4_LIMIT = 40


def _text(node: Optional[ElementTree.Element], path: str) -> Optional[str]:
    if node is None:
        return None
    found = node.find(path)
    return found.text.strip() if found is not None and found.text else None


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None


def _flag(node: Optional[ElementTree.Element], path: str) -> bool:
    value = (_text(node, path) or "").strip().lower()
    return value in {"true", "1"}


def parse_form4(payload: bytes) -> Dict[str, Any]:
    """Parse one Form 4 into transactions, keeping the code that explains it."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return {"status": "unreadable", "transactions": []}

    owner = root.find("reportingOwner")
    relationship = owner.find("reportingOwnerRelationship") if owner is not None else None
    role = []
    if _flag(relationship, "isDirector"):
        role.append("director")
    if _flag(relationship, "isOfficer"):
        role.append("officer")
    if _flag(relationship, "isTenPercentOwner"):
        role.append("ten-percent-owner")
    officer_title = _text(relationship, "officerTitle")
    planned = _flag(root, "aff10b5One")

    transactions: List[Dict[str, Any]] = []
    table = root.find("nonDerivativeTable")
    if table is not None:
        for entry in table.findall("nonDerivativeTransaction"):
            coding = entry.find("transactionCoding")
            code = _text(coding, "transactionCode")
            amounts = entry.find("transactionAmounts")
            shares = _number(_text(amounts, "transactionShares/value"))
            price = _number(_text(amounts, "transactionPricePerShare/value"))
            acquired = (_text(amounts, "transactionAcquiredDisposedCode/value") or "").upper()
            transaction_date = _text(entry, "transactionDate/value")
            if not code or shares is None:
                continue
            transactions.append({
                "code": code,
                "meaning": (
                    "Open-market purchase" if code == OPEN_MARKET_BUY else
                    "Open-market sale" if code == OPEN_MARKET_SELL else
                    ROUTINE_CODES.get(code, "Other transaction")
                ),
                "routine": code in ROUTINE_CODES,
                "transactionDate": transaction_date,
                "shares": shares,
                "pricePerShare": price,
                "value": round(shares * price, 2) if price else None,
                "direction": "acquired" if acquired == "A" else "disposed" if acquired == "D" else None,
                "preArrangedPlan": planned,
            })

    return {
        "status": "parsed",
        "issuerSymbol": _text(root, "issuer/issuerTradingSymbol"),
        "ownerName": _text(owner, "reportingOwnerId/rptOwnerName") if owner is not None else None,
        "roles": role,
        "officerTitle": officer_title,
        "periodOfReport": _text(root, "periodOfReport"),
        "preArrangedPlan": planned,
        "transactions": transactions,
    }


def insider_transactions(symbol: str, limit: int = DEFAULT_FORM4_LIMIT) -> Dict[str, Any]:
    """Recent Form 4 activity for one issuer, newest filing first."""
    identity = sec_identity(symbol)
    if identity.get("status") != "verified":
        return {"status": "unavailable", "symbol": symbol.upper(), "filings": [],
                "reason": "No SEC identity for this ticker"}
    cik = identity["cik"]
    try:
        import json
        payload = json.loads(sec_bytes(SUBMISSIONS_URL.format(cik=cik)).decode("utf-8"))
    except (RuntimeError, ValueError) as error:
        return {"status": "unavailable", "symbol": symbol.upper(), "filings": [],
                "reason": str(error)}

    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    filings: List[Dict[str, Any]] = []
    for index, form in enumerate(forms):
        if form != "4":
            continue
        accession = str((recent.get("accessionNumber") or [""] * len(forms))[index] or "")
        document = str((recent.get("primaryDocument") or [""] * len(forms))[index] or "")
        # The listed document is the styled rendering; the raw XML sits beside it.
        document = document.split("/")[-1]
        url = ARCHIVE_URL.format(
            cik=str(int(cik)), accession=accession.replace("-", ""), document=document
        )
        try:
            parsed = parse_form4(sec_bytes(url, accept="application/xml"))
        except RuntimeError:
            continue
        if parsed["status"] != "parsed":
            continue
        filings.append({
            **parsed,
            "filedOn": str((recent.get("filingDate") or [""] * len(forms))[index] or ""),
            "acceptedAt": str((recent.get("acceptanceDateTime") or [""] * len(forms))[index] or ""),
            "accession": accession,
            "sourceUrl": url,
        })
        if len(filings) >= limit:
            break
    return {"status": "verified" if filings else "none-found", "symbol": identity["symbol"],
            "cik": cik, "filings": filings, "source": "SEC EDGAR Form 4"}


def insider_summary(symbol: str, as_of: Optional[dt.date] = None,
                    filings: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Open-market conviction only, over the declared windows.

    Awards, exercises and tax withholding are excluded from buying entirely.
    They are counted separately so their absence from the buy figure is visible
    rather than silent.
    """
    as_of = as_of or dt.date.today()
    if filings is None:
        result = insider_transactions(symbol)
        if result["status"] not in {"verified", "none-found"}:
            return {"status": "unavailable", "symbol": symbol.upper(),
                    "reason": result.get("reason")}
        filings = result["filings"]

    rows: List[Dict[str, Any]] = []
    routine_count = 0
    for filing in filings:
        filed = filing.get("filedOn")
        try:
            filed_date = dt.date.fromisoformat(str(filed)[:10])
        except (TypeError, ValueError):
            continue
        if filed_date > as_of:
            continue
        for transaction in filing.get("transactions") or []:
            if transaction.get("routine"):
                routine_count += 1
                continue
            rows.append({**transaction, "filedOn": filed, "filedDate": filed_date,
                         "owner": filing.get("ownerName"), "roles": filing.get("roles")})

    windows: Dict[str, Any] = {}
    for days in INSIDER_WINDOWS:
        cutoff = as_of - dt.timedelta(days=days)
        selected = [row for row in rows if row["filedDate"] >= cutoff]
        buys = [row for row in selected if row["code"] == OPEN_MARKET_BUY]
        sells = [row for row in selected if row["code"] == OPEN_MARKET_SELL]
        unplanned_sells = [row for row in sells if not row.get("preArrangedPlan")]
        buy_value = sum(row["value"] or 0 for row in buys)
        sell_value = sum(row["value"] or 0 for row in sells)
        windows[str(days)] = {
            "openMarketBuys": len(buys),
            "openMarketSells": len(sells),
            "salesOutsideAPlan": len(unplanned_sells),
            "buyValue": round(buy_value, 2),
            "sellValue": round(sell_value, 2),
            "netValue": round(buy_value - sell_value, 2),
            "distinctBuyers": len({row["owner"] for row in buys if row.get("owner")}),
        }

    buys = [row for row in rows if row["code"] == OPEN_MARKET_BUY]
    last_buy = max((row["filedDate"] for row in buys), default=None)
    return {
        "status": "measured",
        "symbol": symbol.upper(),
        "asOf": as_of.isoformat(),
        "windows": windows,
        "daysSinceOpenMarketBuy": (as_of - last_buy).days if last_buy else None,
        "lastOpenMarketBuy": last_buy.isoformat() if last_buy else None,
        "routineTransactionsExcluded": routine_count,
        "basis": (
            "Only transaction codes P and S count. Awards, exercises, tax withholding, "
            "gifts and conversions are excluded because the insider chose neither the "
            "timing nor the price."
        ),
        "source": "SEC EDGAR Form 4",
    }


def filing_events(symbol: str, limit: int = 40) -> Dict[str, Any]:
    """Material 8-K events with their item numbers translated into English."""
    identity = sec_identity(symbol)
    if identity.get("status") != "verified":
        return {"status": "unavailable", "symbol": symbol.upper(), "events": []}
    try:
        import json
        payload = json.loads(sec_bytes(SUBMISSIONS_URL.format(cik=identity["cik"])).decode("utf-8"))
    except (RuntimeError, ValueError) as error:
        return {"status": "unavailable", "symbol": symbol.upper(), "events": [],
                "reason": str(error)}

    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    events: List[Dict[str, Any]] = []
    for index, form in enumerate(forms):
        if form != "8-K":
            continue
        raw_items = str((recent.get("items") or [""] * len(forms))[index] or "")
        codes = [item.strip() for item in raw_items.split(",") if item.strip()]
        material = [code for code in codes if code not in ROUTINE_ITEMS]
        events.append({
            "filedOn": str((recent.get("filingDate") or [""] * len(forms))[index] or ""),
            "acceptedAt": str((recent.get("acceptanceDateTime") or [""] * len(forms))[index] or ""),
            "items": codes,
            "descriptions": [EIGHT_K_ITEMS.get(code, f"Item {code}") for code in codes],
            "material": bool(material),
            "accession": str((recent.get("accessionNumber") or [""] * len(forms))[index] or ""),
        })
        if len(events) >= limit:
            break
    return {"status": "verified" if events else "none-found", "symbol": identity["symbol"],
            "events": events, "source": "SEC EDGAR 8-K"}


# -- point-in-time storage ---------------------------------------------
#
# Events are stored with both timestamps the leakage guard needs: when the
# filing was published, and when Kestrel could first have read it. Features
# join on ``available_at`` so a row can never use a filing that arrived after
# its decision cutoff.

def _utc(value: str, fallback_date: str) -> str:
    """Normalise to the UTC form ``feature_is_available`` requires."""
    text = str(value or "").strip()
    if text:
        text = text.replace(" ", "T")
        if text.endswith("Z"):
            return text
        if len(text) >= 19:
            return text[:19] + "Z"
    return f"{str(fallback_date)[:10]}T23:59:59Z"


def store_events(symbol: str, database: Optional[Any] = None,
                 form4_limit: int = DEFAULT_FORM4_LIMIT,
                 include_insider: bool = True) -> Dict[str, Any]:
    """Fetch and persist insider and filing events for one issuer.

    ``include_insider`` off costs a single submissions request, because 8-K
    item numbers arrive with the index. Insider detail needs one further
    request per Form 4, so a whole-universe sweep starts without it.
    """
    import sqlite3
    from pathlib import Path

    from outcome_source import DEFAULT_DATABASE

    database = Path(database) if database else DEFAULT_DATABASE
    if not Path(database).exists():
        return {"status": "no-archive", "symbol": symbol.upper(), "stored": 0}

    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    insider = (insider_transactions(symbol, limit=form4_limit) if include_insider
               else {"status": "skipped", "cik": None, "filings": []})
    events = filing_events(symbol)
    rows: List[tuple] = []
    ticker = symbol.upper()
    cik = insider.get("cik")

    for filing in insider.get("filings") or []:
        published = _utc(filing.get("filedOn"), filing.get("filedOn"))
        available = _utc(filing.get("acceptedAt"), filing.get("filedOn"))
        for transaction in filing.get("transactions") or []:
            if transaction.get("routine"):
                continue
            event_type = ("insider_buy" if transaction["code"] == OPEN_MARKET_BUY
                          else "insider_sell" if transaction["code"] == OPEN_MARKET_SELL else None)
            if not event_type:
                continue
            rows.append((
                ticker, cik, event_type, str(transaction.get("transactionDate") or "")[:10],
                published, available, transaction.get("value"),
                (filing.get("ownerName") or "")[:120], filing.get("accession") or "",
                "SEC EDGAR Form 4", retrieved,
            ))

    for event in events.get("events") or []:
        published = _utc(event.get("filedOn"), event.get("filedOn"))
        available = _utc(event.get("acceptedAt"), event.get("filedOn"))
        for code in event.get("items") or []:
            rows.append((
                ticker, cik, "results" if code == "2.02" else "filing_event",
                str(event.get("filedOn") or "")[:10], published, available, None,
                code, event.get("accession") or "", "SEC EDGAR 8-K", retrieved,
            ))

    if not rows:
        return {"status": "none-found", "symbol": ticker, "stored": 0}
    from market_history import MarketHistoryStore

    # Connect through the store so the schema migration runs; an archive built
    # before issuer_events existed would otherwise have no table to write to.
    try:
        connection = MarketHistoryStore(database).connect()
    except sqlite3.DatabaseError as error:
        return {"status": "failed", "symbol": ticker, "stored": 0, "reason": str(error)}
    try:
        connection.executemany(
            "INSERT OR REPLACE INTO issuer_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
        connection.commit()
    except sqlite3.DatabaseError as error:
        return {"status": "failed", "symbol": ticker, "stored": 0, "reason": str(error)}
    finally:
        connection.close()
    return {"status": "stored", "symbol": ticker, "stored": len(rows),
            "insiderFilings": len(insider.get("filings") or []),
            "filingEvents": len(events.get("events") or [])}


def load_events(ticker: str, database: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Every stored event for one issuer, oldest first."""
    import sqlite3
    from pathlib import Path

    from outcome_source import DEFAULT_DATABASE

    database = Path(database) if database else DEFAULT_DATABASE
    if not Path(database).exists():
        return []
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT event_type, event_date, published_at, available_at, value, detail
               FROM issuer_events WHERE ticker=? ORDER BY available_at""", (ticker.upper(),)
        ).fetchall()
    except sqlite3.DatabaseError:
        return []
    finally:
        connection.close()
    return [dict(row) for row in rows]
