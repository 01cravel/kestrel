"""Deterministic bitemporal outcome and delisting capture tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_history import MarketHistoryStore
from swing_radar_policy import POLICY_VERSION
from universe_ledger import UniverseLedger
from universe_outcomes import UniverseOutcomeCapture


HASH = "1" * 64


class UniverseOutcomeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.ledger = UniverseLedger(root / "ledger.sqlite3")
        self.market = MarketHistoryStore(root / "market.sqlite3")
        self.capture_service = UniverseOutcomeCapture(self.ledger, self.market.database)
        self.snapshot_id = self._freeze()

    def _freeze(self, ticker="AAA", security_id="FIGI:AAA"):
        result = self.ledger.capture_snapshot(
            decision_date="2025-01-02", cutoff_utc="2025-01-02T21:15:00Z",
            recorded_at="2025-01-02T21:15:00Z", model_version="model-v1",
            policy_version="evidence-v1", selection_policy_version="selection-v1",
            members=[{
                "ticker": ticker, "securityId": security_id, "active": True,
                "identityStatus": "verified", "membershipVerified": True, "included": True,
                "identityAvailableAt": "2025-01-02T20:00:00Z",
                "identifiers": {"shareClassFigi": security_id.split(":", 1)[1]},
                "listing": {"market": "US", "currency": "USD"},
                "sources": [{"name": "Point-in-time reference", "tier": 3}],
            }],
            controls={"selectionPolicyFrozen": True, "pointInTimePrices": True,
                      "adjustmentPolicy": "point_in_time_total_return", "oneWayCostBps": 10},
        )
        return result["snapshotId"]

    def _reference(self, date, ticker, active=True, figi="AAA", delisted=None,
                   fetched="2025-01-02T20:00:00Z"):
        with self.market.connect() as connection:
            connection.execute(
                """INSERT INTO reference_snapshots VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date, ticker, int(active), ticker, "stocks", "us", "USD", "XNYS", "CS",
                 "1", "COMP", figi, delisted, date + "T00:00:00Z", 1,
                 "reference-request", fetched, HASH),
            )
            connection.commit()

    def _session(self, date, fetched=None):
        fetched = fetched or date + "T21:00:00Z"
        with self.market.connect() as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, 'complete', 1, 1, ?, ?, ?)",
                (date, "session-request", fetched, HASH),
            )
            connection.commit()

    def _observation(self, date, ticker="AAA", security_id="FIGI:AAA", close=100.0,
                     fetched=None, currency="USD", clean=True):
        fetched = fetched or date + "T21:00:00Z"
        with self.market.connect() as connection:
            connection.execute(
                """INSERT INTO swing_observations
                   (security_id, session_date, cutoff_utc, ticker, policy_version,
                    corporate_actions_clean, currency, adjusted_close, spy_adjusted_close,
                    split_flag, dividend_flag, eligibility_status, eligibility_json,
                    source_retrieved_at, raw_sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100, 0, 0, 'eligible', '{}', ?, ?)""",
                (security_id, date, date + "T21:00:00Z", ticker, POLICY_VERSION,
                 int(clean), currency, close, fetched, HASH),
            )
            connection.commit()

    def _event(self, event_type, effective, consideration, accession="accession-1",
               available="2025-06-02T18:00:00Z", retrieved="2025-06-02T19:00:00Z"):
        with self.market.connect() as connection:
            connection.execute(
                "INSERT INTO issuer_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("AAA", "1", event_type, effective, available, available, None,
                 json.dumps({"effectiveOn": effective, "consideration": consideration}),
                 accession, "SEC EDGAR 8-K", retrieved),
            )
            connection.commit()

    def _outcomes(self):
        with self.ledger.connect(create=False) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM outcome_versions ORDER BY recorded_at, rowid"
            )]

    def test_ordinary_survivor_accumulates_then_completes(self):
        self._reference("2025-01-02", "AAA")
        self._session("2025-01-03")
        self._observation("2025-01-03", close=100)
        first = self.capture_service.capture("2025-06-02T22:00:00Z")
        self.assertEqual(first["results"][0]["outcomeStatus"], "pending")
        self._session("2026-01-02")
        self._observation("2026-01-02", close=125)
        second = self.capture_service.capture("2026-01-03T22:00:00Z")
        self.assertEqual(second["results"][0]["outcomeStatus"], "complete")
        self.assertEqual(json.loads(self._outcomes()[-1]["payload_json"])["totalReturn"], 0.25)

    def test_ticker_change_follows_stable_identity(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-07-01", "BBB")
        self._session("2025-01-03")
        self._observation("2025-01-03", "AAA", close=100)
        self._session("2026-01-02")
        self._observation("2026-01-02", "BBB", close=120)
        result = self.capture_service.capture("2026-01-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "complete")
        self.assertEqual(json.loads(self._outcomes()[-1]["payload_json"])["tickers"], ["AAA", "BBB"])

    def test_currency_change_fails_closed(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-07-01", "BBB")
        with self.market.connect() as connection:
            connection.execute(
                "UPDATE reference_snapshots SET currency='EUR' WHERE ticker='BBB'"
            )
            connection.commit()
        result = self.capture_service.capture("2026-01-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "missing")
        self.assertIn("currency", json.loads(self._outcomes()[-1]["payload_json"])["reason"])

    def test_cash_merger_uses_evidenced_proceeds_and_currency(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-06-02", "AAA", active=False, delisted="2025-06-02")
        for date, close in (("2025-01-03", 100), ("2025-06-02", 140)):
            self._session(date)
            self._observation(date, close=close)
        self._event("merger_cash", "2025-06-02",
                    {"kind": "cash", "cashPerShare": 150, "currency": "USD"})
        result = self.capture_service.capture("2025-06-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "delisted_complete")
        row = self._outcomes()[-1]
        self.assertEqual(row["proceeds"], 150)
        self.assertEqual(row["currency"], "USD")

    def test_cash_merger_currency_conflict_fails_closed(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-06-02", "AAA", active=False, delisted="2025-06-02")
        for date in ("2025-01-03", "2025-06-02"):
            self._session(date)
            self._observation(date)
        self._event("merger_cash", "2025-06-02",
                    {"kind": "cash", "cashPerShare": 150, "currency": "EUR"})
        result = self.capture_service.capture("2025-06-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "conflict")
        self.assertEqual(result["status"], "partial")

    def test_stock_merger_continues_successor_path(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-06-02", "AAA", active=False, delisted="2025-06-02")
        for date, close in (("2025-01-03", 100), ("2025-06-02", 110)):
            self._session(date)
            self._observation(date, close=close)
        self._session("2025-06-03")
        self._session("2026-01-02")
        self._event("merger_stock", "2025-06-02",
                    {"kind": "stock", "sharesPerShare": 0.5,
                     "successorSecurityId": "FIGI:NEW"})
        self._observation("2025-06-03", "NEW", "FIGI:NEW", 200)
        self._observation("2026-01-02", "NEW", "FIGI:NEW", 240)
        result = self.capture_service.capture("2026-01-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "delisted_complete")
        payload = json.loads(self._outcomes()[-1]["payload_json"])
        self.assertEqual(payload["endValuePerOriginalShare"], 120)

    def test_missing_proceeds_and_disappearance_remain_incomplete(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-06-02", "AAA", active=False, delisted="2025-06-02")
        self._session("2025-01-03")
        self._observation("2025-01-03")
        self._event("merger_cash", "2025-06-02", {"kind": "cash", "currency": "USD"})
        result = self.capture_service.capture("2025-06-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "missing")
        row = self._outcomes()[-1]
        self.assertNotEqual(row["status"], "delisted_complete")
        self.assertEqual(row["listing_state"], "delisted_unresolved")
        self.assertEqual(row["delisted_on"], "2025-06-02")

    def test_conflicting_authoritative_terms_fail_closed(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-06-02", "AAA", active=False, delisted="2025-06-02")
        self._event("merger_cash", "2025-06-02",
                    {"kind": "cash", "cashPerShare": 150, "currency": "USD"})
        self._event("merger_cash", "2025-06-02",
                    {"kind": "cash", "cashPerShare": 140, "currency": "USD"},
                    accession="accession-2")
        result = self.capture_service.capture("2025-06-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "conflict")

    def test_late_terminal_evidence_cannot_enter_earlier_state(self):
        self._reference("2025-01-02", "AAA")
        self._reference("2025-06-02", "AAA", active=False, delisted="2025-06-02")
        self._event("merger_cash", "2025-06-02",
                    {"kind": "cash", "cashPerShare": 150, "currency": "USD"},
                    available="2025-06-04T18:00:00Z", retrieved="2025-06-04T19:00:00Z")
        result = self.capture_service.capture("2025-06-03T22:00:00Z")
        self.assertEqual(result["results"][0]["outcomeStatus"], "missing")

    def test_idempotence_and_corrections_preserve_history(self):
        self._reference("2025-01-02", "AAA")
        self._session("2025-01-03")
        self._observation("2025-01-03")
        first = self.capture_service.capture("2025-06-02T22:00:00Z")
        second = self.capture_service.capture("2025-06-03T22:00:00Z")
        self.assertEqual(first["recorded"], 1)
        self.assertEqual(second["unchanged"], 1)
        self._session("2026-01-02")
        self._observation("2026-01-02", close=130)
        self.capture_service.capture("2026-01-03T22:00:00Z")
        rows = self._outcomes()
        self.assertEqual([row["status"] for row in rows], ["pending", "complete"])
        with self.ledger.connect(create=False) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE outcome_versions SET status='changed'")


if __name__ == "__main__":
    unittest.main()
