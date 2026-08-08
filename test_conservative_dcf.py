from __future__ import annotations

import unittest

from conservative_dcf import build_company_dcf, discounted_value, estimate_beta


def history(multiplier=1.0, months=60):
    points, market = [], []
    stock_price = market_price = 100.0
    year, month = 2021, 1
    for index in range(months + 1):
        market_return = 0.01 if index % 2 else -0.004
        stock_return = market_return * multiplier
        market_price *= 1 + market_return
        stock_price *= 1 + stock_return
        day = f"{year:04d}-{month:02d}-28"
        points.append({"date": day, "close": stock_price})
        market.append({"date": day, "close": market_price})
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return {"points": points}, {"points": market}


def cashflow(positive=True, years=6):
    rows = []
    for index in range(years):
        rows.append({
            "knownOn": f"{2020 + index}-12-31", "freeCashFlow": 100 + index * 10,
            "tradedShares": 10, "price": 100,
        })
    current_cash = 160 if positive else -20
    return {
        "current": {"freeCashFlow": current_cash, "tradedShares": 10, "price": 100},
        "history": rows,
    }


class ConservativeDcfTests(unittest.TestCase):
    def test_discounted_value_includes_visible_terminal_share(self):
        result = discounted_value(10, 5, 12, 2)
        self.assertGreater(result["value"], 0)
        self.assertGreater(result["terminalSharePct"], 0)
        self.assertLess(result["terminalSharePct"], 100)

    def test_beta_is_measured_and_conservatively_bounded(self):
        stock, market = history(multiplier=2.5)
        beta = estimate_beta(stock, market)
        self.assertTrue(beta["ready"])
        self.assertEqual(beta["used"], 1.6)

    def test_company_has_ordered_scenarios_and_floored_discount(self):
        stock, market = history(multiplier=1.2)
        result = build_company_dcf("TEST", cashflow(), stock, market)
        self.assertTrue(result["ready"])
        values = [scenario["value"] for scenario in result["scenarios"]]
        self.assertEqual(values, sorted(values))
        self.assertGreaterEqual(result["baseDiscountPct"], 10.5)

    def test_negative_cash_flow_fails_without_manufactured_value(self):
        stock, market = history()
        result = build_company_dcf("TEST", cashflow(positive=False), stock, market)
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("scenarios", result)

    def test_short_company_history_fails_closed(self):
        stock, market = history()
        result = build_company_dcf("TEST", cashflow(years=2), stock, market)
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "limited")


if __name__ == "__main__":
    unittest.main()
