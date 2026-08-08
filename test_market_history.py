"""Tests for the private, market-wide Massive history archive."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from market_history import (
    MarketHistoryPipeline, MarketHistoryStore, MassiveClient, MassiveError,
    default_range, latest_completed_market_date, plan,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if not self.responses:
            raise AssertionError("unexpected request")
        payload = self.responses.pop(0)
        body = json.dumps(payload, sort_keys=True).encode()
        return payload, body, 200


class MarketHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "private" / "history.sqlite3"
        self.store = MarketHistoryStore(self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def test_dry_run_needs_no_key_or_database_write(self):
        result = plan(dt.date(2026, 7, 6), dt.date(2026, 7, 10), self.store)
        self.assertEqual(result["groupedDailyRequestsRemaining"], 15)
        self.assertEqual(result["labelTailThrough"], "2026-07-24")
        self.assertFalse(self.database.exists())

    def test_default_range_stays_inside_free_two_year_boundary(self):
        start, end = default_range(dt.date(2026, 8, 2))
        self.assertEqual(start, dt.date(2024, 8, 2))
        self.assertEqual(end, dt.date(2026, 7, 19))

    def test_latest_completed_market_date_never_requests_an_open_session(self):
        before_open = dt.datetime(2026, 8, 3, 8, 0, tzinfo=dt.timezone.utc)
        after_close = dt.datetime(2026, 8, 3, 21, 0, tzinfo=dt.timezone.utc)
        weekend = dt.datetime(2026, 8, 2, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(latest_completed_market_date(before_open), dt.date(2026, 7, 31))
        self.assertEqual(latest_completed_market_date(after_close), dt.date(2026, 8, 3))
        self.assertEqual(latest_completed_market_date(weekend), dt.date(2026, 7, 31))

    def test_grouped_daily_is_adjusted_archived_and_resumable(self):
        response = {
            "status": "OK", "request_id": "req-1", "adjusted": True,
            "results": [{"T": "AAPL", "o": 100, "h": 110, "l": 99, "c": 108,
                         "v": 120000, "vw": 106, "n": 42, "t": 1783296000000}],
        }
        client = FakeClient([response])
        pipeline = MarketHistoryPipeline(client, self.store)
        day = dt.date(2026, 7, 6)
        first = pipeline.sync_sessions(day, day)
        second = pipeline.sync_sessions(day, day)
        self.assertEqual(first, {"downloaded": 1, "resumed": 0, "bars": 1, "no_data": 0})
        self.assertEqual(second["resumed"], 1)
        self.assertEqual(len(client.calls), 1)
        rows = list(self.store.iter_daily_bars(day.isoformat(), day.isoformat()))
        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertEqual(rows[0]["adjusted"], 1)
        raw_files = list((self.database.parent / "raw").rglob("*.json.gz"))
        self.assertEqual(len(raw_files), 1)

    def test_reference_preserves_active_and_delisted_and_marks_policy_hint(self):
        active = {"request_id": "active", "results": [{
            "ticker": "AAPL", "active": True, "type": "CS", "market": "stocks", "locale": "us"
        }]}
        inactive = {"request_id": "inactive", "results": [{
            "ticker": "OLD", "active": False, "type": "CS", "delisted_utc": "2025-01-02"
        }]}
        pipeline = MarketHistoryPipeline(FakeClient([active, inactive]), self.store)
        self.assertEqual(pipeline.sync_reference(dt.date(2026, 7, 31)), 2)
        with self.store.connect(create=False) as connection:
            rows = connection.execute(
                "SELECT ticker, active, eligible_equity FROM reference_snapshots ORDER BY ticker"
            ).fetchall()
        self.assertEqual([tuple(row) for row in rows], [("AAPL", 1, 1), ("OLD", 0, 1)])

    def test_actions_are_stored_without_double_adjusting_prices(self):
        split = {"request_id": "s", "results": [{
            "id": "split-1", "ticker": "TEST", "execution_date": "2026-07-07",
            "split_from": 1, "split_to": 2, "historical_adjustment_factor": 0.5,
        }]}
        dividend = {"request_id": "d", "results": [{
            "id": "div-1", "ticker": "TEST", "ex_dividend_date": "2026-07-08", "cash_amount": 0.25,
        }]}
        pipeline = MarketHistoryPipeline(FakeClient([split, dividend]), self.store)
        self.assertEqual(pipeline.sync_actions(dt.date(2026, 7, 1), dt.date(2026, 7, 31)), 2)
        with self.store.connect(create=False) as connection:
            kinds = [row[0] for row in connection.execute("SELECT action_kind FROM corporate_actions ORDER BY action_kind")]
        self.assertEqual(kinds, ["dividend", "split"])

    def _certifiable_session(self):
        day = "2026-08-07"
        fetched = "2026-08-07T20:05:00Z"
        digest = "a" * 64
        with self.store.connect() as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, 'complete', 1, 1, 'bars', ?, ?)",
                (day, fetched, digest),
            )
            connection.execute(
                """INSERT INTO daily_bars VALUES
                   (?, 'AAA', 99, 101, 98, 100, 1000000, 100, 1000, 1, 1,
                    'Massive Stocks REST API', 'bars', ?, ?)""",
                (day, fetched, digest),
            )
            connection.execute(
                """INSERT INTO reference_snapshots VALUES
                   (?, 'AAA', 1, 'Acme', 'stocks', 'us', 'USD', 'XNAS', 'CS',
                    '0000000001', 'COMP-AAA', 'SHARE-AAA', NULL, ?, 1, 'refs', ?, ?)""",
                (day, fetched, fetched, digest),
            )
            for endpoint, field, request in (
                ("/stocks/v1/splits", "execution_date", "splits"),
                ("/stocks/v1/dividends", "ex_dividend_date", "dividends"),
            ):
                parameters = json.dumps({field + ".gte": day, field + ".lte": day})
                connection.execute(
                    """INSERT INTO fetch_audit
                       (endpoint, parameters_json, fetched_at, http_status, request_id,
                        sha256, raw_path, row_count) VALUES (?, ?, ?, 200, ?, ?, ?, 0)""",
                    (endpoint, parameters, fetched, request, request[0] * 64, request + ".json.gz"),
                )
            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                [("actions_start", day), ("actions_end", day),
                 ("actions_retrieved_at", fetched)],
            )
            connection.commit()
        return day

    def test_session_certification_requires_prices_identities_and_raw_action_proofs(self):
        day = self._certifiable_session()
        result = self.store.certify_session(day, ["AAA"], "2026-08-07T20:15:00Z")
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["pointInTimePrices"])
        self.assertEqual(result["adjustmentPolicy"], "point_in_time_total_return")
        self.assertEqual(result["members"][0]["securityId"], "FIGI:SHARE-AAA")
        self.assertEqual(result["evidence"][0]["category"], "archived_adjusted_close")
        action = result["evidence"][-1]
        self.assertEqual(action["category"], "corporate_action_coverage")
        self.assertEqual(len(action["payload"]["sourceRequests"]), 2)

    def test_session_certification_fails_closed_for_late_or_missing_coverage(self):
        day = self._certifiable_session()
        late = self.store.certify_session(day, ["AAA"], "2026-08-07T20:04:59Z")
        missing = self.store.certify_session(day, ["AAA", "MISSING"], "2026-08-07T20:15:00Z")
        self.assertEqual(late["status"], "blocked")
        self.assertTrue(any("after the decision cutoff" in item or "late" in item
                            for item in late["failures"]))
        self.assertEqual(missing["status"], "blocked")
        self.assertTrue(any("MISSING" in item for item in missing["failures"]))

    def test_validation_fails_closed_for_missing_dates_and_bad_prices(self):
        response = {"request_id": "bad", "results": [{"T": "BAD", "h": 5, "l": 10, "c": -1, "v": -2}]}
        pipeline = MarketHistoryPipeline(FakeClient([response]), self.store)
        monday = dt.date(2026, 7, 6)
        pipeline.sync_sessions(monday, monday)
        report = pipeline.validate(monday, monday + dt.timedelta(days=1))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["badBars"], 1)
        self.assertEqual(report["missingWeekdays"], ["2026-07-07"])

    def test_phase_one_rows_use_total_return_spy_and_fifth_session_tail(self):
        start = dt.date(2026, 7, 6)
        end = dt.date(2026, 7, 13)
        responses = []
        for offset, day in enumerate([
            "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-13"
        ]):
            responses.append({"request_id": day, "results": [
                {"T": "SPY", "c": 100 if offset == 0 else 99, "h": 101, "l": 98, "v": 1000000},
                {"T": "TEST", "c": 100 if offset == 0 else 111, "h": 112, "l": 99, "v": 100000},
            ]})
        pipeline = MarketHistoryPipeline(FakeClient(responses), self.store)
        pipeline.sync_sessions(start, end)
        reference = {"request_id": "refs", "results": [
            {"ticker": "SPY", "type": "ETF", "currency_name": "usd", "primary_exchange": "ARCX",
             "share_class_figi": "SPY-FIGI", "last_updated_utc": "2026-07-06T00:00:00Z"},
            {"ticker": "TEST", "type": "CS", "currency_name": "usd", "primary_exchange": "XNAS",
             "share_class_figi": "TEST-FIGI", "last_updated_utc": "2026-07-06T00:00:00Z"},
        ]}
        pipeline.client = FakeClient([reference, {"request_id": "none", "results": []}])
        pipeline.sync_reference(start)
        split = {"request_id": "splits", "results": []}
        dividend = {"request_id": "dividends", "results": [{
            "id": "spy-div", "ticker": "SPY", "ex_dividend_date": "2026-07-07",
            "cash_amount": 1.0, "split_adjusted_cash_amount": 1.0,
        }]}
        pipeline.client = FakeClient([split, dividend])
        pipeline.sync_actions(start, start + dt.timedelta(days=14))
        self.assertEqual(pipeline.build_observations(start, start), 2)
        with self.store.connect(create=False) as connection:
            row = connection.execute(
                "SELECT adjusted_close, spy_adjusted_close, stock_close_t5, label_t1_json, label_t5_json "
                "FROM swing_observations WHERE ticker='TEST'"
            ).fetchone()
        self.assertEqual(row[0], 100)
        self.assertEqual(row[1], 99)  # cash distribution neutralises SPY's apparent one-point fall
        self.assertEqual(row[2], 111)
        self.assertTrue(json.loads(row[3])["isSwing"])
        self.assertEqual(json.loads(row[4])["labelStatus"], "ready")
        contract = list(self.store.iter_swing_observations(start.isoformat(), start.isoformat()))
        self.assertEqual(len(contract), 2)
        self.assertIsInstance(contract[0]["eligibility_json"], dict)
        self.assertIn("policyVersion", contract[0]["label_t5_json"])

    def test_client_rejects_external_pagination_urls(self):
        client = MassiveClient("not-a-real-key", opener=lambda *args, **kwargs: None)
        with self.assertRaises(MassiveError):
            client.get("https://example.com/steal")


if __name__ == "__main__":
    unittest.main()
