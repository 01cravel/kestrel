"""Auditable, resumable Massive US-market history for Kestrel's swing radar.

The archive deliberately keeps price observations separate from investability
policy.  Downstream models can use ``iter_daily_bars`` and join the point-in-time
reference snapshot without silently losing delisted or unresolved symbols.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import random
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from swing_radar_policy import (
    POLICY_VERSION, PRIMARY_HORIZON_SESSIONS, SECONDARY_HORIZON_SESSIONS,
    assess_investability, label_forward_return,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / ".kestrel-data" / "market-history"
DEFAULT_DATABASE = DEFAULT_DATA_DIR / "market-history.sqlite3"
SECRETS_PATH = ROOT / ".kestrel-secrets.json"
BASE_URL = "https://api.massive.com"
SCHEMA_VERSION = 1
SOURCE_NAME = "Massive Stocks REST API"
SOURCE_DOCS = "https://massive.com/docs/rest/stocks"
DEFAULT_REQUESTS_PER_MINUTE = 5
LABEL_TAIL_CALENDAR_DAYS = 14
MASSIVE_SECURITY_TYPE_MAP = {
    "CS": "common_stock", "ADRC": "adr", "ADRP": "adr", "GDR": "adr",
}


def load_private_key(name: str) -> str:
    """Read a local key without ever putting it in the source tree."""
    configured = os.environ.get(name, "").strip()
    if configured:
        return configured
    try:
        secrets = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        value = secrets.get(name) if isinstance(secrets, dict) else None
        return str(value or "").strip()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("dates must use YYYY-MM-DD") from error


def default_range(today: Optional[dt.date] = None) -> Tuple[dt.date, dt.date]:
    anchor = today or dt.date.today()
    # Keep the oldest request inside Massive's two-year free-plan boundary.
    # The newest 14 days are reserved for labels to mature, so the trainable
    # portion is slightly shorter than the downloaded price window.
    return (
        anchor - dt.timedelta(days=730),
        anchor - dt.timedelta(days=LABEL_TAIL_CALENDAR_DAYS),
    )


def latest_completed_market_date(now: Optional[dt.datetime] = None) -> dt.date:
    """Return the latest US weekday whose normal close is safely complete."""
    instant = now or dt.datetime.now(dt.timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("now must include a timezone")
    new_york = instant.astimezone(ZoneInfo("America/New_York"))
    candidate = new_york.date()
    if new_york.time() < dt.time(16, 15):
        candidate -= dt.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= dt.timedelta(days=1)
    return candidate


def weekdays(start: dt.date, end: dt.date) -> Iterator[dt.date]:
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            yield cursor
        cursor += dt.timedelta(days=1)


def _number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else None
    except (TypeError, ValueError):
        return None


class MassiveError(RuntimeError):
    """A safe error which never includes the API key."""


class RateLimiter:
    def __init__(self, requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        self.gap = 60.0 / requests_per_minute
        self.last_request = 0.0

    def wait(self) -> None:
        remaining = self.gap - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)

    def mark(self) -> None:
        self.last_request = time.monotonic()


class MassiveClient:
    """Small REST client with header authentication, retries and pagination."""

    def __init__(
        self,
        api_key: str,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        max_retries: int = 5,
        opener: Optional[Callable[..., Any]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key.strip():
            raise MassiveError("MASSIVE_API_KEY is not configured")
        self._api_key = api_key.strip()
        self._limiter = RateLimiter(requests_per_minute)
        self._max_retries = max_retries
        self._opener = opener or urllib.request.urlopen
        self._sleep = sleep

    def get(self, path_or_url: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], bytes, int]:
        if path_or_url.startswith("http"):
            parsed = urllib.parse.urlsplit(path_or_url)
            if parsed.scheme != "https" or parsed.netloc != "api.massive.com":
                raise MassiveError("Massive returned an unsafe pagination URL")
            url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
        else:
            query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
            url = BASE_URL + path_or_url + ("?" + query if query else "")
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Accept": "application/json",
                "User-Agent": "Kestrel local swing-radar research",
            },
        )
        for attempt in range(self._max_retries + 1):
            self._limiter.wait()
            try:
                with self._opener(request, timeout=45) as response:
                    self._limiter.mark()
                    body = response.read()
                    status = int(getattr(response, "status", 200))
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise MassiveError("Massive returned an unexpected response shape")
                return payload, body, status
            except urllib.error.HTTPError as error:
                self._limiter.mark()
                if error.code in {401, 403}:
                    raise MassiveError("Massive authentication or plan access was rejected") from error
                if error.code == 429 or 500 <= error.code < 600:
                    if attempt < self._max_retries:
                        retry_after = error.headers.get("Retry-After") if error.headers else None
                        delay = float(retry_after) if retry_after and retry_after.isdigit() else min(60.0, 2 ** attempt + random.random())
                        self._sleep(delay)
                        continue
                raise MassiveError("Massive returned HTTP %s" % error.code) from error
            except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
                self._limiter.mark()
                if attempt < self._max_retries:
                    self._sleep(min(60.0, 2 ** attempt + random.random()))
                    continue
                raise MassiveError("Massive was unavailable after retries") from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise MassiveError("Massive returned invalid JSON") from error
        raise MassiveError("Massive request failed")


class MarketHistoryStore:
    """SQLite data contract used by ingestion and later training phases."""

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
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fetch_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL, parameters_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL, http_status INTEGER NOT NULL,
                request_id TEXT, sha256 TEXT NOT NULL UNIQUE, raw_path TEXT NOT NULL,
                row_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_date TEXT PRIMARY KEY, status TEXT NOT NULL,
                row_count INTEGER NOT NULL, adjusted INTEGER NOT NULL,
                request_id TEXT, fetched_at TEXT NOT NULL, raw_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daily_bars (
                session_date TEXT NOT NULL, ticker TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                volume_weighted REAL, trades INTEGER, window_start_ms INTEGER,
                adjusted INTEGER NOT NULL, source TEXT NOT NULL,
                source_request_id TEXT, source_fetched_at TEXT NOT NULL,
                raw_sha256 TEXT NOT NULL,
                PRIMARY KEY (session_date, ticker)
            );
            CREATE INDEX IF NOT EXISTS daily_bars_ticker_date
                ON daily_bars(ticker, session_date);
            CREATE TABLE IF NOT EXISTS reference_snapshots (
                snapshot_date TEXT NOT NULL, ticker TEXT NOT NULL, active INTEGER NOT NULL,
                name TEXT, market TEXT, locale TEXT, currency TEXT, primary_exchange TEXT,
                security_type TEXT, cik TEXT, composite_figi TEXT, share_class_figi TEXT,
                delisted_utc TEXT, last_updated_utc TEXT, eligible_equity INTEGER NOT NULL,
                source_request_id TEXT, source_fetched_at TEXT NOT NULL,
                raw_sha256 TEXT NOT NULL,
                PRIMARY KEY (snapshot_date, ticker, active)
            );
            CREATE TABLE IF NOT EXISTS corporate_actions (
                action_kind TEXT NOT NULL, event_id TEXT NOT NULL, ticker TEXT,
                event_date TEXT, payload_json TEXT NOT NULL,
                source_request_id TEXT, source_fetched_at TEXT NOT NULL,
                raw_sha256 TEXT NOT NULL,
                PRIMARY KEY (action_kind, event_id)
            );
            CREATE TABLE IF NOT EXISTS swing_observations (
                security_id TEXT NOT NULL, session_date TEXT NOT NULL,
                cutoff_utc TEXT NOT NULL, ticker TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                exchange_mic TEXT, security_type TEXT, active INTEGER,
                identity_clean INTEGER, corporate_actions_clean INTEGER,
                currency TEXT, adjusted_close REAL, spy_adjusted_close REAL,
                market_cap REAL, median_dollar_volume_20d REAL, prior_sessions INTEGER,
                split_flag INTEGER NOT NULL, dividend_flag INTEGER NOT NULL,
                eligibility_status TEXT NOT NULL, eligibility_json TEXT NOT NULL,
                reference_snapshot_date TEXT, source_available_at TEXT,
                source_retrieved_at TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
                stock_close_t1 REAL, spy_close_t1 REAL, stock_close_t5 REAL, spy_close_t5 REAL,
                label_t1_json TEXT, label_t5_json TEXT,
                PRIMARY KEY (security_id, session_date, policy_version)
            );
            CREATE INDEX IF NOT EXISTS swing_observations_date
                ON swing_observations(session_date, eligibility_status);
            CREATE INDEX IF NOT EXISTS swing_observations_ticker_date
                ON swing_observations(ticker, session_date);
            CREATE TABLE IF NOT EXISTS issuer_events (
                ticker TEXT NOT NULL, cik TEXT, event_type TEXT NOT NULL,
                event_date TEXT NOT NULL, published_at TEXT NOT NULL,
                available_at TEXT NOT NULL, value REAL, detail TEXT,
                accession TEXT NOT NULL, source TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                PRIMARY KEY (ticker, event_type, accession, event_date, detail)
            );
            CREATE INDEX IF NOT EXISTS issuer_events_lookup
                ON issuer_events(ticker, available_at);
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        connection.commit()

    def completed_dates(self, start: dt.date, end: dt.date) -> set:
        if not self.database.exists():
            return set()
        with self.connect(create=False) as connection:
            rows = connection.execute(
                "SELECT session_date FROM sessions WHERE session_date BETWEEN ? AND ? AND status IN ('complete', 'no_data')",
                (start.isoformat(), end.isoformat()),
            )
            return {dt.date.fromisoformat(row[0]) for row in rows}

    def status(self) -> Dict[str, Any]:
        if not self.database.exists():
            return {"status": "empty", "database": str(self.database), "sessions": 0, "bars": 0}
        with self.connect(create=False) as connection:
            result = {
                "status": "ready",
                "database": str(self.database),
                "sessions": connection.execute("SELECT COUNT(*) FROM sessions WHERE status='complete'").fetchone()[0],
                "noDataWeekdays": connection.execute("SELECT COUNT(*) FROM sessions WHERE status='no_data'").fetchone()[0],
                "bars": connection.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0],
                "symbols": connection.execute("SELECT COUNT(DISTINCT ticker) FROM daily_bars").fetchone()[0],
                "referenceRecords": connection.execute("SELECT COUNT(*) FROM reference_snapshots").fetchone()[0],
                "corporateActions": connection.execute("SELECT COUNT(*) FROM corporate_actions").fetchone()[0],
                "swingObservations": connection.execute("SELECT COUNT(*) FROM swing_observations").fetchone()[0],
            }
            extent = connection.execute("SELECT MIN(session_date), MAX(session_date) FROM daily_bars").fetchone()
            result["firstSession"], result["lastSession"] = extent[0], extent[1]
            return result

    def iter_daily_bars(self, start: str, end: str) -> Iterator[Dict[str, Any]]:
        """Stable Phase 2 -> modelling contract; one adjusted observation per ticker/day."""
        with self.connect(create=False) as connection:
            rows = connection.execute(
                "SELECT * FROM daily_bars WHERE session_date BETWEEN ? AND ? ORDER BY session_date, ticker",
                (start, end),
            )
            for row in rows:
                yield dict(row)

    def iter_swing_observations(self, start: str, end: str) -> Iterator[Dict[str, Any]]:
        """Return the versioned Phase 1 rows ready for chronological modelling."""
        with self.connect(create=False) as connection:
            rows = connection.execute(
                """SELECT * FROM swing_observations
                   WHERE session_date BETWEEN ? AND ? AND policy_version=?
                   ORDER BY session_date, security_id""", (start, end, POLICY_VERSION)
            )
            for row in rows:
                result = dict(row)
                for field in ("eligibility_json", "label_t1_json", "label_t5_json"):
                    result[field] = json.loads(result[field]) if result.get(field) else None
                yield result


class MarketHistoryPipeline:
    def __init__(self, client: MassiveClient, store: MarketHistoryStore) -> None:
        self.client = client
        self.store = store
        self.raw_dir = store.database.parent / "raw"

    def _archive(
        self, connection: sqlite3.Connection, endpoint: str, parameters: Dict[str, Any],
        payload: Dict[str, Any], body: bytes, status: int, category: str,
    ) -> Tuple[str, str, str]:
        digest = hashlib.sha256(body).hexdigest()
        fetched_at = utc_now()
        request_id = str(payload.get("request_id") or "")
        relative = Path("raw") / category / (digest + ".json.gz")
        destination = self.store.database.parent / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_suffix(".tmp")
            with gzip.open(str(temporary), "wb") as handle:
                handle.write(body)
            temporary.replace(destination)
        results = payload.get("results")
        row_count = len(results) if isinstance(results, list) else 0
        connection.execute(
            """INSERT OR IGNORE INTO fetch_audit
               (endpoint, parameters_json, fetched_at, http_status, request_id, sha256, raw_path, row_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (endpoint, json.dumps(parameters, sort_keys=True), fetched_at, status, request_id,
             digest, str(relative), row_count),
        )
        return digest, fetched_at, request_id

    def sync_sessions(self, start: dt.date, end: dt.date, include_otc: bool = False) -> Dict[str, int]:
        completed = self.store.completed_dates(start, end)
        counts = {"downloaded": 0, "resumed": len(completed), "bars": 0, "no_data": 0}
        with self.store.connect() as connection:
            for session_date in weekdays(start, end):
                if session_date in completed:
                    continue
                params = {"adjusted": "true", "include_otc": str(include_otc).lower()}
                path = "/v2/aggs/grouped/locale/us/market/stocks/" + session_date.isoformat()
                payload, body, status = self.client.get(path, params)
                digest, fetched_at, request_id = self._archive(
                    connection, path, params, payload, body, status, "grouped-daily"
                )
                rows = payload.get("results") or []
                if not isinstance(rows, list):
                    raise MassiveError("Grouped Daily results were not a list")
                valid = []
                for row in rows:
                    if not isinstance(row, dict) or not str(row.get("T") or "").strip():
                        continue
                    ticker = str(row["T"]).strip().upper()
                    valid.append((
                        session_date.isoformat(), ticker, _number(row.get("o")), _number(row.get("h")),
                        _number(row.get("l")), _number(row.get("c")), _number(row.get("v")),
                        _number(row.get("vw")), int(row["n"]) if row.get("n") is not None else None,
                        int(row["t"]) if row.get("t") is not None else None, 1, SOURCE_NAME,
                        request_id, fetched_at, digest,
                    ))
                connection.executemany(
                    """INSERT OR REPLACE INTO daily_bars VALUES
                       (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", valid
                )
                state = "complete" if valid else "no_data"
                connection.execute(
                    "INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, 1, ?, ?, ?)",
                    (session_date.isoformat(), state, len(valid), request_id, fetched_at, digest),
                )
                connection.commit()
                counts["downloaded"] += 1
                counts["bars"] += len(valid)
                if not valid:
                    counts["no_data"] += 1
        return counts

    def _pages(self, path: str, params: Dict[str, Any], category: str) -> Iterator[Tuple[List[Dict[str, Any]], str, str, str]]:
        next_url: Optional[str] = path
        next_params: Optional[Dict[str, Any]] = params
        with self.store.connect() as connection:
            while next_url:
                payload, body, status = self.client.get(next_url, next_params)
                digest, fetched_at, request_id = self._archive(
                    connection, path, next_params or {"pagination": True}, payload, body, status, category
                )
                connection.commit()
                rows = payload.get("results") or []
                if not isinstance(rows, list):
                    raise MassiveError("Massive paginated results were not a list")
                yield [row for row in rows if isinstance(row, dict)], digest, fetched_at, request_id
                next_url = payload.get("next_url")
                next_params = None

    def sync_reference(
        self, snapshot_date: dt.date, *, include_active: bool = True, include_inactive: bool = True,
    ) -> int:
        total = 0
        with self.store.connect() as connection:
            active_states = ([True] if include_active else []) + ([False] if include_inactive else [])
            for active in active_states:
                params = {
                    "market": "stocks", "locale": "us", "active": str(active).lower(),
                    "date": snapshot_date.isoformat(), "limit": 1000, "sort": "ticker", "order": "asc",
                }
                for rows, digest, fetched_at, request_id in self._pages("/v3/reference/tickers", params, "reference"):
                    values = []
                    for row in rows:
                        ticker = str(row.get("ticker") or "").strip().upper()
                        if not ticker:
                            continue
                        raw_security_type = str(row.get("type") or "").upper()
                        values.append((
                            snapshot_date.isoformat(), ticker, int(active), row.get("name"), row.get("market"),
                            row.get("locale"), row.get("currency_name") or row.get("currency_symbol"),
                            row.get("primary_exchange"), raw_security_type, row.get("cik"), row.get("composite_figi"),
                            row.get("share_class_figi"), row.get("delisted_utc"), row.get("last_updated_utc"),
                            int(raw_security_type in MASSIVE_SECURITY_TYPE_MAP), request_id, fetched_at, digest,
                        ))
                    connection.executemany(
                        "INSERT OR REPLACE INTO reference_snapshots VALUES (%s)" % ",".join("?" * 18), values
                    )
                    connection.commit()
                    total += len(values)
        return total

    def sync_reference_timeline(self, start: dt.date, end: dt.date) -> int:
        """Keep monthly point-in-time identities plus all delisted identities.

        A traded bar proves daily activity. Monthly snapshots preserve identity
        vintages without turning a two-year free-plan backfill into thousands of
        reference pages. New listings remain unresolved until the next snapshot.
        """
        snapshots = {start, end}
        cursor = dt.date(start.year, start.month, 1)
        while cursor <= end:
            next_month = (
                dt.date(cursor.year + 1, 1, 1) if cursor.month == 12
                else dt.date(cursor.year, cursor.month + 1, 1)
            )
            month_end = min(end, next_month - dt.timedelta(days=1))
            if month_end >= start:
                snapshots.add(month_end)
            cursor = next_month
        total = 0
        for snapshot in sorted(snapshots):
            total += self.sync_reference(snapshot, include_active=True, include_inactive=False)
        total += self.sync_reference(end, include_active=False, include_inactive=True)
        return total

    def sync_actions(self, start: dt.date, end: dt.date) -> int:
        total = 0
        endpoints = (
            ("split", "/stocks/v1/splits", "execution_date"),
            ("dividend", "/stocks/v1/dividends", "ex_dividend_date"),
        )
        with self.store.connect() as connection:
            for kind, path, date_field in endpoints:
                params = {
                    date_field + ".gte": start.isoformat(), date_field + ".lte": end.isoformat(),
                    "limit": 5000, "sort": date_field + ".asc",
                }
                for rows, digest, fetched_at, request_id in self._pages(path, params, "corporate-actions"):
                    values = []
                    for row in rows:
                        event_id = str(row.get("id") or hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest())
                        values.append((kind, event_id, row.get("ticker"), row.get(date_field),
                                       json.dumps(row, sort_keys=True), request_id, fetched_at, digest))
                    connection.executemany("INSERT OR REPLACE INTO corporate_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
                    connection.commit()
                    total += len(values)
            connection.execute("INSERT OR REPLACE INTO metadata VALUES('actions_start', ?)", (start.isoformat(),))
            connection.execute("INSERT OR REPLACE INTO metadata VALUES('actions_end', ?)", (end.isoformat(),))
            connection.execute("INSERT OR REPLACE INTO metadata VALUES('actions_retrieved_at', ?)", (utc_now(),))
            connection.commit()
        return total

    def build_observations(self, start: dt.date, end: dt.date,
                           tickers: Optional[Sequence[str]] = None,
                           progress: Optional[Any] = None) -> int:
        """Materialise the Phase 1 contract without filling unavailable facts.

        Grouped Daily contains no point-in-time market cap, so market_cap remains
        NULL and ``assess_investability`` returns unknown. That is intentional.

        ``tickers`` restricts the build to a chosen universe; the benchmark is
        always included because every row needs it. Work is committed after each
        security and progress is reported, so a build interrupted after an hour
        keeps everything it had already finished rather than discarding it.
        """
        selected = None
        if tickers:
            selected = {ticker.upper() for ticker in tickers}
            selected.add("SPY")
        label_end = end + dt.timedelta(days=LABEL_TAIL_CALENDAR_DAYS)
        with self.store.connect() as connection:
            action_extent = {
                row[0]: row[1] for row in connection.execute(
                    "SELECT key, value FROM metadata WHERE key IN ('actions_start', 'actions_end')"
                )
            }
            actions_clean_range = (
                action_extent.get("actions_start", "9999-12-31") <= start.isoformat()
                and action_extent.get("actions_end", "0001-01-01") >= end.isoformat()
            )
            actions_clean_tail = action_extent.get("actions_end", "0001-01-01") >= label_end.isoformat()
            action_rows = connection.execute(
                "SELECT action_kind, ticker, event_date, payload_json FROM corporate_actions WHERE event_date BETWEEN ? AND ?",
                (start.isoformat(), label_end.isoformat()),
            ).fetchall()
            action_dates: Dict[Tuple[str, str], set] = {}
            dividends: Dict[str, List[Tuple[str, Optional[float]]]] = {}
            for action in action_rows:
                ticker = str(action[1] or "").upper()
                event_date = str(action[2] or "")
                action_dates.setdefault((ticker, action[0]), set()).add(event_date)
                if action[0] == "dividend":
                    payload = json.loads(action[3])
                    dividends.setdefault(ticker, []).append((
                        event_date, _number(payload.get("split_adjusted_cash_amount") or payload.get("cash_amount"))
                    ))
            for values in dividends.values():
                values.sort()

            if selected:
                placeholders = ",".join("?" * len(selected))
                bar_rows = connection.execute(
                    f"""SELECT * FROM daily_bars WHERE session_date BETWEEN ? AND ?
                        AND ticker IN ({placeholders})
                        ORDER BY ticker, session_date""",
                    (start.isoformat(), label_end.isoformat(), *sorted(selected)),
                ).fetchall()
            else:
                bar_rows = connection.execute(
                    """SELECT * FROM daily_bars WHERE session_date BETWEEN ? AND ?
                       ORDER BY ticker, session_date""", (start.isoformat(), label_end.isoformat())
                ).fetchall()
            by_ticker: Dict[str, List[sqlite3.Row]] = {}
            for row in bar_rows:
                by_ticker.setdefault(row["ticker"], []).append(row)
            adjusted_closes: Dict[str, Dict[str, Optional[float]]] = {}
            dividend_clean: Dict[str, Dict[str, bool]] = {}
            for ticker, rows in by_ticker.items():
                raw_by_date = {row["session_date"]: _number(row["close"]) for row in rows}
                factors: List[Tuple[str, Optional[float]]] = []
                for event_date, cash_amount in dividends.get(ticker, []):
                    prior_dates = [date_value for date_value in raw_by_date if date_value < event_date]
                    prior_close = raw_by_date[max(prior_dates)] if prior_dates else None
                    factor = None
                    if cash_amount is not None and cash_amount >= 0 and prior_close and prior_close > cash_amount:
                        factor = (prior_close - cash_amount) / prior_close
                    factors.append((event_date, factor))
                adjusted_closes[ticker] = {}
                dividend_clean[ticker] = {}
                for row in rows:
                    cumulative_factor = 1.0
                    clean = True
                    for event_date, event_factor in factors:
                        if event_date > row["session_date"]:
                            if event_factor is None or event_factor <= 0:
                                clean = False
                            else:
                                cumulative_factor *= event_factor
                    raw_close = _number(row["close"])
                    adjusted_closes[ticker][row["session_date"]] = (
                        raw_close * cumulative_factor if raw_close is not None and clean else None
                    )
                    dividend_clean[ticker][row["session_date"]] = clean
            spy_dates = sorted(adjusted_closes.get("SPY", {}))
            spy_date_index = {date_value: index for index, date_value in enumerate(spy_dates)}
            inserted = 0
            completed = 0
            total_tickers = len(by_ticker)
            for ticker, rows in by_ticker.items():
                closes = adjusted_closes[ticker]
                dollar_volumes = [
                    (_number(row["close"]) or 0) * (_number(row["volume"]) or 0) for row in rows
                ]
                for index, row in enumerate(rows):
                    session_date = row["session_date"]
                    if session_date > end.isoformat():
                        continue
                    reference = connection.execute(
                        """SELECT * FROM reference_snapshots WHERE ticker=? AND snapshot_date<=?
                           ORDER BY snapshot_date DESC, active DESC LIMIT 1""", (ticker, session_date)
                    ).fetchone()
                    raw_type = reference["security_type"] if reference else None
                    security_type = MASSIVE_SECURITY_TYPE_MAP.get(str(raw_type or "").upper())
                    identity_clean = bool(reference and (reference["share_class_figi"] or reference["composite_figi"] or reference["cik"]))
                    security_id = str(
                        (reference["share_class_figi"] if reference else None)
                        or (reference["composite_figi"] if reference else None)
                        or (reference["cik"] if reference else None)
                        or ("ticker:" + ticker)
                    )
                    prior = index
                    trailing = sorted(dollar_volumes[max(0, index - 19):index + 1])
                    median_volume = None
                    if len(trailing) == 20:
                        middle = len(trailing) // 2
                        median_volume = (trailing[middle - 1] + trailing[middle]) / 2
                    current_close = closes.get(session_date)
                    corp_clean = bool(
                        actions_clean_range and dividend_clean[ticker].get(session_date) and current_close is not None
                    )
                    raw_inputs = {
                        "exchange_mic": reference["primary_exchange"] if reference else None,
                        "security_type": security_type,
                        "active": True,  # A valid market aggregate proves it traded in this session.
                        "identity_clean": identity_clean,
                        "corporate_actions_clean": corp_clean,
                        "currency": (reference["currency"] if reference else None),
                        "close": current_close, "market_cap": None,
                        "median_dollar_volume_20d": median_volume, "prior_sessions": prior,
                    }
                    eligibility = assess_investability(raw_inputs)
                    spy_index = spy_date_index.get(session_date)
                    target1 = spy_dates[spy_index + 1] if spy_index is not None and spy_index + 1 < len(spy_dates) else None
                    target5 = spy_dates[spy_index + 5] if spy_index is not None and spy_index + 5 < len(spy_dates) else None
                    stock_t1 = closes.get(target1) if target1 else None
                    stock_t5 = closes.get(target5) if target5 else None
                    spy_closes = adjusted_closes.get("SPY", {})
                    spy_close = spy_closes.get(session_date)
                    spy_t1 = spy_closes.get(target1) if target1 else None
                    spy_t5 = spy_closes.get(target5) if target5 else None
                    clean1 = bool(
                        corp_clean and actions_clean_tail and target1 and dividend_clean[ticker].get(target1)
                        and dividend_clean.get("SPY", {}).get(session_date)
                        and dividend_clean.get("SPY", {}).get(target1)
                    )
                    clean5 = bool(
                        corp_clean and actions_clean_tail and target5 and dividend_clean[ticker].get(target5)
                        and dividend_clean.get("SPY", {}).get(session_date)
                        and dividend_clean.get("SPY", {}).get(target5)
                    )
                    label1 = label_forward_return(
                        current_close, stock_t1, spy_close, spy_t1,
                        horizon_sessions=PRIMARY_HORIZON_SESSIONS, data_clean=clean1,
                    )
                    label5 = label_forward_return(
                        current_close, stock_t5, spy_close, spy_t5,
                        horizon_sessions=SECONDARY_HORIZON_SESSIONS, data_clean=clean5,
                    )
                    local_cutoff = dt.datetime.combine(
                        dt.date.fromisoformat(session_date), dt.time(16, 15), ZoneInfo("America/New_York")
                    )
                    cutoff = local_cutoff.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    connection.execute(
                        """INSERT OR REPLACE INTO swing_observations VALUES
                           (%s)""" % ",".join("?" * 30),
                        (
                            security_id, session_date, cutoff, ticker, POLICY_VERSION,
                            raw_inputs["exchange_mic"], security_type, 1, int(identity_clean), int(corp_clean),
                            raw_inputs["currency"], current_close, spy_close, None, median_volume, prior,
                            int(session_date in action_dates.get((ticker, "split"), set())),
                            int(session_date in action_dates.get((ticker, "dividend"), set())),
                            eligibility["status"], json.dumps(eligibility, sort_keys=True),
                            reference["snapshot_date"] if reference else None,
                            reference["last_updated_utc"] if reference else None,
                            row["source_fetched_at"], row["raw_sha256"], stock_t1, spy_t1, stock_t5, spy_t5,
                            json.dumps(label1, sort_keys=True), json.dumps(label5, sort_keys=True),
                        ),
                    )
                    inserted += 1
                # Commit per security so an interrupted build keeps its work.
                connection.commit()
                completed += 1
                if progress and completed % 25 == 0:
                    progress(completed, total_tickers, inserted)
            connection.commit()
            if progress:
                progress(completed, total_tickers, inserted)
            return inserted

    def validate(self, start: dt.date, end: dt.date) -> Dict[str, Any]:
        expected = list(weekdays(start, end))
        with self.store.connect(create=False) as connection:
            session_rows = connection.execute(
                "SELECT session_date, status, row_count FROM sessions WHERE session_date BETWEEN ? AND ?",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
            recorded = {dt.date.fromisoformat(row[0]): row for row in session_rows}
            missing = [day.isoformat() for day in expected if day not in recorded]
            bad_prices = connection.execute(
                """SELECT COUNT(*) FROM daily_bars WHERE session_date BETWEEN ? AND ?
                   AND (close IS NULL OR close <= 0 OR high < low OR volume < 0 OR adjusted != 1)""",
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]
            duplicate_count = connection.execute(
                """SELECT COUNT(*) FROM (
                   SELECT session_date, ticker, COUNT(*) AS n FROM daily_bars
                   WHERE session_date BETWEEN ? AND ? GROUP BY session_date, ticker HAVING n > 1)""",
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]
            completed = sum(1 for row in session_rows if row[1] == "complete")
            no_data = sum(1 for row in session_rows if row[1] == "no_data")
            observations = connection.execute(
                "SELECT COUNT(*) FROM swing_observations WHERE session_date BETWEEN ? AND ? AND policy_version=?",
                (start.isoformat(), end.isoformat(), POLICY_VERSION),
            ).fetchone()[0]
            bars = connection.execute(
                "SELECT COUNT(*) FROM daily_bars WHERE session_date BETWEEN ? AND ?",
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]
        problems = []
        if missing:
            problems.append("%d weekday dates have not been fetched" % len(missing))
        if bad_prices:
            problems.append("%d bars fail price integrity checks" % bad_prices)
        if duplicate_count:
            problems.append("%d duplicate ticker-session keys exist" % duplicate_count)
        if expected and completed == 0:
            problems.append("No populated market sessions were found in the requested range")
        if bars and observations != bars:
            problems.append("Phase 1 observations do not cover every stored bar")
        return {
            "status": "valid" if not problems else "incomplete",
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "completedSessions": completed, "noDataWeekdays": no_data,
            "missingWeekdays": missing, "badBars": bad_prices,
            "duplicateKeys": duplicate_count, "problems": problems,
            "bars": bars, "policyObservations": observations, "policyVersion": POLICY_VERSION,
            "priceAdjustment": "split-adjusted by Massive; dividends stored separately and not embedded in close",
        }


def plan(start: dt.date, end: dt.date, store: MarketHistoryStore) -> Dict[str, Any]:
    tail_end = min(latest_completed_market_date(), end + dt.timedelta(days=LABEL_TAIL_CALENDAR_DAYS))
    candidate_dates = list(weekdays(start, tail_end))
    completed = store.completed_dates(start, tail_end)
    remaining = [day for day in candidate_dates if day not in completed]
    return {
        "mode": "dry-run", "source": SOURCE_NAME, "sourceDocs": SOURCE_DOCS,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "labelTailThrough": tail_end.isoformat(),
        "weekdayRequestsMaximum": len(candidate_dates), "groupedDailyRequestsRemaining": len(remaining),
        "reference": "monthly point-in-time active identities plus inactive/delisted identities at range end",
        "corporateActions": ["splits", "dividends"], "includeOtc": False,
        "database": str(store.database), "apiKeyConfigured": bool(load_private_key("MASSIVE_API_KEY")),
    }


def build_parser() -> argparse.ArgumentParser:
    default_start, default_end = default_range()
    parser = argparse.ArgumentParser(description="Kestrel market-wide Massive history pipeline")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show local archive coverage without network access")
    for name in ("plan", "sync", "validate"):
        command = subparsers.add_parser(name)
        command.add_argument("--start", type=parse_date, default=default_start)
        command.add_argument("--end", type=parse_date, default=default_end)
        if name == "sync":
            command.add_argument("--requests-per-minute", type=int, default=DEFAULT_REQUESTS_PER_MINUTE)
            command.add_argument("--include-otc", action="store_true", help="include OTC bars; off by default")
            command.add_argument("--skip-reference", action="store_true")
            command.add_argument("--skip-actions", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    store = MarketHistoryStore(args.database)
    if args.command == "status":
        print(json.dumps(store.status(), indent=2, sort_keys=True))
        return 0
    if args.start > args.end:
        print("start must not be after end", file=sys.stderr)
        return 2
    if args.command == "plan":
        print(json.dumps(plan(args.start, args.end, store), indent=2, sort_keys=True))
        return 0
    if args.command == "validate":
        if not store.database.exists():
            print(json.dumps({"status": "empty", "database": str(store.database)}, indent=2))
            return 1
        result = MarketHistoryPipeline.__new__(MarketHistoryPipeline)
        result.store = store
        report = result.validate(args.start, args.end)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "valid" else 1

    api_key = load_private_key("MASSIVE_API_KEY")
    if not api_key:
        print("MASSIVE_API_KEY is not configured. Run the plan command for a safe dry run.", file=sys.stderr)
        return 2
    client = MassiveClient(api_key, requests_per_minute=args.requests_per_minute)
    pipeline = MarketHistoryPipeline(client, store)
    tail_end = min(latest_completed_market_date(), args.end + dt.timedelta(days=LABEL_TAIL_CALENDAR_DAYS))
    summary: Dict[str, Any] = {
        "sessions": pipeline.sync_sessions(args.start, tail_end, args.include_otc),
        "requestedRange": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "labelTailFetchedThrough": tail_end.isoformat(),
    }
    if not args.skip_reference:
        summary["referenceRecords"] = pipeline.sync_reference_timeline(args.start, args.end)
    if not args.skip_actions:
        summary["corporateActions"] = pipeline.sync_actions(args.start, tail_end)
    summary["policyObservations"] = pipeline.build_observations(args.start, args.end)
    summary["validation"] = pipeline.validate(args.start, args.end)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["validation"]["status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
