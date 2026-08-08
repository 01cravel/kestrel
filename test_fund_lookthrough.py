from __future__ import annotations

import unittest
from datetime import date

from fund_lookthrough import EQUITY_FUNDS, calculate_lookthrough


class FundLookthroughTests(unittest.TestCase):
    def complete_funds(self):
        return {
            fund: {
                "asOf": "2026-08-07",
                "holdings": [{"ticker": "CASH", "name": "Other holdings", "weight": 100.0}],
            }
            for fund in EQUITY_FUNDS
        }

    def test_combines_direct_and_hidden_share_classes(self):
        funds = self.complete_funds()
        funds["VTI"]["holdings"] = [
            {"ticker": "GOOGL", "name": "Alphabet Inc Class A", "weight": 3.0},
            {"ticker": "GOOG", "name": "Alphabet Inc Class C", "weight": 2.5},
            {"ticker": "CASH", "name": "Other holdings", "weight": 94.5},
        ]
        result = calculate_lookthrough({"VTI": 20, "GOOGL": 6}, funds, date(2026, 8, 8))
        alphabet = next(item for item in result["exposures"] if item["symbol"] == "GOOGL")
        self.assertEqual(alphabet["insideFunds"], 1.1)
        self.assertEqual(alphabet["effective"], 7.1)
        self.assertTrue(result["complete"])

    def test_missing_or_stale_fund_fails_closed(self):
        funds = self.complete_funds()
        funds["IEMG"]["holdings"] = []
        funds["VEA"]["asOf"] = "2025-01-01"
        result = calculate_lookthrough({}, funds, date(2026, 8, 8))
        self.assertFalse(result["complete"])
        self.assertEqual(result["fundsReady"], 4)

    def test_incomplete_weight_total_fails_closed(self):
        funds = self.complete_funds()
        funds["PAVE"]["holdings"] = [{"ticker": "ETN", "name": "Eaton Corp", "weight": 3.2}]
        result = calculate_lookthrough({}, funds, date(2026, 8, 8))
        self.assertFalse(result["complete"])


if __name__ == "__main__":
    unittest.main()
