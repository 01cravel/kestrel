from __future__ import annotations

import copy
import unittest

from portfolio_selection import COMPANY_WEIGHTS, candidate_from_latest, select_frozen_candidate


def company(symbol: str, index: int) -> tuple[dict, dict]:
    member = {
        "ticker": symbol,
        "security_id": f"FIGI:{symbol}",
        "included": 1,
        "active": 1,
        "identity_clean": 1,
        "membership_verified": 1,
    }
    payload = {
        "fetchedAt": 1786133100,
        "quote": {"c": 100 + index, "t": 1786132800},
        "profile": {"name": f"Company {symbol}", "finnhubIndustry": "Technology"},
        "metrics": {
            "peTTM": 12 + index,
            "pbQuarterly": 2 + index / 10,
            "roeTTM": 30 - index,
            "netProfitMarginTTM": 25 - index / 2,
            "totalDebt/totalEquityQuarterly": 0.2 + index / 20,
            "26WeekPriceReturnDaily": 30 - index,
            "52WeekPriceReturnDaily": 40 - index,
            "3MonthADReturnStd": 15 + index,
        },
        "sec": {"status": "verified", "conflictCount": 0},
    }
    evidence = {
        "category": "live_symbol_evidence",
        "record_key": symbol,
        "payload_hash": (f"{index + 1:x}" * 64)[:64],
        "payload": payload,
    }
    return member, evidence


def snapshot(count: int = 10) -> dict:
    pairs = [company(f"C{index:02d}", index) for index in range(count)]
    return {
        "status": "verified",
        "snapshotId": "a" * 64,
        "manifestHash": "b" * 64,
        "cutoffUtc": "2026-08-07T21:00:00Z",
        "snapshotStatus": "incomplete",
        "manifest": {"controls": {"selectionPolicyFrozen": True}},
        "members": [pair[0] for pair in pairs],
        "evidence": [pair[1] for pair in pairs],
    }


class PortfolioSelectionTests(unittest.TestCase):
    def test_selects_eight_companies_deterministically_from_frozen_evidence(self):
        frozen = snapshot()
        first = select_frozen_candidate(frozen)
        second = select_frozen_candidate(copy.deepcopy(frozen))
        self.assertEqual(first["status"], "selected")
        self.assertEqual(first["candidateHash"], second["candidateHash"])
        self.assertEqual(len(first["selected"]), 8)
        self.assertEqual(tuple(row["weight"] for row in first["selected"]), COMPANY_WEIGHTS)
        self.assertEqual(sum(first["weights"].values()), 100)
        self.assertFalse(first["promotionReady"])
        self.assertTrue(all(row["evidenceHash"] for row in first["selected"]))

    def test_missing_frozen_universe_fails_closed(self):
        result = candidate_from_latest({"status": "empty"})
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["weights"], {})
        self.assertFalse(result["promotionReady"])

    def test_unfrozen_selection_policy_is_rejected(self):
        frozen = snapshot()
        frozen["manifest"]["controls"]["selectionPolicyFrozen"] = False
        result = select_frozen_candidate(frozen)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("not frozen", result["reason"])

    def test_missing_descriptors_do_not_receive_a_score(self):
        frozen = snapshot(8)
        frozen["evidence"][0]["payload"]["metrics"] = {"peTTM": 10}
        result = select_frozen_candidate(frozen)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["eligibleCount"], 7)
        self.assertTrue(any(row["symbol"] == "C00" for row in result["excluded"]))

    def test_conflicting_official_evidence_is_excluded(self):
        frozen = snapshot(9)
        frozen["evidence"][0]["payload"]["sec"]["conflictCount"] = 1
        result = select_frozen_candidate(frozen)
        self.assertEqual(result["status"], "selected")
        self.assertNotIn("C00", [row["symbol"] for row in result["selected"]])
        self.assertTrue(any(
            row["symbol"] == "C00" and "conflicts" in row["reason"]
            for row in result["excluded"]
        ))

    def test_identity_and_listing_gates_cannot_be_bypassed(self):
        frozen = snapshot(8)
        frozen["members"][0]["membership_verified"] = 0
        result = select_frozen_candidate(frozen)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["eligibleCount"], 7)


if __name__ == "__main__":
    unittest.main()
