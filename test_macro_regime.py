from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from macro_regime import SERIES, build_macro_regime, macro_regime_snapshot


FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "fred_alfred_vintage.json").read_text(encoding="utf-8")
)


class MacroRegimeTests(unittest.TestCase):
    def test_fixture_builds_only_from_evidence_visible_at_cutoff(self):
        cutoff = dt.date.fromisoformat(FIXTURE["asOf"])
        result = build_macro_regime(cutoff, FIXTURE["observations"], FIXTURE["vintage_dates"])

        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["regime"]["label"], "downturn_risk")
        self.assertEqual(result["regime"]["inflation"], "elevated")
        self.assertEqual(result["regime"]["yieldCurve"], "inverted")
        self.assertEqual(result["derived"]["tenYearMinusTwoYear"], -0.5)
        self.assertEqual(result["evidence"]["CPIAUCSL"]["value"], 315.0)
        self.assertEqual(result["evidence"]["CPIAUCSL"]["latestSeriesVintageDate"], "2024-06-12")
        self.assertEqual(result["evidence"]["CPIAUCSL"]["requestedVintageDate"], "2024-06-30")
        self.assertEqual(result["ratingImpact"], "none")

    def test_missing_or_stale_required_evidence_fails_closed(self):
        cutoff = dt.date.fromisoformat(FIXTURE["asOf"])
        observations = dict(FIXTURE["observations"])
        observations["GDPC1"] = []
        missing = build_macro_regime(cutoff, observations, FIXTURE["vintage_dates"])
        self.assertFalse(missing["ready"])
        self.assertEqual(missing["regime"]["label"], "unavailable")
        self.assertIn("GDPC1", missing["missingSeries"])

        vintages = dict(FIXTURE["vintage_dates"])
        vintages["DGS10"] = ["2024-06-01"]
        stale = build_macro_regime(cutoff, FIXTURE["observations"], vintages)
        self.assertFalse(stale["ready"])
        self.assertEqual(stale["status"], "stale")
        self.assertIn("DGS10", stale["staleSeries"])

        gapped = dict(FIXTURE["observations"])
        gapped["CPIAUCSL"] = [
            row for row in FIXTURE["observations"]["CPIAUCSL"]
            if row["date"] != "2023-05-01"
        ]
        missing_period = build_macro_regime(cutoff, gapped, FIXTURE["vintage_dates"])
        self.assertFalse(missing_period["ready"])
        self.assertIn("headlineInflationYoY", missing_period["missingDerived"])

    def test_connector_uses_alfred_cutoff_and_reuses_immutable_cache(self):
        calls = []

        def downloader(url):
            calls.append(url)
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            series_id = query["series_id"][0]
            self.assertEqual(query.get("realtime_end"), [FIXTURE["asOf"]])
            if parsed.path.endswith("/series/observations"):
                self.assertEqual(query.get("realtime_start"), [FIXTURE["asOf"]])
                self.assertEqual(query.get("observation_end"), [FIXTURE["asOf"]])
                return {"observations": FIXTURE["observations"][series_id]}
            return {"vintage_dates": FIXTURE["vintage_dates"][series_id]}

        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "macro.json"
            result = macro_regime_snapshot(
                dt.date.fromisoformat(FIXTURE["asOf"]), api_key="x" * 32,
                cache_path=cache_path, downloader=downloader,
                now=dt.datetime(2024, 7, 1, tzinfo=dt.timezone.utc),
            )
            self.assertTrue(result["ready"])
            self.assertEqual(len(calls), len(SERIES) * 2)
            saved = cache_path.read_text(encoding="utf-8")
            self.assertNotIn("x" * 32, saved)

            cached = macro_regime_snapshot(
                dt.date.fromisoformat(FIXTURE["asOf"]), api_key="x" * 32,
                cache_path=cache_path,
                downloader=lambda _url: self.fail("immutable historical cache should be reused"),
                now=dt.datetime(2024, 8, 1, tzinfo=dt.timezone.utc),
            )
            self.assertTrue(cached["ready"])
            self.assertTrue(cached["cache"]["hit"])

    def test_no_key_and_future_cutoff_are_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_key = macro_regime_snapshot(
                dt.date(2024, 6, 30), api_key="", cache_path=Path(directory) / "macro.json",
                now=dt.datetime(2024, 7, 1, tzinfo=dt.timezone.utc),
            )
            self.assertFalse(missing_key["ready"])
            self.assertFalse(missing_key["keyConfigured"])
            self.assertIn("FRED_API_KEY", missing_key["errors"][0])

            future = macro_regime_snapshot(
                dt.date(2024, 7, 2), api_key="x" * 32, cache_path=Path(directory) / "macro.json",
                now=dt.datetime(2024, 7, 1, tzinfo=dt.timezone.utc),
            )
            self.assertFalse(future["ready"])
            self.assertIn("future", future["errors"][0].lower())

    def test_failed_refresh_retains_but_disables_an_expired_cache(self):
        def downloader(url):
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            series_id = query["series_id"][0]
            if parsed.path.endswith("/series/observations"):
                return {"observations": FIXTURE["observations"][series_id]}
            return {"vintage_dates": FIXTURE["vintage_dates"][series_id]}

        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "macro.json"
            cutoff = dt.date.fromisoformat(FIXTURE["asOf"])
            original = macro_regime_snapshot(
                cutoff, api_key="x" * 32, cache_path=cache_path, downloader=downloader,
                now=dt.datetime(2024, 6, 30, 8, tzinfo=dt.timezone.utc),
            )
            self.assertTrue(original["ready"])

            expired = macro_regime_snapshot(
                cutoff, api_key="x" * 32, cache_path=cache_path,
                downloader=lambda _url: (_ for _ in ()).throw(RuntimeError("offline")),
                now=dt.datetime(2024, 7, 1, tzinfo=dt.timezone.utc),
            )
            self.assertFalse(expired["ready"])
            self.assertEqual(expired["status"], "stale")
            self.assertEqual(expired["regime"]["label"], "unavailable")
            self.assertTrue(expired["cache"]["stale"])
            self.assertIn("refresh failed", expired["errors"][-1].lower())

            unconfigured = macro_regime_snapshot(
                cutoff, api_key="", cache_path=cache_path,
                now=dt.datetime(2024, 7, 1, tzinfo=dt.timezone.utc),
            )
            self.assertFalse(unconfigured["keyConfigured"])
            self.assertFalse(unconfigured["ready"])
            self.assertTrue(unconfigured["cache"]["stale"])


if __name__ == "__main__":
    unittest.main()
