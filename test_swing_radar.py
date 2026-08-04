"""Guarantees for the computed weekly move list."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import swing_radar
from swing_radar import (
    JUMP_THRESHOLD,
    RadarArchive,
    _volatility_bucket,
    build_candidates,
    freeze_weekly_list,
)
from test_outcome_source import _write


def _archive(database: Path, securities, sessions: int = 300) -> None:
    """Build sessions where the per-security daily move is fixed and known."""
    rows = []
    day = dt.date(2025, 1, 1)
    dates = []
    while len(dates) < sessions:
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += dt.timedelta(days=1)
    spy = 100.0
    for date in dates:
        rows.append((date, "SPY", spy, spy, True))
    for ticker, step in securities.items():
        price = 50.0
        for index, date in enumerate(dates):
            price *= (1 + step) if index % 2 == 0 else (1 - step * 0.5)
            rows.append((date, ticker, price, spy, True))
    _write(database, rows)
    connection = sqlite3.connect(str(database))
    connection.execute(
        "UPDATE swing_observations SET median_dollar_volume_20d=50000000, security_type='common_stock'"
        " WHERE ticker!='SPY'")
    connection.execute("UPDATE swing_observations SET security_type='common_stock' WHERE ticker='SPY'")
    connection.commit()
    connection.close()


class RadarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"

    def test_volatility_bands_are_ordered(self) -> None:
        self.assertEqual(_volatility_bucket(0.2), "calm")
        self.assertEqual(_volatility_bucket(0.45), "normal")
        self.assertEqual(_volatility_bucket(0.8), "lively")
        self.assertEqual(_volatility_bucket(1.5), "wild")
        self.assertEqual(_volatility_bucket(None), "unknown")

    def test_a_jumpy_security_outranks_a_calm_one(self) -> None:
        _archive(self.database, {"WILD": 0.06, "CALM": 0.001})
        result = build_candidates(self.database, today=dt.date(2026, 1, 5))
        self.assertEqual(result["status"], "ready")
        symbols = [row["symbol"] for row in result["candidates"]]
        self.assertEqual(symbols[0], "WILD")
        chances = {row["symbol"]: row["jumpChance10"] for row in result["candidates"]}
        self.assertGreater(chances["WILD"], chances.get("CALM", 0))

    def test_the_chance_is_a_probability(self) -> None:
        _archive(self.database, {"WILD": 0.06, "CALM": 0.001})
        for row in build_candidates(self.database, today=dt.date(2026, 1, 5))["candidates"]:
            self.assertGreaterEqual(row["jumpChance10"], 0.0)
            self.assertLessEqual(row["jumpChance10"], 1.0)

    def test_every_candidate_shows_the_evidence_behind_its_number(self) -> None:
        _archive(self.database, {"WILD": 0.06, "CALM": 0.001})
        for row in build_candidates(self.database, today=dt.date(2026, 1, 5))["candidates"]:
            self.assertIn("cohortSessions", row["cohort"])
            self.assertIn("sessions", row["ownRecord"])
            self.assertIsNotNone(row["volatilityBand"])
            self.assertIn("asOf", row)

    def test_funds_are_excluded_by_the_investability_policy(self) -> None:
        _archive(self.database, {"WILD": 0.06, "LEVERAGED": 0.09})
        connection = sqlite3.connect(str(self.database))
        connection.execute("UPDATE swing_observations SET security_type=NULL WHERE ticker='LEVERAGED'")
        connection.commit()
        connection.close()
        archive = RadarArchive(self.database).load()
        self.assertIn("WILD", archive.series)
        self.assertNotIn("LEVERAGED", archive.series)

    def test_no_direction_is_ever_stated(self) -> None:
        _archive(self.database, {"WILD": 0.06})
        result = build_candidates(self.database, today=dt.date(2026, 1, 5))
        self.assertIn("No direction is stated", result["directionPolicy"])
        for row in result["candidates"]:
            self.assertNotIn("direction", row)

    def test_the_headline_is_described_as_a_measured_rate(self) -> None:
        _archive(self.database, {"WILD": 0.06})
        result = build_candidates(self.database, today=dt.date(2026, 1, 5))
        self.assertIn("not a prediction", result["chanceMethod"])
        self.assertIn(str(int(JUMP_THRESHOLD * 100)), result["target"])

    def test_an_empty_archive_says_so(self) -> None:
        result = build_candidates(Path(self.directory.name) / "absent.sqlite3")
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["candidates"], [])


class FreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"
        self.path = Path(self.directory.name) / "watchlist.json"
        _archive(self.database, {"WILD": 0.06, "CALM": 0.001})

    def test_a_frozen_week_is_never_rewritten(self) -> None:
        first = freeze_weekly_list(self.path, self.database, today=dt.date(2026, 1, 5))
        self.assertEqual(first["weekEnding"], "2026-01-09")
        original = json.loads(self.path.read_text())

        again = freeze_weekly_list(self.path, self.database, today=dt.date(2026, 1, 7))
        self.assertEqual(again["status"], "already-frozen")
        self.assertEqual(json.loads(self.path.read_text()), original)

    def test_a_new_week_produces_a_new_list(self) -> None:
        freeze_weekly_list(self.path, self.database, today=dt.date(2026, 1, 5))
        later = freeze_weekly_list(self.path, self.database, today=dt.date(2026, 1, 12))
        self.assertEqual(later["weekEnding"], "2026-01-16")
        self.assertNotEqual(later.get("status"), "already-frozen")

    def test_candidates_are_ranked(self) -> None:
        result = freeze_weekly_list(self.path, self.database, today=dt.date(2026, 1, 5))
        ranks = [row["rank"] for row in result["candidates"]]
        self.assertEqual(ranks, list(range(1, len(ranks) + 1)))


if __name__ == "__main__":
    unittest.main()
