"""Safeguards for manager-skill validation."""

from __future__ import annotations

import unittest

from investor_history import _outcome, investor_calibration_summary


class InvestorHistoryTests(unittest.TestCase):
    def test_outcome_is_measured_against_spy(self) -> None:
        record = {"observations": [
            {"date": "2025-01-01", "price": 100, "benchmarkPrice": 100},
            {"date": "2026-01-02", "price": 130, "benchmarkPrice": 110},
        ]}
        outcome = _outcome(record, 365)
        self.assertEqual(outcome["stockReturn"], 30.0)
        self.assertEqual(outcome["benchmarkReturn"], 10.0)
        self.assertEqual(outcome["excessReturn"], 20.0)

    def test_manager_is_not_validated_without_ten_mature_ideas(self) -> None:
        records = [{
            "managerId": "one", "managerName": "Manager One", "symbol": "TEST",
            "action": "Increased", "recordedAt": "2025-01-01",
            "observations": [
                {"date": "2025-01-01", "price": 100, "benchmarkPrice": 100},
                {"date": "2026-01-02", "price": 130, "benchmarkPrice": 110},
            ],
        }]
        summary = investor_calibration_summary(records)
        self.assertEqual(summary["status"], "building")
        self.assertEqual(summary["managers"][0]["matured365"], 1)
        self.assertFalse(summary["managers"][0]["validated"])


if __name__ == "__main__":
    unittest.main()
