"""Immutable, bitemporal investable-universe and evidence snapshots.

Kestrel's current security master answers "what do these tickers mean now?".
This ledger answers the harder research question: "what identity, membership and
evidence did Kestrel actually retain at a past decision cutoff?"

Rows are append-only.  Valid time describes the period an identity or outcome
applies to; recorded time describes when Kestrel learned it.  SQLite triggers
reject updates and deletes so a later correction becomes a new version rather
than silently rewriting a historical information set.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / ".kestrel-data" / "universe" / "universe-ledger.sqlite3"
SCHEMA_VERSION = 2
PROTOCOL_VERSION = "bitemporal-universe-v2"
COMPLETE_OUTCOMES = {"complete", "delisted_complete"}
OUTCOME_STATUSES = {"pending", "complete", "missing", "conflict", "delisted_complete"}
ADJUSTMENT_DEFINITIONS = {"point_in_time_total_return"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if len(raw) != 64:
        return None
    try:
        int(raw, 16)
    except ValueError:
        return None
    return raw


def _utc(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: Any) -> Optional[str]:
    try:
        return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(record: Dict[str, Any]) -> Optional[str]:
    supplied = str(record.get("securityId") or "").strip()
    if supplied:
        return supplied
    identifiers = record.get("identifiers") or {}
    for name in ("shareClassFigi", "figi", "compositeFigi"):
        value = str(identifiers.get(name) or "").strip()
        if value:
            return f"FIGI:{value}"
    cik = str(identifiers.get("cik") or "").strip()
    if cik:
        return f"CIK:{cik}"
    if str(record.get("assetClass") or "").lower() == "crypto":
        symbol = str(record.get("symbol") or record.get("ticker") or "").upper()
        return f"CRYPTO:{symbol}" if symbol else None
    return None


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class UniverseLedger:
    """Append-only SQLite ledger for prospective, reconstructable research."""

    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        self.database = Path(database)

    def connect(self, create: bool = True) -> sqlite3.Connection:
        if create:
            self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        if create:
            connection.execute("PRAGMA journal_mode=WAL")
            self._migrate(connection)
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ledger_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS universe_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                decision_date TEXT NOT NULL,
                cutoff_utc TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                model_version TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                selection_policy_version TEXT NOT NULL,
                status TEXT NOT NULL,
                manifest_hash TEXT NOT NULL UNIQUE,
                manifest_json TEXT NOT NULL,
                UNIQUE(decision_date, model_version, policy_version, selection_policy_version)
            );
            CREATE INDEX IF NOT EXISTS universe_snapshots_cutoff
                ON universe_snapshots(cutoff_utc);
            CREATE TABLE IF NOT EXISTS identity_versions (
                version_id TEXT PRIMARY KEY,
                security_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                recorded_at TEXT NOT NULL,
                identity_available_at TEXT,
                active INTEGER,
                identity_status TEXT NOT NULL,
                identifiers_json TEXT NOT NULL,
                listing_json TEXT NOT NULL,
                source_json TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                UNIQUE(security_id, valid_from, recorded_at, content_hash)
            );
            CREATE INDEX IF NOT EXISTS identity_versions_asof
                ON identity_versions(security_id, valid_from, valid_to, recorded_at);
            CREATE TABLE IF NOT EXISTS snapshot_members (
                snapshot_id TEXT NOT NULL,
                security_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                included INTEGER NOT NULL,
                active INTEGER,
                identity_clean INTEGER NOT NULL,
                membership_verified INTEGER NOT NULL,
                reason TEXT NOT NULL,
                identity_version_id TEXT NOT NULL,
                PRIMARY KEY(snapshot_id, security_id),
                FOREIGN KEY(snapshot_id) REFERENCES universe_snapshots(snapshot_id),
                FOREIGN KEY(identity_version_id) REFERENCES identity_versions(version_id)
            );
            CREATE TABLE IF NOT EXISTS evidence_versions (
                evidence_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                security_id TEXT,
                category TEXT NOT NULL,
                record_key TEXT NOT NULL,
                effective_at TEXT,
                available_at TEXT,
                retrieved_at TEXT NOT NULL,
                source TEXT NOT NULL,
                source_tier INTEGER,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES universe_snapshots(snapshot_id),
                UNIQUE(snapshot_id, category, record_key, payload_hash)
            );
            CREATE TABLE IF NOT EXISTS lookthrough_versions (
                lookthrough_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                as_of TEXT NOT NULL,
                available_at TEXT NOT NULL,
                complete INTEGER NOT NULL,
                source TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES universe_snapshots(snapshot_id),
                UNIQUE(snapshot_id, as_of, available_at, payload_hash)
            );
            CREATE TABLE IF NOT EXISTS outcome_versions (
                outcome_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                security_id TEXT NOT NULL,
                valid_through TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                status TEXT NOT NULL,
                delisted_on TEXT,
                proceeds REAL,
                currency TEXT,
                source TEXT NOT NULL,
                source_record_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES universe_snapshots(snapshot_id),
                UNIQUE(snapshot_id, security_id, valid_through, recorded_at, payload_hash)
            );
            CREATE INDEX IF NOT EXISTS outcome_versions_latest
                ON outcome_versions(snapshot_id, security_id, valid_through, recorded_at);
            """
        )
        # Version 2 makes the evidence clock and return definition first-class.
        # ALTER TABLE is deliberately additive so existing immutable rows remain
        # byte-for-byte untouched; old rows simply cannot certify the v2 protocol.
        outcome_columns = {row[1] for row in connection.execute("PRAGMA table_info(outcome_versions)")}
        additions = {
            "effective_at": "TEXT", "available_at": "TEXT", "retrieved_at": "TEXT",
            "listing_state": "TEXT", "adjustment_definition": "TEXT",
            "consideration_json": "TEXT", "source_record_hash": "TEXT",
            "evidence_hash": "TEXT",
        }
        for name, definition in additions.items():
            if name not in outcome_columns:
                connection.execute(f"ALTER TABLE outcome_versions ADD COLUMN {name} {definition}")
        immutable_tables = (
            "universe_snapshots", "identity_versions", "snapshot_members",
            "evidence_versions", "lookthrough_versions", "outcome_versions",
        )
        for table in immutable_tables:
            connection.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table} BEGIN
                    SELECT RAISE(ABORT, 'immutable ledger rows cannot be updated'); END"""
            )
            connection.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table} BEGIN
                    SELECT RAISE(ABORT, 'immutable ledger rows cannot be deleted'); END"""
            )
        connection.execute(
            "INSERT OR REPLACE INTO ledger_metadata(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        connection.commit()

    @staticmethod
    def _normalize_member(record: Dict[str, Any], decision_date: str, cutoff: str,
                          recorded_at: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ticker = str(record.get("ticker") or record.get("symbol") or "").upper().strip()
        security_id = _stable_id(record)
        valid_from = _date(record.get("validFrom")) or decision_date
        valid_to = _date(record.get("validTo")) if record.get("validTo") else None
        active = record.get("active") if isinstance(record.get("active"), bool) else None
        identity_status = str(record.get("identityStatus") or record.get("status") or "unresolved")
        identity_clean = bool(security_id and identity_status in {"resolved", "verified", "canonical"})
        identity_available_at = _utc(record.get("identityAvailableAt"))
        available_by_cutoff = bool(identity_available_at and identity_available_at <= cutoff)
        membership_verified = bool(record.get("membershipVerified") and available_by_cutoff)
        requested = record.get("included", True) is True
        included = bool(requested and identity_clean and active is not None and membership_verified)
        reasons = []
        if not security_id:
            reasons.append("stable identity missing")
            security_id = f"UNRESOLVED:{ticker or _digest(record)[:12]}"
        if not identity_clean:
            reasons.append("identity unresolved")
        if active is None:
            reasons.append("listing status missing")
        if not membership_verified:
            reasons.append("membership evidence unverified")
        if not available_by_cutoff:
            reasons.append("identity was not available by the cutoff")
        if not requested:
            reasons.append("selection policy excluded it")
        reason = "; ".join(reasons) or "Included by the frozen selection policy"
        identity_payload = {
            "securityId": security_id, "ticker": ticker, "validFrom": valid_from,
            "validTo": valid_to, "active": active, "identityStatus": identity_status,
            "identityAvailableAt": identity_available_at,
            "identifiers": record.get("identifiers") or {},
            "listing": record.get("listing") or {}, "sources": record.get("sources") or [],
        }
        content_hash = _digest(identity_payload)
        # An identical identity observation reuses the first recorded version;
        # a changed valid-time fact receives a different content-addressed ID.
        version_id = _digest(identity_payload)
        identity = {**identity_payload, "contentHash": content_hash,
                    "versionId": version_id, "recordedAt": recorded_at}
        member = {
            "securityId": security_id, "ticker": ticker, "included": included,
            "active": active, "identityClean": identity_clean,
            "membershipVerified": membership_verified, "reason": reason,
            "identityVersionId": version_id,
        }
        return identity, member

    @staticmethod
    def _normalize_evidence(row: Dict[str, Any], cutoff: str,
                            recorded_at: str) -> Dict[str, Any]:
        category = str(row.get("category") or "").strip()
        record_key = str(row.get("recordKey") or "").strip()
        source = str(row.get("source") or "").strip()
        retrieved_at = _utc(row.get("retrievedAt")) or recorded_at
        available_at = _utc(row.get("availableAt")) if row.get("availableAt") else None
        effective_at = _utc(row.get("effectiveAt")) if row.get("effectiveAt") else None
        if not category or not record_key or not source:
            raise ValueError("Evidence category, record key and source are required")
        if not retrieved_at or retrieved_at > cutoff:
            raise ValueError("Evidence retrieved after the snapshot cutoff cannot enter that snapshot")
        if available_at and available_at > cutoff:
            raise ValueError("Evidence published after the snapshot cutoff cannot enter that snapshot")
        tier = row.get("sourceTier")
        if tier is not None and tier not in {1, 2, 3, 4}:
            raise ValueError("Evidence source tier must be between 1 and 4")
        payload = row.get("payload")
        payload_hash = _digest(payload)
        normalized = {
            "securityId": row.get("securityId"), "category": category,
            "recordKey": record_key, "effectiveAt": effective_at,
            "availableAt": available_at, "retrievedAt": retrieved_at,
            "source": source, "sourceTier": tier, "payloadHash": payload_hash,
            "payload": payload,
        }
        normalized["evidenceId"] = _digest(normalized)
        return normalized

    @staticmethod
    def _normalize_lookthrough(row: Dict[str, Any], cutoff: str) -> Dict[str, Any]:
        as_of = _date(row.get("asOf"))
        available_at = _utc(row.get("availableAt"))
        source = str(row.get("source") or "").strip()
        if not as_of or not available_at or not source:
            raise ValueError("ETF look-through requires as-of date, exact availability time and source")
        if available_at > cutoff:
            raise ValueError("ETF look-through published after the cutoff cannot enter the snapshot")
        payload = row.get("payload") or {}
        payload_hash = _digest(payload)
        normalized = {
            "asOf": as_of, "availableAt": available_at,
            "complete": row.get("complete") is True, "source": source,
            "payloadHash": payload_hash, "payload": payload,
        }
        normalized["lookthroughId"] = _digest(normalized)
        return normalized

    def capture_snapshot(
        self, *, decision_date: str, cutoff_utc: str,
        model_version: str, policy_version: str, selection_policy_version: str,
        members: Sequence[Dict[str, Any]], evidence: Sequence[Dict[str, Any]] = (),
        lookthrough: Sequence[Dict[str, Any]] = (), controls: Optional[Dict[str, Any]] = None,
        recorded_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Freeze one decision information set; same-day changes are conflicts."""
        day = _date(decision_date)
        cutoff = _utc(cutoff_utc)
        recorded = _utc(recorded_at) if recorded_at else _now()
        if not day or not cutoff or not recorded:
            raise ValueError("Decision date, cutoff and recorded time must be valid ISO values")
        if not model_version or not policy_version or not selection_policy_version:
            raise ValueError("Model, evidence policy and selection policy versions are required")
        identities: List[Dict[str, Any]] = []
        normalized_members: List[Dict[str, Any]] = []
        for raw in members:
            identity, member = self._normalize_member(raw, day, cutoff, recorded)
            identities.append(identity)
            normalized_members.append(member)
        if not normalized_members:
            raise ValueError("At least one universe member is required")
        if len({row["securityId"] for row in normalized_members}) != len(normalized_members):
            raise ValueError("A stable security identity may appear only once per snapshot")
        normalized_evidence = [self._normalize_evidence(row, cutoff, recorded) for row in evidence]
        normalized_lookthrough = [self._normalize_lookthrough(row, cutoff) for row in lookthrough]
        control_values = {
            "selectionPolicyFrozen": bool((controls or {}).get("selectionPolicyFrozen")),
            "pointInTimePrices": bool((controls or {}).get("pointInTimePrices")),
            "adjustmentPolicy": (controls or {}).get("adjustmentPolicy"),
            "oneWayCostBps": _finite((controls or {}).get("oneWayCostBps")),
        }
        issues = []
        excluded = [row["ticker"] for row in normalized_members if not row["included"]]
        if excluded:
            issues.append("Unverified or excluded members: " + ", ".join(sorted(excluded)))
        if not control_values["selectionPolicyFrozen"]:
            issues.append("Selection policy is not frozen")
        if not control_values["pointInTimePrices"]:
            issues.append("Point-in-time price coverage is incomplete")
        if control_values["adjustmentPolicy"] != "point_in_time_total_return":
            issues.append("Corporate-action adjustment policy is not point-in-time")
        manifest = {
            "schemaVersion": SCHEMA_VERSION, "protocolVersion": PROTOCOL_VERSION,
            "decisionDate": day, "cutoffUtc": cutoff, "modelVersion": model_version,
            "policyVersion": policy_version,
            "selectionPolicyVersion": selection_policy_version,
            "members": sorted(normalized_members, key=lambda row: (row["ticker"], row["securityId"])),
            "identityHashes": sorted(row["contentHash"] for row in identities),
            "evidence": sorted((row["category"], row["recordKey"], row["payloadHash"],
                                row["availableAt"], row["retrievedAt"]) for row in normalized_evidence),
            "lookthrough": sorted((row["asOf"], row["availableAt"], row["payloadHash"],
                                   row["complete"]) for row in normalized_lookthrough),
            "controls": control_values, "issues": issues,
        }
        manifest_hash = _digest(manifest)
        snapshot_id = _digest({"manifestHash": manifest_hash, "cutoffUtc": cutoff})
        status = "complete" if not issues else "incomplete"
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT snapshot_id, manifest_hash, status FROM universe_snapshots
                   WHERE decision_date=? AND model_version=? AND policy_version=?
                   AND selection_policy_version=?""",
                (day, model_version, policy_version, selection_policy_version),
            ).fetchone()
            if existing:
                if existing["manifest_hash"] == manifest_hash:
                    return {"status": "unchanged", "snapshotId": existing["snapshot_id"],
                            "snapshotStatus": existing["status"], "manifestHash": manifest_hash,
                            "issues": issues}
                return {"status": "conflict", "snapshotId": existing["snapshot_id"],
                        "snapshotStatus": existing["status"], "manifestHash": existing["manifest_hash"],
                        "attemptedManifestHash": manifest_hash,
                        "reason": "A different immutable snapshot already exists for this decision date."}
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO universe_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (snapshot_id, day, cutoff, recorded, model_version, policy_version,
                 selection_policy_version, status, manifest_hash, _canonical(manifest)),
            )
            for identity in identities:
                connection.execute(
                    "INSERT OR IGNORE INTO identity_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (identity["versionId"], identity["securityId"], identity["ticker"],
                     identity["validFrom"], identity["validTo"], identity["recordedAt"],
                     identity["identityAvailableAt"],
                     None if identity["active"] is None else int(identity["active"]),
                     identity["identityStatus"], _canonical(identity["identifiers"]),
                     _canonical(identity["listing"]), _canonical(identity["sources"]),
                     identity["contentHash"]),
                )
            for member in normalized_members:
                connection.execute(
                    "INSERT INTO snapshot_members VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (snapshot_id, member["securityId"], member["ticker"], int(member["included"]),
                     None if member["active"] is None else int(member["active"]),
                     int(member["identityClean"]), int(member["membershipVerified"]),
                     member["reason"], member["identityVersionId"]),
                )
            for row in normalized_evidence:
                connection.execute(
                    "INSERT INTO evidence_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (row["evidenceId"], snapshot_id, row["securityId"], row["category"],
                     row["recordKey"], row["effectiveAt"], row["availableAt"], row["retrievedAt"],
                     row["source"], row["sourceTier"], row["payloadHash"], _canonical(row["payload"])),
                )
            for row in normalized_lookthrough:
                connection.execute(
                    "INSERT INTO lookthrough_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (row["lookthroughId"], snapshot_id, row["asOf"], row["availableAt"],
                     int(row["complete"]), row["source"], row["payloadHash"], _canonical(row["payload"])),
                )
            connection.commit()
        return {"status": "captured", "snapshotId": snapshot_id,
                "snapshotStatus": status, "manifestHash": manifest_hash, "issues": issues}

    def append_outcome(
        self, *, snapshot_id: str, security_id: str, valid_through: str,
        status: str, source: str, source_record_id: str,
        payload: Optional[Dict[str, Any]] = None, delisted_on: Optional[str] = None,
        proceeds: Optional[float] = None, currency: Optional[str] = None,
        recorded_at: Optional[str] = None,
        effective_at: Optional[str] = None, available_at: Optional[str] = None,
        retrieved_at: Optional[str] = None, listing_state: str = "active",
        adjustment_definition: Optional[str] = None,
        consideration: Optional[Dict[str, Any]] = None,
        source_record_hash: Optional[str] = None,
        evidence_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append a later outcome state; prior states remain untouched."""
        through = _date(valid_through)
        recorded = _utc(recorded_at) if recorded_at else _now()
        effective = _utc(effective_at) if effective_at else None
        available = _utc(available_at) if available_at else None
        retrieved = _utc(retrieved_at) if retrieved_at else None
        delisted = _date(delisted_on) if delisted_on else None
        if not through or not recorded or status not in OUTCOME_STATUSES:
            raise ValueError("Outcome date, recorded time or status is invalid")
        if not source.strip() or not source_record_id.strip():
            raise ValueError("Outcome source and source record ID are required")
        if not effective or not available or not retrieved:
            raise ValueError("Outcome effective, availability and retrieval times are required")
        if available > recorded or retrieved > recorded:
            raise ValueError("Late outcome evidence cannot enter an earlier recorded state")
        if available > retrieved:
            raise ValueError("Outcome evidence cannot be retrieved before it was available")
        if effective[:10] > through:
            raise ValueError("Outcome effective time cannot follow its valid-through date")
        if status in COMPLETE_OUTCOMES and recorded[:10] < through:
            raise ValueError("A complete outcome cannot be recorded before its valid-through date")
        normalized_currency = str(currency or "").strip().upper() or None
        if normalized_currency and (len(normalized_currency) != 3 or not normalized_currency.isalpha()):
            raise ValueError("Outcome currency must be an ISO 4217 code")
        if adjustment_definition not in ADJUSTMENT_DEFINITIONS:
            raise ValueError("A recognized point-in-time adjustment definition is required")
        normalized_source_hash = _sha256(source_record_hash)
        normalized_evidence_hash = _sha256(evidence_hash)
        if not normalized_source_hash:
            raise ValueError("A valid SHA-256 source record hash is required")
        if not normalized_evidence_hash:
            raise ValueError("A valid SHA-256 evidence hash is required")
        if status in COMPLETE_OUTCOMES and (not payload or not normalized_currency):
            raise ValueError("A complete outcome requires independent evidence and currency")
        consideration_body = consideration or {}
        if status == "delisted_complete":
            kind = str(consideration_body.get("kind") or "")
            cash_value = _finite(proceeds)
            cash_complete = kind in {"cash", "mixed"} and cash_value is not None and cash_value >= 0
            stock_complete = kind in {"stock", "mixed"} and bool(
                consideration_body.get("successorSecurityId")
                and (_finite(consideration_body.get("sharesPerShare")) or 0) > 0
            )
            if (not delisted or listing_state != "delisted" or not (cash_complete or stock_complete)):
                raise ValueError("A complete delisting requires dated listing and consideration evidence")
        body = payload or {}
        payload_hash = _digest(body)
        outcome = {
            "snapshotId": snapshot_id, "securityId": security_id,
            "validThrough": through, "recordedAt": recorded, "status": status,
            "effectiveAt": effective, "availableAt": available, "retrievedAt": retrieved,
            "listingState": listing_state, "adjustmentDefinition": adjustment_definition,
            "delistedOn": delisted, "proceeds": _finite(proceeds), "currency": normalized_currency,
            "consideration": consideration_body,
            "source": source, "sourceRecordId": source_record_id, "payloadHash": payload_hash,
            "sourceRecordHash": normalized_source_hash, "evidenceHash": normalized_evidence_hash,
        }
        outcome_id = _digest(outcome)
        with self.connect() as connection:
            member = connection.execute(
                "SELECT 1 FROM snapshot_members WHERE snapshot_id=? AND security_id=?",
                (snapshot_id, security_id),
            ).fetchone()
            if not member:
                raise ValueError("Outcome does not belong to a frozen universe member")
            existing = connection.execute(
                """SELECT outcome_id FROM outcome_versions
                   WHERE snapshot_id=? AND security_id=? AND status=? AND valid_through=?
                   AND source_record_id=? AND source_record_hash=? AND payload_hash=?""",
                (snapshot_id, security_id, status, through, source_record_id,
                 normalized_source_hash, payload_hash),
            ).fetchone()
            if existing:
                return {"status": "unchanged", "outcomeId": existing["outcome_id"]}
            connection.execute(
                """INSERT INTO outcome_versions
                   (outcome_id, snapshot_id, security_id, valid_through, recorded_at, status,
                    delisted_on, proceeds, currency, source, source_record_id, payload_hash,
                    payload_json, effective_at, available_at, retrieved_at, listing_state,
                    adjustment_definition, consideration_json, source_record_hash, evidence_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (outcome_id, snapshot_id, security_id, through, recorded, status, delisted,
                 _finite(proceeds), normalized_currency, source, source_record_id, payload_hash,
                 _canonical(body), effective, available, retrieved, listing_state,
                 adjustment_definition, _canonical(consideration_body), normalized_source_hash,
                 normalized_evidence_hash),
            )
            connection.commit()
        return {"status": "recorded", "outcomeId": outcome_id}

    def reconstruct(self, snapshot_id: str) -> Dict[str, Any]:
        """Rebuild and cryptographically verify one frozen information set."""
        with self.connect(create=False) as connection:
            snapshot = connection.execute(
                "SELECT * FROM universe_snapshots WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()
            if not snapshot:
                return {"status": "not_found", "snapshotId": snapshot_id}
            manifest = json.loads(snapshot["manifest_json"])
            members = [dict(row) for row in connection.execute(
                "SELECT * FROM snapshot_members WHERE snapshot_id=? ORDER BY ticker", (snapshot_id,)
            )]
            evidence = [dict(row) for row in connection.execute(
                "SELECT * FROM evidence_versions WHERE snapshot_id=? ORDER BY category, record_key", (snapshot_id,)
            )]
            lookthrough = [dict(row) for row in connection.execute(
                "SELECT * FROM lookthrough_versions WHERE snapshot_id=? ORDER BY available_at", (snapshot_id,)
            )]
        payloads_clean = all(_digest(json.loads(row["payload_json"])) == row["payload_hash"]
                             for row in [*evidence, *lookthrough])
        manifest_clean = _digest(manifest) == snapshot["manifest_hash"]
        return {
            "status": "verified" if payloads_clean and manifest_clean else "corrupt",
            "snapshotId": snapshot_id, "decisionDate": snapshot["decision_date"],
            "cutoffUtc": snapshot["cutoff_utc"], "recordedAt": snapshot["recorded_at"],
            "snapshotStatus": snapshot["status"], "manifestHash": snapshot["manifest_hash"],
            "manifest": manifest, "members": members, "evidence": evidence,
            "lookthrough": lookthrough, "manifestClean": manifest_clean,
            "payloadsClean": payloads_clean,
        }

    def latest(self) -> Dict[str, Any]:
        if not self.database.exists():
            return {"status": "empty", "database": str(self.database), "snapshots": 0}
        with self.connect(create=False) as connection:
            row = connection.execute(
                "SELECT snapshot_id FROM universe_snapshots ORDER BY cutoff_utc DESC LIMIT 1"
            ).fetchone()
            counts = {
                "snapshots": connection.execute("SELECT COUNT(*) FROM universe_snapshots").fetchone()[0],
                "identityVersions": connection.execute("SELECT COUNT(*) FROM identity_versions").fetchone()[0],
                "evidenceVersions": connection.execute("SELECT COUNT(*) FROM evidence_versions").fetchone()[0],
                "outcomeVersions": connection.execute("SELECT COUNT(*) FROM outcome_versions").fetchone()[0],
            }
            latest_outcomes: Dict[Tuple[str, str], str] = {}
            for outcome in connection.execute(
                """SELECT snapshot_id, security_id, status FROM outcome_versions
                   ORDER BY recorded_at, rowid"""
            ):
                latest_outcomes[(outcome["snapshot_id"], outcome["security_id"])] = outcome["status"]
            outcome_states: Dict[str, int] = {}
            for state in latest_outcomes.values():
                outcome_states[state] = outcome_states.get(state, 0) + 1
            counts["outcomeStates"] = outcome_states
        if not row:
            return {"status": "empty", "database": str(self.database), **counts}
        return {"status": "ready", "database": str(self.database), **counts,
                "latest": self.reconstruct(row["snapshot_id"])}

    def build_protocol(self, snapshot_id: str, expected_symbols: Iterable[str],
                       benchmark: str, one_way_cost_bps: float) -> Dict[str, Any]:
        """Produce the only protocol shape allowed to certify walk-forward data."""
        rebuilt = self.reconstruct(snapshot_id)
        expected = sorted({str(symbol).upper() for symbol in expected_symbols})
        if rebuilt.get("status") != "verified":
            return {"status": "blocked", "ledgerVerified": False,
                    "failures": ["The immutable snapshot could not be verified"]}
        by_ticker = {row["ticker"]: row for row in rebuilt["members"]}
        with self.connect(create=False) as connection:
            related_ids = [row[0] for row in connection.execute(
                """SELECT snapshot_id FROM universe_snapshots
                   WHERE decision_date>=? AND model_version=? AND policy_version=?
                   AND selection_policy_version=? ORDER BY cutoff_utc""",
                (rebuilt["decisionDate"], rebuilt["manifest"]["modelVersion"],
                 rebuilt["manifest"]["policyVersion"],
                 rebuilt["manifest"]["selectionPolicyVersion"]),
            )]
            outcomes: Dict[str, Dict[str, Any]] = {}
            for member in rebuilt["members"]:
                row = connection.execute(
                    """SELECT * FROM outcome_versions WHERE snapshot_id=? AND security_id=?
                       ORDER BY recorded_at DESC, rowid DESC LIMIT 1""",
                    (snapshot_id, member["security_id"]),
                ).fetchone()
                outcomes[member["ticker"]] = dict(row) if row else {}
        universe_records = {}
        for symbol in expected:
            member = by_ticker.get(symbol) or {}
            outcome = outcomes.get(symbol) or {}
            try:
                consideration_kind = str(json.loads(outcome.get("consideration_json") or "{}").get("kind") or "")
            except (AttributeError, TypeError, json.JSONDecodeError):
                consideration_kind = ""
            universe_records[symbol] = {
                "securityId": member.get("security_id"),
                "includedAtFreeze": bool(member.get("included")),
                "activeAtFreeze": None if member.get("active") is None else bool(member.get("active")),
                "membershipVerified": bool(member.get("membership_verified")),
                "outcomeComplete": outcome.get("status") in COMPLETE_OUTCOMES,
                "delisted": outcome.get("status") == "delisted_complete",
                "validThrough": outcome.get("valid_through"),
                "outcomeStatus": outcome.get("status") or "pending",
                "listingState": outcome.get("listing_state") or "unknown",
                "currency": outcome.get("currency"),
                "adjustmentDefinition": outcome.get("adjustment_definition"),
                "considerationKind": consideration_kind or None,
            }
        chain = [self.reconstruct(value) for value in related_ids]
        chain_clean = bool(chain) and all(item.get("status") == "verified" for item in chain)
        lookthrough_by_version: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for frozen in chain:
            for row in frozen.get("lookthrough") or []:
                payload = json.loads(row["payload_json"])
                lookthrough_by_version[(row["payload_hash"], row["available_at"])] = {
                    **payload, "asOf": row["as_of"], "availableAt": row["available_at"][:10],
                    "complete": bool(row["complete"]), "contentHash": row["payload_hash"],
                }
        lookthrough = sorted(
            lookthrough_by_version.values(), key=lambda row: (row["availableAt"], row["contentHash"])
        )
        control_chain = [item["manifest"].get("controls") or {} for item in chain if item.get("manifest")]
        latest_chain_date = max(
            (_date(item.get("decisionDate")) for item in chain), default=rebuilt["decisionDate"]
        ) or rebuilt["decisionDate"]
        one_year = (dt.date.fromisoformat(rebuilt["decisionDate"]) + dt.timedelta(days=365)).isoformat()
        required_through = max(latest_chain_date, one_year)
        for record in universe_records.values():
            terminal = record["delisted"] and record.get("considerationKind") == "cash"
            record["outcomeComplete"] = bool(
                record["outcomeComplete"] and
                (terminal or str(record.get("validThrough") or "") >= required_through)
                and record.get("currency")
                and record.get("adjustmentDefinition") == "point_in_time_total_return"
            )
            record["requiredThrough"] = required_through
        all_records = all(
            record["includedAtFreeze"] and record["membershipVerified"]
            and record["outcomeComplete"] and record["securityId"]
            for record in universe_records.values()
        )
        return {
            "status": "ready" if all_records else "accumulating",
            "protocolVersion": PROTOCOL_VERSION, "ledgerVerified": chain_clean,
            "snapshotIds": [item["snapshotId"] for item in chain],
            "manifestHashes": [item["manifestHash"] for item in chain],
            "modelVersion": rebuilt["manifest"]["modelVersion"],
            "frozenAt": rebuilt["decisionDate"], "universe": expected,
            "universeRecords": universe_records, "benchmark": benchmark,
            "survivorshipFree": all_records,
            "selectionPolicyFrozen": bool(control_chain) and all(
                item.get("selectionPolicyFrozen") is True for item in control_chain
            ),
            "pointInTimePrices": bool(control_chain) and all(
                item.get("pointInTimePrices") is True for item in control_chain
            ),
            "adjustmentPolicy": (
                "point_in_time_total_return"
                if control_chain and all(item.get("adjustmentPolicy") == "point_in_time_total_return"
                                         for item in control_chain)
                else "unverified"
            ),
            "oneWayCostBps": one_way_cost_bps,
            "lookthroughSnapshots": lookthrough,
            "message": ("The frozen universe has complete outcomes."
                        if all_records else "The frozen universe is valid and is accumulating future outcomes."),
        }


def security_master_members(snapshot: Dict[str, Any], symbols: Iterable[str],
                            market_data: Optional[Dict[str, Any]] = None,
                            cutoff_utc: Optional[str] = None) -> List[Dict[str, Any]]:
    """Conservatively adapt the live master into prospective member records."""
    records = snapshot.get("instruments") or {}
    data = market_data or {}
    cutoff = _utc(cutoff_utc) if cutoff_utc else None
    members = []
    for symbol in dict.fromkeys(str(value).upper() for value in symbols if value):
        record = dict(records.get(symbol) or {})
        quote = (data.get(symbol) or {}).get("quote") or {}
        quote_price = _finite(quote.get("c"))
        quote_time = quote.get("t")
        try:
            quote_at = dt.datetime.fromtimestamp(int(quote_time), tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OSError):
            quote_at = None
        resolved_at = record.get("resolvedAt")
        try:
            identity_at = dt.datetime.fromtimestamp(int(resolved_at), tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OSError):
            identity_at = None
        current_quote = bool(
            quote_price and quote_price > 0 and quote_at and identity_at
            and (not cutoff or (quote_at <= cutoff and identity_at <= cutoff))
        )
        record.update({
            "ticker": symbol, "active": True if current_quote else None,
            "identityAvailableAt": identity_at,
            "identityStatus": ("canonical" if record.get("assetClass") == "crypto"
                               and record.get("status") == "partial" else record.get("status")),
            "membershipVerified": bool(
                current_quote and (record.get("status") == "resolved"
                                   or record.get("assetClass") == "crypto")
            ),
            "included": True,
        })
        members.append(record)
    return members


def market_evidence(data: Dict[str, Any], cutoff_utc: str) -> List[Dict[str, Any]]:
    """Freeze cached per-symbol evidence, using retrieval as a conservative availability time."""
    cutoff = _utc(cutoff_utc)
    if not cutoff:
        raise ValueError("A valid cutoff is required")
    rows = []
    for symbol, payload in sorted(data.items()):
        if not isinstance(payload, dict):
            continue
        fetched = payload.get("fetchedAt")
        try:
            retrieved = dt.datetime.fromtimestamp(int(fetched), tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OSError):
            continue
        if retrieved > cutoff:
            continue
        rows.append({
            "securityId": None, "category": "live_symbol_evidence",
            "recordKey": symbol, "availableAt": retrieved, "retrievedAt": retrieved,
            "source": "Kestrel cached SEC, market and analyst evidence",
            "sourceTier": 3, "payload": payload,
        })
    return rows
