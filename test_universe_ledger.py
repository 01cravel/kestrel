from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from universe_ledger import PROTOCOL_VERSION, UniverseLedger, security_master_members


OUTCOME_PROVENANCE = {
    "effective_at": "2027-08-07T20:00:00Z",
    "available_at": "2027-08-08T10:00:00Z",
    "retrieved_at": "2027-08-08T11:00:00Z",
    "currency": "USD", "adjustment_definition": "point_in_time_total_return",
    "source_record_hash": "a" * 64, "evidence_hash": "b" * 64,
}


def member(symbol="AAA", security_id="FIGI:AAA", **changes):
    row = {
        "ticker": symbol, "securityId": security_id, "active": True,
        "identityStatus": "resolved", "membershipVerified": True, "included": True,
        "identityAvailableAt": "2026-08-07T19:00:00Z",
        "identifiers": {"figi": security_id.split(":", 1)[-1]},
        "listing": {"market": "US", "currency": "USD"},
        "sources": [{"name": "Official listing directory", "tier": 1}],
    }
    row.update(changes)
    return row


def evidence(**changes):
    row = {
        "securityId": "FIGI:AAA", "category": "price",
        "recordKey": "AAA:2026-08-07", "effectiveAt": "2026-08-07T20:00:00Z",
        "availableAt": "2026-08-07T20:01:00Z", "retrievedAt": "2026-08-07T20:05:00Z",
        "source": "Official close", "sourceTier": 1, "payload": {"close": 100.0},
    }
    row.update(changes)
    return row


def lookthrough(**changes):
    payload = {
        "archiveEvidence": True, "fundSecurityId": "FIGI:FUND-VTI",
        "shareClassId": "FIGI:CLASS-VTI", "holdingsReportId": "holdings-1",
        "feeReportId": "fees-1", "reportingLagDays": 1, "maxReportingLagDays": 75,
        "baseCurrency": "USD", "weightUnit": "percent", "reportedTotalWeight": 100.0,
        "coverageComplete": True, "cashResolved": True, "derivativesResolved": True,
        "currencyResolved": True,
        "positions": [{"positionType": "cash", "name": "USD", "reportedWeight": 100.0}],
        "fees": {"netExpenseRatio": 0.03, "feeUnit": "percent"},
        "sources": [
            {"documentId": "document-1", "sourceRecordId": "issuer-holdings-1",
             "url": "https://issuer.example/holdings.csv", "sha256": "a" * 64},
            {"documentId": "document-2", "sourceRecordId": "issuer-fees-1",
             "url": "https://issuer.example/fees.pdf", "sha256": "b" * 64},
        ],
    }
    payload.update(changes.pop("payload", {}))
    row = {
        "asOf": "2026-08-07", "availableAt": "2026-08-07T19:00:00Z",
        "retrievedAt": "2026-08-07T19:05:00Z", "complete": True,
        "source": "Archived issuer/SEC ETF evidence",
        "fundSecurityId": "FIGI:FUND-VTI", "shareClassId": "FIGI:CLASS-VTI",
        "payload": payload,
    }
    if "availableAt" in changes and "retrievedAt" not in changes:
        row["retrievedAt"] = changes["availableAt"]
    row.update(changes)
    return row


class UniverseLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "universe.sqlite3"
        self.ledger = UniverseLedger(self.database)

    def capture(self, **changes):
        arguments = {
            "decision_date": "2026-08-07", "cutoff_utc": "2026-08-07T20:15:00Z",
            "recorded_at": "2026-08-07T20:10:00Z",
            "model_version": "portfolio-science-v7", "policy_version": "evidence-v1",
            "selection_policy_version": "ideal-portfolio-v1",
            "members": [member()], "evidence": [evidence()], "lookthrough": [lookthrough()],
            "controls": {"selectionPolicyFrozen": True, "pointInTimePrices": True,
                         "adjustmentPolicy": "point_in_time_total_return", "oneWayCostBps": 10},
        }
        arguments.update(changes)
        return self.ledger.capture_snapshot(**arguments)

    def test_snapshot_round_trips_with_verified_hashes(self):
        captured = self.capture()
        self.assertEqual(captured["status"], "captured")
        self.assertEqual(captured["snapshotStatus"], "complete")
        rebuilt = self.ledger.reconstruct(captured["snapshotId"])
        self.assertEqual(rebuilt["status"], "verified")
        self.assertTrue(rebuilt["manifestClean"])
        self.assertTrue(rebuilt["payloadsClean"])
        self.assertEqual(rebuilt["members"][0]["ticker"], "AAA")

    def test_same_snapshot_is_idempotent_but_changed_same_day_conflicts(self):
        first = self.capture()
        second = self.capture(recorded_at="2026-08-07T20:12:00Z")
        changed = self.capture(members=[member(active=False)])
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["snapshotId"], first["snapshotId"])
        self.assertEqual(changed["status"], "conflict")
        self.assertNotEqual(changed["attemptedManifestHash"], changed["manifestHash"])

    def test_future_evidence_is_rejected_not_shifted_back(self):
        with self.assertRaisesRegex(ValueError, "after the snapshot cutoff"):
            self.capture(evidence=[evidence(availableAt="2026-08-07T20:16:00Z")])
        self.assertFalse(self.database.exists() and self.ledger.latest().get("snapshots"))

    def test_unresolved_or_unknown_listing_is_preserved_but_excluded(self):
        result = self.capture(
            members=[member(security_id="", active=None, identityStatus="unresolved",
                            membershipVerified=False)],
        )
        self.assertEqual(result["snapshotStatus"], "incomplete")
        rebuilt = self.ledger.reconstruct(result["snapshotId"])
        row = rebuilt["members"][0]
        self.assertFalse(row["included"])
        self.assertIn("stable identity missing", row["reason"])
        self.assertIn("listing status missing", row["reason"])

    def test_immutable_tables_reject_update_and_delete(self):
        result = self.capture()
        with self.ledger.connect(create=False) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE universe_snapshots SET status='changed'")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM snapshot_members WHERE snapshot_id=?",
                                   (result["snapshotId"],))

    def test_ticker_change_creates_a_later_identity_version_without_rewriting_old_snapshot(self):
        first = self.capture()
        second = self.capture(
            decision_date="2026-08-08", cutoff_utc="2026-08-08T20:15:00Z",
            recorded_at="2026-08-08T20:10:00Z",
            members=[member(symbol="BBB", security_id="FIGI:AAA", validFrom="2026-08-08")],
            evidence=[evidence(recordKey="BBB:2026-08-08", availableAt="2026-08-08T20:01:00Z",
                               retrievedAt="2026-08-08T20:05:00Z")],
            lookthrough=[lookthrough(asOf="2026-08-08", availableAt="2026-08-08T19:00:00Z")],
        )
        self.assertEqual(self.ledger.reconstruct(first["snapshotId"])["members"][0]["ticker"], "AAA")
        self.assertEqual(self.ledger.reconstruct(second["snapshotId"])["members"][0]["ticker"], "BBB")
        self.assertEqual(self.ledger.latest()["identityVersions"], 2)

    def test_protocol_accumulates_until_every_member_has_a_complete_outcome(self):
        result = self.capture()
        accumulating = self.ledger.build_protocol(result["snapshotId"], ["AAA"], "VT", 10)
        self.assertEqual(accumulating["status"], "accumulating")
        self.assertFalse(accumulating["survivorshipFree"])
        self.assertEqual(accumulating["protocolVersion"], PROTOCOL_VERSION)
        self.ledger.append_outcome(
            snapshot_id=result["snapshotId"], security_id="FIGI:AAA",
            valid_through="2027-08-07", status="complete", source="Official total-return archive",
            source_record_id="AAA-2027-08-07", payload={"totalReturn": 0.12},
            recorded_at="2027-08-08T12:00:00Z",
            **OUTCOME_PROVENANCE,
        )
        ready = self.ledger.build_protocol(result["snapshotId"], ["AAA"], "VT", 10)
        self.assertEqual(ready["status"], "ready")
        self.assertTrue(ready["ledgerVerified"])
        self.assertTrue(ready["survivorshipFree"])
        self.assertTrue(ready["universeRecords"]["AAA"]["outcomeComplete"])
        self.assertEqual(ready["universeRecords"]["AAA"]["outcomeStatus"], "complete")
        self.assertEqual(self.ledger.latest()["outcomeStates"], {"complete": 1})

    def test_short_outcome_path_cannot_certify_an_annual_window(self):
        result = self.capture()
        self.ledger.append_outcome(
            snapshot_id=result["snapshotId"], security_id="FIGI:AAA",
            valid_through="2026-12-31", status="complete", source="Official total-return archive",
            source_record_id="AAA-2026-12-31", payload={"totalReturn": 0.05},
            recorded_at="2027-01-02T12:00:00Z",
            effective_at="2026-12-31T20:00:00Z",
            available_at="2027-01-02T10:00:00Z", retrieved_at="2027-01-02T11:00:00Z",
            currency="USD", adjustment_definition="point_in_time_total_return",
            source_record_hash="c" * 64, evidence_hash="d" * 64,
        )
        protocol = self.ledger.build_protocol(result["snapshotId"], ["AAA"], "VT", 10)
        self.assertFalse(protocol["survivorshipFree"])
        self.assertFalse(protocol["universeRecords"]["AAA"]["outcomeComplete"])
        self.assertEqual(protocol["universeRecords"]["AAA"]["requiredThrough"], "2027-08-07")

    def test_protocol_chains_later_verified_lookthrough_snapshots(self):
        first = self.capture()
        second = self.capture(
            decision_date="2026-08-08", cutoff_utc="2026-08-08T20:15:00Z",
            recorded_at="2026-08-08T20:10:00Z",
            members=[member(validFrom="2026-08-07")],
            evidence=[evidence(recordKey="AAA:2026-08-08", availableAt="2026-08-08T20:01:00Z",
                               retrievedAt="2026-08-08T20:05:00Z")],
            lookthrough=[lookthrough(asOf="2026-08-08", availableAt="2026-08-08T19:00:00Z",
                                     payload={"fundOverlaps": {"VTI": {"AAA": 1.2}}})],
        )
        protocol = self.ledger.build_protocol(first["snapshotId"], ["AAA"], "VT", 10)
        self.assertEqual(protocol["snapshotIds"], [first["snapshotId"], second["snapshotId"]])
        self.assertEqual(len(protocol["manifestHashes"]), 2)
        self.assertEqual(len(protocol["lookthroughSnapshots"]), 2)
        self.assertTrue(protocol["ledgerVerified"])
        self.assertTrue(protocol["archivedLookthroughComplete"])
        self.assertEqual(protocol["lookthroughSnapshots"][0]["availableAt"],
                         "2026-08-07T19:00:00Z")
        self.assertEqual(protocol["lookthroughSnapshots"][0]["retrievedAt"],
                         "2026-08-07T19:05:00Z")

    def test_legacy_live_lookthrough_cannot_open_archived_evidence_gate(self):
        result = self.capture(lookthrough=[{
            "asOf": "2026-08-07", "availableAt": "2026-08-07T19:00:00Z",
            "retrievedAt": "2026-08-07T19:05:00Z", "complete": True,
            "source": "Live issuer holdings", "payload": {"fundsReady": 6},
        }])
        self.ledger.append_outcome(
            snapshot_id=result["snapshotId"], security_id="FIGI:AAA",
            valid_through="2027-08-07", status="complete", source="Official total-return archive",
            source_record_id="AAA-2027-08-07", payload={"totalReturn": 0.12},
            recorded_at="2027-08-08T12:00:00Z", **OUTCOME_PROVENANCE,
        )
        protocol = self.ledger.build_protocol(result["snapshotId"], ["AAA"], "VT", 10)
        self.assertEqual(protocol["status"], "accumulating")
        self.assertFalse(protocol["archivedLookthroughComplete"])
        self.assertTrue(protocol["survivorshipFree"])

    def test_delisting_requires_proceeds_currency_and_source_evidence(self):
        result = self.capture()
        with self.assertRaises(ValueError):
            self.ledger.append_outcome(
                snapshot_id=result["snapshotId"], security_id="FIGI:AAA",
                valid_through="2027-01-01", status="delisted_complete",
                source="Exchange notice", source_record_id="delist-1", delisted_on="2027-01-01",
                effective_at="2027-01-01T20:00:00Z", available_at="2027-01-02T10:00:00Z",
                retrieved_at="2027-01-02T11:00:00Z", recorded_at="2027-01-02T12:00:00Z",
                currency="USD", adjustment_definition="point_in_time_total_return",
                source_record_hash="e" * 64, evidence_hash="f" * 64,
            )

    def test_outcome_rejects_unrecognized_adjustment_definition(self):
        result = self.capture()
        with self.assertRaisesRegex(ValueError, "adjustment definition"):
            self.ledger.append_outcome(
                snapshot_id=result["snapshotId"], security_id="FIGI:AAA",
                valid_through="2027-08-07", status="complete",
                source="Archive", source_record_id="row-1", payload={"totalReturn": 0.1},
                recorded_at="2027-08-08T12:00:00Z", effective_at="2027-08-07T20:00:00Z",
                available_at="2027-08-08T10:00:00Z", retrieved_at="2027-08-08T11:00:00Z",
                currency="USD", adjustment_definition="split_only",
                source_record_hash="1" * 64, evidence_hash="2" * 64,
            )

    def test_live_adapter_does_not_claim_activity_without_a_current_quote(self):
        snapshot = {"instruments": {"AAA": {
            "symbol": "AAA", "status": "resolved", "identifiers": {"figi": "AAA"},
            "listing": {"currency": "USD"}, "resolvedAt": 1786120000,
        }}}
        missing = security_master_members(snapshot, ["AAA"], {})[0]
        quoted = security_master_members(snapshot, ["AAA"], {
            "AAA": {"quote": {"c": 10, "t": 1786120000}}
        })[0]
        self.assertIsNone(missing["active"])
        self.assertFalse(missing["membershipVerified"])
        self.assertTrue(quoted["active"])
        self.assertTrue(quoted["membershipVerified"])


if __name__ == "__main__":
    unittest.main()
