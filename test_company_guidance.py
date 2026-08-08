from __future__ import annotations

import unittest

import company_guidance
from company_guidance import build_guidance_view, compare_guidance, extract_guidance, official_ir_guidance


def evidence(**changes):
    row = {
        "sourceKind": "sec_filing",
        "sourceUrl": "https://www.sec.gov/Archives/edgar/data/1/release.htm",
        "sourceRecordId": "0001-26-000001",
        "accession": "0001-26-000001",
        "publishedAt": "2026-05-01T20:05:00Z",
        "retrievedAt": "2026-05-02T08:00:00Z",
    }
    row.update(changes)
    return row


def guidance(low=10.0, high=12.0, published="2026-05-01T20:05:00Z", **changes):
    row = {
        "status": "verified", "metric": "revenue", "definition": "revenue",
        "period": {"type": "fiscal_year", "label": "FY 2026", "year": "2026"},
        "low": low, "high": high, "unit": "currency", "currency": "USD",
        "publishedAt": published, "managementMidpoint": None, "midpointInferred": False,
    }
    row.update(changes)
    return row


class ExtractionTests(unittest.TestCase):
    def test_preserves_exact_range_period_units_and_cutoff_without_midpoint(self):
        result = extract_guidance(
            "Management expects full-year 2026 revenue of $10 billion USD to $12 billion USD.", evidence())
        self.assertEqual(result["status"], "verified")
        row = result["observations"][0]
        self.assertEqual((row["low"], row["high"]), (10_000_000_000.0, 12_000_000_000.0))
        self.assertEqual(row["period"]["label"], "FY 2026")
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["publishedAt"], "2026-05-01T20:05:00Z")
        self.assertIsNone(row["managementMidpoint"])
        self.assertFalse(row["midpointInferred"])

    def test_percentage_guidance_has_no_currency(self):
        result = extract_guidance(
            "We expect Q3 2026 gross margin of 47% to 49%.", evidence())
        row = result["observations"][0]
        self.assertEqual(row["unit"], "percent")
        self.assertIsNone(row["currency"])
        self.assertEqual(row["period"]["label"], "Q3 2026")

    def test_management_midpoint_is_kept_only_when_explicit(self):
        result = extract_guidance(
            "Management expects FY 2026 revenue of $10 billion USD to $12 billion USD, with a midpoint of $11 billion USD.",
            evidence())
        self.assertEqual(result["observations"][0]["managementMidpoint"], 11_000_000_000.0)
        self.assertFalse(result["observations"][0]["midpointInferred"])

    def test_missing_period_or_explicit_range_fails_closed(self):
        result = extract_guidance(
            "Management expects revenue of approximately $11 billion.", evidence())
        self.assertEqual(result["status"], "no-explicit-guidance")
        self.assertEqual(result["observations"], [])

    def test_ambiguous_shared_currency_and_scale_fail_closed(self):
        result = extract_guidance(
            "Management expects full-year 2026 revenue of $10 to 12 billion.", evidence())
        self.assertEqual(result["observations"], [])

    def test_bare_dollar_symbol_does_not_silently_become_usd(self):
        result = extract_guidance(
            "Management expects FY 2026 revenue of $10 billion to $12 billion.", evidence())
        self.assertEqual(result["observations"], [])

    def test_official_ir_requires_verified_issuer_domain_and_exact_timezone(self):
        unverified = evidence(sourceKind="official_ir", sourceUrl="https://example.com/release",
                              issuerDomainVerified=False)
        self.assertEqual(extract_guidance("expects FY 2026 revenue $10 billion to $12 billion", unverified)["status"], "rejected")
        missing_zone = evidence(publishedAt="2026-05-01T20:05:00")
        self.assertEqual(extract_guidance("expects FY 2026 revenue $10 billion to $12 billion", missing_zone)["status"], "rejected")

    def test_official_ir_domain_allowlist_rejects_deceptive_hosts(self):
        text = "Management expects FY 2026 revenue of $10 billion USD to $12 billion USD."
        accepted = official_ir_guidance(
            text, "https://investor.acme.com/releases/1", "2026-05-01T20:05:00Z", ["acme.com"])
        rejected = official_ir_guidance(
            text, "https://acme.com.evil.example/releases/1", "2026-05-01T20:05:00Z", ["acme.com"])
        self.assertEqual(accepted["status"], "verified")
        self.assertEqual(rejected["status"], "rejected")

    def test_sec_label_cannot_make_a_non_sec_url_authoritative(self):
        result = extract_guidance(
            "Management expects FY 2026 revenue of $10 billion USD to $12 billion USD.",
            evidence(sourceUrl="https://example.com/release"))
        self.assertEqual(result["status"], "rejected")

    def test_unrecognized_adjusted_definition_is_not_mixed_with_gaap_metric(self):
        result = extract_guidance(
            "Management expects FY 2026 adjusted revenue of $10 billion USD to $12 billion USD.",
            evidence())
        self.assertEqual(result["observations"], [])

    def test_reversed_range_fails_closed(self):
        result = extract_guidance(
            "Management expects FY 2026 revenue of $12 billion USD to $10 billion USD.", evidence())
        self.assertEqual(result["observations"], [])

    def test_conflicting_ranges_in_one_publication_are_removed(self):
        text = ("We expect FY 2026 revenue of $10 billion USD to $12 billion USD. "
                "We expect FY 2026 revenue of $9 billion USD to $11 billion USD.")
        result = extract_guidance(text, evidence())
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["observations"], [])


