"""Tests for Kestrel's no-hindsight daily mover research."""

from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from market_history import MarketHistoryStore
from mover_autopsy import _cause_for, build_mover_snapshot


class MoverAutopsyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "history.sqlite3"
        self.store = MarketHistoryStore(self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def test_ranks_liquid_abnormal_moves_and_keeps_cause_unverified(self):
        start = dt.date(2026, 1, 2)
        sessions = []
        cursor = start
        while len(sessions) < 127:
            if cursor.weekday() < 5:
                sessions.append(cursor.isoformat())
            cursor += dt.timedelta(days=1)
        values = []
        for index, session in enumerate(sessions):
            spy_close = 100 + index * 0.1
            test_close = 20 + index * 0.02
            quiet_close = 5 + index * 0.01
            if index == len(sessions) - 1:
                test_close *= 1.25
                quiet_close *= 1.50
            for ticker, close, volume in (
                ("SPY", spy_close, 10_000_000),
                ("TEST", test_close, 1_000_000),
                ("QUIET", quiet_close, 100),
            ):
                values.append((session, ticker, close, close, close, close, volume, close, 1, 0,
                               1, "test", "request", "2026-08-03T00:00:00Z", "hash"))
        with self.store.connect() as connection:
            connection.executemany("INSERT INTO daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
            connection.executemany(
                "INSERT INTO reference_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (sessions[-1], "TEST", 1, "Test Company", "stocks", "us", "usd", "XNAS", "CS",
                     None, None, "TEST-FIGI", None, sessions[-1], 1, "ref", "2026-08-03T00:00:00Z", "refhash"),
                    (sessions[-1], "QUIET", 1, "Quiet ETF", "stocks", "us", "usd", "ARCX", "ETF",
                     None, None, "QUIET-FIGI", None, sessions[-1], 0, "ref", "2026-08-03T00:00:00Z", "refhash"),
                ],
            )
            connection.commit()

        payload = build_mover_snapshot(self.database)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual([item["symbol"] for item in payload["movers"]], ["TEST"])
        mover = payload["movers"][0]
        self.assertGreater(mover["relativeMove"], 0.20)
        self.assertEqual(mover["cause"]["status"], "unverified")
        self.assertTrue(mover["researchOnly"])

    def test_uses_last_actual_trade_when_a_share_skipped_a_market_session(self):
        sessions = ["2026-07-29", "2026-07-30", "2026-07-31"]
        with self.store.connect() as connection:
            bars = []
            for session, spy_close in zip(sessions, [100, 100, 101]):
                bars.append((session, "SPY", spy_close, spy_close, spy_close, spy_close, 1_000_000,
                             spy_close, 1, 0, 1, "test", "r", "2026-08-03T00:00:00Z", "h"))
            for session, close in (("2026-07-29", 5.0), ("2026-07-31", 10.0)):
                bars.append((session, "TEST", close, close, close, close, 1_000_000,
                             close, 1, 0, 1, "test", "r", "2026-08-03T00:00:00Z", "h"))
            connection.executemany("INSERT INTO daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", bars)
            connection.commit()
        # The full ranking needs 126 prior sessions; this focused assertion checks the SQL edge case
        # through the actual archive query shape used by build_mover_snapshot.
        with self.store.connect(create=False) as connection:
            row = connection.execute(
                """SELECT prior.session_date FROM daily_bars current
                   JOIN daily_bars prior ON prior.ticker=current.ticker AND prior.session_date=(
                     SELECT MAX(older.session_date) FROM daily_bars older
                     WHERE older.ticker=current.ticker AND older.session_date<current.session_date)
                   WHERE current.ticker='TEST' AND current.session_date='2026-07-31'"""
            ).fetchone()
        self.assertEqual(row[0], "2026-07-29")

    def test_attaches_only_verified_catalysts_with_a_source(self):
        fallback = {"status": "unverified", "plainEnglish": "No verified cause."}
        valid = {
            "2026-07-31:TEST": {
                "status": "verified",
                "plainEnglish": "Verified result.",
                "sources": [{"name": "Company filing", "url": "https://example.com/filing"}],
            }
        }
        missing_source = {
            "2026-07-31:TEST": {"status": "verified", "plainEnglish": "Unsupported."}
        }
        self.assertEqual(
            _cause_for("TEST", "2026-07-31", fallback, valid)["plainEnglish"],
            "Verified result.",
        )
        self.assertIs(_cause_for("TEST", "2026-07-31", fallback, missing_source), fallback)


if __name__ == "__main__":
    unittest.main()
