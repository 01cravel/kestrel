from __future__ import annotations

import json
import unittest
from datetime import date

from fund_lookthrough import EQUITY_FUNDS, _parse_vanguard, calculate_lookthrough


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

    def test_exposes_every_named_fund_company_with_source_date(self):
        funds = self.complete_funds()
        funds["VTI"]["holdings"] = [
            {"ticker": "CME", "name": "CME Group Inc.", "weight": 0.11},
            {"ticker": "PBLS", "name": "Parabilis Medicines Inc.", "weight": 0.00134},
            {"ticker": "CASH", "name": "Cash and equivalents", "weight": 99.88866},
        ]
        result = calculate_lookthrough({"VTI": 20}, funds, date(2026, 8, 8))
        rows = {row["symbol"]: row for row in result["fundHoldings"]}
        self.assertEqual(rows["CME"]["fund"], "VTI")
        self.assertEqual(rows["CME"]["portfolioWeight"], 0.022)
        self.assertEqual(rows["PBLS"]["portfolioWeight"], 0.000268)
        self.assertEqual(rows["PBLS"]["asOf"], "2026-08-07")
        self.assertNotIn("CASH", rows)
        self.assertTrue(result["fundHoldingsComplete"])

    def test_vanguard_market_values_preserve_positions_rounded_to_zero(self):
        parsed = _parse_vanguard(json.dumps({
            "asOfDate": "2026-06-30T00:00:00-04:00",
            "fund": {"entity": [
                {"ticker": "BIG", "longName": "Big Company", "marketValue": 999.0,
                 "percentWeight": "99.90"},
                {"ticker": "TINY", "longName": "Tiny Company", "marketValue": 1.0,
                 "percentWeight": "0.00"},
            ]},
        }))
        tiny = next(row for row in parsed["holdings"] if row["ticker"] == "TINY")
        self.assertEqual(tiny["weight"], 0.1)
        self.assertIn("market value", parsed["weightMethod"])

    def test_incomplete_fund_never_contributes_partial_positions(self):
        funds = self.complete_funds()
        funds["VEA"]["asOf"] = "2025-01-01"
        funds["VEA"]["holdings"] = [
            {"ticker": "LATE", "name": "Late Company", "weight": 100.0},
        ]
        result = calculate_lookthrough({"VEA": 7}, funds, date(2026, 8, 8))
        self.assertFalse(result["fundHoldingsComplete"])
        self.assertNotIn("LATE", [row["symbol"] for row in result["fundHoldings"]])

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
