"""Tests for frozen Swing Radar watchlists."""

import json
import tempfile
import unittest
from pathlib import Path

from swing_watchlist import swing_watchlist_snapshot


class SwingWatchlistTests(unittest.TestCase):
    def test_reads_a_frozen_shadow_list_without_changing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watch.json"
            path.write_text(json.dumps({
                "status": "shadow",
                "frozenAt": "2026-08-03T17:09:00-04:00",
                "candidates": [{
                    "symbol": "TEST", "direction": "Unknown", "jumpChance10": 0.28,
                    "earningsEventsMeasured": 8, "earningsJumpsAbove10": 2,
                }],
            }), encoding="utf-8")
            payload = swing_watchlist_snapshot(path)
        self.assertEqual(payload["candidateCount"], 1)
        self.assertEqual(payload["candidates"][0]["direction"], "Unknown")
        self.assertEqual(payload["candidates"][0]["jumpChance10"], 0.28)

    def test_fails_closed_when_candidates_are_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watch.json"
            path.write_text('{"status":"shadow"}', encoding="utf-8")
            payload = swing_watchlist_snapshot(path)
        self.assertEqual(payload["status"], "invalid")
        self.assertEqual(payload["candidates"], [])

    def test_rejects_an_invalid_jump_percentage(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watch.json"
            path.write_text(json.dumps({
                "status": "shadow",
                "candidates": [{"symbol": "TEST", "jumpChance10": 1.2}],
            }), encoding="utf-8")
            payload = swing_watchlist_snapshot(path)
        self.assertEqual(payload["status"], "invalid")

    def test_rejects_an_invalid_setup_score(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "watch.json"
            path.write_text(json.dumps({
                "status": "shadow",
                "candidates": [{
                    "symbol": "TEST", "jumpChance10": 0.28,
                    "setupSignalsPassed": 6, "setupSignalsTotal": 5,
                }],
            }), encoding="utf-8")
            payload = swing_watchlist_snapshot(path)
        self.assertEqual(payload["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
