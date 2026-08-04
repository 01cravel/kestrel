"""Guarantees for the results-window event study."""

from __future__ import annotations

import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

from event_study import (
    ROUND_TRIP_COST_PERCENT,
    collect_events,
    run_study,
    window_results,
)
from test_outcome_source import _write


def _archive(database: Path, announcements, sessions: int = 260, drift: float = 0.0) -> None:
    """Flat prices apart from a fixed drift, so expected returns are known."""
    day = dt.date(2025, 1, 1)
    dates = []
    while len(dates) < sessions:
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += dt.timedelta(days=1)
    rows = []
    for date in dates:
        rows.append((date, "SPY", 100.0, 100.0, True))
    for ticker in {ticker for ticker, _ in announcements}:
        price = 50.0
        for date in dates:
            rows.append((date, ticker, price, 100.0, True))
            price *= 1 + drift
    _write(database, rows)

    connection = sqlite3.connect(str(database))
    connection.execute("UPDATE swing_observations SET security_type='common_stock'")
    for ticker, announced in announcements:
        connection.execute(
            """INSERT OR REPLACE INTO issuer_events VALUES
               (?, '1', 'results', ?, ?, ?, NULL, '2.02', ?, 'test', ?)""",
            (ticker, announced, announced + "T20:00:00Z", announced + "T20:00:00Z",
             "acc-" + ticker + announced, "2026-01-01T00:00:00Z"),
        )
    connection.commit()
    connection.close()
    return dates


class EventCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"

    def test_the_reaction_is_the_session_after_the_filing(self) -> None:
        dates = _archive(self.database, [("AAA", "2025-03-05")])
        events = collect_events(self.database)
        self.assertEqual(len(events), 1)
        self.assertGreater(events[0]["reactionDate"], "2025-03-05")
        self.assertEqual(events[0]["reactionDate"], min(d for d in dates if d > "2025-03-05"))

    def test_an_announcement_before_the_archive_is_discarded(self) -> None:
        """Otherwise it collapses onto the first session and is measured there."""
        _archive(self.database, [("AAA", "2023-05-23"), ("AAA", "2025-03-05")])
        events = collect_events(self.database)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["announcedOn"], "2025-03-05")
        self.assertGreater(events[0]["reactionIndex"], 0)

    def test_no_archive_returns_nothing(self) -> None:
        self.assertEqual(collect_events(Path(self.directory.name) / "absent.sqlite3"), [])


class WindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"

    def _events(self, drift: float) -> list:
        announcements = [
            (f"T{index:02d}", date)
            for index in range(45)
            for date in ("2025-03-05", "2025-06-05", "2025-09-04")
        ]
        _archive(self.database, announcements, drift=drift)
        return collect_events(self.database)

    def test_a_known_drift_is_recovered(self) -> None:
        events = self._events(drift=0.01)  # 1% per session against a flat benchmark
        result = window_results(events, -1, 1)
        self.assertTrue(result["sufficient"])
        # Two sessions of compounding at 1%.
        self.assertAlmostEqual(result["meanExcess"], 2.01, places=1)
        self.assertEqual(result["winRate"], 1.0)

    def test_a_flat_market_shows_no_edge(self) -> None:
        result = window_results(self._events(drift=0.0), -1, 1)
        self.assertAlmostEqual(result["meanExcess"], 0.0, places=6)
        self.assertFalse(result["beatsCosts"])

    def test_a_thin_window_is_marked_insufficient(self) -> None:
        _archive(self.database, [("AAA", "2025-03-05")])
        result = window_results(collect_events(self.database), -1, 1)
        self.assertFalse(result["sufficient"])
        self.assertNotIn("meanExcess", result)

    def test_windows_spanning_the_announcement_are_flagged(self) -> None:
        events = self._events(drift=0.0)
        self.assertTrue(window_results(events, -1, 1)["holdsThroughAnnouncement"])
        self.assertFalse(window_results(events, 0, 5)["holdsThroughAnnouncement"])

    def test_costs_must_be_cleared_not_merely_beaten_by_the_average(self) -> None:
        # A drift small enough that the average is positive but under costs.
        events = self._events(drift=0.0004)
        result = window_results(events, -1, 0)
        self.assertGreater(result["meanExcess"], 0)
        self.assertLess(result["meanExcess"], ROUND_TRIP_COST_PERCENT)
        self.assertFalse(result["beatsCosts"])


class StudyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"

    def test_the_study_reports_how_many_windows_it_tried(self) -> None:
        announcements = [
            (f"T{index:02d}", date) for index in range(45)
            for date in ("2025-03-05", "2025-06-05", "2025-09-04")
        ]
        _archive(self.database, announcements)
        result = run_study(self.database)
        self.assertEqual(result["status"], "ready")
        self.assertGreater(result["windowsTested"], 1)
        self.assertIn("expected to look good by chance", result["multipleComparisons"])
        self.assertIn("no slippage", result["limitation"])

    def test_an_empty_archive_says_so(self) -> None:
        result = run_study(Path(self.directory.name) / "absent.sqlite3")
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["windows"], [])


if __name__ == "__main__":
    unittest.main()
