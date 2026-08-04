"""Guarantees for the earnings calendar.

The network is never touched: SEC responses are stubbed so these tests assert
behaviour, not connectivity.
"""

from __future__ import annotations

import datetime as dt
import unittest

import earnings_calendar
from earnings_calendar import confirmed_announcements, earnings_context, next_expected


def _submissions(rows):
    """Build a submissions payload in the shape EDGAR returns."""
    return {"filings": {"recent": {
        "form": [row[0] for row in rows],
        "items": [row[1] for row in rows],
        "filingDate": [row[2] for row in rows],
        "acceptanceDateTime": [row[3] for row in rows],
        "reportDate": [row[4] for row in rows],
        "accessionNumber": [f"0001-{index:04d}" for index, _ in enumerate(rows)],
    }}}


QUARTERLY = [
    ("8-K", "2.02,9.01", "2026-05-06", "2026-05-06T20:07:59.000Z", "2026-03-31"),
    ("8-K", "5.07", "2026-04-07", "2026-04-07T12:00:00.000Z", "2026-04-07"),
    ("8-K", "2.02,9.01", "2026-02-11", "2026-02-11T21:07:25.000Z", "2025-12-31"),
    ("8-K", "2.02,9.01", "2025-11-05", "2025-11-05T21:07:48.000Z", "2025-09-30"),
    ("8-K", "2.02,9.01", "2025-08-06", "2025-08-06T20:08:54.000Z", "2025-06-30"),
    ("10-Q", "", "2025-08-06", "2025-08-06T20:30:00.000Z", "2025-06-30"),
]


