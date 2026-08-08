from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from etf_evidence import EtfEvidenceArchive


def document(record_id="issuer-vti-20260807", available="2026-08-08T10:00:00Z", **changes):
    row = {
        "sourceType": "issuer", "sourceRecordId": record_id,
        "publicationAt": available, "availableAt": available,
        "retrievedAt": "2026-08-08T10:05:00Z",
        "sourceUrl": f"https://issuer.example/{record_id}.csv",
        "sourceHash": "a" * 64, "rawHash": "b" * 64,
    }
    row.update(changes)
    return row


def holdings(**changes):
    row = {
        "document": document(), "fundId": "FIGI:FUND-VTI",
        "shareClassId": "FIGI:CLASS-VTI", "ticker": "VTI",
        "cik": "0000036405", "seriesId": "S000002848",
        "classContractId": "C000007040", "asOfDate": "2026-08-07",
        "baseCurrency": "USD", "weightUnit": "percent",
        "reportedTotalWeight": 100.0, "coverageComplete": True,
        "cashResolved": True, "derivativesResolved": True, "currencyResolved": True,
        "positions": [
            {"positionType": "security", "securityId": "FIGI:AAA", "ticker": "AAA",
             "name": "Alpha", "units": 10, "unitName": "shares", "marketValue": 95,
             "currency": "USD", "reportedWeight": 95.0},
            {"positionType": "cash", "name": "US Dollar", "units": 5,
             "unitName": "USD", "marketValue": 5, "currency": "USD", "reportedWeight": 5.0},
        ],
    }
    row.update(changes)
    return row


def fees(**changes):
    row = {
        "document": document("issuer-vti-fee-2026", sourceHash="c" * 64),
        "fundId": "FIGI:FUND-VTI", "shareClassId": "FIGI:CLASS-VTI",
        "asOfDate": "2026-08-01", "grossExpenseRatio": 0.03,
        "netExpenseRatio": 0.03, "feeUnit": "percent", "currency": "USD",
    }
    row.update(changes)
    return row


class EtfEvidenceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.archive = EtfEvidenceArchive(Path(self.directory.name) / "etf.sqlite3")

    def test_complete_issuer_holdings_and_fees_build_ledger_evidence(self):
        report = self.archive.append_holdings(holdings())
        fee = self.archive.append_fees(fees())
        selected = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:CLASS-VTI", "2026-08-08T11:00:00Z"
        )
        rows = self.archive.build_lookthrough(
            [{"fundId": "FIGI:FUND-VTI", "shareClassId": "FIGI:CLASS-VTI"}],
            "2026-08-08T11:00:00Z",
        )
        self.assertTrue(selected["complete"])
        self.assertEqual(selected["reporting_lag_days"], 1)
        self.assertEqual(rows[0]["payload"]["holdingsReportId"], report["reportId"])
        self.assertEqual(rows[0]["payload"]["feeReportId"], fee["feeReportId"])
        self.assertEqual(rows[0]["payload"]["weightUnit"], "percent")
        self.assertTrue(rows[0]["complete"])

    def test_missing_fee_evidence_keeps_ledger_row_incomplete(self):
        self.archive.append_holdings(holdings())
        rows = self.archive.build_lookthrough(
            [{"fundId": "FIGI:FUND-VTI", "shareClassId": "FIGI:CLASS-VTI"}],
            "2026-08-08T11:00:00Z",
        )
        self.assertFalse(rows[0]["complete"])
        self.assertIsNone(rows[0]["payload"]["feeReportId"])

    def test_late_and_stale_reports_fail_closed(self):
        late = holdings(document=document(available="2026-08-09T10:00:00Z",
                                          retrievedAt="2026-08-09T10:05:00Z"))
        self.archive.append_holdings(late)
        missing = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:CLASS-VTI", "2026-08-08T20:00:00Z"
        )
        self.assertEqual(missing["status"], "missing")

        stale_record = holdings(
            document=document("issuer-stale", available="2026-08-08T10:00:00Z"),
            asOfDate="2026-01-01",
        )
        self.archive.append_holdings(stale_record)
        stale = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:CLASS-VTI", "2026-08-08T20:00:00Z"
        )
        self.assertGreater(stale["reporting_lag_days"], 75)
        self.assertFalse(stale["complete"])

    def test_share_class_mismatch_does_not_fall_back_to_same_ticker(self):
        self.archive.append_holdings(holdings())
        selected = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:ANOTHER-CLASS", "2026-08-08T11:00:00Z"
        )
        self.assertEqual(selected["status"], "missing")

    def test_duplicate_is_idempotent_and_changed_record_requires_amendment(self):
        first = self.archive.append_holdings(holdings())
        duplicate = self.archive.append_holdings(holdings())
        self.assertEqual(duplicate["status"], "unchanged")
        changed = holdings(document=document(sourceHash="d" * 64))
        with self.assertRaisesRegex(ValueError, "amendment or correction"):
            self.archive.append_holdings(changed)

        amended_document = document(
            sourceHash="d" * 64, amendment=True,
            supersedesDocumentId=first["documentId"], formType="NPORT-P/A",
        )
        amended = holdings(document=amended_document, reportedTotalWeight=99.8)
        second = self.archive.append_holdings(amended)
        self.assertEqual(second["status"], "recorded")
        self.assertEqual(self.archive.counts()["holdingsReports"], 2)

    def test_sec_nport_accession_and_amendment_are_preserved(self):
        nport = holdings(document=document(
            "0000036405-26-000123", sourceType="sec_nport", accession="0000036405-26-000123",
            formType="NPORT-P", sourceUrl="https://www.sec.gov/Archives/edgar/data/36405/report.xml",
        ))
        result = self.archive.append_holdings(nport)
        selected = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:CLASS-VTI", "2026-08-08T11:00:00Z"
        )
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(selected["accession"], "0000036405-26-000123")
        self.assertEqual(selected["source_type"], "sec_nport")

    def test_cash_derivatives_and_incomplete_totals_remain_visible_and_close_gate(self):
        positions = holdings()["positions"] + [{
            "positionType": "derivative", "name": "Index future", "units": 1,
            "unitName": "contracts", "marketValue": 1, "currency": "USD",
            "reportedWeight": 1.0, "derivative": {"kind": "future", "notional": 10,
                                                     "notionalCurrency": "USD"},
        }]
        record = holdings(
            positions=positions, reportedTotalWeight=96.0,
            derivativesResolved=False, coverageComplete=False,
        )
        self.archive.append_holdings(record)
        selected = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:CLASS-VTI", "2026-08-08T11:00:00Z"
        )
        self.assertFalse(selected["complete"])
        self.assertEqual(selected["reported_total_weight"], 96.0)
        self.assertEqual(selected["positions"][-1]["position_type"], "derivative")
        self.assertEqual(selected["positions"][-1]["derivative"]["notional"], 10)

    def test_mixed_market_value_currencies_cannot_be_marked_resolved(self):
        positions = holdings()["positions"]
        positions[1] = {**positions[1], "currency": "EUR"}
        self.archive.append_holdings(holdings(positions=positions))
        selected = self.archive.select_holdings(
            "FIGI:FUND-VTI", "FIGI:CLASS-VTI", "2026-08-08T11:00:00Z"
        )
        self.assertFalse(selected["currency_resolved"])
        self.assertFalse(selected["complete"])

    def test_correction_appends_and_immutable_history_rejects_mutation(self):
        first = self.archive.append_holdings(holdings())
        corrected = holdings(
            document=document("issuer-vti-correction", sourceHash="e" * 64),
            correctionOf=first["reportId"], reportedTotalWeight=99.9,
        )
        second = self.archive.append_holdings(corrected)
        self.assertNotEqual(first["reportId"], second["reportId"])
        with self.archive.connect(create=False) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE holdings_reports SET reported_total_weight=100")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM source_documents")
        self.assertEqual(self.archive.counts()["holdingsReports"], 2)

    def test_missing_reported_total_is_rejected_not_inferred(self):
        with self.assertRaisesRegex(ValueError, "source-reported total"):
            self.archive.append_holdings(holdings(reportedTotalWeight=None))


if __name__ == "__main__":
    unittest.main()
