# Universe ledger operations

The private universe and outcome ledger is append-only. Its operational status is
reported by `/api/universe-ledger` under `health`; `healthy` is the only state that
permits the daily workflow to write or publish a backup. A failed SQLite check,
foreign key, schema or migration check, missing immutable trigger, malformed JSON,
or content-hash mismatch blocks the workflow before it changes the ledger.

Connections use WAL mode, full synchronous commits, foreign-key enforcement, a
30-second busy timeout and immediate write transactions. The daily workflow audits
before writing, freezes the universe, appends outcomes, audits again, then creates a
backup. It never changes valuation, risk, universe, price/action, outcome or
five-window eligibility gates.

## Audit and backup

Run a read-only deterministic audit:

```sh
python3 ledger_maintenance.py audit
```

Create a backup on demand:

```sh
python3 ledger_maintenance.py backup .kestrel-data/universe/backups
```

SQLite's online backup API reads one consistent transaction even while WAL writes
continue. The result is converted to a standalone non-WAL database, audited, and
stored as `<sha256>.sqlite3` with `<sha256>.json`. Repeating a backup of identical
content is idempotent. A damaged live ledger is never backed up.

Verify a backup without restoring it:

```sh
python3 ledger_maintenance.py verify BACKUP.sqlite3 BACKUP.json --database-id DATABASE_ID
```

The database ID is shown by `audit`. Verification checks the manifest, database
identity, exact schema version, size, SHA-256, standalone WAL state, SQLite and
foreign-key integrity, immutable triggers, every retained content address and the
deterministic logical root.

## Recovery

Restore is deliberately separate from the daily workflow and always targets a new,
absent path:

```sh
python3 ledger_maintenance.py restore BACKUP.sqlite3 BACKUP.json RECOVERY.sqlite3 \
  --database-id DATABASE_ID
```

Restore fails closed if the target is the live ledger or already exists, the backup
belongs to another database, its hash or logical root differs, WAL state is present,
the schema is incompatible, or recovery verification fails. It never silently
replaces the live file. After a successful restore, inspect the reported health and
logical root before explicitly reconfiguring or moving any live database. Keep the
original ledger and credentials untouched during that review.

Schema migrations are additive and versioned. Startup accepts only known prior
versions with the complete expected source schema, applies missing versions once,
recreates immutable protection for the new migration history, and rejects future,
unversioned or partial schemas.
