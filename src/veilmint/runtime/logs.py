"""Path-aware structured log protection before the local SQLite sink.

The sink receives only the pipeline's sanitized copy. Diagnostics contain no
event values; unknown fields and unusable policies never fall back to raw data.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from typing import Any

from ..policy.models import CompiledPolicy, LogAction, RevisionStatus


MASK = "[REDACTED]"
_DROP = object()


class LogProtectionError(ValueError):
    """A log operation failed with a message safe to expose to the demo."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _json_copy(event: Any) -> dict[str, Any]:
    def check(value: Any) -> None:
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
        elif value is not None and not isinstance(value, (str, bool, int, float)):
            raise ValueError

    try:
        if not isinstance(event, dict):
            raise ValueError
        check(event)
        return json.loads(_json(event))
    except Exception:
        raise LogProtectionError("Log event must be a finite JSON object.") from None


@dataclass(frozen=True)
class LogResult:
    event: dict[str, Any]
    record_id: int
    policy_revision: str | None
    warnings: tuple[str, ...]
    actions: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": _json_copy(self.event), "record_id": self.record_id,
            "policy_revision": self.policy_revision, "warnings": list(self.warnings),
            "actions": [{"path": list(action["path"]), "action": action["action"]} for action in self.actions],
        }


class LogSink:
    """Small on-disk SQLite sink with separate value-free audit metadata.

    Every operation owns and closes its connection, so independent request
    threads can share this object. Existing policy schema version is untouched.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) == ":memory:":
            raise LogProtectionError("Log sink requires an on-disk SQLite database.")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as db, db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS veilmint_protected_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_json TEXT NOT NULL,
                        policy_revision TEXT,
                        mode TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS veilmint_runtime_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        kind TEXT NOT NULL,
                        policy_revision TEXT,
                        mode TEXT NOT NULL,
                        warnings_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                """)
        except Exception:
            raise LogProtectionError("Log database is unavailable or invalid.") from None

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout = 5000")
            return db
        except Exception:
            db.close()
            raise

    def append(self, event: dict[str, Any], *, policy_revision: str | None, mode: str = "PROTECT") -> int:
        """Persist an already protected event; raw input belongs in process()."""
        try:
            safe_event = _json_copy(event)
            with closing(self._connect()) as db, db:
                cursor = db.execute(
                    "INSERT INTO veilmint_protected_logs(event_json,policy_revision,mode,created_at) VALUES (?,?,?,?)",
                    (_json(safe_event), policy_revision, mode, _now()),
                )
                return int(cursor.lastrowid)
        except Exception:
            raise LogProtectionError("Protected log persistence failed.") from None

    def get(self, record_id: int) -> dict[str, Any]:
        """Inspection helper returns the persisted sanitized event only."""
        try:
            with closing(self._connect()) as db:
                row = db.execute("SELECT * FROM veilmint_protected_logs WHERE id = ?", (record_id,)).fetchone()
                if row is None:
                    raise ValueError
                return {
                    "id": row["id"], "event": json.loads(row["event_json"]),
                    "policy_revision": row["policy_revision"], "mode": row["mode"],
                    "created_at": row["created_at"],
                }
        except Exception:
            raise LogProtectionError("Protected log record is unavailable.") from None

    def record_audit(
        self, kind: str, policy_revision: str | None, mode: str,
        warnings: Iterable[str] = (),
    ) -> int:
        try:
            metadata_warnings = tuple(warnings)
            if not isinstance(kind, str) or not isinstance(mode, str) or any(not isinstance(item, str) for item in metadata_warnings):
                raise ValueError
            with closing(self._connect()) as db, db:
                cursor = db.execute(
                    "INSERT INTO veilmint_runtime_audit(kind,policy_revision,mode,warnings_json,created_at) VALUES (?,?,?,?,?)",
                    (kind, policy_revision, mode, _json(sorted(set(metadata_warnings))), _now()),
                )
                return int(cursor.lastrowid)
        except Exception:
            raise LogProtectionError("Runtime audit persistence failed.") from None

    def audits(self) -> list[dict[str, Any]]:
        try:
            with closing(self._connect()) as db:
                return [{
                    "id": row["id"], "kind": row["kind"], "policy_revision": row["policy_revision"],
                    "mode": row["mode"], "warnings": json.loads(row["warnings_json"]),
                    "created_at": row["created_at"],
                } for row in db.execute("SELECT * FROM veilmint_runtime_audit ORDER BY id")]
        except Exception:
            raise LogProtectionError("Runtime audit records are unavailable.") from None


