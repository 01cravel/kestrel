"""Safeguards for manager-skill validation."""

from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import investor_history
from investor_history import _outcome, investor_calibration_summary
from outcome_source import OutcomeSource
from test_outcome_source import _sessions, _write


class InvestorHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"
        original = investor_history.shared_source
        investor_history.shared_source = lambda: OutcomeSource(self.database)
        self.addCleanup(setattr, investor_history, "shared_source", original)

    @staticmethod
    def _record(symbol: str = "TEST", start: str = "2025-01-01") -> dict:
        finish = (dt.date.fromisoformat(start) + dt.timedelta(days=366)).isoformat()
        return {
            "managerId": "one", "managerName": "Manager One", "symbol": symbol,
            "action": "Increased", "recordedAt": start,
            "observations": [
                {"date": start, "price": 100, "benchmarkPrice": 100},
                {"date": finish, "price": 130, "benchmarkPrice": 110},
            ],
        }

    def test_outcome_is_measured_against_spy(self) -> None:
        outcome = _outcome(self._record(), 365)
        self.assertEqual(outcome["stockReturn"], 30.0)
        self.assertEqual(outcome["benchmarkReturn"], 10.0)
        self.assertEqual(outcome["excessReturn"], 20.0)

    def test_kestrel_snapshots_are_visible_but_never_count_as_matured(self) -> None:
        outcome = _outcome(self._record(), 365)
        self.assertEqual(outcome["source"], "journal-snapshot")

        summary = investor_calibration_summary([self._record()])
        self.assertEqual(summary["status"], "building")
        self.assertEqual(summary["managers"][0]["matured365"], 0)
        self.assertEqual(summary["managers"][0]["provisional365"], 1)
        self.assertFalse(summary["managers"][0]["validated"])

    def test_archived_adjusted_prices_are_preferred_over_snapshots(self) -> None:
        _write(self.database, _sessions(dt.date(2026, 1, 5), 80, stock_step=1.0, spy_step=0.2))
        outcome = _outcome(self._record(start="2026-01-05"), 90)
        self.assertEqual(outcome["source"], "archive")
        self.assertIsNotNone(outcome["maxDrawdown"])

        summary = investor_calibration_summary([self._record(start="2026-01-05")])
        self.assertEqual(summary["managers"][0]["matured90"], 1)
        self.assertEqual(summary["managers"][0]["provisional365"], 1)


if __name__ == "__main__":
    unittest.main()
