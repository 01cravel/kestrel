"""Fail-closed integrity, backup and restore operations for the universe ledger."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


BACKUP_FORMAT = "kestrel-sqlite-backup-v1"
BACKUP_METHOD = "sqlite-online-backup"
IMMUTABLE_TABLES = (
    "universe_snapshots", "identity_versions", "snapshot_members",
    "evidence_versions", "lookthrough_versions", "outcome_versions",
    "schema_migrations",
)
EXPECTED_COLUMNS = {
    "ledger_metadata": {"key", "value"},
    "schema_migrations": {"version", "applied_at", "migration_hash"},
    "universe_snapshots": {
        "snapshot_id", "decision_date", "cutoff_utc", "recorded_at", "model_version",
        "policy_version", "selection_policy_version", "status", "manifest_hash", "manifest_json",
    },
    "identity_versions": {
        "version_id", "security_id", "ticker", "valid_from", "valid_to", "recorded_at",
        "identity_available_at", "active", "identity_status", "identifiers_json", "listing_json",
        "source_json", "content_hash",
    },
    "snapshot_members": {
        "snapshot_id", "security_id", "ticker", "included", "active", "identity_clean",
        "membership_verified", "reason", "identity_version_id",
    },
    "evidence_versions": {
        "evidence_id", "snapshot_id", "security_id", "category", "record_key", "effective_at",
        "available_at", "retrieved_at", "source", "source_tier", "payload_hash", "payload_json",
    },
    "lookthrough_versions": {
        "lookthrough_id", "snapshot_id", "as_of", "available_at", "complete", "source",
        "payload_hash", "payload_json", "retrieved_at", "fund_security_id",
        "share_class_id", "holdings_report_id", "fee_report_id", "reporting_lag_days",
        "source_hashes_json",
    },
    "outcome_versions": {
        "outcome_id", "snapshot_id", "security_id", "valid_through", "recorded_at", "status",
        "delisted_on", "proceeds", "currency", "source", "source_record_id", "payload_hash",
        "payload_json", "effective_at", "available_at", "retrieved_at", "listing_state",
        "adjustment_definition", "consideration_json", "source_record_hash", "evidence_hash",
    },
}
MIGRATION_NAMES = {
    1: "initial-bitemporal-ledger",
    2: "outcome-provenance",
    3: "operational-integrity",
    4: "archived-etf-evidence",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _migration_hash(version: int) -> str:
    return _digest({
        "ledger": "universe", "schemaVersion": version,
        "migration": MIGRATION_NAMES[version],
    })


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def _metadata(connection: sqlite3.Connection) -> Dict[str, str]:
    try:
        return {str(row[0]): str(row[1]) for row in connection.execute(
            "SELECT key, value FROM ledger_metadata ORDER BY key"
        )}
    except sqlite3.DatabaseError:
        return {}


def _logical_root(connection: sqlite3.Connection, tables: Iterable[str]) -> str:
    content = []
    for table in sorted(tables):
        columns = [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")]
        if not columns:
            continue
        order = ", ".join(f'"{column}"' for column in columns)
        rows = [list(row) for row in connection.execute(f'SELECT {order} FROM "{table}" ORDER BY {order}')]
        content.append({"table": table, "columns": columns, "rows": rows})
    return _digest(content)


def audit_database(database: Path, expected_schema_version: int) -> Dict[str, Any]:
    """Return a deterministic, read-only audit. Any uncertainty is unhealthy."""
    path = Path(database)
    failures = []
    checks: Dict[str, Any] = {}
    if not path.is_file():
        return {
            "status": "empty", "healthy": False, "database": str(path),
            "schemaVersion": None, "databaseId": None,
            "failures": ["Ledger database does not exist"],
        }
    try:
        with _read_only(path) as connection:
            integrity = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
            checks["sqliteIntegrity"] = integrity == ["ok"]
            if not checks["sqliteIntegrity"]:
                failures.extend(f"SQLite integrity: {message}" for message in integrity)
            foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
            checks["foreignKeys"] = not foreign_keys
            if foreign_keys:
                failures.append(f"Foreign-key violations: {len(foreign_keys)}")

            metadata = _metadata(connection)
            database_id = metadata.get("database_id")
            try:
                schema_version = int(metadata.get("schema_version", ""))
            except ValueError:
                schema_version = None
            checks["schemaVersion"] = schema_version == expected_schema_version
            if not checks["schemaVersion"]:
                failures.append(
                    f"Schema version is {schema_version}; expected {expected_schema_version}"
                )
            try:
                identity_valid = bool(database_id and len(database_id) == 64 and int(database_id, 16) >= 0)
            except ValueError:
                identity_valid = False
            checks["databaseIdentity"] = identity_valid
            if not checks["databaseIdentity"]:
                failures.append("Ledger database identity is missing or invalid")

            objects = {str(row[0]): {"type": str(row[1]), "sql": str(row[2] or "")} for row in connection.execute(
                "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table', 'trigger')"
            )}
            for table, expected in sorted(EXPECTED_COLUMNS.items()):
                actual = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
                if actual != expected:
                    failures.append(
                        f"Schema mismatch in {table}: missing {sorted(expected - actual)}, "
                        f"unexpected {sorted(actual - expected)}"
                    )
            missing_triggers = []
            for table in IMMUTABLE_TABLES:
                for suffix in ("no_update", "no_delete"):
                    name = f"{table}_{suffix}"
                    action = "UPDATE" if suffix == "no_update" else "DELETE"
                    message = "updated" if suffix == "no_update" else "deleted"
                    sql = objects.get(name, {}).get("sql", "").upper()
                    if (
                        objects.get(name, {}).get("type") != "trigger"
                        or f"BEFORE {action} ON {table}".upper() not in sql
                        or "RAISE(ABORT" not in sql
                        or f"IMMUTABLE LEDGER ROWS CANNOT BE {message.upper()}" not in sql
                    ):
                        missing_triggers.append(name)
            checks["immutableTriggers"] = not missing_triggers
            if missing_triggers:
                failures.append("Missing immutable triggers: " + ", ".join(missing_triggers))
            migrations = [tuple(row) for row in connection.execute(
                "SELECT version, migration_hash FROM schema_migrations ORDER BY version"
            )]
            expected_migrations = [
                (version, _migration_hash(version)) for version in range(1, expected_schema_version + 1)
            ] if expected_schema_version == max(MIGRATION_NAMES) else []
            checks["migrationHistory"] = migrations == expected_migrations
            if not checks["migrationHistory"]:
                failures.append("Migration history is incomplete or has been altered")

            payload_failures = []
            for table in ("evidence_versions", "lookthrough_versions", "outcome_versions"):
                for row in connection.execute(
                    f"SELECT rowid, payload_hash, payload_json FROM {table} ORDER BY rowid"
                ):
                    try:
                        clean = _digest(json.loads(row["payload_json"])) == row["payload_hash"]
                    except (TypeError, json.JSONDecodeError):
                        clean = False
                    if not clean:
                        payload_failures.append(f"{table}:{row['rowid']}")
            manifest_failures = []
            for row in connection.execute(
                "SELECT snapshot_id, cutoff_utc, manifest_hash, manifest_json "
                "FROM universe_snapshots ORDER BY snapshot_id"
            ):
                try:
                    manifest = json.loads(row["manifest_json"])
                    clean = (
                        _digest(manifest) == row["manifest_hash"]
                        and _digest({
                            "manifestHash": row["manifest_hash"], "cutoffUtc": row["cutoff_utc"]
                        }) == row["snapshot_id"]
                    )
                except (TypeError, json.JSONDecodeError):
                    clean = False
                if not clean:
                    manifest_failures.append(str(row["snapshot_id"]))
            address_failures = []
            for row in connection.execute("SELECT * FROM identity_versions ORDER BY version_id"):
                try:
                    body = {
                        "securityId": row["security_id"], "ticker": row["ticker"],
                        "validFrom": row["valid_from"], "validTo": row["valid_to"],
                        "active": None if row["active"] is None else bool(row["active"]),
                        "identityStatus": row["identity_status"],
                        "identityAvailableAt": row["identity_available_at"],
                        "identifiers": json.loads(row["identifiers_json"]),
                        "listing": json.loads(row["listing_json"]),
                        "sources": json.loads(row["source_json"]),
                    }
                    clean = _digest(body) == row["content_hash"] == row["version_id"]
                except (TypeError, json.JSONDecodeError):
                    clean = False
                if not clean:
                    address_failures.append(f"identity_versions:{row['version_id']}")
            for row in connection.execute("SELECT * FROM evidence_versions ORDER BY evidence_id"):
                try:
                    payload = json.loads(row["payload_json"])
                    body = {
                        "securityId": row["security_id"], "category": row["category"],
                        "recordKey": row["record_key"], "effectiveAt": row["effective_at"],
                        "availableAt": row["available_at"], "retrievedAt": row["retrieved_at"],
                        "source": row["source"], "sourceTier": row["source_tier"],
                        "payloadHash": row["payload_hash"], "payload": payload,
                    }
                    clean = _digest(body) == row["evidence_id"]
                except (TypeError, json.JSONDecodeError):
                    clean = False
                if not clean:
                    address_failures.append(f"evidence_versions:{row['evidence_id']}")
            for row in connection.execute("SELECT * FROM lookthrough_versions ORDER BY lookthrough_id"):
                try:
                    payload = json.loads(row["payload_json"])
                    body = {
                        "asOf": row["as_of"], "availableAt": row["available_at"],
                        "retrievedAt": row["retrieved_at"],
                        "complete": bool(row["complete"]), "source": row["source"],
                        "fundSecurityId": row["fund_security_id"],
                        "shareClassId": row["share_class_id"],
                        "holdingsReportId": row["holdings_report_id"],
                        "feeReportId": row["fee_report_id"],
                        "reportingLagDays": row["reporting_lag_days"],
                        "sourceHashes": json.loads(row["source_hashes_json"] or "[]"),
                        "payloadHash": row["payload_hash"], "payload": payload,
                    }
                    clean = _digest(body) == row["lookthrough_id"]
                except (TypeError, json.JSONDecodeError):
                    clean = False
                if not clean:
                    address_failures.append(f"lookthrough_versions:{row['lookthrough_id']}")
            for row in connection.execute("SELECT * FROM outcome_versions ORDER BY outcome_id"):
                try:
                    body = {
                        "snapshotId": row["snapshot_id"], "securityId": row["security_id"],
                        "validThrough": row["valid_through"], "recordedAt": row["recorded_at"],
                        "status": row["status"], "effectiveAt": row["effective_at"],
                        "availableAt": row["available_at"], "retrievedAt": row["retrieved_at"],
                        "listingState": row["listing_state"],
                        "adjustmentDefinition": row["adjustment_definition"],
                        "delistedOn": row["delisted_on"], "proceeds": row["proceeds"],
                        "currency": row["currency"],
                        "consideration": json.loads(row["consideration_json"] or "{}"),
                        "source": row["source"], "sourceRecordId": row["source_record_id"],
                        "payloadHash": row["payload_hash"],
                        "sourceRecordHash": row["source_record_hash"],
                        "evidenceHash": row["evidence_hash"],
                    }
                    clean = _digest(body) == row["outcome_id"]
                except (TypeError, json.JSONDecodeError):
                    clean = False
                if not clean:
                    address_failures.append(f"outcome_versions:{row['outcome_id']}")
            checks["contentHashes"] = (
                not payload_failures and not manifest_failures and not address_failures
            )
            if payload_failures:
                failures.append("Payload hash mismatch: " + ", ".join(payload_failures))
            if manifest_failures:
                failures.append("Manifest hash mismatch: " + ", ".join(manifest_failures))
            if address_failures:
                failures.append("Content address mismatch: " + ", ".join(address_failures))

            tables = tuple(EXPECTED_COLUMNS)
            logical_root = _logical_root(connection, tables)
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in sorted(EXPECTED_COLUMNS) if table != "ledger_metadata"
            }
    except sqlite3.DatabaseError as error:
        return {
            "status": "corrupt", "healthy": False, "database": str(path),
            "schemaVersion": None, "databaseId": None,
            "failures": [f"SQLite could not read the ledger: {error}"],
        }
    return {
        "status": "healthy" if not failures else "corrupt",
        "healthy": not failures, "database": str(path),
        "schemaVersion": schema_version, "databaseId": database_id,
        "logicalRoot": logical_root, "checks": checks, "counts": counts,
        "failures": sorted(failures),
    }


def verify_backup(backup: Path, manifest_path: Path, expected_schema_version: int,
                  expected_database_id: Optional[str] = None) -> Dict[str, Any]:
    backup = Path(backup)
    manifest_path = Path(manifest_path)
    failures = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"status": "invalid", "verified": False, "failures": [f"Backup manifest is unreadable: {error}"]}
    required = {
        "format", "method", "databaseId", "schemaVersion", "sha256", "size",
        "logicalRoot", "walState",
    }
    if not required.issubset(manifest):
        failures.append("Backup manifest is incomplete")
    if manifest.get("format") != BACKUP_FORMAT or manifest.get("method") != BACKUP_METHOD:
        failures.append("Backup format or creation method is not trusted")
    if manifest.get("walState") != "self-contained":
        failures.append("Backup manifest does not certify a complete WAL state")
    if manifest.get("schemaVersion") != expected_schema_version:
        failures.append("Backup schema is incompatible")
    if expected_database_id and manifest.get("databaseId") != expected_database_id:
        failures.append("Backup belongs to a different ledger database")
    if not backup.is_file():
        failures.append("Backup database does not exist")
    else:
        if backup.stem != manifest.get("sha256") or manifest_path.stem != manifest.get("sha256"):
            failures.append("Backup paths are not content-addressed by their SHA-256")
        if backup.stat().st_size != manifest.get("size"):
            failures.append("Backup size does not match its manifest")
        if _file_hash(backup) != manifest.get("sha256"):
            failures.append("Backup SHA-256 does not match its manifest")
        for suffix in ("-wal", "-shm"):
            if Path(str(backup) + suffix).exists():
                failures.append("Backup has an incomplete or unexpected WAL state")
    # Do not ask SQLite to interpret an untrusted file until its external
    # identity, schema declaration, complete-WAL claim and bytes all match.
    if failures:
        return {
            "status": "invalid", "verified": False,
            "backup": str(backup), "manifest": str(manifest_path),
            "databaseId": manifest.get("databaseId"), "sha256": manifest.get("sha256"),
            "logicalRoot": manifest.get("logicalRoot"), "audit": {},
            "failures": sorted(set(failures)),
        }
    audit = audit_database(backup, expected_schema_version) if backup.is_file() else {}
    if audit and not audit.get("healthy"):
        failures.extend(audit.get("failures") or ["Backup database audit failed"])
    if audit and audit.get("databaseId") != manifest.get("databaseId"):
        failures.append("Backup database identity does not match its manifest")
    if audit and audit.get("logicalRoot") != manifest.get("logicalRoot"):
        failures.append("Backup logical root does not match its manifest")
    if backup.is_file():
        try:
            with _read_only(backup) as connection:
                if str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal":
                    failures.append("Backup is still WAL-dependent")
        except sqlite3.DatabaseError:
            pass
    return {
        "status": "verified" if not failures else "invalid", "verified": not failures,
        "backup": str(backup), "manifest": str(manifest_path),
        "databaseId": manifest.get("databaseId"), "sha256": manifest.get("sha256"),
        "logicalRoot": manifest.get("logicalRoot"), "audit": audit,
        "failures": sorted(set(failures)),
    }


def audit_backup_directory(directory: Path, expected_schema_version: int,
                           expected_database_id: str) -> Dict[str, Any]:
    """Report deterministic recovery coverage for every published backup pair."""
    directory = Path(directory)
    if not directory.is_dir():
        return {
            "status": "empty", "healthy": False, "directory": str(directory),
            "verifiedBackups": 0, "failures": ["No ledger backups have been published"],
        }
    stems = sorted(
        {path.stem for path in directory.glob("*.sqlite3")}
        | {path.stem for path in directory.glob("*.json")}
    )
    failures = []
    verified = 0
    for stem in stems:
        result = verify_backup(
            directory / f"{stem}.sqlite3", directory / f"{stem}.json",
            expected_schema_version, expected_database_id,
        )
        if result.get("verified"):
            verified += 1
        else:
            failures.append({"backupId": stem, "failures": result.get("failures") or []})
    if not stems:
        return {
            "status": "empty", "healthy": False, "directory": str(directory),
            "verifiedBackups": 0, "failures": ["No ledger backups have been published"],
        }
    return {
        "status": "healthy" if not failures else "degraded",
        "healthy": not failures, "directory": str(directory),
        "verifiedBackups": verified, "failures": failures,
    }


def create_backup(database: Path, backup_directory: Path, expected_schema_version: int) -> Dict[str, Any]:
    """Create a transactionally consistent, standalone, content-addressed backup."""
    database = Path(database)
    before = audit_database(database, expected_schema_version)
    if not before.get("healthy"):
        raise RuntimeError("Refusing to back up an unhealthy ledger: " + "; ".join(before["failures"]))
    directory = Path(backup_directory)
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".ledger-backup-", suffix=".sqlite3", dir=directory)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with _read_only(database) as source, sqlite3.connect(str(temporary), timeout=30) as target:
            source.backup(target, pages=256)
            target.execute("PRAGMA journal_mode=DELETE")
            target.execute("PRAGMA synchronous=FULL")
            target.commit()
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        audit = audit_database(temporary, expected_schema_version)
        if not audit.get("healthy") or audit.get("databaseId") != before.get("databaseId"):
            raise RuntimeError("The completed backup failed integrity verification")
        sha256 = _file_hash(temporary)
        backup = directory / f"{sha256}.sqlite3"
        manifest_path = directory / f"{sha256}.json"
        manifest = {
            "format": BACKUP_FORMAT, "method": BACKUP_METHOD,
            "databaseId": audit["databaseId"], "schemaVersion": expected_schema_version,
            "sha256": sha256, "size": temporary.stat().st_size,
            "logicalRoot": audit["logicalRoot"], "walState": "self-contained",
        }
        with (directory / ".backup.lock").open("a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if backup.exists() or manifest_path.exists():
                existing = verify_backup(
                    backup, manifest_path, expected_schema_version, audit["databaseId"]
                )
                if not existing.get("verified"):
                    raise RuntimeError("A conflicting content-addressed backup already exists")
                return {**existing, "status": "unchanged"}
            os.link(temporary, backup)
            try:
                manifest_descriptor, manifest_temporary_name = tempfile.mkstemp(
                    prefix=".ledger-manifest-", suffix=".json", dir=directory
                )
                try:
                    with os.fdopen(manifest_descriptor, "w", encoding="utf-8") as stream:
                        stream.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.link(manifest_temporary_name, manifest_path)
                finally:
                    Path(manifest_temporary_name).unlink(missing_ok=True)
                directory_descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
                verified = verify_backup(
                    backup, manifest_path, expected_schema_version, audit["databaseId"]
                )
                if not verified.get("verified"):
                    raise RuntimeError("The published backup failed verification")
                return {**verified, "status": "created"}
            except Exception:
                manifest_path.unlink(missing_ok=True)
                backup.unlink(missing_ok=True)
                raise
    finally:
        temporary.unlink(missing_ok=True)


def restore_backup(backup: Path, manifest: Path, target: Path, expected_schema_version: int,
                   expected_database_id: str, live_database: Optional[Path] = None) -> Dict[str, Any]:
    """Restore to a new path only; never replace a live or existing database."""
    if not expected_database_id:
        raise ValueError("The expected ledger database identity is required")
    target = Path(target)
    if live_database and target.resolve() == Path(live_database).resolve():
        raise ValueError("Restore target must not be the live ledger")
    if target.exists() or Path(str(target) + "-wal").exists() or Path(str(target) + "-shm").exists():
        raise FileExistsError("Restore target or WAL state already exists")
    verified = verify_backup(
        Path(backup), Path(manifest), expected_schema_version, expected_database_id
    )
    if not verified.get("verified"):
        raise RuntimeError("Backup verification failed: " + "; ".join(verified["failures"]))
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".restore", dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with _read_only(Path(backup)) as source, sqlite3.connect(str(temporary), timeout=30) as destination:
            source.backup(destination, pages=256)
            destination.execute("PRAGMA journal_mode=DELETE")
            destination.execute("PRAGMA synchronous=FULL")
            destination.commit()
        recovered = audit_database(temporary, expected_schema_version)
        if (
            not recovered.get("healthy")
            or recovered.get("databaseId") != expected_database_id
            or recovered.get("logicalRoot") != verified.get("logicalRoot")
        ):
            raise RuntimeError("Recovered database failed identity or integrity verification")
        os.link(temporary, target)
        final = audit_database(target, expected_schema_version)
        if not final.get("healthy") or final.get("logicalRoot") != recovered.get("logicalRoot"):
            target.unlink(missing_ok=True)
            raise RuntimeError("Published restore failed recovery verification")
        return {
            "status": "restored", "target": str(target),
            "databaseId": expected_database_id, "logicalRoot": final["logicalRoot"],
            "verified": True,
        }
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    from universe_ledger import DEFAULT_DATABASE, SCHEMA_VERSION, UniverseLedger

    parser = argparse.ArgumentParser(description="Audit, back up, verify or restore Kestrel's ledger")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit")
    backup = commands.add_parser("backup")
    backup.add_argument("directory", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("backup", type=Path)
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--database-id")
    restore = commands.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument("manifest", type=Path)
    restore.add_argument("target", type=Path)
    restore.add_argument("--database-id", required=True)
    arguments = parser.parse_args()
    ledger = UniverseLedger(arguments.database)
    if arguments.command == "audit":
        result = ledger.audit()
    elif arguments.command == "backup":
        result = ledger.backup(arguments.directory)
    elif arguments.command == "verify":
        result = verify_backup(arguments.backup, arguments.manifest, SCHEMA_VERSION, arguments.database_id)
    else:
        result = ledger.restore(
            arguments.backup, arguments.manifest, arguments.target, arguments.database_id
        )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("healthy", result.get("verified", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