def _matches(pattern: tuple[str, ...], path: tuple[str | int, ...]) -> bool:
    if len(pattern) != len(path):
        return False
    return all(
        part == actual if isinstance(actual, str) else part in ("*", str(actual))
        for part, actual in zip(pattern, path)
    )


class StructuredLogPipeline:
    def __init__(
        self, policy_loader: Callable[[], CompiledPolicy], sink: LogSink,
        hmac_key: bytes | None = None,
    ):
        if hmac_key is not None and (not isinstance(hmac_key, bytes) or not hmac_key):
            raise LogProtectionError("HMAC configuration must supply a nonempty secret key.")
        self.policy_loader = policy_loader
        self.sink = sink
        self._hmac_key = hmac_key

    def process(
        self, event: dict[str, Any], *, expected_analysis_digest: str | None = None,
    ) -> LogResult:
        original = _json_copy(event)
        warnings: set[str] = set()
        actions: list[dict[str, Any]] = []
        policy_revision = None
        policy: CompiledPolicy | None = None
        rules: dict[tuple[str, ...], LogAction] = {}
        try:
            loaded = self.policy_loader()
            if not isinstance(loaded, CompiledPolicy):
                raise ValueError
            loaded = CompiledPolicy.from_dict(loaded.to_dict())
            if loaded.revision.status is not RevisionStatus.APPROVED or loaded.approval is None:
                raise ValueError
            if expected_analysis_digest is not None and loaded.revision.analysis_digest != expected_analysis_digest:
                raise ValueError
            for field in loaded.fields:
                if field.path in rules:
                    raise ValueError
                rules[field.path] = field.log_action
            policy = loaded
            policy_revision = loaded.revision.revision_id
        except Exception:
            warnings.add("Active approved log policy is unavailable or stale; all event fields are masked.")

        def record(path: tuple[str | int, ...], action: str) -> None:
            actions.append({"path": list(path), "action": action})

        def visit(value: Any, path: tuple[str | int, ...]) -> Any:
            matching = [(pattern, action) for pattern, action in rules.items() if _matches(pattern, path)]
            action = None
            if matching:
                specificity = max(sum(part != "*" for part in pattern) for pattern, _ in matching)
                best = {candidate for pattern, candidate in matching if sum(part != "*" for part in pattern) == specificity}
                if len(best) == 1:
                    action = best.pop()
                else:
                    action = LogAction.MASK
                    warnings.add("Ambiguous log policy paths were conservatively masked.")
            if action is LogAction.DROP:
                record(path, action.value)
                return _DROP
            if action is LogAction.MASK:
                record(path, action.value)
                return MASK
            if action is LogAction.HMAC_PSEUDONYM:
                if self._hmac_key is None:
                    raise LogProtectionError("HMAC log action requires a configured secret; event was not persisted.")
                record(path, action.value)
                return "hmac-sha256:" + hmac.new(self._hmac_key, _json(value).encode("utf-8"), hashlib.sha256).hexdigest()
            if action is LogAction.ALLOW:
                record(path, action.value)
                if not isinstance(value, (dict, list)):
                    return value
            elif not any(len(pattern) > len(path) and _matches(pattern[:len(path)], path) for pattern in rules):
                warnings.add("Unmapped log field was masked.")
                record(path, LogAction.MASK.value)
                return MASK
            if isinstance(value, dict):
                protected = {}
                for key in sorted(value):
                    result = visit(value[key], path + (key,))
                    if result is not _DROP:
                        protected[key] = result
                return protected
            if isinstance(value, list):
                protected = []
                for index, child in enumerate(value):
                    result = visit(child, path + (index,))
                    if result is not _DROP:
                        protected.append(result)
                return protected
            warnings.add("Unmapped log field was masked.")
            record(path, LogAction.MASK.value)
            return MASK

        try:
            if policy is None:
                protected = {key: MASK for key in sorted(original)}
                for key in sorted(original):
                    record((key,), LogAction.MASK.value)
            else:
                protected = {}
                for key in sorted(original):
                    result = visit(original[key], (key,))
                    if result is not _DROP:
                        protected[key] = result
            record_id = self.sink.append(protected, policy_revision=policy_revision, mode="PROTECT")
            self.sink.record_audit("STRUCTURED_LOG", policy_revision, "PROTECT", tuple(sorted(warnings)))
            return LogResult(protected, record_id, policy_revision, tuple(sorted(warnings)), tuple(actions))
        except Exception:
            raise LogProtectionError("Structured log protection failed; no raw event was persisted.") from None
