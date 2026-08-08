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

    def test_dated_investment_evidence_can_value_positive_owner_cash_without_hiding_reported_loss(self):
        stock, market = history(multiplier=1.2)
        rows = []
        for index in range(6):
            operating, capex, depreciation = 150 + index * 10, 120, 70
            rows.append({
                "knownOn": f"{2020 + index}-12-31",
                "operatingCashFlow": operating, "capitalInvestment": capex,
                "depreciation": depreciation, "freeCashFlow": operating - capex,
                "tradedShares": 10, "price": 100,
            })
        record = {
            "current": {
                "knownOn": "2026-08-08", "operatingCashFlow": 150,
                "capitalInvestment": 200, "depreciation": 80,
                "freeCashFlow": -50, "tradedShares": 10, "price": 100,
            },
            "history": rows,
        }
        result = build_company_dcf("AMZN", record, stock, market)
        self.assertFalse(result["reportedReady"])
        self.assertTrue(result["normalizedReady"])
        self.assertEqual(result["currentFcfPerShare"], -5.0)
        self.assertEqual(result["selectedView"], "ownerCash")

    def test_complete_financing_evidence_opens_fcfe_without_reapplying_balance_sheet_claims(self):
        stock, market = history(multiplier=1.2)
        rows = []
        for index in range(6):
            rows.append({
                "knownOn": f"{2020 + index}-12-31", "operatingCashFlow": 180,
                "capitalInvestment": 100, "depreciation": 70, "freeCashFlow": 80,
                "netBorrowing": -5, "tradedShares": 10, "price": 100,
                "financingEvidence": {"ready": True},
            })
        financing = {
            "ready": True, "cash": {"value": 100}, "debt": {"value": 50},
            "leases": {"value": 20}, "minorityInterests": {"value": 4},
            "netBorrowing": {"value": -5}, "netDebtLikeClaims": -26,
        }
        record = {
            "current": {
                "knownOn": "2026-08-08", "operatingCashFlow": 180,
                "capitalInvestment": 100, "depreciation": 70, "freeCashFlow": 80,
                "tradedShares": 10, "price": 100, "financingEvidence": financing,
            },
            "history": rows,
        }
        result = build_company_dcf("AMZN", record, stock, market)
        self.assertTrue(result["normalizedReady"])
        self.assertTrue(result["equityReady"])
        self.assertEqual(result["fcfeView"]["normalizedNetBorrowingPerShare"], -0.5)
        self.assertFalse(result["fcfeView"]["balanceSheetClaimsAppliedToFcfe"])
        owner_base = next(item for item in result["ownerCashView"]["scenarios"] if item["id"] == "base")
        fcfe_base = next(item for item in result["fcfeView"]["scenarios"] if item["id"] == "base")
        self.assertLess(fcfe_base["value"], owner_base["value"])

    def test_positive_borrowing_is_visible_but_gets_no_perpetual_value_credit(self):
        stock, market = history(multiplier=1.2)
        rows = [{
            "knownOn": f"{2020 + index}-12-31", "freeCashFlow": 80,
            "netBorrowing": 30, "tradedShares": 10,
            "financingEvidence": {"ready": True},
        } for index in range(6)]
        record = {
            "current": {
                "knownOn": "2026-08-08", "operatingCashFlow": 180,
                "capitalInvestment": 100, "depreciation": 70, "freeCashFlow": 80,
                "tradedShares": 10, "price": 100,
                "financingEvidence": {"ready": True, "netBorrowing": {"value": 30}},
            },
            "history": rows,
        }
        result = build_company_dcf("AMZN", record, stock, market)
        self.assertTrue(result["equityReady"])
        self.assertEqual(result["fcfeView"]["normalizedNetBorrowingPerShare"], 0.0)
        self.assertEqual(result["fcfeView"]["rangeLow"], result["ownerCashView"]["rangeLow"])


if __name__ == "__main__":
    unittest.main()
