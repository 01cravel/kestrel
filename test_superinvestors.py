"""Focused safeguards for the SEC 13F discovery layer."""

from __future__ import annotations

import unittest

from superinvestors import _aggregate, _change_label, _consolidate_holdings, _deduplicate_companies, _parse_holdings


SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>Example Inc</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>123456789</cusip>
    <value>1000</value><shrsOrPrnAmt><sshPrnamt>100</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>Example Inc</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>123456789</cusip>
    <value>500</value><shrsOrPrnAmt><sshPrnamt>50</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>Option Inc</nameOfIssuer><titleOfClass>CALL</titleOfClass><cusip>987654321</cusip>
    <value>250</value><shrsOrPrnAmt><sshPrnamt>5</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><putCall>Call</putCall>
  </infoTable>
</informationTable>"""


class SuperinvestorTests(unittest.TestCase):
    def test_options_are_excluded_and_included_managers_are_consolidated(self) -> None:
        rows = _parse_holdings(SAMPLE_XML)
        self.assertEqual(len(rows), 2)
        holdings = _consolidate_holdings(rows)
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0]["shares"], 150)
        self.assertEqual(holdings[0]["value"], 1500)

    def test_changes_use_clear_ten_percent_bands(self) -> None:
        self.assertEqual(_change_label(100, None)[0], "New")
        self.assertEqual(_change_label(111, 100)[0], "Increased")
        self.assertEqual(_change_label(89, 100)[0], "Reduced")
        self.assertEqual(_change_label(105, 100)[0], "Held")

    def test_manager_agreement_counts_managers_not_rows(self) -> None:
        managers = [{
            "id": "one", "name": "Manager One", "style": "Quality", "periodEnd": "2026-03-31",
            "filedAt": "2026-05-15", "filingUrl": "https://www.sec.gov/example",
            "holdings": [{"issuer": "Example", "class": "COM", "cusip": "123456789", "shares": 120, "value": 1200}],
            "priorHoldings": [{"issuer": "Example", "class": "COM", "cusip": "123456789", "shares": 100, "value": 1000}],
        }]
        idea = _aggregate(managers)[0]
        self.assertEqual(idea["ownerCount"], 1)
        self.assertEqual(idea["activeBuyerCount"], 1)
        self.assertEqual(idea["managers"][0]["action"], "Increased")

    def test_share_classes_are_one_company_and_manager_weights_are_combined(self) -> None:
        base_manager = {
            "id": "one", "name": "Manager One", "style": "Quality", "action": "Held",
            "changePercent": 1, "portfolioWeight": 2.5, "periodEnd": "2026-03-31",
            "filedAt": "2026-05-15", "filingUrl": "https://www.sec.gov/example",
        }
        ideas = [{
            "cusip": "A", "issuer": "Alphabet Inc", "class": "Class A", "symbol": "GOOGL",
            "name": "Alphabet", "ownerCount": 1, "activeBuyerCount": 0, "highestConviction": 2.5,
            "managers": [base_manager],
        }, {
            "cusip": "C", "issuer": "Alphabet Inc", "class": "Class C", "symbol": "GOOG",
            "name": "Alphabet", "ownerCount": 1, "activeBuyerCount": 1, "highestConviction": 1.5,
            "managers": [{**base_manager, "action": "Increased", "portfolioWeight": 1.5}],
        }]
        merged = _deduplicate_companies(ideas)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["symbol"], "GOOGL")
        self.assertEqual(merged[0]["shareClasses"], ["GOOG", "GOOGL"])
        self.assertEqual(merged[0]["ownerCount"], 1)
        self.assertEqual(merged[0]["activeBuyerCount"], 1)
        self.assertEqual(merged[0]["managers"][0]["portfolioWeight"], 4.0)


if __name__ == "__main__":
    unittest.main()
