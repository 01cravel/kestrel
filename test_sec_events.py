"""Guarantees for insider and filing evidence. No network is touched."""

from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import sec_events
from feature_store import event_features, session_cutoff
from sec_events import filing_events, insider_summary, parse_form4


def _form4(code: str, shares: str = "1000", price: str = "50",
           planned: str = "false", director: str = "true") -> bytes:
    return f"""<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2026-07-15</periodOfReport>
  <issuer><issuerTradingSymbol>APP</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>SMITH JANE</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>{director}</isDirector><isOfficer>false</isOfficer>
      <isTenPercentOwner>false</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>
  <aff10b5One>{planned}</aff10b5One>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-07-15</value></transactionDate>
      <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>""".encode("utf-8")


def _filing(code: str, filed: str = "2026-07-16", **kwargs) -> dict:
    parsed = parse_form4(_form4(code, **kwargs))
    return {**parsed, "filedOn": filed, "acceptedAt": f"{filed}T20:00:00.000Z",
            "accession": f"acc-{code}-{filed}"}


class Form4Tests(unittest.TestCase):
    def test_an_open_market_purchase_is_recognised(self) -> None:
        parsed = parse_form4(_form4("P"))
        transaction = parsed["transactions"][0]
        self.assertEqual(transaction["code"], "P")
        self.assertFalse(transaction["routine"])
        self.assertEqual(transaction["value"], 50000.0)
        self.assertEqual(parsed["roles"], ["director"])

    def test_awards_exercises_and_tax_are_marked_routine(self) -> None:
        for code in ("A", "M", "F", "G"):
            transaction = parse_form4(_form4(code))["transactions"][0]
            self.assertTrue(transaction["routine"], code)

    def test_a_grant_is_never_counted_as_buying(self) -> None:
        summary = insider_summary("APP", as_of=dt.date(2026, 8, 1),
                                  filings=[_filing("A"), _filing("M"), _filing("F")])
        self.assertEqual(summary["windows"]["30"]["openMarketBuys"], 0)
        self.assertEqual(summary["windows"]["30"]["buyValue"], 0)
        self.assertEqual(summary["routineTransactionsExcluded"], 3)
        self.assertIsNone(summary["daysSinceOpenMarketBuy"])

    def test_real_buying_is_counted_and_dated(self) -> None:
        summary = insider_summary("APP", as_of=dt.date(2026, 8, 1),
                                  filings=[_filing("P"), _filing("A")])
        window = summary["windows"]["30"]
        self.assertEqual(window["openMarketBuys"], 1)
        self.assertEqual(window["buyValue"], 50000.0)
        self.assertEqual(window["distinctBuyers"], 1)
        self.assertEqual(summary["daysSinceOpenMarketBuy"], 16)

    def test_a_pre_arranged_sale_is_separated_from_a_discretionary_one(self) -> None:
        summary = insider_summary("APP", as_of=dt.date(2026, 8, 1), filings=[
            _filing("S", planned="true"), _filing("S", planned="false", filed="2026-07-17"),
        ])
        window = summary["windows"]["30"]
        self.assertEqual(window["openMarketSells"], 2)
        self.assertEqual(window["salesOutsideAPlan"], 1)

    def test_filings_after_the_as_of_date_are_ignored(self) -> None:
        summary = insider_summary("APP", as_of=dt.date(2026, 7, 1), filings=[_filing("P")])
        self.assertEqual(summary["windows"]["30"]["openMarketBuys"], 0)

    def test_unreadable_xml_does_not_raise(self) -> None:
        self.assertEqual(parse_form4(b"not xml")["status"], "unreadable")
        self.assertEqual(parse_form4(b"not xml")["transactions"], [])


class FilingEventTests(unittest.TestCase):
    def setUp(self) -> None:
        original_identity = sec_events.sec_identity
        original_bytes = sec_events.sec_bytes
        sec_events.sec_identity = lambda symbol: {
            "status": "verified", "symbol": symbol.upper(), "cik": "0001751008"}
        payload = (
            b'{"filings":{"recent":{'
            b'"form":["8-K","8-K","8-K"],'
            b'"items":["2.02,9.01","9.01","1.01,5.02"],'
            b'"filingDate":["2026-05-06","2026-04-01","2026-03-02"],'
            b'"acceptanceDateTime":["2026-05-06T20:07:00.000Z","2026-04-01T12:00:00.000Z","2026-03-02T12:00:00.000Z"],'
            b'"accessionNumber":["a1","a2","a3"],"primaryDocument":["d","d","d"],'
            b'"reportDate":["2026-03-31","2026-03-31","2026-02-28"]}}}'
        )
        sec_events.sec_bytes = lambda url, accept="application/json": payload
        self.addCleanup(setattr, sec_events, "sec_identity", original_identity)
        self.addCleanup(setattr, sec_events, "sec_bytes", original_bytes)

    def test_item_numbers_become_readable_descriptions(self) -> None:
        events = filing_events("APP")["events"]
        self.assertIn("Results of operations", events[0]["descriptions"])
        self.assertIn("Director or officer change", events[2]["descriptions"])

    def test_a_purely_administrative_filing_is_not_material(self) -> None:
        events = filing_events("APP")["events"]
        self.assertTrue(events[0]["material"])
        self.assertFalse(events[1]["material"])


