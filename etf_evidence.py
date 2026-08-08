"""Append-only point-in-time ETF holdings and fee evidence.

The archive stores the issuer or SEC document separately from its normalized
facts.  Valid time (the holdings/fee as-of date) and recorded time (publication,
availability and retrieval) are all retained.  A correction is another row;
SQLite triggers prevent old evidence from being edited or deleted.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / ".kestrel-data" / "etf" / "etf-evidence.sqlite3"
SOURCE_TYPES = {"issuer", "sec_nport"}
POSITION_TYPES = {"security", "cash", "derivative"}
WEIGHT_UNITS = {"percent", "fraction"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if len(raw) != 64:
        return None
    try:
        int(raw, 16)
    except ValueError:
        return None
    return raw


def _utc(value: Any) -> Optional[str]:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: Any) -> Optional[str]:
    try:
        return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _currency(value: Any) -> Optional[str]:
    raw = str(value or "").strip().upper()
    return raw if len(raw) == 3 and raw.isalpha() else None


class EtfEvidenceArchive:
    """Immutable issuer/SEC evidence with conservative look-through selection."""

    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)

    def connect(self, create: bool = True) -> sqlite3.Connection:
        if create:
            self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        if create:
            connection.execute("PRAGMA journal_mode=WAL")
            self._migrate(connection)
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_documents (
                document_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_record_id TEXT NOT NULL,
                accession TEXT,
                form_type TEXT,
                amendment INTEGER NOT NULL,
                supersedes_document_id TEXT,
                publication_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                raw_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                UNIQUE(source_type, source_record_id, source_hash)
            );
            CREATE TABLE IF NOT EXISTS holdings_reports (
                report_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                fund_id TEXT NOT NULL,
                share_class_id TEXT NOT NULL,
                ticker TEXT,
                cik TEXT,
                series_id TEXT,
                class_contract_id TEXT,
                as_of_date TEXT NOT NULL,
                publication_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                reporting_lag_days INTEGER NOT NULL,
                base_currency TEXT NOT NULL,
                weight_unit TEXT NOT NULL,
                reported_total_weight REAL,
                coverage_complete INTEGER NOT NULL,
                cash_resolved INTEGER NOT NULL,
                derivatives_resolved INTEGER NOT NULL,
                currency_resolved INTEGER NOT NULL,
                correction_of TEXT,
                content_hash TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES source_documents(document_id)
            );
            CREATE INDEX IF NOT EXISTS holdings_reports_asof
                ON holdings_reports(fund_id, share_class_id, available_at, retrieved_at);
            CREATE TABLE IF NOT EXISTS holding_positions (
                position_id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                position_type TEXT NOT NULL,
                security_id TEXT,
                issuer_id TEXT,
                ticker TEXT,
                name TEXT NOT NULL,
                units REAL,
                unit_name TEXT,
                market_value REAL,
                currency TEXT,
                reported_weight REAL,
                derivative_json TEXT NOT NULL,
                quality_flags_json TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES holdings_reports(report_id),
                UNIQUE(report_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS fee_reports (
                fee_report_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                fund_id TEXT NOT NULL,
                share_class_id TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                publication_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                reporting_lag_days INTEGER NOT NULL,
                currency TEXT,
                gross_expense_ratio REAL,
                net_expense_ratio REAL,
                fee_unit TEXT NOT NULL,
                waiver_end_date TEXT,
                correction_of TEXT,
                content_hash TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES source_documents(document_id)
            );
            CREATE INDEX IF NOT EXISTS fee_reports_asof
                ON fee_reports(fund_id, share_class_id, available_at, retrieved_at);
            """
        )
        for table in ("source_documents", "holdings_reports", "holding_positions", "fee_reports"):
            connection.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'immutable ETF evidence cannot be updated'); END"""
            )
            connection.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'immutable ETF evidence cannot be deleted'); END"""
            )
        connection.commit()

    @staticmethod
    def _document(raw: Dict[str, Any]) -> Dict[str, Any]:
        source_type = str(raw.get("sourceType") or "").strip()
        record_id = str(raw.get("sourceRecordId") or "").strip()
        publication = _utc(raw.get("publicationAt"))
        available = _utc(raw.get("availableAt"))
        retrieved = _utc(raw.get("retrievedAt"))
        source_url = str(raw.get("sourceUrl") or "").strip()
        source_hash = _sha256(raw.get("sourceHash"))
        raw_hash = _sha256(raw.get("rawHash")) or source_hash
        amendment = raw.get("amendment") is True
        supersedes = str(raw.get("supersedesDocumentId") or "").strip() or None
        if source_type not in SOURCE_TYPES or not record_id or not source_url:
            raise ValueError("Authoritative source type, record ID and URL are required")
        if not publication or not available or not retrieved or not source_hash or not raw_hash:
            raise ValueError("Exact source times and SHA-256 hashes are required")
        if publication > available or available > retrieved:
            raise ValueError("Source publication, availability and retrieval clocks are inconsistent")
        if amendment and not supersedes:
            raise ValueError("An amended filing must identify the document it supersedes")
        body = {
            "sourceType": source_type, "sourceRecordId": record_id,
            "accession": str(raw.get("accession") or "").strip() or None,
            "formType": str(raw.get("formType") or "").strip() or None,
            "amendment": amendment, "supersedesDocumentId": supersedes,
            "publicationAt": publication, "availableAt": available, "retrievedAt": retrieved,
            "sourceUrl": source_url, "sourceHash": source_hash, "rawHash": raw_hash,
            "metadata": raw.get("metadata") or {},
        }
        body["documentId"] = _digest(body)
        return body

    @staticmethod
    def _position(raw: Dict[str, Any], weight_unit: str, ordinal: int) -> Dict[str, Any]:
        position_type = str(raw.get("positionType") or "security").strip().lower()
        name = str(raw.get("name") or "").strip()
        currency = _currency(raw.get("currency")) if raw.get("currency") else None
        weight = _finite(raw.get("reportedWeight"))
        units = _finite(raw.get("units"))
        market_value = _finite(raw.get("marketValue"))
        derivative = raw.get("derivative") or {}
        if position_type not in POSITION_TYPES or not name:
            raise ValueError("Every holding needs a recognized position type and name")
        if raw.get("currency") and not currency:
            raise ValueError("Holding currency must be an ISO 4217 code")
        if weight is not None and weight < 0 and position_type != "derivative":
            raise ValueError("Only derivatives may carry a negative reported weight")
        if position_type == "derivative" and not derivative:
            raise ValueError("Derivative positions must preserve their contract details")
        body = {
            "ordinal": ordinal, "positionType": position_type,
            "securityId": str(raw.get("securityId") or "").strip() or None,
            "issuerId": str(raw.get("issuerId") or "").strip() or None,
            "ticker": str(raw.get("ticker") or "").strip().upper() or None,
            "name": name, "units": units,
            "unitName": str(raw.get("unitName") or "").strip() or None,
            "marketValue": market_value, "currency": currency,
            "reportedWeight": weight, "weightUnit": weight_unit,
            "derivative": derivative, "qualityFlags": sorted(set(raw.get("qualityFlags") or [])),
        }
        body["contentHash"] = _digest(body)
        return body

    def append_holdings(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append one issuer/N-PORT holdings report without deriving missing facts."""
        document = self._document(record.get("document") or {})
        fund_id = str(record.get("fundId") or "").strip()
        share_class_id = str(record.get("shareClassId") or "").strip()
        as_of = _date(record.get("asOfDate"))
        base_currency = _currency(record.get("baseCurrency"))
        weight_unit = str(record.get("weightUnit") or "").strip()
        if not fund_id or not share_class_id or not as_of or not base_currency:
            raise ValueError("Stable fund/share-class identity, as-of date and currency are required")
        if weight_unit not in WEIGHT_UNITS:
            raise ValueError("Holdings weight unit must be percent or fraction")
        if as_of > document["publicationAt"][:10]:
            raise ValueError("Holdings cannot be published before their as-of date")
        positions = [self._position(row, weight_unit, index) for index, row in enumerate(record.get("positions") or [])]
        reported_total = _finite(record.get("reportedTotalWeight"))
        if reported_total is None and any(row["reportedWeight"] is not None for row in positions):
            # A total is never manufactured from a potentially incomplete position list.
            raise ValueError("A source-reported total is required when position weights are present")
        currencies = {row["currency"] for row in positions if row["marketValue"] is not None and row["currency"]}
        currency_resolved = (
            record.get("currencyResolved") is True
            and currencies.issubset({base_currency})
        )
        report_body = {
            "documentId": document["documentId"], "fundId": fund_id,
            "shareClassId": share_class_id, "ticker": str(record.get("ticker") or "").upper() or None,
            "cik": str(record.get("cik") or "").strip() or None,
            "seriesId": str(record.get("seriesId") or "").strip() or None,
            "classContractId": str(record.get("classContractId") or "").strip() or None,
            "asOfDate": as_of, "publicationAt": document["publicationAt"],
            "availableAt": document["availableAt"], "retrievedAt": document["retrievedAt"],
            "reportingLagDays": (dt.date.fromisoformat(document["availableAt"][:10]) - dt.date.fromisoformat(as_of)).days,
            "baseCurrency": base_currency, "weightUnit": weight_unit,
            "reportedTotalWeight": reported_total,
            "coverageComplete": record.get("coverageComplete") is True,
            "cashResolved": record.get("cashResolved") is True,
            "derivativesResolved": record.get("derivativesResolved") is True,
            "currencyResolved": currency_resolved,
            "correctionOf": str(record.get("correctionOf") or "").strip() or None,
            "positions": positions,
        }
        report_hash = _digest(report_body)
        report_id = _digest({"kind": "holdings", "contentHash": report_hash})
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT report_id FROM holdings_reports WHERE report_id=?", (report_id,)
            ).fetchone()
            if existing:
                return {"status": "unchanged", "reportId": report_id,
                        "documentId": document["documentId"]}
            same_record = connection.execute(
                """SELECT d.document_id, d.source_hash FROM source_documents d
                   WHERE d.source_type=? AND d.source_record_id=? ORDER BY d.retrieved_at DESC LIMIT 1""",
                (document["sourceType"], document["sourceRecordId"]),
            ).fetchone()
            if same_record and same_record["source_hash"] != document["sourceHash"]:
                if not (document["amendment"] or report_body["correctionOf"]):
                    raise ValueError("Changed source record must be appended as an amendment or correction")
            if document["amendment"]:
                parent = connection.execute(
                    "SELECT 1 FROM source_documents WHERE document_id=?",
                    (document["supersedesDocumentId"],),
                ).fetchone()
                if not parent:
                    raise ValueError("Amended filing references an unknown source document")
            if report_body["correctionOf"]:
                parent = connection.execute(
                    "SELECT 1 FROM holdings_reports WHERE report_id=?", (report_body["correctionOf"],)
                ).fetchone()
                if not parent:
                    raise ValueError("Correction references an unknown holdings report")
            connection.execute(
                """INSERT OR IGNORE INTO source_documents VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document["documentId"], document["sourceType"], document["sourceRecordId"],
                 document["accession"], document["formType"], int(document["amendment"]),
                 document["supersedesDocumentId"], document["publicationAt"],
                 document["availableAt"], document["retrievedAt"], document["sourceUrl"],
                 document["sourceHash"], document["rawHash"], _canonical(document["metadata"])),
            )
            connection.execute(
                """INSERT INTO holdings_reports VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, document["documentId"], fund_id, share_class_id,
                 report_body["ticker"], report_body["cik"], report_body["seriesId"],
                 report_body["classContractId"], as_of, document["publicationAt"],
                 document["availableAt"], document["retrievedAt"], report_body["reportingLagDays"],
                 base_currency, weight_unit, reported_total, int(report_body["coverageComplete"]),
                 int(report_body["cashResolved"]), int(report_body["derivativesResolved"]),
                 int(currency_resolved), report_body["correctionOf"], report_hash),
            )
            for row in positions:
                position_id = _digest({"reportId": report_id, "ordinal": row["ordinal"],
                                       "contentHash": row["contentHash"]})
                connection.execute(
                    """INSERT INTO holding_positions VALUES
                       (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (position_id, report_id, row["ordinal"], row["positionType"],
                     row["securityId"], row["issuerId"], row["ticker"], row["name"],
                     row["units"], row["unitName"], row["marketValue"], row["currency"],
                     row["reportedWeight"], _canonical(row["derivative"]),
                     _canonical(row["qualityFlags"]), row["contentHash"]),
                )
            connection.commit()
        return {"status": "recorded", "reportId": report_id,
                "documentId": document["documentId"], "contentHash": report_hash}

    def append_fees(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Append share-class fee evidence; percent and fraction are never conflated."""
        document = self._document(record.get("document") or {})
        fund_id = str(record.get("fundId") or "").strip()
        share_class_id = str(record.get("shareClassId") or "").strip()
        as_of = _date(record.get("asOfDate"))
        fee_unit = str(record.get("feeUnit") or "").strip()
        gross = _finite(record.get("grossExpenseRatio"))
        net = _finite(record.get("netExpenseRatio"))
        currency = _currency(record.get("currency")) if record.get("currency") else None
        correction_of = str(record.get("correctionOf") or "").strip() or None
        if not fund_id or not share_class_id or not as_of or fee_unit not in WEIGHT_UNITS:
            raise ValueError("Fee evidence requires fund/share class, as-of date and explicit unit")
        if gross is None and net is None:
            raise ValueError("At least one source-reported expense ratio is required")
        if min(value for value in (gross, net) if value is not None) < 0:
            raise ValueError("Expense ratios cannot be negative")
        if record.get("currency") and not currency:
            raise ValueError("Fee currency must be an ISO 4217 code")
        if as_of > document["publicationAt"][:10]:
            raise ValueError("Fees cannot be published before their as-of date")
        body = {
            "documentId": document["documentId"], "fundId": fund_id,
            "shareClassId": share_class_id, "asOfDate": as_of,
            "publicationAt": document["publicationAt"], "availableAt": document["availableAt"],
            "retrievedAt": document["retrievedAt"],
            "reportingLagDays": (dt.date.fromisoformat(document["availableAt"][:10]) - dt.date.fromisoformat(as_of)).days,
            "currency": currency, "grossExpenseRatio": gross, "netExpenseRatio": net,
            "feeUnit": fee_unit, "waiverEndDate": _date(record.get("waiverEndDate")),
            "correctionOf": correction_of,
        }
        content_hash = _digest(body)
        fee_report_id = _digest({"kind": "fees", "contentHash": content_hash})
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT fee_report_id FROM fee_reports WHERE fee_report_id=?", (fee_report_id,)
            ).fetchone()
            if existing:
                return {"status": "unchanged", "feeReportId": fee_report_id}
            same_record = connection.execute(
                """SELECT document_id, source_hash FROM source_documents
                   WHERE source_type=? AND source_record_id=? ORDER BY retrieved_at DESC LIMIT 1""",
                (document["sourceType"], document["sourceRecordId"]),
            ).fetchone()
            if same_record and same_record["source_hash"] != document["sourceHash"]:
                if not (document["amendment"] or correction_of):
                    raise ValueError("Changed source record must be appended as an amendment or correction")
            if document["amendment"] and not connection.execute(
                "SELECT 1 FROM source_documents WHERE document_id=?",
                (document["supersedesDocumentId"],),
            ).fetchone():
                raise ValueError("Amended filing references an unknown source document")
            if correction_of and not connection.execute(
                "SELECT 1 FROM fee_reports WHERE fee_report_id=?", (correction_of,)
            ).fetchone():
                raise ValueError("Correction references an unknown fee report")
            connection.execute(
                """INSERT OR IGNORE INTO source_documents VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document["documentId"], document["sourceType"], document["sourceRecordId"],
                 document["accession"], document["formType"], int(document["amendment"]),
                 document["supersedesDocumentId"], document["publicationAt"],
                 document["availableAt"], document["retrievedAt"], document["sourceUrl"],
                 document["sourceHash"], document["rawHash"], _canonical(document["metadata"])),
            )
            connection.execute(
                "INSERT INTO fee_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fee_report_id, document["documentId"], fund_id, share_class_id, as_of,
                 document["publicationAt"], document["availableAt"], document["retrievedAt"],
                 body["reportingLagDays"], currency, gross, net, fee_unit,
                 body["waiverEndDate"], correction_of, content_hash),
            )
            connection.commit()
        return {"status": "recorded", "feeReportId": fee_report_id,
                "documentId": document["documentId"], "contentHash": content_hash}

    def _report(self, report_id: str) -> Dict[str, Any]:
        with self.connect(create=False) as connection:
            report = connection.execute(
                """SELECT r.*, d.source_type, d.source_record_id, d.accession, d.form_type,
                          d.source_url, d.source_hash, d.raw_hash, d.amendment
                   FROM holdings_reports r JOIN source_documents d USING(document_id)
                   WHERE r.report_id=?""", (report_id,)
            ).fetchone()
            if not report:
                return {}
            positions = [dict(row) for row in connection.execute(
                "SELECT * FROM holding_positions WHERE report_id=? ORDER BY ordinal", (report_id,)
            )]
        body = dict(report)
        for row in positions:
            row["derivative"] = json.loads(row.pop("derivative_json"))
            row["qualityFlags"] = json.loads(row.pop("quality_flags_json"))
        body["positions"] = positions
        return body

    def select_holdings(self, fund_id: str, share_class_id: str, cutoff_utc: str,
                        max_reporting_lag_days: int = 75) -> Dict[str, Any]:
        """Select only evidence actually retrieved by the cutoff; never substitute today."""
        cutoff = _utc(cutoff_utc)
        if not cutoff:
            raise ValueError("A valid point-in-time cutoff is required")
        with self.connect(create=False) as connection:
            row = connection.execute(
                """SELECT report_id FROM holdings_reports
                   WHERE fund_id=? AND share_class_id=? AND available_at<=? AND retrieved_at<=?
                   ORDER BY as_of_date DESC, available_at DESC, retrieved_at DESC, rowid DESC LIMIT 1""",
                (fund_id, share_class_id, cutoff, cutoff),
            ).fetchone()
        if not row:
            return {"status": "missing", "fundId": fund_id, "shareClassId": share_class_id,
                    "cutoffUtc": cutoff, "complete": False}
        report = self._report(row["report_id"])
        expected_total = 100.0 if report["weight_unit"] == "percent" else 1.0
        tolerance = 5.0 if report["weight_unit"] == "percent" else 0.05
        total_complete = (
            report["reported_total_weight"] is not None
            and expected_total - tolerance <= report["reported_total_weight"] <= expected_total + tolerance
        )
        identity_match = report["fund_id"] == fund_id and report["share_class_id"] == share_class_id
        complete = bool(
            identity_match and report["positions"] and report["coverage_complete"]
            and report["cash_resolved"] and report["derivatives_resolved"]
            and report["currency_resolved"] and total_complete
            and 0 <= report["reporting_lag_days"] <= max_reporting_lag_days
        )
        return {
            "status": "complete" if complete else "incomplete", "complete": complete,
            "identityMatch": identity_match, "totalComplete": total_complete,
            "maxReportingLagDays": max_reporting_lag_days, **report,
        }

    def build_lookthrough(self, funds: Sequence[Dict[str, str]], cutoff_utc: str,
                          max_reporting_lag_days: int = 75) -> List[Dict[str, Any]]:
        """Build ledger-ready rows linked to archived holdings and fee documents."""
        cutoff = _utc(cutoff_utc)
        if not cutoff:
            raise ValueError("A valid point-in-time cutoff is required")
        rows: List[Dict[str, Any]] = []
        with self.connect(create=False) as connection:
            for identity in funds:
                fund_id = str(identity.get("fundId") or "")
                share_class_id = str(identity.get("shareClassId") or "")
                selected = self.select_holdings(fund_id, share_class_id, cutoff, max_reporting_lag_days)
                fee = connection.execute(
                    """SELECT f.*, d.source_type, d.source_record_id, d.source_url, d.source_hash
                       FROM fee_reports f JOIN source_documents d USING(document_id)
                       WHERE f.fund_id=? AND f.share_class_id=?
                       AND f.available_at<=? AND f.retrieved_at<=?
                       ORDER BY f.as_of_date DESC, f.available_at DESC, f.rowid DESC LIMIT 1""",
                    (fund_id, share_class_id, cutoff, cutoff),
                ).fetchone()
                if not selected.get("report_id"):
                    rows.append({
                        "asOf": cutoff[:10], "availableAt": cutoff, "retrievedAt": cutoff,
                        "complete": False, "source": "Archived issuer/SEC ETF evidence",
                        "fundSecurityId": fund_id, "shareClassId": share_class_id,
                        "payload": {"archiveEvidence": True, "holdingsMissing": True,
                                    "feeMissing": fee is None},
                    })
                    continue
                fee_body = dict(fee) if fee else None
                sources = [{
                    "documentId": selected["document_id"],
                    "sourceType": selected["source_type"],
                    "sourceRecordId": selected["source_record_id"],
                    "url": selected["source_url"], "sha256": selected["source_hash"],
                }]
                if fee_body:
                    sources.append({
                        "documentId": fee_body["document_id"], "sourceType": fee_body["source_type"],
                        "sourceRecordId": fee_body["source_record_id"],
                        "url": fee_body["source_url"], "sha256": fee_body["source_hash"],
                    })
                payload = {
                    "archiveEvidence": True, "fundSecurityId": fund_id,
                    "shareClassId": share_class_id, "holdingsReportId": selected["report_id"],
                    "feeReportId": fee_body["fee_report_id"] if fee_body else None,
                    "reportingLagDays": selected["reporting_lag_days"],
                    "maxReportingLagDays": max_reporting_lag_days,
                    "baseCurrency": selected["base_currency"],
                    "weightUnit": selected["weight_unit"],
                    "reportedTotalWeight": selected["reported_total_weight"],
                    "coverageComplete": bool(selected["coverage_complete"]),
                    "cashResolved": bool(selected["cash_resolved"]),
                    "derivativesResolved": bool(selected["derivatives_resolved"]),
                    "currencyResolved": bool(selected["currency_resolved"]),
                    "positions": selected["positions"], "fees": fee_body, "sources": sources,
                }
                rows.append({
                    "asOf": selected["as_of_date"], "availableAt": selected["available_at"],
                    "retrievedAt": selected["retrieved_at"],
                    "complete": bool(selected["complete"] and fee_body),
                    "source": "Archived issuer/SEC ETF evidence",
                    "fundSecurityId": fund_id, "shareClassId": share_class_id,
                    "payload": payload,
                })
        return rows

    def counts(self) -> Dict[str, int]:
        if not self.database.exists():
            return {"documents": 0, "holdingsReports": 0, "positions": 0, "feeReports": 0}
        with self.connect(create=False) as connection:
            return {
                "documents": connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0],
                "holdingsReports": connection.execute("SELECT COUNT(*) FROM holdings_reports").fetchone()[0],
                "positions": connection.execute("SELECT COUNT(*) FROM holding_positions").fetchone()[0],
                "feeReports": connection.execute("SELECT COUNT(*) FROM fee_reports").fetchone()[0],
            }
