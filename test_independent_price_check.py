from __future__ import annotations

import json
import unittest
from datetime import date

from independent_price_check import cross_check_prices, nasdaq_raw_prices, parse_nasdaq_history


class IndependentPriceCheckTests(unittest.TestCase):
    def record(self):
        return {
            "symbol": "TEST", "priceSource": "Working feed",
            "history": [
                {"priceDate": f"2026-01-0{day}", "price": 100 + day}
                for day in range(1, 6)
            ],
            "current": {"priceDate": "2026-01-06", "price": 106},
        }

    def independent(self, multiplier=1.0):
        return [
            {"date": date(2026, 1, day), "close": (100 + day) * multiplier}
            for day in range(1, 7)
        ]

    def test_parses_nasdaq_currency_and_reverse_order(self):
        payload = {"data": {"tradesTable": {"rows": [
            {"date": "01/06/2026", "close": "$1,106.25"},
            {"date": "01/05/2026", "close": "$105.50"},
        ]}}}
        rows = parse_nasdaq_history(payload)
        self.assertEqual(rows[0], {"date": date(2026, 1, 5), "close": 105.5})
        self.assertEqual(rows[1]["close"], 1106.25)

    def test_all_dates_agree_and_current_date_is_covered(self):
        result = cross_check_prices(self.record(), self.independent(multiplier=1.005))
        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["datesMatched"], 6)

    def test_material_difference_fails_closed(self):
        result = cross_check_prices(self.record(), self.independent(multiplier=1.04))
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "disagreed")
        self.assertEqual(result["materialDisagreements"], 6)

    def test_missing_coverage_fails_closed(self):
        result = cross_check_prices(self.record(), self.independent()[:4])
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["currentDateMatched"])

    def test_nasdaq_request_uses_iso_dates_and_parses_response(self):
        seen = []
        payload = {"data": {"tradesTable": {"rows": [
            {"date": "01/06/2026", "close": "$106.00"}
        ]}}}
        rows = nasdaq_raw_prices("TEST", lambda url: seen.append(url) or json.dumps(payload), today=date(2026, 1, 6))
        self.assertIn("fromdate=2015-12-30", seen[0])
        self.assertIn("todate=2026-01-06", seen[0])
        self.assertEqual(rows[0]["close"], 106.0)


if __name__ == "__main__":
    unittest.main()
