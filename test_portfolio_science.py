from __future__ import annotations

import datetime as dt
import math
import unittest

from portfolio_science import (
    BENCHMARK_SYMBOL, BOUNDS, CANDIDATE_WEIGHTS, SYMBOLS,
    analyze_portfolio_science, portfolio_science_snapshot,
)
from price_history import _downsample


def histories(months: int = 150):
    result = {}
    symbols = [*SYMBOLS, BENCHMARK_SYMBOL]
    for symbol_index, symbol in enumerate(symbols):
        price = 100.0
        points = []
        year, month = 2014, 1
        for index in range(months):
            date = dt.date(year, month, 1)
            market = 0.006 + 0.025 * math.sin(index / 5)
            specific = 0.004 * math.sin(index / 3 + symbol_index)
            if symbol == "SGOV":
                monthly_return = 0.0025
            elif symbol == "IBIT":
                monthly_return = market + 0.07 * math.sin(index / 2)
            else:
                monthly_return = market + specific
            price *= 1 + monthly_return
            points.append({"date": date.isoformat(), "close": price})
            month += 1
            if month == 13:
                year += 1
                month = 1
        result[symbol] = {
            "symbol": symbol,
            "points": points,
            "source": "Synthetic test history",
            "method": "Adjusted monthly prices",
        }
    return result


class PortfolioScienceTests(unittest.TestCase):
    def complete_lookthrough(self):
        return {
            "complete": True, "fundsReady": 6, "fundsTotal": 6,
            "fundOverlaps": {"VTI": {"GOOGL": 5.5, "AMZN": 3.5}},
            "sources": [], "exposures": [],
        }

    def complete_fundamentals(self):
        return {"complete": True, "companiesReady": 8, "companiesTotal": 8,
                "priceCrossCheckReady": True, "companies": {},
                "cashFlow": {"complete": True, "companiesReady": 8, "companiesTotal": 8}}

    def test_monthly_model_history_is_not_thinned_at_chart_limit(self):
        points = [{"date": str(index), "close": 100 + index} for index in range(500)]
        self.assertEqual(len(_downsample(points, maximum=720)), 500)

    def test_candidate_is_frozen_and_challenger_is_constrained(self):
        report = analyze_portfolio_science(histories(), iterations=500)
        self.assertEqual(report["candidate"]["weights"], CANDIDATE_WEIGHTS)
        self.assertEqual(report["research"]["portfoliosTested"], 500)
        weights = report["challenger"]["weights"]
        self.assertAlmostEqual(sum(weights.values()), 100, delta=0.12)
        for symbol, weight in weights.items():
            self.assertGreaterEqual(weight, BOUNDS[symbol][0] - 0.01)
            self.assertLessEqual(weight, BOUNDS[symbol][1] + 0.01)
        self.assertFalse(report["challenger"]["promotionReady"])
        self.assertEqual(report["status"], "research_only")

    def test_search_is_deterministic_and_reports_two_year_risk(self):
        first = analyze_portfolio_science(histories(), iterations=300)
        second = analyze_portfolio_science(histories(), iterations=300)
        self.assertEqual(first["challenger"]["weights"], second["challenger"]["weights"])
        self.assertIsNotNone(first["candidate"]["metrics"]["worstTwoYear"])
        self.assertEqual(first["candidate"]["bootstrap"]["samples"], 1000)

    def test_complete_lookthrough_passes_gate_and_constrains_effective_exposure(self):
        report = analyze_portfolio_science(
            histories(), iterations=300, lookthrough=self.complete_lookthrough()
        )
        gates = {gate["id"]: gate for gate in report["gates"]["items"]}
        self.assertTrue(gates["lookthrough"]["passed"])
        self.assertTrue(gates["effective_concentration"]["passed"])
        weights = report["challenger"]["weights"]
        effective_alphabet = weights["GOOGL"] + weights["VTI"] * 0.055
        self.assertLessEqual(effective_alphabet, 8.01)

    def test_point_in_time_gate_uses_verified_company_coverage(self):
        report = analyze_portfolio_science(
            histories(), iterations=100, fundamentals=self.complete_fundamentals()
        )
        gate = next(item for item in report["gates"]["items"] if item["id"] == "point_in_time")
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["detail"], "8 of 8 as-filed histories; 8 of 8 cash-flow histories; 8 of 8 Nasdaq prices")

    def test_investment_split_has_its_own_fail_closed_gate(self):
        report = analyze_portfolio_science(histories(), iterations=100)
        gate = next(item for item in report["gates"]["items"] if item["id"] == "investment_split")
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["detail"], "0 of 8 companies have dated issuer evidence and a depreciation cross-check")

    def test_missing_history_fails_closed(self):
        available = histories()

        def provider(symbol):
            if symbol == "ASML":
                raise RuntimeError("missing")
            return available[symbol]

        report = portfolio_science_snapshot(provider=provider, iterations=100)
        self.assertEqual(report["status"], "data_incomplete")
        self.assertIn("ASML", report["errors"])
        self.assertFalse(report["challenger"]["promotionReady"])


if __name__ == "__main__":
    unittest.main()
