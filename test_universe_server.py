from __future__ import annotations

import datetime as dt
import unittest
from unittest.mock import patch

import server


class _Ledger:
    def __init__(self):
        self.arguments = None

    def capture_snapshot(self, **arguments):
        self.arguments = arguments
        return {"status": "captured", "snapshotId": "test"}


class _MarketStore:
    def __init__(self, result=None):
        self.result = result or {"status": "unavailable"}

    def certify_session(self, session_date, symbols, cutoff):
        return self.result


class _BrokenMarketStore:
    def certify_session(self, session_date, symbols, cutoff):
        raise server.sqlite3.OperationalError("missing schema")


class _Outcomes:
    def __init__(self):
        self.recorded_at = None

    def capture(self, recorded_at=None):
        self.recorded_at = recorded_at
        return {"status": "captured", "recorded": 1}


class UniverseServerTests(unittest.TestCase):
    def setUp(self):
        with server.STATE_LOCK:
            self.old_status = server.STATE["status"]
            self.old_data = server.STATE["data"]
            server.STATE["status"] = "ready"
            server.STATE["data"] = {
                "AAA": {
                    "fetchedAt": 1786133100,
                    "quote": {"c": 100, "t": 1786132800},
                    "sec": {"status": "verified"},
                }
            }
        self.addCleanup(self._restore_state)

    def _restore_state(self):
        with server.STATE_LOCK:
            server.STATE["status"] = self.old_status
            server.STATE["data"] = self.old_data

    @staticmethod
    def identity():
        return {"status": "ready", "instruments": {"AAA": {
            "symbol": "AAA", "status": "resolved", "assetClass": "equity",
            "resolvedAt": 1786129200, "identifiers": {"figi": "AAA"},
            "listing": {"market": "US", "currency": "USD"},
            "sources": [{"name": "OpenFIGI", "tier": 2}],
        }}}

    @staticmethod
    def lookthrough():
        return {
            "generatedAt": 1786133160, "complete": True,
            "sources": [{"symbol": "VTI", "asOf": "2026-08-07", "ready": True}],
            "fundOverlaps": {},
        }

    def test_post_close_worker_freezes_exact_evidence_and_keeps_price_gate_closed(self):
        ledger = _Ledger()
        instant = dt.datetime(2026, 8, 7, 21, 0, tzinfo=dt.timezone.utc)
        with (
            patch.object(server, "all_symbols", return_value=["AAA"]),
            patch.object(server, "security_master_snapshot", return_value=self.identity()),
            patch.object(server, "fund_lookthrough_snapshot", return_value=self.lookthrough()),
            patch.object(server, "UNIVERSE_LEDGER", ledger),
            patch.object(server, "MARKET_HISTORY_STORE", _MarketStore()),
        ):
            result = server.freeze_daily_universe(instant)
        self.assertEqual(result["status"], "captured")
        self.assertEqual(ledger.arguments["decision_date"], "2026-08-07")
        self.assertEqual(ledger.arguments["cutoff_utc"], "2026-08-07T21:00:00Z")
        self.assertEqual(len(ledger.arguments["members"]), 1)
        self.assertEqual(len(ledger.arguments["evidence"]), 1)
        self.assertEqual(len(ledger.arguments["lookthrough"]), 1)
        self.assertFalse(ledger.arguments["controls"]["pointInTimePrices"])
        self.assertEqual(ledger.arguments["controls"]["adjustmentPolicy"], "unverified")

    def test_certified_archive_opens_point_in_time_price_and_action_controls(self):
        ledger = _Ledger()
        instant = dt.datetime(2026, 8, 7, 21, 0, tzinfo=dt.timezone.utc)
        certification = {
            "status": "ready", "members": [{"ticker": "AAA"}],
            "evidence": [{"category": "archived_adjusted_close"}],
        }
        with (
            patch.object(server, "all_symbols", return_value=["AAA"]),
            patch.object(server, "security_master_snapshot", return_value=self.identity()),
            patch.object(server, "fund_lookthrough_snapshot", return_value=self.lookthrough()),
            patch.object(server, "UNIVERSE_LEDGER", ledger),
            patch.object(server, "MARKET_HISTORY_STORE", _MarketStore(certification)),
        ):
            result = server.freeze_daily_universe(instant)
        self.assertEqual(result["status"], "captured")
        self.assertEqual(
            ledger.arguments["selection_policy_version"],
            server.CERTIFIED_UNIVERSE_SELECTION_POLICY,
        )
        self.assertEqual(ledger.arguments["members"], certification["members"])
        self.assertEqual(ledger.arguments["evidence"], certification["evidence"])
        self.assertTrue(ledger.arguments["controls"]["pointInTimePrices"])
        self.assertEqual(
            ledger.arguments["controls"]["adjustmentPolicy"],
            "point_in_time_total_return",
        )

    def test_broken_optional_archive_still_freezes_a_fail_closed_manifest(self):
        ledger = _Ledger()
        instant = dt.datetime(2026, 8, 7, 21, 0, tzinfo=dt.timezone.utc)
        with (
            patch.object(server, "all_symbols", return_value=["AAA"]),
            patch.object(server, "security_master_snapshot", return_value=self.identity()),
            patch.object(server, "fund_lookthrough_snapshot", return_value=self.lookthrough()),
            patch.object(server, "UNIVERSE_LEDGER", ledger),
            patch.object(server, "MARKET_HISTORY_STORE", _BrokenMarketStore()),
        ):
            result = server.freeze_daily_universe(instant)
        self.assertEqual(result["status"], "captured")
        self.assertFalse(ledger.arguments["controls"]["pointInTimePrices"])
        self.assertEqual(
            ledger.arguments["selection_policy_version"], server.UNIVERSE_SELECTION_POLICY
        )

    def test_weekend_never_freezes_a_snapshot(self):
        ledger = _Ledger()
        saturday = dt.datetime(2026, 8, 8, 21, 0, tzinfo=dt.timezone.utc)
        with patch.object(server, "UNIVERSE_LEDGER", ledger):
            result = server.freeze_daily_universe(saturday)
        self.assertEqual(result["status"], "waiting")
        self.assertIsNone(ledger.arguments)

    def test_daily_workflow_advances_outcomes_after_freeze(self):
        instant = dt.datetime(2026, 8, 7, 21, 0, tzinfo=dt.timezone.utc)
        outcomes = _Outcomes()
        with (
            patch.object(server, "freeze_daily_universe", return_value={"status": "captured"}),
            patch.object(server, "UNIVERSE_OUTCOMES", outcomes),
        ):
            result = server.update_daily_universe_ledger(instant)
        self.assertEqual(result["snapshot"]["status"], "captured")
        self.assertEqual(result["outcomes"]["recorded"], 1)
        self.assertEqual(outcomes.recorded_at, "2026-08-07T21:00:00Z")


if __name__ == "__main__":
    unittest.main()
