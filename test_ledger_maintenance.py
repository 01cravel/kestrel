from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from ledger_maintenance import IMMUTABLE_TABLES, verify_backup
from test_universe_ledger import evidence, lookthrough, member
from universe_ledger import SCHEMA_VERSION, UniverseLedger


class LedgerMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.ledger = UniverseLedger(self.root / "ledger.sqlite3")
        self.ledger.capture_snapshot(
            decision_date="2026-08-07", cutoff_utc="2026-08-07T20:15:00Z",
            recorded_at="2026-08-07T20:10:00Z", model_version="portfolio-science-v7",
            policy_version="evidence-v1", selection_policy_version="ideal-portfolio-v1",
            members=[member()], evidence=[evidence()], lookthrough=[lookthrough()],
            controls={
                "selectionPolicyFrozen": True, "pointInTimePrices": True,
                "adjustmentPolicy": "point_in_time_total_return", "oneWayCostBps": 10,
            },
        )

    def test_backup_is_consistent_while_a_wal_write_is_open(self):
        write_started = threading.Event()
        release_write = threading.Event()
        errors = []

        def writer():
            try:
                with self.ledger.connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "INSERT INTO ledger_metadata(key, value) VALUES('concurrent_probe', 'committed')"
                    )
                    write_started.set()
                    release_write.wait(5)
                    connection.commit()
            except Exception as error:  # pragma: no cover - reported by the assertion
                errors.append(error)
                write_started.set()

        thread = threading.Thread(target=writer)
        thread.start()
        self.assertTrue(write_started.wait(2))
        try:
            backup = self.ledger.backup(self.root / "backups")
        finally:
            release_write.set()
            thread.join(5)
        self.assertFalse(errors)
        self.assertTrue(backup["verified"])
        self.assertEqual(backup["sha256"], Path(backup["backup"]).stem)
        with sqlite3.connect(backup["backup"]) as connection:
            self.assertIsNone(connection.execute(
                "SELECT value FROM ledger_metadata WHERE key='concurrent_probe'"
            ).fetchone())
        with self.ledger.connect(create=False) as connection:
            self.assertEqual(connection.execute(
                "SELECT value FROM ledger_metadata WHERE key='concurrent_probe'"
            ).fetchone()[0], "committed")

    def test_backup_is_idempotent_and_recovery_has_the_same_logical_root(self):
        first = self.ledger.backup(self.root / "backups")
        second = self.ledger.backup(self.root / "backups")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["sha256"], first["sha256"])
        recovery_health = self.ledger.recovery_health(self.root / "backups")
        self.assertTrue(recovery_health["healthy"])
        self.assertEqual(recovery_health["verifiedBackups"], 1)
        target = self.root / "recovery" / "ledger.sqlite3"
        restored = self.ledger.restore(
            Path(first["backup"]), Path(first["manifest"]), target, first["databaseId"]
        )
        self.assertTrue(restored["verified"])
        self.assertEqual(restored["logicalRoot"], first["logicalRoot"])
        self.assertEqual(UniverseLedger(target).audit()["logicalRoot"], first["logicalRoot"])
        with self.assertRaises(FileExistsError):
            self.ledger.restore(
                Path(first["backup"]), Path(first["manifest"]), target, first["databaseId"]
            )

    def test_restore_fails_closed_on_wrong_identity_hash_schema_and_wal(self):
        created = self.ledger.backup(self.root / "backups")
        backup = Path(created["backup"])
        manifest = Path(created["manifest"])
        with self.assertRaisesRegex(ValueError, "live ledger"):
            self.ledger.restore(
                backup, manifest, self.ledger.database, created["databaseId"]
            )
        with self.assertRaisesRegex(RuntimeError, "different ledger"):
            self.ledger.restore(backup, manifest, self.root / "wrong.sqlite3", "0" * 64)

        tampered = self.root / "tampered.sqlite3"
        tampered.write_bytes(backup.read_bytes() + b"tamper")
        result = verify_backup(tampered, manifest, SCHEMA_VERSION, created["databaseId"])
        self.assertFalse(result["verified"])
        self.assertTrue(any("SHA-256" in failure for failure in result["failures"]))

        altered_manifest = self.root / "bad-schema.json"
        body = json.loads(manifest.read_text(encoding="utf-8"))
        body["schemaVersion"] = SCHEMA_VERSION + 1
        altered_manifest.write_text(json.dumps(body), encoding="utf-8")
        self.assertFalse(verify_backup(
            backup, altered_manifest, SCHEMA_VERSION, created["databaseId"]
        )["verified"])

        wal = Path(str(backup) + "-wal")
        wal.touch()
        try:
            result = verify_backup(backup, manifest, SCHEMA_VERSION, created["databaseId"])
            self.assertFalse(result["verified"])
            self.assertTrue(any("WAL" in failure for failure in result["failures"]))
        finally:
            wal.unlink()

    def test_audit_detects_logical_corruption(self):
        with sqlite3.connect(self.ledger.database) as connection:
            connection.execute("DROP TRIGGER evidence_versions_no_update")
            connection.execute("UPDATE evidence_versions SET payload_json='{}'")
            connection.commit()
        health = self.ledger.audit()
        self.assertEqual(health["status"], "corrupt")
        self.assertFalse(health["checks"]["contentHashes"])
        self.assertFalse(health["checks"]["immutableTriggers"])
        with self.assertRaisesRegex(RuntimeError, "unhealthy ledger"):
            self.ledger.backup(self.root / "backups")

    def test_v2_migrates_once_and_restores_all_immutable_triggers(self):
        with sqlite3.connect(self.ledger.database) as connection:
            retained_manifest = connection.execute(
                "SELECT manifest_json FROM universe_snapshots"
            ).fetchone()[0]
            connection.execute("DROP TRIGGER schema_migrations_no_update")
            connection.execute("DROP TRIGGER schema_migrations_no_delete")
            connection.execute("DROP TABLE schema_migrations")
            connection.execute(
                "UPDATE ledger_metadata SET value='2' WHERE key='schema_version'"
            )
            connection.commit()
        migrated = UniverseLedger(self.ledger.database)
        with migrated.connect() as connection:
            versions = [row[0] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )]
            self.assertEqual(versions, [1, 2, 3])
            triggers = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )}
            self.assertEqual(
                triggers,
                {
                    f"{table}_{suffix}" for table in IMMUTABLE_TABLES
                    for suffix in ("no_update", "no_delete")
                },
            )
            self.assertEqual(connection.execute(
                "SELECT manifest_json FROM universe_snapshots"
            ).fetchone()[0], retained_manifest)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE universe_snapshots SET status='changed'")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM schema_migrations WHERE version=3")
        first = migrated.audit()["logicalRoot"]
        with migrated.connect():
            pass
        self.assertEqual(migrated.audit()["logicalRoot"], first)

    def test_incomplete_or_future_schema_never_migrates_silently(self):
        broken = self.root / "broken.sqlite3"
        with sqlite3.connect(broken) as connection:
            connection.execute("CREATE TABLE ledger_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO ledger_metadata VALUES('schema_version', '2')")
            connection.commit()
        with self.assertRaisesRegex(RuntimeError, "incomplete before migration"):
            UniverseLedger(broken).connect()

        future = self.root / "future.sqlite3"
        with sqlite3.connect(future) as connection:
            connection.execute("CREATE TABLE ledger_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT INTO ledger_metadata VALUES('schema_version', '999')")
            connection.commit()
        with self.assertRaisesRegex(RuntimeError, "incompatible"):
            UniverseLedger(future).connect()


if __name__ == "__main__":
    unittest.main()