class ComparisonTests(unittest.TestCase):
    def test_range_change_uses_endpoints_not_an_inferred_midpoint(self):
        result = compare_guidance(guidance(11, 13), guidance(10, 12, "2026-04-01T20:05:00Z"))
        self.assertEqual(result["previous"]["change"], "raised")

    def test_currency_definition_and_period_must_all_match(self):
        for changed in (
            guidance(currency="EUR"),
            guidance(definition="adjusted revenue"),
            guidance(period={"type": "fiscal_year", "label": "FY 2027", "year": "2027"}),
        ):
            changed["publishedAt"] = "2026-04-01T20:05:00Z"
            result = compare_guidance(guidance(), changed)
            self.assertEqual(result["previous"]["status"], "not-comparable")

    def test_later_actual_and_consensus_compare_only_when_exactly_comparable(self):
        actual = guidance(value=12.5, publishedAt="2027-02-01T20:05:00Z")
        consensus = guidance(value=11.0, publishedAt="2026-04-30T20:05:00Z")
        result = compare_guidance(guidance(10, 12), actual=actual, consensus=consensus)
        self.assertEqual(result["actual"]["position"], "above")
        self.assertEqual(result["consensus"]["position"], "within")
        mismatch = guidance(value=11.0, currency="EUR", publishedAt="2026-04-30T20:05:00Z")
        self.assertEqual(compare_guidance(guidance(), consensus=mismatch)["consensus"]["status"], "not-comparable")

    def test_cutoff_excludes_future_publications_and_gates_never_change(self):
        view = build_guidance_view([
            guidance(10, 12, "2026-05-01T20:05:00Z"),
            guidance(12, 14, "2026-08-01T20:05:00Z"),
        ], cutoff="2026-06-01T00:00:00Z")
        self.assertEqual(view["entries"][0]["latest"]["low"], 10)
        self.assertEqual(view["ratingImpact"], "none")
        self.assertIn("never overrides", view["gatePolicy"])

    def test_conflict_across_filing_documents_fails_closed(self):
        view = build_guidance_view([guidance(10, 12), guidance(9, 11)])
        self.assertEqual(view["status"], "conflict")
        self.assertEqual(view["entries"], [])

    def test_identical_filing_cover_and_exhibit_are_deduplicated(self):
        view = build_guidance_view([guidance(10, 12), guidance(10, 12)])
        self.assertEqual(len(view["entries"]), 1)
        self.assertIsNone(view["entries"][0]["comparisons"]["previous"])


class SecCollectionTests(unittest.TestCase):
    def setUp(self):
        self.old_identity = company_guidance.sec_identity
        self.old_bytes = company_guidance.sec_bytes
        company_guidance.sec_identity = lambda symbol: {
            "status": "verified", "symbol": symbol, "name": "Acme", "cik": "0000000001"}
        self.addCleanup(setattr, company_guidance, "sec_identity", self.old_identity)
        self.addCleanup(setattr, company_guidance, "sec_bytes", self.old_bytes)

    def test_sec_acceptance_time_is_the_cutoff(self):
        submissions = b'{"filings":{"recent":{"form":["8-K"],"items":["2.02,9.01"],"acceptanceDateTime":["2026-05-01T20:05:00Z"],"accessionNumber":["0001-26-000001"],"primaryDocument":["release.htm"]}}}'
        release = b'<p>Management expects FY 2026 revenue of $10 billion USD to $12 billion USD.</p>'
        company_guidance.sec_bytes = lambda url, accept="application/json": submissions if "submissions" in url else release
        hidden = company_guidance.sec_guidance_evidence("ACME", cutoff="2026-05-01T20:00:00Z")
        visible = company_guidance.sec_guidance_evidence("ACME", cutoff="2026-05-01T20:06:00Z")
        self.assertEqual(hidden["observations"], [])
        self.assertEqual(visible["observations"][0]["publishedAt"], "2026-05-01T20:05:00Z")

    def test_invalid_cutoff_fails_closed(self):
        with self.assertRaises(ValueError):
            company_guidance.sec_guidance_evidence("ACME", cutoff="2026-05-01")


if __name__ == "__main__":
    unittest.main()
