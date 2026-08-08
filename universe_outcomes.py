"""Automatic, fail-closed outcomes for frozen universe members.

The capturer reads only Kestrel's retained no-cost market archive.  It follows
stable identities across ticker changes, requires a continuous adjusted path,
and pairs any terminal listing record with timely SEC or issuer consideration
evidence.  It never interprets a missing quote or a vanished ticker as a
delisting.  Every observation is appended to :mod:`universe_ledger`; no prior
state is updated.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from market_history import DEFAULT_DATABASE as DEFAULT_MARKET_DATABASE
from swing_radar_policy import POLICY_VERSION
from universe_ledger import UniverseLedger


ADJUSTMENT_DEFINITION = "point_in_time_total_return"
AUTHORITATIVE_TERMINAL_SOURCES = ("SEC EDGAR", "Official issuer")
TERMINAL_EVENT_TYPES = {
    "merger_cash", "cash_merger", "delisting_cash",
    "merger_stock", "stock_merger", "delisting_stock",
    "merger_mixed", "mixed_merger",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_hash(value: Any) -> bool:
    raw = str(value or "")
    if len(raw) != 64:
        return False
    try:
        int(raw, 16)
    except ValueError:
        return False
    return True


def _utc(value: Any) -> Optional[str]:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: Any) -> Optional[str]:
    try:
        return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _positive(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _nonnegative(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _currency(value: Any) -> Optional[str]:
    result = str(value or "").strip().upper()
    return result if len(result) == 3 and result.isalpha() else None


def _stable_reference_id(row: sqlite3.Row) -> Optional[str]:
    if row["share_class_figi"]:
        return "FIGI:" + str(row["share_class_figi"])
    if row["composite_figi"]:
        return "FIGI:" + str(row["composite_figi"])
    if row["cik"]:
        return "CIK:" + str(row["cik"])
    return None


class UniverseOutcomeCapture:
    """Accumulate independently evidenced paths for every frozen member."""

    def __init__(
        self, ledger: UniverseLedger,
        market_database: Path = DEFAULT_MARKET_DATABASE,
    ) -> None:
        self.ledger = ledger
        self.market_database = Path(market_database)

    def capture(self, recorded_at: Optional[str] = None) -> Dict[str, Any]:
        recorded = _utc(recorded_at) if recorded_at else dt.datetime.now(
            dt.timezone.utc
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if not recorded:
            raise ValueError("Outcome capture time must include a timezone")
        if not self.ledger.database.exists() or not self.market_database.exists():
            return {"status": "unavailable", "recordedAt": recorded, "recorded": 0,
                    "unchanged": 0, "failures": ["The ledger or market archive is unavailable"]}

        try:
            market = sqlite3.connect(str(self.market_database))
            market.row_factory = sqlite3.Row
            with self.ledger.connect(create=False) as connection:
                members = connection.execute(
                    """SELECT s.snapshot_id, s.decision_date, m.security_id, m.ticker,
                              m.included, i.identifiers_json, i.listing_json, i.source_json
                       FROM universe_snapshots s
                       JOIN snapshot_members m ON m.snapshot_id=s.snapshot_id
                       JOIN identity_versions i ON i.version_id=m.identity_version_id
                       ORDER BY s.decision_date, m.security_id"""
                ).fetchall()
            results = []
            for row in members:
                member = dict(row)
                try:
                    results.append(self._capture_member(market, member, recorded))
                except (KeyError, TypeError, ValueError) as error:
                    results.append({
                        "status": "blocked", "snapshotId": member.get("snapshot_id"),
                        "securityId": member.get("security_id"),
                        "reason": f"Outcome evidence was invalid: {error}",
                    })
        except sqlite3.DatabaseError as error:
            return {"status": "blocked", "recordedAt": recorded, "recorded": 0,
                    "unchanged": 0, "failures": [f"Archive schema could not be read: {error}"]}
        finally:
            if "market" in locals():
                market.close()

        failures = [row for row in results if (
            row.get("status") in {"blocked", "failed"}
            or row.get("outcomeStatus") in {"missing", "conflict"}
        )]
        return {
            "status": "partial" if failures else "captured",
            "recordedAt": recorded,
            "members": len(results),
            "recorded": sum(row.get("status") == "recorded" for row in results),
            "unchanged": sum(row.get("status") == "unchanged" for row in results),
            "failures": failures,
            "results": results,
        }

    @staticmethod
    def _references(
        market: sqlite3.Connection, security_id: str, recorded: str,
    ) -> Tuple[List[sqlite3.Row], List[sqlite3.Row]]:
        prefix, separator, identifier = security_id.partition(":")
        if not separator or not identifier:
            return [], []
        if prefix.upper() == "FIGI":
            identity_clause = "(UPPER(share_class_figi)=UPPER(?) OR UPPER(composite_figi)=UPPER(?))"
            identity_values: Tuple[str, ...] = (identifier, identifier)
        elif prefix.upper() == "CIK":
            identity_clause = "cik=?"
            identity_values = (identifier,)
        else:
            return [], []
        rows = market.execute(
            f"""SELECT * FROM reference_snapshots WHERE {identity_clause}
                AND source_fetched_at<=? AND snapshot_date<=?
                ORDER BY snapshot_date, ticker, active DESC""",
            (*identity_values, recorded, recorded[:10]),
        ).fetchall()
        late_rows = market.execute(
            f"""SELECT * FROM reference_snapshots WHERE {identity_clause}
                AND source_fetched_at>? ORDER BY source_fetched_at""",
            (*identity_values, recorded),
        ).fetchall()
        # A reference may contain both composite and share-class FIGIs. Keep
        # only the stable identity shape used by the frozen member.
        timely = [row for row in rows if (_stable_reference_id(row) or "").upper() == security_id.upper()]
        late = [row for row in late_rows if (_stable_reference_id(row) or "").upper() == security_id.upper()]
        return timely, late

    @staticmethod
    def _terminal_evidence(
        market: sqlite3.Connection, aliases: Sequence[str], ciks: Sequence[str], recorded: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        if not aliases:
            return [], 0
        placeholders = ",".join("?" for _ in aliases)
        rows = market.execute(
            f"""SELECT * FROM issuer_events WHERE ticker IN ({placeholders})
                AND event_type IN ({','.join('?' for _ in TERMINAL_EVENT_TYPES)})
                ORDER BY available_at, accession""",
            (*aliases, *sorted(TERMINAL_EVENT_TYPES)),
        ).fetchall()
        candidates: List[Dict[str, Any]] = []
        late = 0
        for row in rows:
            source = str(row["source"] or "")
            available = _utc(row["available_at"])
            retrieved = _utc(row["retrieved_at"])
            if not source.startswith(AUTHORITATIVE_TERMINAL_SOURCES):
                continue
            if not row["accession"] or not row["cik"] or str(row["cik"]) not in ciks:
                continue
            if not available or not retrieved or available > recorded or retrieved > recorded:
                late += 1
                continue
            try:
                detail = json.loads(row["detail"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(detail, dict):
                continue
            source_url = str(detail.get("sourceUrl") or "")
            source_kind = str(detail.get("sourceKind") or "")
            parsed_source = urlparse(source_url)
            source_authoritative = (
                source_kind == "sec_filing"
                and parsed_source.scheme == "https"
                and (parsed_source.hostname or "").lower() in {"sec.gov", "www.sec.gov"}
                and parsed_source.path.startswith("/Archives/edgar/data/")
            ) or (
                source_kind == "official_issuer"
                and parsed_source.scheme == "https"
                and detail.get("issuerDomainVerified") is True
            )
            raw_hashes = detail.get("rawDocumentHashes") or []
            raw_record_hash = str(detail.get("rawRecordHash") or "")
            if (detail.get("schemaVersion") != "authoritative-terminal-event-v1"
                    or not source_authoritative
                    or not raw_hashes or any(not _is_hash(value) for value in raw_hashes)
                    or not _is_hash(raw_record_hash)
                    or detail.get("accession") != row["accession"]
                    or str(detail.get("targetSecurityId") or "").upper()
                    != f"CIK:{int(row['cik'])}".upper()
                    or _utc(detail.get("publishedAt")) != _utc(row["published_at"])
                    or _utc(detail.get("availableAt")) != available
                    or _utc(detail.get("retrievedAt")) != retrieved):
                continue
            consideration = detail.get("consideration") or {}
            kind = str(consideration.get("kind") or "").lower()
            normalized: Dict[str, Any] = {"kind": kind}
            if kind in {"cash", "mixed"}:
                cash = _nonnegative(consideration.get("cashPerShare"))
                currency = _currency(consideration.get("currency"))
                if cash is None or not currency:
                    continue
                normalized.update({"cashPerShare": cash, "currency": currency})
            if kind in {"stock", "mixed"}:
                ratio = _positive(consideration.get("sharesPerShare"))
                successor = str(consideration.get("successorSecurityId") or "").strip()
                if ratio is None or not successor:
                    continue
                normalized.update({"sharesPerShare": ratio, "successorSecurityId": successor})
            if kind not in {"cash", "stock", "mixed"}:
                continue
            effective = _date(detail.get("effectiveOn") or row["event_date"])
            if not effective or effective > recorded[:10]:
                continue
            record = dict(row)
            record.update({"effectiveOn": effective, "consideration": normalized,
                           "available_at": available, "retrieved_at": retrieved,
                           "recordHash": _hash({"rawRecordHash": raw_record_hash,
                                                "rawDocumentHashes": raw_hashes}),
                           "supersedesAccession": detail.get("supersedesAccession")})
            candidates.append(record)

        # An explicit amendment suppresses only the named earlier accession at
        # cutoffs where the amendment itself was already available. An
        # unlinked difference remains a conflict and fails the outcome fold.
        by_accession = {str(row["accession"]): row for row in candidates}
        superseded = set()
        invalid_amendment = False
        for row in candidates:
            prior = str(row.get("supersedesAccession") or "")
            if not prior:
                continue
            previous = by_accession.get(prior)
            if (not previous or previous["cik"] != row["cik"]
                    or previous["available_at"] >= row["available_at"]):
                invalid_amendment = True
                continue
            superseded.add(prior)
        if invalid_amendment:
            for row in candidates:
                row["invalidAmendment"] = True
            return candidates, late
        return [row for row in candidates if str(row["accession"]) not in superseded], late

    def _append(
        self, member: Dict[str, Any], recorded: str, *, status: str,
        valid_through: str, effective_at: str, available_at: str, retrieved_at: str,
        source: str, source_record_id: str, source_record_hash: str,
        payload: Dict[str, Any], currency: Optional[str], listing_state: str = "active",
        delisted_on: Optional[str] = None, proceeds: Optional[float] = None,
        consideration: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        evidence_hash = _hash({"sourceRecordHash": source_record_hash, "payload": payload})
        result = self.ledger.append_outcome(
            snapshot_id=member["snapshot_id"], security_id=member["security_id"],
            valid_through=valid_through, recorded_at=recorded, status=status,
            effective_at=effective_at, available_at=available_at, retrieved_at=retrieved_at,
            listing_state=listing_state, delisted_on=delisted_on, proceeds=proceeds,
            currency=currency, adjustment_definition=ADJUSTMENT_DEFINITION,
            consideration=consideration, source=source, source_record_id=source_record_id,
            source_record_hash=source_record_hash, evidence_hash=evidence_hash, payload=payload,
        )
        return {**result, "snapshotId": member["snapshot_id"],
                "securityId": member["security_id"], "outcomeStatus": status}

    def _capture_member(
        self, market: sqlite3.Connection, member: Dict[str, Any], recorded: str,
    ) -> Dict[str, Any]:
        decision = member["decision_date"]
        required = (dt.date.fromisoformat(decision) + dt.timedelta(days=365)).isoformat()
        listing = json.loads(member["listing_json"] or "{}")
        frozen_currency = _currency(listing.get("currency"))
        references, late_references = self._references(market, member["security_id"], recorded)
        aliases = sorted({str(row["ticker"]).upper() for row in references} | {member["ticker"].upper()})
        verified_aliases = {str(row["ticker"]).upper() for row in references}
        identifiers = json.loads(member["identifiers_json"] or "{}")
        ciks = sorted({str(row["cik"]) for row in references if row["cik"]}
                      | ({str(identifiers.get("cik"))} if identifiers.get("cik") else set()))
        reference_currencies = {_currency(row["currency"]) for row in references}
        if not frozen_currency or None in reference_currencies or any(
            value != frozen_currency for value in reference_currencies
        ):
            return self._missing(member, recorded, decision, frozen_currency,
                                 "Missing or conflicting listing currency")

        inactive = [row for row in references if not row["active"] and _date(row["delisted_utc"])]
        delisted_dates = {_date(row["delisted_utc"]) for row in inactive}
        if len(delisted_dates) > 1:
            return self._conflict(member, recorded, decision, frozen_currency,
                                  "Conflicting delisting dates", inactive)
        terminal_events, late_events = self._terminal_evidence(market, aliases, ciks, recorded)
        if any(row.get("invalidAmendment") for row in terminal_events):
            return self._conflict(member, recorded, decision, frozen_currency,
                                  "Invalid or unattributable authoritative amendment", terminal_events)
        event_terms = {(row["effectiveOn"], _canonical(row["consideration"])) for row in terminal_events}
        if len(event_terms) > 1:
            return self._conflict(member, recorded, decision, frozen_currency,
                                  "Conflicting authoritative consideration", terminal_events)

        placeholders = ",".join("?" for _ in aliases)
        observations = market.execute(
            f"""SELECT * FROM swing_observations
                WHERE ticker IN ({placeholders}) AND session_date>? AND policy_version=?
                AND source_retrieved_at<=? ORDER BY session_date, ticker""",
            (*aliases, decision, POLICY_VERSION, recorded),
        ).fetchall()
        by_date: Dict[str, sqlite3.Row] = {}
        for row in observations:
            row_currency = _currency(row["currency"])
            if (not row["corporate_actions_clean"] or _positive(row["adjusted_close"]) is None
                    or row_currency != frozen_currency):
                continue
            same_id = str(row["security_id"] or "").upper() == member["security_id"].upper()
            if not same_id and row["ticker"].upper() not in verified_aliases:
                continue
            if row["session_date"] in by_date and by_date[row["session_date"]]["ticker"] != row["ticker"]:
                return self._conflict(member, recorded, row["session_date"], frozen_currency,
                                      "Two tickers claim the stable identity on one session", [dict(row)])
            by_date[row["session_date"]] = row

        session_rows = market.execute(
            """SELECT session_date, fetched_at, raw_sha256 FROM sessions
               WHERE session_date>? AND status='complete' AND fetched_at<=?
               ORDER BY session_date""", (decision, recorded)
        ).fetchall()
        expected = [row["session_date"] for row in session_rows]
        if not expected or expected[0] not in by_date:
            note = "No adjusted entry observation for the frozen identity"
            if late_references or late_events:
                note += "; later evidence was excluded"
            return self._missing(member, recorded, decision, frozen_currency, note)

        delisted_on = next(iter(delisted_dates), None)
        event = terminal_events[0] if len(terminal_events) == 1 else None
        if event and event["consideration"].get("currency", frozen_currency) != frozen_currency:
            return self._conflict(member, recorded, event["effectiveOn"], frozen_currency,
                                  "Transaction consideration currency conflicts with the listing",
                                  [event])
        if delisted_on and (not event or event["effectiveOn"] != delisted_on):
            return self._missing(member, recorded, delisted_on, frozen_currency,
                                 "Delisting lacks matching timely proceeds or successor evidence",
                                 listing_state="delisted_unresolved", delisted_on=delisted_on)
        if event and not delisted_on:
            return self._missing(member, recorded, event["effectiveOn"], frozen_currency,
                                 "Transaction evidence lacks an inactive listing record")

        path_end = delisted_on or expected[-1]
        required_sessions = [value for value in expected if value <= path_end]
        missing_sessions = [value for value in required_sessions if value not in by_date]
        if missing_sessions:
            return self._missing(member, recorded, missing_sessions[0], frozen_currency,
                                 "Adjusted path has missing sessions; disappearance is not delisting")

        path = [by_date[value] for value in required_sessions]
        first, last = path[0], path[-1]
        source_hashes = [str(row["raw_sha256"] or "") for row in path]
        if any(not _is_hash(value) for value in source_hashes):
            return self._missing(member, recorded, last["session_date"], frozen_currency,
                                 "Adjusted path has an invalid source hash")
        payload: Dict[str, Any] = {
            "startDate": first["session_date"], "endDate": last["session_date"],
            "startAdjustedClose": float(first["adjusted_close"]),
            "endAdjustedClose": float(last["adjusted_close"]),
            "totalReturn": float(last["adjusted_close"]) / float(first["adjusted_close"]) - 1,
            "sessions": len(path), "tickers": sorted({row["ticker"] for row in path}),
            "adjustmentDefinition": ADJUSTMENT_DEFINITION, "currency": frozen_currency,
            "observationHashes": source_hashes,
        }
        available = max(str(row["source_retrieved_at"]) for row in path)
        retrieved = available
        source_record_hash = _hash(source_hashes)

        if delisted_on and event:
            consideration = event["consideration"]
            kind = consideration["kind"]
            proceeds = consideration.get("cashPerShare")
            listing_hashes = [str(row["raw_sha256"] or "") for row in inactive]
            if any(not _is_hash(value) for value in listing_hashes):
                return self._missing(member, recorded, delisted_on, frozen_currency,
                                     "Delisting listing record lacks a source hash",
                                     listing_state="delisted_unresolved", delisted_on=delisted_on)
            if kind in {"stock", "mixed"}:
                successor = self._successor_path(
                    market, consideration["successorSecurityId"], delisted_on,
                    required, recorded, frozen_currency,
                )
                if successor.get("status") != "complete":
                    return self._missing(member, recorded, delisted_on, frozen_currency,
                                         successor.get("reason") or "Successor path is incomplete",
                                         listing_state="delisted_unresolved", delisted_on=delisted_on)
                payload["successorPath"] = successor["payload"]
                end_value = (proceeds or 0.0) + consideration["sharesPerShare"] * successor["endClose"]
                payload["endValuePerOriginalShare"] = end_value
                payload["totalReturn"] = end_value / float(first["adjusted_close"]) - 1
                path_end = successor["validThrough"]
                available = max(available, successor["availableAt"], event["available_at"])
                retrieved = max(retrieved, successor["retrievedAt"], event["retrieved_at"])
                source_record_hash = _hash(
                    [source_record_hash, successor["sourceHash"], event["recordHash"], *listing_hashes]
                )
            else:
                payload["endValuePerOriginalShare"] = proceeds
                payload["totalReturn"] = proceeds / float(first["adjusted_close"]) - 1
                available = max(available, event["available_at"])
                retrieved = max(retrieved, event["retrieved_at"])
                source_record_hash = _hash([source_record_hash, event["recordHash"], *listing_hashes])
            payload["terminalEvidence"] = {
                "accession": event["accession"], "source": event["source"],
                "recordHash": event["recordHash"], "effectiveOn": delisted_on,
                "listingRecordHashes": listing_hashes,
            }
            return self._append(
                member, recorded, status="delisted_complete", valid_through=path_end,
                effective_at=delisted_on + "T00:00:00Z", available_at=available,
                retrieved_at=retrieved, source="No-cost archive plus authoritative transaction evidence",
                source_record_id=str(event["accession"]), source_record_hash=source_record_hash,
                payload=payload, currency=frozen_currency, listing_state="delisted",
                delisted_on=delisted_on, proceeds=proceeds, consideration=consideration,
            )

        status = "complete" if expected[-1] >= required else "pending"
        return self._append(
            member, recorded, status=status, valid_through=last["session_date"],
            effective_at=last["cutoff_utc"], available_at=available, retrieved_at=retrieved,
            source="Kestrel no-cost point-in-time total-return archive",
            source_record_id=(f"path:{member['security_id']}:{first['session_date']}:{last['session_date']}"),
            source_record_hash=source_record_hash, payload=payload, currency=frozen_currency,
        )

    def _successor_path(
        self, market: sqlite3.Connection, security_id: str, start: str, required: str,
        recorded: str, currency: str,
    ) -> Dict[str, Any]:
        rows = market.execute(
            """SELECT * FROM swing_observations WHERE UPPER(security_id)=UPPER(?)
               AND session_date>? AND policy_version=?
               AND source_retrieved_at<=? ORDER BY session_date""",
            (security_id, start, POLICY_VERSION, recorded),
        ).fetchall()
        clean = [row for row in rows if row["corporate_actions_clean"]
                 and _positive(row["adjusted_close"]) is not None
                 and _currency(row["currency"]) == currency]
        expected_rows = market.execute(
            """SELECT session_date FROM sessions WHERE session_date>? AND status='complete'
               AND fetched_at<=? ORDER BY session_date""", (start, recorded)
        ).fetchall()
        expected = [row["session_date"] for row in expected_rows]
        exits = [value for value in expected if value >= required]
        if not clean or not exits:
            return {"status": "pending", "reason": "Stock consideration successor path has not matured"}
        exit_date = exits[0]
        clean_by_date = {row["session_date"]: row for row in clean if row["session_date"] <= exit_date}
        required_sessions = [value for value in expected if value <= exit_date]
        if any(value not in clean_by_date for value in required_sessions):
            return {"status": "missing", "reason": "Stock consideration successor path has missing sessions"}
        clean = [clean_by_date[value] for value in required_sessions]
        hashes = [str(row["raw_sha256"] or "") for row in clean]
        if any(not _is_hash(value) for value in hashes):
            return {"status": "missing", "reason": "Successor path lacks source hashes"}
        return {
            "status": "complete", "validThrough": clean[-1]["session_date"],
            "endClose": float(clean[-1]["adjusted_close"]),
            "availableAt": max(row["source_retrieved_at"] for row in clean),
            "retrievedAt": max(row["source_retrieved_at"] for row in clean),
            "sourceHash": _hash(hashes),
            "payload": {"securityId": security_id, "startDate": clean[0]["session_date"],
                        "endDate": clean[-1]["session_date"], "sessions": len(clean),
                        "endAdjustedClose": float(clean[-1]["adjusted_close"]),
                        "observationHashes": hashes},
        }

    def _missing(
        self, member: Dict[str, Any], recorded: str, effective: str,
        currency: Optional[str], reason: str, listing_state: str = "active",
        delisted_on: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {"reason": reason, "adjustmentDefinition": ADJUSTMENT_DEFINITION,
                   "currency": currency}
        return self._append(
            member, recorded, status="missing", valid_through=_date(effective) or member["decision_date"],
            effective_at=(f"{_date(effective) or member['decision_date']}T00:00:00Z"),
            available_at=recorded, retrieved_at=recorded,
            source="Kestrel outcome evidence audit", source_record_id=_hash(payload),
            source_record_hash=_hash(payload), payload=payload, currency=currency,
            listing_state=listing_state, delisted_on=delisted_on,
        )

    def _conflict(
        self, member: Dict[str, Any], recorded: str, effective: str,
        currency: Optional[str], reason: str, records: Iterable[Any],
    ) -> Dict[str, Any]:
        normalized = [dict(row) for row in records]
        payload = {"reason": reason, "conflictingRecordHashes": [_hash(row) for row in normalized],
                   "adjustmentDefinition": ADJUSTMENT_DEFINITION, "currency": currency}
        return self._append(
            member, recorded, status="conflict", valid_through=_date(effective) or member["decision_date"],
            effective_at=(f"{_date(effective) or member['decision_date']}T00:00:00Z"),
            available_at=recorded, retrieved_at=recorded,
            source="Kestrel outcome evidence conflict audit", source_record_id=_hash(payload),
            source_record_hash=_hash(normalized), payload=payload, currency=currency,
        )
