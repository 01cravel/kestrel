from __future__ import annotations

import unittest
import json
from datetime import date

from point_in_time_valuation import _raw_prices, build_company_valuation, ttm_eps_as_of


def eps(start, end, value, filed, form, accession):
    return {"start": start, "end": end, "val": value, "filed": filed, "form": form, "accn": accession}


class PointInTimeValuationTests(unittest.TestCase):
    def facts(self):
        rows = [
            eps("2024-01-01", "2024-12-31", 8.0, "2025-02-01", "10-K", "annual24"),
            eps("2024-01-01", "2024-06-30", 3.0, "2025-07-20", "10-Q", "q225"),
            eps("2025-01-01", "2025-06-30", 5.0, "2025-07-20", "10-Q", "q225"),
            eps("2025-01-01", "2025-12-31", 12.0, "2026-02-01", "10-K", "annual25"),
        ]
        return {"entityName": "Example", "facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": rows}}}}}

    def test_future_filing_never_leaks_backwards(self):
        rows = self.facts()["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]
        before = ttm_eps_as_of(rows, date(2025, 7, 19))
        after = ttm_eps_as_of(rows, date(2025, 7, 20))
        self.assertEqual(before["eps"], 8.0)
        self.assertEqual(after["eps"], 10.0)
        self.assertEqual(after["method"], "As-filed annual EPS plus current YTD minus prior comparable YTD")

    def test_later_annual_filing_never_rewrites_earlier_snapshot(self):
        rows = self.facts()["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]
        old = ttm_eps_as_of(rows, date(2025, 12, 31))
        new = ttm_eps_as_of(rows, date(2026, 2, 1))
        self.assertEqual(old["eps"], 10.0)
        self.assertEqual(new["eps"], 12.0)

    def test_company_requires_fresh_evidence_and_enough_own_history(self):
        prices = [
            {"date": date(year, 2, 2), "close": 100 + (year - 2020) * 10}
            for year in range(2020, 2027)
        ]
        rows = [eps(f"{year}-01-01", f"{year}-12-31", 5 + year - 2020, f"{year + 1}-02-01", "10-K", f"a{year}") for year in range(2020, 2026)]
        facts = {"entityName": "Example", "facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": rows}}}}}
        result = build_company_valuation("GOOGL", "0000000001", facts, prices, {}, today=date(2026, 2, 2))
        self.assertTrue(result["ready"])
        self.assertGreaterEqual(result["comparison"]["observations"], 5)
        self.assertEqual(result["current"]["filed"], "2026-02-01")

    def test_non_usd_earnings_need_official_fx(self):
        facts = {"entityName": "Example", "facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"EUR/shares": [
            eps("2025-01-01", "2025-12-31", 10, "2026-02-01", "20-F", "a")
        ]}}}}}
        prices = [{"date": date(2026, 2, 2), "close": 100}]
        result = build_company_valuation("ASML", "0000000002", facts, prices, {}, today=date(2026, 2, 2))
        self.assertEqual(result["status"], "unavailable")

    def test_split_normalized_price_carries_matching_share_factor(self):
        payload = {"chart": {"result": [{
            "timestamp": [1577836800, 1654128000],
            "indicators": {"quote": [{"close": [100, 110]}]},
            "events": {"splits": {"one": {
                "date": 1654128000, "numerator": 20, "denominator": 1,
            }}},
        }]}}
        rows = _raw_prices("TEST", lambda _url: json.dumps(payload))
        self.assertEqual(rows[0]["shareFactor"], 20)
        self.assertEqual(rows[1]["shareFactor"], 1)

    def test_split_factor_normalizes_historical_eps_before_pe(self):
        facts = {"entityName": "Example", "facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": [
            eps("2020-01-01", "2020-12-31", 20, "2021-02-01", "10-K", "a")
        ]}}}}}
        price = {"date": date(2021, 2, 2), "close": 100, "shareFactor": 20}
        result = build_company_valuation("GOOGL", "0001", facts, [price], {}, today=date(2021, 2, 2))
        self.assertEqual(result["current"]["ttmEps"], 1.0)
        self.assertEqual(result["current"]["pe"], 100.0)


if __name__ == "__main__":
    unittest.main()
