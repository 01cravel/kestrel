"""Safeguards for the Phase 1 Swing Radar contract."""

from __future__ import annotations

import unittest

from swing_radar_policy import (
    alert_status,
    assess_investability,
    feature_is_available,
    label_forward_return,
    promotion_failures,
)


ELIGIBLE = {
    "exchange_mic": "XNAS",
    "security_type": "common_stock",
    "active": True,
    "identity_clean": True,
    "corporate_actions_clean": True,
    "currency": "USD",
    "close": 20,
    "market_cap": 1_000_000_000,
    "median_dollar_volume_20d": 20_000_000,
    "prior_sessions": 300,
}


class SwingRadarPolicyTests(unittest.TestCase):
    def test_eligibility_passes_only_complete_investable_rows(self) -> None:
        self.assertTrue(assess_investability(ELIGIBLE)["eligible"])
        excluded = assess_investability({**ELIGIBLE, "security_type": "etf"})
        self.assertFalse(excluded["eligible"])
        self.assertIn("not a common stock or ADR", excluded["reasons"][0])

    def test_missing_eligibility_input_is_unknown_not_false(self) -> None:
        incomplete = dict(ELIGIBLE)
        del incomplete["market_cap"]
        result = assess_investability(incomplete)
        self.assertIsNone(result["eligible"])
        self.assertEqual(result["status"], "unknown")

    def test_primary_label_is_benchmark_relative_and_boundary_inclusive(self) -> None:
        result = label_forward_return(100, 111, 100, 101)
        self.assertTrue(result["isSwing"])
        self.assertAlmostEqual(result["excessReturn"], 0.10)
        self.assertEqual(result["direction"], "up")

    def test_unclean_return_is_quarantined(self) -> None:
        result = label_forward_return(100, 200, 100, 100, data_clean=False)
        self.assertEqual(result["labelStatus"], "quarantined")
        self.assertNotIn("isSwing", result)

    def test_feature_requires_both_pre_cutoff_timestamps(self) -> None:
        cutoff = "2026-08-01T20:15:00Z"
        self.assertTrue(feature_is_available({
            "published_at": "2026-08-01T18:00:00Z",
            "available_at": "2026-08-01T18:01:00Z",
        }, cutoff))
        self.assertFalse(feature_is_available({
            "published_at": "2026-08-01T18:00:00Z",
            "available_at": "2026-08-01T20:16:00Z",
        }, cutoff))
        self.assertFalse(feature_is_available({"published_at": "2026-08-01T18:00:00Z"}, cutoff))

    def test_promotion_requires_every_calibration_and_human_gate(self) -> None:
        passing = {
            "trading_sessions": 60,
            "matured_predictions": 200,
            "matured_watches": 40,
            "realized_swings": 15,
            "brier_skill": 0.10,
            "calibration_error": 0.05,
            "alert_precision": 0.20,
            "base_rate": 0.10,
            "alert_precision_lower_95": 0.11,
            "directional_accuracy": 0.60,
            "critical_incident": False,
            "risk_review_accepted": True,
        }
        self.assertEqual(promotion_failures(passing), [])
        self.assertTrue(promotion_failures({**passing, "risk_review_accepted": False}))

    def test_alert_status_never_promotes_unclean_evidence(self) -> None:
        self.assertEqual(alert_status(0.50, 0.10, model_promoted=True, evidence_clean=False), "abstain")
        self.assertEqual(alert_status(0.40, 0.10, model_promoted=False, evidence_clean=True), "early_watch")
        self.assertEqual(alert_status(0.40, 0.10, model_promoted=True, evidence_clean=True), "research_alert")


if __name__ == "__main__":
    unittest.main()
