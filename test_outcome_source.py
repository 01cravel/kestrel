"""Guarantees for independently graded outcomes."""

from __future__ import annotations

import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_history import MarketHistoryStore
from outcome_source import STATUS_MATURED, STATUS_PENDING, STATUS_UNAVAILABLE, OutcomeSource, verdict
from swing_radar_policy import POLICY_VERSION


def _write(database: Path, rows) -> None:
    """Insert only the columns the outcome reader depends on."""
    store = MarketHistoryStore(database)
    with store.connect() as connection:
        for session_date, ticker, close, spy_close, clean in rows:
            connection.execute(
                """INSERT OR REPLACE INTO swing_observations
                   (security_id, session_date, cutoff_utc, ticker, policy_version,
                    corporate_actions_clean, adjusted_close, spy_adjusted_close,
                    split_flag, dividend_flag, eligibility_status, eligibility_json,
                    source_retrieved_at, raw_sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'eligible', '{}', ?, ?)""",
                (f"ticker:{ticker}", session_date, session_date + "T20:15:00Z", ticker,
                 POLICY_VERSION, int(clean), close, spy_close, session_date, "hash"),
            )
        connection.commit()


def _sessions(start: dt.date, count: int, stock_step: float, spy_step: float, clean: bool = True):
    rows = []
    stock, spy = 100.0, 100.0
    session = start
    for _ in range(count):
        while session.weekday() >= 5:
            session += dt.timedelta(days=1)
        rows.append((session.isoformat(), "TEST", stock, spy, clean))
        rows.append((session.isoformat(), "SPY", spy, spy, True))
        stock += stock_step
        spy += spy_step
        session += dt.timedelta(days=1)
    return rows


class OutcomeSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"

    def test_missing_archive_never_invents_an_outcome(self) -> None:
        source = OutcomeSource(Path(self.directory.name) / "absent.sqlite3")
        self.assertEqual(source.coverage()["status"], "empty")
        self.assertEqual(source.outcome("TEST", "2026-01-05", 30)["status"], STATUS_UNAVAILABLE)

    def test_outcome_is_benchmark_relative_and_entered_after_the_decision(self) -> None:
        _write(self.database, _sessions(dt.date(2026, 1, 5), 60, stock_step=1.0, spy_step=0.2))
        source = OutcomeSource(self.database)
        outcome = source.outcome("TEST", "2026-01-05", 30)
        self.assertEqual(outcome["status"], STATUS_MATURED)
        # Entry is the session after the decision, so never the decision price.
        self.assertGreater(outcome["entryDate"], "2026-01-05")
        self.assertGreater(outcome["exitDate"], "2026-02-03")
        self.assertGreater(outcome["stockReturn"], outcome["benchmarkReturn"])
        self.assertAlmostEqual(
            outcome["excessReturn"],
            round(outcome["stockReturn"] - outcome["benchmarkReturn"], 2),
            places=2,
        )
        self.assertEqual(outcome["verdict"], "outperformed")

    def test_unresolved_corporate_action_blocks_the_grade(self) -> None:
        rows = _sessions(dt.date(2026, 1, 5), 60, stock_step=1.0, spy_step=0.2)
        rows = [
            (date, ticker, close, spy, False if ticker == "TEST" and date == "2026-01-20" else clean)
            for date, ticker, close, spy, clean in rows
        ]
        _write(self.database, rows)
        outcome = OutcomeSource(self.database).outcome("TEST", "2026-01-05", 30)
        self.assertEqual(outcome["status"], STATUS_UNAVAILABLE)
        self.assertIn("corporate action", outcome["reason"])

    def test_short_archive_reports_pending_not_a_result(self) -> None:
        _write(self.database, _sessions(dt.date(2026, 1, 5), 10, stock_step=1.0, spy_step=0.2))
        outcome = OutcomeSource(self.database).outcome("TEST", "2026-01-05", 30)
        self.assertEqual(outcome["status"], STATUS_PENDING)

    def test_drawdown_uses_the_whole_path_not_the_endpoints(self) -> None:
        rows = _sessions(dt.date(2026, 1, 5), 60, stock_step=1.0, spy_step=0.0)
        dipped = []
        for date, ticker, close, spy, clean in rows:
            if ticker == "TEST" and date == "2026-01-15":
                close = 50.0
            dipped.append((date, ticker, close, spy, clean))
        _write(self.database, dipped)
        outcome = OutcomeSource(self.database).outcome("TEST", "2026-01-05", 30)
        self.assertEqual(outcome["status"], STATUS_MATURED)
        self.assertLess(outcome["maxDrawdown"], -40)
        self.assertGreater(outcome["stockReturn"], 0)

    def test_cost_band_makes_a_tiny_edge_neutral(self) -> None:
        self.assertEqual(verdict(0.1), "neutral")
        self.assertEqual(verdict(-0.1), "neutral")
        self.assertEqual(verdict(4.0), "outperformed")
        self.assertEqual(verdict(-4.0), "underperformed")


if __name__ == "__main__":
    unittest.main()
