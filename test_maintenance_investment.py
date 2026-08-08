from __future__ import annotations

import unittest

from maintenance_investment import evidence_as_of, investment_sensitivity


class MaintenanceInvestmentTests(unittest.TestCase):
    def test_future_disclosure_is_never_used_at_old_cutoff(self):
        self.assertIsNone(evidence_as_of("AMZN", "2026-02-05"))
        self.assertEqual(evidence_as_of("AMZN", "2026-02-06")["source"], "Amazon 2025 Form 10-K")

    def test_sensitivity_keeps_all_capex_in_downside_and_uses_bounded_excess(self):
        result = investment_sensitivity("AMZN", {
            "knownOn": "2026-08-08", "operatingCashFlow": 180,
            "capitalInvestment": 140, "depreciation": 80,
        })
        self.assertTrue(result["ready"])
        self.assertEqual(result["maintenanceRange"], [80.0, 140.0])
        self.assertEqual(result["growthRange"], [0.0, 60.0])
        scenarios = {item["id"]: item for item in result["scenarios"]}
        self.assertEqual(scenarios["downside"]["ownerCash"], 40.0)
        self.assertEqual(scenarios["base"]["ownerCash"], 70.0)
        self.assertEqual(scenarios["strong"]["ownerCash"], 100.0)

    def test_depreciation_alone_never_opens_the_model(self):
        result = investment_sensitivity("UNKNOWN", {
            "knownOn": "2026-08-08", "operatingCashFlow": 180,
            "capitalInvestment": 140, "depreciation": 80,
        })
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "not_public")

    def test_mixed_unquantified_constellation_evidence_fails_closed(self):
        result = investment_sensitivity("CEG", {
            "knownOn": "2026-08-08", "operatingCashFlow": 180,
            "capitalInvestment": 140, "depreciation": 80,
        })
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "insufficient")


if __name__ == "__main__":
    unittest.main()