class EarningsCalendarTests(unittest.TestCase):
    def setUp(self) -> None:
        original_identity = earnings_calendar.sec_identity
        original_json = earnings_calendar._sec_json
        earnings_calendar.sec_identity = lambda symbol: {
            "status": "verified", "symbol": symbol.upper(),
            "name": "Test Corp", "cik": "0001751008",
        }
        earnings_calendar._sec_json = lambda url: _submissions(QUARTERLY)
        self.addCleanup(setattr, earnings_calendar, "sec_identity", original_identity)
        self.addCleanup(setattr, earnings_calendar, "_sec_json", original_json)

    def test_only_results_filings_are_treated_as_earnings(self) -> None:
        result = confirmed_announcements("APP")
        self.assertEqual(result["status"], "verified")
        dates = [entry["announcedOn"] for entry in result["announcements"]]
        self.assertEqual(dates, ["2026-05-06", "2026-02-11", "2025-11-05", "2025-08-06"])
        # The shareholder-vote 8-K and the 10-Q must not be counted.
        self.assertNotIn("2026-04-07", dates)

    def test_an_after_close_filing_reacts_the_next_session(self) -> None:
        first = confirmed_announcements("APP")["announcements"][0]
        self.assertTrue(first["afterMarketClose"])
        self.assertEqual(first["announcedOn"], "2026-05-06")
        self.assertEqual(first["marketReactionDate"], "2026-05-07")

    def test_a_reaction_date_never_lands_on_a_weekend(self) -> None:
        rows = [("8-K", "2.02", "2026-05-08", "2026-05-08T21:00:00.000Z", "2026-03-31")] + QUARTERLY[1:]
        earnings_calendar._sec_json = lambda url: _submissions(rows)
        first = confirmed_announcements("APP")["announcements"][0]
        reaction = dt.date.fromisoformat(first["marketReactionDate"])
        self.assertLess(reaction.weekday(), 5)
        self.assertEqual(first["marketReactionDate"], "2026-05-11")

    def test_every_announcement_carries_a_verifiable_source(self) -> None:
        for entry in confirmed_announcements("APP")["announcements"]:
            self.assertIn("sec.gov", entry["sourceUrl"])
            self.assertTrue(entry["accession"])

    def test_projection_is_a_window_not_a_diary_entry(self) -> None:
        result = next_expected("APP", today=dt.date(2026, 8, 4))
        self.assertEqual(result["status"], "projected")
        projection = result["projection"]
        self.assertEqual(projection["expectedDate"], "2026-08-05")
        self.assertLess(projection["windowStart"], projection["expectedDate"])
        self.assertGreater(projection["windowEnd"], projection["expectedDate"])
        self.assertTrue(projection["windowIsOpen"])
        self.assertIn("window rather than a diary entry", result["confidence"])

    def test_projection_never_claims_to_know_the_result(self) -> None:
        result = next_expected("APP", today=dt.date(2026, 8, 4))
        self.assertIn("nothing about the result or its direction", result["limitation"])
        combined = " ".join(str(value) for value in result.values()).lower()
        for word in ("buy", "sell", "expect a rise", "will beat"):
            self.assertNotIn(word, combined)

    def test_an_extra_filing_inside_a_quarter_does_not_open_the_window_early(self) -> None:
        """A guidance 8-K days after results must not become the cadence."""
        rows = [
            ("8-K", "2.02", "2026-07-24", "2026-07-24T20:00:00.000Z", "2026-06-30"),
            ("8-K", "2.02", "2026-07-14", "2026-07-14T20:00:00.000Z", "2026-06-30"),
            ("8-K", "2.02", "2026-04-24", "2026-04-24T20:00:00.000Z", "2026-03-31"),
            ("8-K", "2.02", "2026-01-23", "2026-01-23T20:00:00.000Z", "2025-12-31"),
            ("8-K", "2.02", "2025-10-24", "2025-10-24T20:00:00.000Z", "2025-09-30"),
            ("8-K", "2.02", "2025-07-25", "2025-07-25T20:00:00.000Z", "2025-06-30"),
        ]
        earnings_calendar._sec_json = lambda url: _submissions(rows)
        result = next_expected("HCA", today=dt.date(2026, 8, 4))
        self.assertEqual(result["status"], "projected")
        window = result["projection"]
        # Roughly a quarter after 24 July, not ten days after it.
        self.assertGreater(window["expectedDate"], "2026-10-01")
        self.assertFalse(window["windowIsOpen"])

    def test_an_irregular_filer_is_refused_rather_than_guessed(self) -> None:
        rows = [
            ("8-K", "2.02", date, f"{date}T20:00:00.000Z", date)
            for date in ("2026-05-14", "2026-05-12", "2026-04-28", "2026-03-09",
                         "2026-01-16", "2025-11-12", "2025-09-09")
        ]
        earnings_calendar._sec_json = lambda url: _submissions(rows)
        result = next_expected("ONDS", today=dt.date(2026, 8, 4))
        self.assertEqual(result["status"], "irregular-cadence")
        self.assertIsNone(result["projection"])

    def test_a_passed_window_is_reported_as_overdue(self) -> None:
        result = next_expected("APP", today=dt.date(2026, 9, 30))
        self.assertTrue(result["projection"]["overdue"])
        context = earnings_context("APP", today=dt.date(2026, 9, 30))
        self.assertEqual(context["flag"], "overdue")

    def test_window_width_is_labelled_so_a_vague_date_looks_vague(self) -> None:
        result = next_expected("APP", today=dt.date(2026, 8, 4))
        window = result["projection"]
        self.assertIn(window["precision"], {"firm", "approximate", "wide"})
        self.assertLessEqual(window["windowHalfWidthDays"],
                             earnings_calendar.MAX_WINDOW_HALF_WIDTH_DAYS)

    def test_too_little_history_refuses_to_project(self) -> None:
        earnings_calendar._sec_json = lambda url: _submissions(QUARTERLY[:1])
        result = next_expected("APP", today=dt.date(2026, 8, 4))
        self.assertEqual(result["status"], "insufficient-history")
        self.assertIsNone(result["projection"])

    def test_context_flags_an_open_window(self) -> None:
        context = earnings_context("APP", today=dt.date(2026, 8, 4))
        self.assertEqual(context["flag"], "window-open")
        self.assertIn("unknowable outcome", context["plainEnglish"])

    def test_context_is_clear_when_results_are_far_away(self) -> None:
        context = earnings_context("APP", today=dt.date(2026, 6, 1))
        self.assertEqual(context["flag"], "clear")

    def test_an_unknown_ticker_reports_unavailable(self) -> None:
        earnings_calendar.sec_identity = lambda symbol: {"status": "unavailable"}
        result = earnings_context("NOPE", today=dt.date(2026, 8, 4))
        self.assertEqual(result["flag"], "unknown")
        self.assertEqual(result["announcements"], [])


if __name__ == "__main__":
    unittest.main()
