from __future__ import annotations

import datetime as dt
import copy
import math
import unittest

from portfolio_science import (
    BENCHMARK_SYMBOL, BOUNDS, CANDIDATE_WEIGHTS, SYMBOLS,
    MODEL_VERSION, THEME_CAPS, THEME_GROUPS, analyze_portfolio_science,
    portfolio_science_snapshot, walk_forward_evaluation,
)
from price_history import _downsample
from universe_ledger import PROTOCOL_VERSION as UNIVERSE_PROTOCOL_VERSION


def histories(months: int = 150, point_in_time: bool = False):
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
            point = {"date": date.isoformat(), "close": price}
            if point_in_time:
                point["availableAt"] = date.isoformat()
            points.append(point)
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


def persistent_edge_histories(months: int = 150):
    result = histories(months=months, point_in_time=True)
    for symbol, history in result.items():
        price = 100.0
        for point in history["points"]:
            monthly_return = 0.02 if symbol == "VTI" else 0.001 if symbol == BENCHMARK_SYMBOL else 0.002 if symbol == "SGOV" else -0.005
            price *= 1 + monthly_return
            point["close"] = price
    return result


class PortfolioScienceTests(unittest.TestCase):
    def protocol(self):
        return {
            "protocolVersion": UNIVERSE_PROTOCOL_VERSION,
            "ledgerVerified": True,
            "snapshotIds": ["a" * 64],
            "manifestHashes": ["b" * 64],
            "modelVersion": MODEL_VERSION,
            "frozenAt": "2013-12-01",
            "universe": sorted([*SYMBOLS, BENCHMARK_SYMBOL]),
            "universeRecords": {
                symbol: {"securityId": f"FIGI:{symbol}", "membershipVerified": True,
                         "includedAtFreeze": True, "outcomeComplete": True}
                for symbol in [*SYMBOLS, BENCHMARK_SYMBOL]
            },
            "benchmark": BENCHMARK_SYMBOL,
            "survivorshipFree": True,
            "selectionPolicyFrozen": True,
            "pointInTimePrices": True,
            "adjustmentPolicy": "point_in_time_total_return",
            "oneWayCostBps": 10,
            "lookthroughSnapshots": [
                {"asOf": f"{year}-{month:02d}-01", "availableAt": f"{year}-{month:02d}-01",
                 "complete": True, "fundOverlaps": {}}
                for year in range(2013, 2027) for month in range(1, 13)
            ],
        }

    def complete_lookthrough(self):
        return {
            "complete": True, "fundsReady": 6, "fundsTotal": 6,
            "fundOverlaps": {"VTI": {"GOOGL": 5.5, "V": 0.2}},
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
        for theme, cap in THEME_CAPS.items():
            exposure = sum(
                weights.get(symbol, 0) for symbol, assigned in THEME_GROUPS.items()
                if assigned == theme
            )
            self.assertLessEqual(exposure, cap + 0.01)

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

    def test_equity_valuation_has_separate_complete_financing_gate(self):
        report = analyze_portfolio_science(histories(), iterations=100)
        gate = next(item for item in report["gates"]["items"] if item["id"] == "equity_valuation")
        self.assertFalse(gate["passed"])
        self.assertEqual(
            gate["detail"],
            "0 of 8 companies have complete cash, debt, lease, minority-interest and net-borrowing evidence",
        )

    def test_missing_history_fails_closed(self):
        available = histories()

        def provider(symbol):
            if symbol == "NVO":
                raise RuntimeError("missing")
            return available[symbol]

        report = portfolio_science_snapshot(provider=provider, iterations=100)
        self.assertEqual(report["status"], "data_incomplete")
        self.assertIn("NVO", report["errors"])
        self.assertFalse(report["challenger"]["promotionReady"])

    def test_walk_forward_refuses_current_ticker_history_without_provenance(self):
        report = analyze_portfolio_science(histories(), iterations=100)
        walk_forward = report["walkForward"]
        gate = next(item for item in report["gates"]["items"] if item["id"] == "walk_forward")
        self.assertEqual(walk_forward["status"], "blocked")
        self.assertEqual(walk_forward["windowCount"], 0)
        self.assertIn("pre-registered", walk_forward["failures"][0])
        self.assertFalse(gate["passed"])

    def test_walk_forward_uses_five_or_more_non_overlapping_unseen_windows(self):
        report = walk_forward_evaluation(
            histories(point_in_time=True), self.protocol(), iterations=100
        )
        self.assertGreaterEqual(report["windowCount"], 5)
        self.assertEqual(report["minimumWindows"], 5)
        for previous, current in zip(report["windows"], report["windows"][1:]):
            self.assertLess(previous["through"], current["from"])
        self.assertEqual(report["uncertainty"]["versusCandidate"]["samples"], 2000)
        self.assertIn("informationRatioVsBenchmark", report["metrics"]["challenger"])

    def test_future_outcomes_cannot_change_an_earlier_fold_selection(self):
        original = histories(point_in_time=True)
        changed = copy.deepcopy(original)
        for symbol in SYMBOLS:
            for point in changed[symbol]["points"]:
                if point["date"] >= "2020-01-01":
                    point["close"] *= 1.75 if symbol == "VTI" else 0.65
        before = walk_forward_evaluation(original, self.protocol(), iterations=100)
        after = walk_forward_evaluation(changed, self.protocol(), iterations=100)
        self.assertEqual(before["windows"][0]["weights"], after["windows"][0]["weights"])
        self.assertEqual(before["windows"][0]["challengerNetReturn"], after["windows"][0]["challengerNetReturn"])

    def test_selection_and_availability_leakage_fail_closed(self):
        wrong_model = {**self.protocol(), "modelVersion": "chosen-after-seeing-results"}
        selection_leak = walk_forward_evaluation(histories(point_in_time=True), wrong_model, iterations=100)
        self.assertEqual(selection_leak["status"], "blocked")
        self.assertTrue(any("exact model version" in failure for failure in selection_leak["failures"]))

        late_protocol = {**self.protocol(), "frozenAt": "2025-01-01"}
        selection = walk_forward_evaluation(histories(point_in_time=True), late_protocol, iterations=100)
        self.assertEqual(selection["status"], "insufficient_evidence")
        self.assertLess(selection["windowCount"], selection["minimumWindows"])
        self.assertGreaterEqual(selection["windows"][0]["from"], "2025-02")

        missing_timestamp = histories(point_in_time=True)
        missing_timestamp["VTI"]["points"][5].pop("availableAt")
        availability = walk_forward_evaluation(missing_timestamp, self.protocol(), iterations=100)
        self.assertEqual(availability["status"], "blocked")
        self.assertTrue(any("availability" in failure for failure in availability["failures"]))

    def test_weak_unseen_evidence_never_promotes(self):
        report = analyze_portfolio_science(
            histories(point_in_time=True), iterations=100,
            walk_forward_protocol=self.protocol(),
        )
        gate = next(item for item in report["gates"]["items"] if item["id"] == "walk_forward")
        self.assertEqual(report["walkForward"]["status"], "insufficient_evidence")
        self.assertFalse(gate["passed"])
        self.assertFalse(report["challenger"]["promotionReady"])

    def test_strong_repeatable_net_evidence_can_pass_the_walk_forward_gate(self):
        report = walk_forward_evaluation(
            persistent_edge_histories(), self.protocol(), iterations=300
        )
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["eligible"])
        self.assertEqual(report["candidateWins"], report["windowCount"])
        self.assertEqual(report["benchmarkWins"], report["windowCount"])
        self.assertGreater(report["uncertainty"]["versusCandidate"]["low"], 0)
        self.assertGreater(report["uncertainty"]["versusBenchmark"]["low"], 0)


if __name__ == "__main__":
    unittest.main()
