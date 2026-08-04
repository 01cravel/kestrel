"""Guarantees for the append-only signal journal."""

from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import signal_history
from outcome_source import OutcomeSource
from test_outcome_source import _sessions, _write


class SignalJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.database = root / "market-history.sqlite3"

        original_path = signal_history.HISTORY_PATH
        signal_history.HISTORY_PATH = root / "signal-history.json"
        self.addCleanup(setattr, signal_history, "HISTORY_PATH", original_path)

        original_source = signal_history.shared_source
        signal_history.shared_source = lambda: OutcomeSource(self.database)
        self.addCleanup(setattr, signal_history, "shared_source", original_source)

    @staticmethod
    def _signal(symbol: str = "TEST", action: str = "Buy") -> dict:
        return {"symbol": symbol, "action": action, "confidence": "High", "price": 100, "score": 80}

    def test_a_prediction_is_never_rewritten(self) -> None:
        first = signal_history.record_signals([self._signal()], "2026-08-04T12:00:00Z")
        self.assertEqual(first["predictionsAppended"], 1)
        second = signal_history.record_signals(
            [{**self._signal(), "action": "Sell", "price": 999}], "2026-08-04T18:00:00Z"
        )
        self.assertEqual(second["predictionsAppended"], 0)
        self.assertEqual(second["duplicatesRefused"], 1)

        stored = signal_history._load()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["action"], "Buy")
        self.assertEqual(stored[0]["price"], 100)

    def test_old_predictions_are_not_pruned(self) -> None:
        ancient = {
            "date": "2009-01-02", "symbol": "TEST", "action": "Buy", "confidence": "High",
            "price": 10, "modelVersion": "2009.1",
        }
        signal_history._save([ancient])
        signal_history.record_signals([self._signal()], "2026-08-04T12:00:00Z")
        dates = {row["date"] for row in signal_history._load()}
        self.assertIn("2009-01-02", dates)

    def test_no_archive_means_no_hit_rate(self) -> None:
        summary = signal_history.record_signals([self._signal()], "2026-08-04T12:00:00Z")
        self.assertEqual(summary["maturedSignals"], 0)
        self.assertIsNone(summary["hitRate"])
        self.assertEqual(summary["outcomeSource"]["status"], "empty")
        self.assertIn("archive is empty", summary["limitations"])

    def test_outcomes_come_from_the_archive_and_beat_the_benchmark(self) -> None:
        _write(self.database, _sessions(dt.date(2026, 1, 5), 60, stock_step=1.0, spy_step=0.2))
        signal_history._save([{
            "date": "2026-01-05", "symbol": "TEST", "action": "Buy", "confidence": "High",
            "price": 100, "modelVersion": signal_history.MODEL_VERSION,
        }])
        summary = signal_history.calibration_summary()
        self.assertEqual(summary["maturedSignals"], 1)
        self.assertEqual(summary["hitRate"], 100.0)
        self.assertGreater(summary["averageExcessReturn"], 0)
        self.assertEqual(summary["outcomeSource"]["status"], "ready")

    def test_a_rise_that_lags_the_benchmark_is_not_a_hit(self) -> None:
        _write(self.database, _sessions(dt.date(2026, 1, 5), 60, stock_step=0.2, spy_step=1.0))
        signal_history._save([{
            "date": "2026-01-05", "symbol": "TEST", "action": "Buy", "confidence": "High",
            "price": 100, "modelVersion": signal_history.MODEL_VERSION,
        }])
        summary = signal_history.calibration_summary()
        self.assertEqual(summary["maturedSignals"], 1)
        self.assertEqual(summary["hitRate"], 0.0)
        self.assertLess(summary["averageExcessReturn"], 0)

    def test_longer_horizons_are_reported_separately(self) -> None:
        _write(self.database, _sessions(dt.date(2026, 1, 5), 60, stock_step=1.0, spy_step=0.2))
        signal_history._save([{
            "date": "2026-01-05", "symbol": "TEST", "action": "Buy", "confidence": "High",
            "price": 100, "modelVersion": signal_history.MODEL_VERSION,
        }])
        summary = signal_history.calibration_summary()
        self.assertEqual(summary["horizons"]["30"]["maturedSignals"], 1)
        self.assertEqual(summary["horizons"]["180"]["maturedSignals"], 0)
        self.assertEqual(summary["horizons"]["180"]["awaitingOutcome"], 1)


if __name__ == "__main__":
    unittest.main()
