from __future__ import annotations

import unittest
from datetime import date

from point_in_time_cashflow import (
    build_company_cashflow, financing_evidence_as_of, ttm_flow_as_of,
)


def flow(start, end, value, filed, form, accession):
    return {"start": start, "end": end, "val": value, "filed": filed, "form": form, "accn": accession}


def instant(end, value, filed="2026-02-01", accession="a"):
    return {"end": end, "val": value, "filed": filed, "form": "10-K", "accn": accession}


class PointInTimeCashFlowTests(unittest.TestCase):
    def test_ttm_bridge_never_uses_future_filing(self):
        rows = [
            flow("2024-01-01", "2024-12-31", 100, "2025-02-01", "10-K", "a24"),
            flow("2024-01-01", "2024-06-30", 40, "2025-07-20", "10-Q", "q25"),
            flow("2025-01-01", "2025-06-30", 70, "2025-07-20", "10-Q", "q25"),
        ]
        self.assertEqual(ttm_flow_as_of(rows, date(2025, 7, 19))["value"], 100)
        self.assertEqual(ttm_flow_as_of(rows, date(2025, 7, 20))["value"], 130)

    def test_company_uses_operating_cash_less_capex_and_own_history(self):
        cfo, capex, shares = [], [], []
        for year in range(2019, 2026):
            filed = f"{year + 1}-02-01"
            cfo.append(flow(f"{year}-01-01", f"{year}-12-31", 1_000 + year, filed, "10-K", f"a{year}"))
            capex.append(flow(f"{year}-01-01", f"{year}-12-31", 200, filed, "10-K", f"a{year}"))
            shares.append({"end": f"{year}-12-31", "val": 100, "filed": filed, "form": "10-K", "accn": f"a{year}"})
        facts = {"facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": cfo}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": capex}},
            },
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": shares}}},
        }}
        prices = [{"date": date(year, 2, 2), "close": 100 + year} for year in range(2020, 2027)]
        result = build_company_cashflow("AMZN", "0001", facts, prices, {}, today=date(2026, 2, 2))
        self.assertTrue(result["ready"])
        self.assertGreater(result["current"]["freeCashFlow"], 0)
        self.assertGreaterEqual(result["comparison"]["observations"], 5)

    def test_negative_free_cash_flow_is_not_given_a_valuation(self):
        facts = {"facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [flow("2025-01-01", "2025-12-31", 50, "2026-02-01", "10-K", "a")]}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [flow("2025-01-01", "2025-12-31", 100, "2026-02-01", "10-K", "a")]}},
            },
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2025-12-31", "val": 100, "filed": "2026-02-01", "form": "10-K"}]}}},
        }}
        result = build_company_cashflow("AMZN", "0001", facts, [{"date": date(2026, 2, 2), "close": 100}], {}, today=date(2026, 2, 2))
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "partial")
        self.assertLess(result["current"]["freeCashFlow"], 0)
        self.assertIsNone(result["current"]["fcfYield"])

    def test_split_factor_normalizes_share_count_for_market_value(self):
        facts = {"facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [flow("2020-01-01", "2020-12-31", 100, "2021-02-01", "10-K", "a")]}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [flow("2020-01-01", "2020-12-31", 20, "2021-02-01", "10-K", "a")]}},
            },
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2020-12-31", "val": 10, "filed": "2021-02-01", "form": "10-K"}]}}},
        }}
        price = {"date": date(2021, 2, 2), "close": 10, "shareFactor": 20}
        result = build_company_cashflow("AMZN", "0001", facts, [price], {}, today=date(2021, 2, 2))
        self.assertEqual(result["current"]["tradedShares"], 200)
        self.assertEqual(result["current"]["priceToFcf"], 25.0)

    def test_point_in_time_ppe_depreciation_is_exposed_only_when_filed(self):
        facts = {"facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [flow("2025-01-01", "2025-12-31", 100, "2026-02-01", "10-K", "a")]}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [flow("2025-01-01", "2025-12-31", 60, "2026-02-01", "10-K", "a")]}},
                "Depreciation": {"units": {"USD": [flow("2025-01-01", "2025-12-31", 35, "2026-02-01", "10-K", "a")]}},
            },
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2025-12-31", "val": 10, "filed": "2026-02-01", "form": "10-K"}]}}},
        }}
        price = {"date": date(2026, 2, 2), "close": 10}
        result = build_company_cashflow("AMZN", "0001", facts, [price], {}, today=date(2026, 2, 2))
        self.assertEqual(result["current"]["depreciation"], 35.0)
        self.assertEqual(result["depreciationTag"], "us-gaap:Depreciation")

    def test_financing_evidence_is_as_filed_same_period_and_never_double_counts_claims(self):
        annual = lambda value: [flow("2025-01-01", "2025-12-31", value, "2026-02-01", "10-K", "a")]
        concepts = {
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [instant("2025-12-31", 100)]}},
            "LongTermDebtCurrent": {"units": {"USD": [instant("2025-12-31", 10)]}},
            "LongTermDebtNoncurrent": {"units": {"USD": [instant("2025-12-31", 40)]}},
            "ShortTermBorrowings": {"units": {"USD": [instant("2025-12-31", 5)]}},
            "OperatingLeaseLiabilityCurrent": {"units": {"USD": [instant("2025-12-31", 3)]}},
            "OperatingLeaseLiabilityNoncurrent": {"units": {"USD": [instant("2025-12-31", 7)]}},
            "FinanceLeaseLiabilityCurrent": {"units": {"USD": [instant("2025-12-31", 2)]}},
            "FinanceLeaseLiabilityNoncurrent": {"units": {"USD": [instant("2025-12-31", 8)]}},
            "MinorityInterest": {"units": {"USD": [instant("2025-12-31", 4)]}},
            "ProceedsFromIssuanceOfDebt": {"units": {"USD": annual(30)}},
            "RepaymentsOfDebt": {"units": {"USD": annual(12)}},
        }
        facts = {"facts": {"us-gaap": concepts}}
        self.assertFalse(financing_evidence_as_of(facts, "USD", date(2026, 1, 31))["ready"])
        result = financing_evidence_as_of(facts, "USD", date(2026, 2, 1))
        self.assertTrue(result["ready"])
        self.assertEqual(result["debt"]["value"], 55.0)
        self.assertEqual(result["leases"]["value"], 20.0)
        self.assertEqual(result["netBorrowing"]["value"], 18.0)
        self.assertEqual(result["netDebtLikeClaims"], -21.0)

    def test_missing_lease_component_fails_closed_instead_of_assuming_zero(self):
        facts = {"facts": {"us-gaap": {
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [instant("2025-12-31", 100)]}},
            "LongTermDebtCurrent": {"units": {"USD": [instant("2025-12-31", 0)]}},
            "LongTermDebtNoncurrent": {"units": {"USD": [instant("2025-12-31", 50)]}},
            "ShortTermBorrowings": {"units": {"USD": [instant("2025-12-31", 0)]}},
            "OperatingLeaseLiability": {"units": {"USD": [instant("2025-12-31", 10)]}},
            "MinorityInterest": {"units": {"USD": [instant("2025-12-31", 0)]}},
        }}}
        result = financing_evidence_as_of(facts, "USD", date(2026, 2, 1))
        self.assertFalse(result["balanceSheetReady"])
        self.assertFalse(result["leases"]["ready"])


if __name__ == "__main__":
    unittest.main()
