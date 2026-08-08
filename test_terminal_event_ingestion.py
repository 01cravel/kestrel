"""Deterministic authoritative merger-term ingestion tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_history import MarketHistoryStore
from terminal_event_ingestion import (
    extract_terminal_terms, ingest_official_issuer_release, ingest_terminal_record,
    refresh_sec_terminal_events,
)


ROOT = Path(__file__).resolve().parent
FIXTURES = json.loads((ROOT / "fixtures" / "terminal_events.json").read_text(encoding="utf-8"))


class TerminalEventIngestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market.sqlite3"
        MarketHistoryStore(self.database).connect().close()

    def record(self, fixture: str, **changes):
        record = {
            "ticker": "AAA", "cik": "1", "accession": "0000000001-25-000001",
            "sourceKind": "sec_filing",
            "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/",
            "publishedAt": "2025-06-02T18:00:00Z",
            "availableAt": "2025-06-02T18:00:00Z",
            "retrievedAt": "2025-06-02T19:00:00Z",
            "targetSecurityId": "CIK:1", "expectedTargetSecurityId": "CIK:1",
            "documents": [{"name": "terms.htm", "content": FIXTURES[fixture]}],
        }
        record.update(changes)
        return record

    def rows(self):
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(
                "SELECT * FROM issuer_events ORDER BY available_at, accession"
            )]

    def test_cash_stock_and_mixed_terms_are_structured_without_inference(self):
        for fixture, kind in (("cash", "cash"), ("stock", "stock"), ("mixed", "mixed")):
            record = self.record(fixture, accession=f"0000000001-25-00000{len(self.rows()) + 1}")
            result = ingest_terminal_record(record, self.database)
            self.assertEqual(result["status"], "stored")
            detail = json.loads(self.rows()[-1]["detail"])
            self.assertEqual(detail["consideration"]["kind"], kind)
            self.assertEqual(detail["effectiveOn"], "2025-06-02")
            self.assertEqual(len(detail["rawDocumentHashes"][0]), 64)
            self.assertTrue(detail["sourceUrl"].startswith("https://www.sec.gov/Archives/"))
        self.assertEqual(json.loads(self.rows()[0]["detail"])["consideration"]["currency"], "USD")
        self.assertEqual(json.loads(self.rows()[1]["detail"])["consideration"]["successorSecurityId"], "FIGI:NEW")

    def test_explicit_delisting_terms_are_not_derived_from_a_form_code(self):
        result = ingest_terminal_record(self.record("delisting_cash"), self.database)
        self.assertEqual(result["eventType"], "delisting_cash")
        self.assertEqual(json.loads(self.rows()[0]["detail"])["consideration"]["cashPerShare"], 150)

    def test_missing_ambiguous_and_mismatched_terms_fail_closed(self):
        missing = ingest_terminal_record(self.record("missing_currency"), self.database)
        conflict = ingest_terminal_record(self.record("conflicting"), self.database)
        mismatch = ingest_terminal_record(self.record("identity_mismatch"), self.database)
        self.assertEqual([missing["status"], conflict["status"], mismatch["status"]],
                         ["rejected", "rejected", "rejected"])
        self.assertEqual(self.rows(), [])

    def test_late_or_inconsistent_clocks_are_rejected(self):
        result = ingest_terminal_record(self.record(
            "cash", availableAt="2025-06-03T18:00:00Z",
            retrievedAt="2025-06-02T19:00:00Z",
        ), self.database)
        self.assertEqual(result["status"], "rejected")
        self.assertIn("clocks", result["reason"])

    def test_idempotence_amendment_and_immutable_history(self):
        original = self.record("cash")
        self.assertEqual(ingest_terminal_record(original, self.database)["status"], "stored")
        self.assertEqual(ingest_terminal_record(
            {**original, "retrievedAt": "2025-06-03T10:00:00Z"}, self.database
        )["status"], "unchanged")
        amended = self.record(
            "amended", accession="0000000001-25-000002",
            publishedAt="2025-06-03T18:00:00Z", availableAt="2025-06-03T18:00:00Z",
            retrievedAt="2025-06-03T19:00:00Z",
        )
        self.assertEqual(ingest_terminal_record(amended, self.database)["status"], "stored")
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[1]["detail"])["supersedesAccession"], original["accession"])
        with sqlite3.connect(self.database) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE issuer_events SET event_date='2025-06-03'")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM issuer_events")

    def test_official_issuer_requires_exact_verified_domain(self):
        record = self.record(
            "cash", sourceKind="official_issuer", sourceUrl="https://ir.example.com/release",
            accession="", sourceRecordId="issuer-release-2025-06-02",
        )
        rejected = ingest_official_issuer_release(record, ["issuer.example"], self.database)
        accepted = ingest_official_issuer_release(record, ["example.com"], self.database)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(accepted["status"], "stored")

    def test_sec_package_discovery_ingests_once_per_daily_window(self):
        submissions = json.dumps({"filings": {"recent": {
            "form": ["8-K"], "accessionNumber": ["0000000001-25-000001"],
            "acceptanceDateTime": ["2025-06-02T18:00:00Z"],
        }}}).encode()
        package = json.dumps({"directory": {"item": [{"name": "terms.htm"}]}}).encode()
        calls = []

        def fetcher(url, **_kwargs):
            calls.append(url)
            if url.endswith("submissions/CIK0000000001.json"):
                return submissions
            if url.endswith("index.json"):
                return package
            if url.endswith("terms.htm"):
                return FIXTURES["cash"].encode()
            raise RuntimeError("unexpected URL")

        identity = lambda _symbol: {"status": "verified", "cik": "1"}
        first = refresh_sec_terminal_events(
            ["AAA"], self.database, fetcher, identity, "2025-06-02T19:00:00Z"
        )
        call_count = len(calls)
        second = refresh_sec_terminal_events(
            ["AAA"], self.database, fetcher, identity, "2025-06-02T20:00:00Z"
        )
        self.assertEqual(first["stored"], 1)
        self.assertEqual(second["stored"], 0)
        self.assertEqual(len(calls), call_count)


if __name__ == "__main__":
    unittest.main()
