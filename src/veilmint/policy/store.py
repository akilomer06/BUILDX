"""Local append-preserving policy revisions and one-time reviews in SQLite.

Each read recompiles the saved analysis, configuration and decision, then checks
the stored compiled snapshot. SQLite is a local trusted store, not a signed
policy distribution channel. No customer payload or runtime event is stored here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .compiler import (
    analysis_digest,
    compile_policy,
    normalize_log_mapping,
    policy_inputs_digest,
)
from .models import CompiledPolicy, PolicyRevision, ReviewerDecision, RevisionStatus


class PolicyStoreError(ValueError):
    """A policy store operation failed without exposing its input values."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PolicyStore:
    """SQLite policy store; callers may use it as a context manager.

    A connection lock allows use by a small local threaded demo. Independent
    instances coordinate writes with SQLite's BEGIN IMMEDIATE transaction.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path) if str(path) != ":memory:" else ":memory:"
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        try:
            if isinstance(self.path, Path):
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(path), timeout=5, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise PolicyStoreError("Unsupported policy database schema version.")
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS veilmint_policy_revisions (
                    revision_id TEXT PRIMARY KEY,
                    number INTEGER NOT NULL UNIQUE CHECK(number > 0),
                    analysis_digest TEXT NOT NULL,
                    inputs_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('REVIEW_REQUIRED','APPROVED','REJECTED')),
                    analysis_json TEXT NOT NULL,
                    log_mapping_json TEXT NOT NULL,
                    known_fields_json TEXT NOT NULL,
                    compiled_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS veilmint_reviewer_decisions (
                    revision_id TEXT PRIMARY KEY REFERENCES veilmint_policy_revisions(revision_id),
                    decision_json TEXT NOT NULL
                );
            """)
            self._connection.execute("PRAGMA user_version = 1")
            self._connection.commit()
        except (sqlite3.Error, OSError):
            self.close()
            raise PolicyStoreError("Policy database is unavailable or invalid.") from None
        except PolicyStoreError:
            self.close()
            raise

    def __enter__(self) -> PolicyStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    @property
    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise PolicyStoreError("Policy database is closed.")
        return self._connection

    @contextmanager
    def _transaction(self):
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                yield
                self._db.commit()
            except sqlite3.Error:
                self._db.rollback()
                raise PolicyStoreError("Policy database operation failed.") from None
            except Exception:
                self._db.rollback()
                raise

    def _row(self, revision_id: str | None = None) -> sqlite3.Row:
        if revision_id is None:
            row = self._db.execute(
                "SELECT * FROM veilmint_policy_revisions ORDER BY number DESC LIMIT 1"
            ).fetchone()
        else:
            row = self._db.execute(
                "SELECT * FROM veilmint_policy_revisions WHERE revision_id = ?", (revision_id,)
            ).fetchone()
        if row is None:
            raise PolicyStoreError("Policy revision was not found.")
        return row

    def _decode(self, row: sqlite3.Row) -> CompiledPolicy:
        try:
            report = json.loads(row["analysis_json"])
            log_mapping = json.loads(row["log_mapping_json"])
            known_fields = json.loads(row["known_fields_json"])
            stored = json.loads(row["compiled_json"])
            revision = PolicyRevision(
                revision_id=row["revision_id"], number=row["number"],
                analysis_digest=row["analysis_digest"], inputs_digest=row["inputs_digest"],
                created_at=row["created_at"], status=RevisionStatus(row["status"]),
            )
            decision_row = self._db.execute(
                "SELECT decision_json FROM veilmint_reviewer_decisions WHERE revision_id = ?",
                (revision.revision_id,),
            ).fetchone()
            decision = (
                ReviewerDecision.from_dict(json.loads(decision_row["decision_json"]))
                if decision_row is not None else None
            )
            result = compile_policy(
                report, revision, decision, log_mapping=log_mapping, known_fields=known_fields
            )
            if _json(result.to_dict()) != _json(stored):
                raise ValueError("Compiled snapshot differs from source inputs")
            if result.revision.status.value != row["status"]:
                raise ValueError("Revision status differs from source decision")
            if revision.revision_id != f"r{revision.number}-{revision.inputs_digest[:12]}":
                raise ValueError("Revision identifier differs from source inputs")
            return result
        except (ValueError, TypeError, KeyError, AttributeError):
            raise PolicyStoreError("Stored policy data failed integrity validation.") from None

    def create_revision(
        self,
        report: Mapping[str, Any],
        *,
        log_mapping: Mapping[str, str] | None = None,
        known_fields: Iterable[str] | None = None,
        force_new: bool = False,
    ) -> CompiledPolicy:
        """Reuse identical latest inputs, or append a fresh review-required revision.

        Matching an older revision never revives its approval. Use force_new for
        regenerated evidence even when its normalized content happens to match.
        """
        try:
            mapping = normalize_log_mapping(log_mapping)
            inventory = tuple(known_fields) if known_fields is not None else None
            digest = analysis_digest(report)
            inputs_digest = policy_inputs_digest(report, log_mapping=mapping, known_fields=inventory)
            # JSON round-trip detaches mutable caller inputs before persistence.
            report_json = _json(report)
            mapping_json = _json(mapping)
            inventory_json = _json(inventory)
        except (ValueError, TypeError, KeyError):
            raise PolicyStoreError("Policy inputs are invalid.") from None

        with self._transaction():
            latest = self._db.execute(
                "SELECT * FROM veilmint_policy_revisions ORDER BY number DESC LIMIT 1"
            ).fetchone()
            latest_policy = self._decode(latest) if latest is not None else None
            if latest is not None and latest["inputs_digest"] == inputs_digest and not force_new:
                return latest_policy
            number = latest["number"] + 1 if latest is not None else 1
            revision = PolicyRevision(
                revision_id=f"r{number}-{inputs_digest[:12]}", number=number,
                analysis_digest=digest, inputs_digest=inputs_digest,
                created_at=_now(), status=RevisionStatus.REVIEW_REQUIRED,
            )
            try:
                result = compile_policy(report, revision, log_mapping=mapping, known_fields=inventory)
            except (ValueError, TypeError, KeyError):
                raise PolicyStoreError("Policy inputs are invalid.") from None
            self._db.execute(
                """INSERT INTO veilmint_policy_revisions
                (revision_id,number,analysis_digest,inputs_digest,created_at,status,
                 analysis_json,log_mapping_json,known_fields_json,compiled_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    revision.revision_id, revision.number, revision.analysis_digest,
                    revision.inputs_digest, revision.created_at, revision.status.value,
                    report_json, mapping_json, inventory_json, _json(result.to_dict()),
                ),
            )
            return result

    def get(self, revision_id: str | None = None) -> CompiledPolicy:
        """Load a validated revision; default is latest, including pending review."""
        with self._read_snapshot():
            try:
                return self._decode(self._row(revision_id))
            except sqlite3.Error:
                raise PolicyStoreError("Policy database operation failed.") from None

    def history(self) -> list[dict[str, Any]]:
        with self._read_snapshot():
            try:
                rows = self._db.execute(
                    "SELECT * FROM veilmint_policy_revisions ORDER BY number"
                ).fetchall()
                return [self._decode(row).revision.to_dict() for row in rows]
            except sqlite3.Error:
                raise PolicyStoreError("Policy database operation failed.") from None

    def load_inputs(self, revision_id: str) -> dict[str, Any]:
        with self._read_snapshot():
            try:
                row = self._row(revision_id)
                self._decode(row)
                return {
                    "report": json.loads(row["analysis_json"]),
                    "log_mapping": json.loads(row["log_mapping_json"]),
                    "known_fields": json.loads(row["known_fields_json"]),
                }
            except sqlite3.Error:
                raise PolicyStoreError("Policy database operation failed.") from None

    @contextmanager
    def _read_snapshot(self):
        """Keep revision, decision and compiled snapshot on one read version."""
        with self._lock:
            try:
                self._db.execute("BEGIN")
                yield
                self._db.commit()
            except sqlite3.Error:
                self._db.rollback()
                raise PolicyStoreError("Policy database operation failed.") from None
            except Exception:
                self._db.rollback()
                raise

    def review(
        self,
        revision_id: str,
        reviewer: str,
        approved_fields: Iterable[str],
        *,
        notes: str = "",
        decision: str = "APPROVE",
    ) -> CompiledPolicy:
        """Atomically save a single decision for the latest pending revision."""
        with self._transaction():
            row = self._row(revision_id)
            latest = self._row()
            if row["revision_id"] != latest["revision_id"]:
                raise PolicyStoreError("Cannot review a stale policy revision; review the latest revision.")
            current = self._decode(row)
            if current.revision.status != RevisionStatus.REVIEW_REQUIRED:
                raise PolicyStoreError("This policy revision already has a reviewer decision; create a new revision.")
            try:
                reviewer_decision = ReviewerDecision(
                    revision_id=revision_id,
                    analysis_digest=current.revision.analysis_digest,
                    inputs_digest=current.revision.inputs_digest,
                    reviewer=reviewer, approved_fields=tuple(approved_fields),
                    decided_at=_now(), notes=notes, decision=decision,
                )
                compiled = compile_policy(
                    json.loads(row["analysis_json"]), current.revision, reviewer_decision,
                    log_mapping=json.loads(row["log_mapping_json"]),
                    known_fields=json.loads(row["known_fields_json"]),
                )
            except (ValueError, TypeError, KeyError):
                raise PolicyStoreError("Review decision is invalid for this policy revision.") from None
            self._db.execute(
                "INSERT INTO veilmint_reviewer_decisions(revision_id,decision_json) VALUES (?,?)",
                (revision_id, _json(reviewer_decision.to_dict())),
            )
            self._db.execute(
                "UPDATE veilmint_policy_revisions SET status = ?, compiled_json = ? WHERE revision_id = ?",
                (compiled.revision.status.value, _json(compiled.to_dict()), revision_id),
            )
            return compiled