class EventFeatureTests(unittest.TestCase):
    @staticmethod
    def _event(event_type, event_date, available, value=None):
        return {"event_type": event_type, "event_date": event_date,
                "published_at": available, "available_at": available, "value": value}

    def test_a_filing_accepted_after_the_cutoff_is_invisible(self) -> None:
        cutoff = session_cutoff("2026-08-03")
        self.assertEqual(cutoff, "2026-08-03T20:15:00Z")
        late = [self._event("filing_event", "2026-08-03", "2026-08-03T23:00:00Z")]
        early = [self._event("filing_event", "2026-08-03", "2026-08-03T13:00:00Z")]
        self.assertEqual(event_features(late, "2026-08-03")["material_filings_30d"], 0.0)
        self.assertEqual(event_features(early, "2026-08-03")["material_filings_30d"], 1.0)

    def test_net_insider_value_is_signed(self) -> None:
        buying = [self._event("insider_buy", "2026-07-20", "2026-07-21T12:00:00Z", 1_000_000)]
        selling = [self._event("insider_sell", "2026-07-20", "2026-07-21T12:00:00Z", 1_000_000)]
        self.assertGreater(event_features(buying, "2026-08-03")["insider_net_value_90d"], 0)
        self.assertLess(event_features(selling, "2026-08-03")["insider_net_value_90d"], 0)

    def test_days_since_events_are_capped(self) -> None:
        ancient = [self._event("results", "2020-01-02", "2020-01-02T12:00:00Z")]
        features = event_features(ancient, "2026-08-03")
        self.assertEqual(features["days_since_results"], 365.0)

    def test_absent_evidence_stays_absent(self) -> None:
        features = event_features([], "2026-08-03")
        self.assertIsNone(features["days_since_results"])
        self.assertIsNone(features["days_since_insider_buy"])
        self.assertEqual(features["material_filings_30d"], 0.0)


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "market-history.sqlite3"
        from market_history import MarketHistoryStore
        with MarketHistoryStore(self.database).connect():
            pass

    def test_stored_events_round_trip_with_both_timestamps(self) -> None:
        original_insider = sec_events.insider_transactions
        original_events = sec_events.filing_events
        sec_events.insider_transactions = lambda symbol, limit=40: {
            "status": "verified", "cik": "1", "filings": [_filing("P")]}
        sec_events.filing_events = lambda symbol, limit=40: {
            "status": "verified", "events": [{
                "filedOn": "2026-05-06", "acceptedAt": "2026-05-06T20:07:00.000Z",
                "items": ["2.02"], "accession": "a1"}]}
        self.addCleanup(setattr, sec_events, "insider_transactions", original_insider)
        self.addCleanup(setattr, sec_events, "filing_events", original_events)

        result = sec_events.store_events("APP", self.database)
        self.assertEqual(result["status"], "stored")
        stored = sec_events.load_events("APP", self.database)
        self.assertEqual({row["event_type"] for row in stored}, {"insider_buy", "results"})
        for row in stored:
            self.assertTrue(row["available_at"].endswith("Z"))
            self.assertTrue(row["published_at"].endswith("Z"))

    def test_storing_twice_does_not_duplicate(self) -> None:
        original_insider = sec_events.insider_transactions
        original_events = sec_events.filing_events
        sec_events.insider_transactions = lambda symbol, limit=40: {
            "status": "verified", "cik": "1", "filings": [_filing("P")]}
        sec_events.filing_events = lambda symbol, limit=40: {"status": "none-found", "events": []}
        self.addCleanup(setattr, sec_events, "insider_transactions", original_insider)
        self.addCleanup(setattr, sec_events, "filing_events", original_events)

        sec_events.store_events("APP", self.database)
        sec_events.store_events("APP", self.database)
        self.assertEqual(len(sec_events.load_events("APP", self.database)), 1)

    def test_no_archive_is_reported_rather_than_crashing(self) -> None:
        result = sec_events.store_events("APP", Path(self.directory.name) / "absent.sqlite3")
        self.assertEqual(result["status"], "no-archive")


if __name__ == "__main__":
    unittest.main()
