"""Validated immutable policy metadata using the standard library only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any

from ..analyzer.ast_analyzer import Usage
from ..analyzer.sensitivity import Sensitivity


class APIAction(str, Enum):
    KEEP = "KEEP"
    REMOVE = "REMOVE"


class LogAction(str, Enum):
    ALLOW = "ALLOW"
    MASK = "MASK"
    DROP = "DROP"
    HMAC_PSEUDONYM = "HMAC_PSEUDONYM"


class RevisionStatus(str, Enum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def _label(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _timestamp(value: Any, name: str) -> str:
    _label(value, name)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return value


def _strings(value: Any, name: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a list or tuple of strings")
    result = tuple(_label(item, name) for item in value)
    if nonempty and not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Policy data must be a JSON object")
    return value


@dataclass(frozen=True)
class PolicyRevision:
    revision_id: str
    number: int
    analysis_digest: str
    inputs_digest: str
    created_at: str
    status: RevisionStatus

    def __post_init__(self) -> None:
        _label(self.revision_id, "revision_id")
        if isinstance(self.number, bool) or not isinstance(self.number, int) or self.number < 1:
            raise ValueError("Revision number must be a positive integer")
        _digest(self.analysis_digest, "analysis_digest")
        _digest(self.inputs_digest, "inputs_digest")
        _timestamp(self.created_at, "created_at")
        object.__setattr__(self, "status", RevisionStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id, "number": self.number,
            "analysis_digest": self.analysis_digest, "inputs_digest": self.inputs_digest,
            "created_at": self.created_at, "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PolicyRevision:
        data = _object(value)
        try:
            return cls(**{key: data[key] for key in (
                "revision_id", "number", "analysis_digest", "inputs_digest", "created_at", "status",
            )})
        except KeyError as exc:
            raise ValueError(f"Missing policy revision property: {exc.args[0]}") from exc


@dataclass(frozen=True)
class ReviewerDecision:
    revision_id: str
    analysis_digest: str
    inputs_digest: str
    reviewer: str
    approved_fields: tuple[str, ...]
    decided_at: str
    notes: str = ""
    decision: str = "APPROVE"

    def __post_init__(self) -> None:
        _label(self.revision_id, "revision_id")
        _digest(self.analysis_digest, "analysis_digest")
        _digest(self.inputs_digest, "inputs_digest")
        _label(self.reviewer, "reviewer")
        _timestamp(self.decided_at, "decided_at")
        if not isinstance(self.notes, str):
            raise ValueError("Decision notes must be a string")
        selected = _strings(self.approved_fields, "approved_fields")
        if len(set(selected)) != len(selected):
            raise ValueError("Approved fields must not contain duplicates")
        object.__setattr__(self, "approved_fields", tuple(sorted(selected)))
        if self.decision not in {"APPROVE", "REJECT"}:
            raise ValueError("Decision must be APPROVE or REJECT")
        if self.decision == "REJECT" and selected:
            raise ValueError("A rejected decision cannot approve field removals")

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id, "analysis_digest": self.analysis_digest,
            "inputs_digest": self.inputs_digest, "reviewer": self.reviewer,
            "approved_fields": list(self.approved_fields), "decided_at": self.decided_at,
            "notes": self.notes, "decision": self.decision,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ReviewerDecision:
        data = _object(value)
        try:
            return cls(
                revision_id=data["revision_id"], analysis_digest=data["analysis_digest"],
                inputs_digest=data["inputs_digest"], reviewer=data["reviewer"],
                approved_fields=data["approved_fields"], decided_at=data["decided_at"],
                notes=data.get("notes", ""), decision=data.get("decision", "APPROVE"),
            )
        except KeyError as exc:
            raise ValueError(f"Missing reviewer decision property: {exc.args[0]}") from exc


@dataclass(frozen=True)
class FieldPolicy:
    name: str
    usage: Usage
    sensitivity: Sensitivity
    api_action: APIAction
    log_action: LogAction
    evidence: tuple[str, ...]
    path: tuple[str, ...] = ()
    removal_allowed: bool = False

    def __post_init__(self) -> None:
        _label(self.name, "field name")
        object.__setattr__(self, "usage", Usage(self.usage))
        object.__setattr__(self, "sensitivity", Sensitivity(self.sensitivity))
        object.__setattr__(self, "api_action", APIAction(self.api_action))
        object.__setattr__(self, "log_action", LogAction(self.log_action))
        object.__setattr__(self, "evidence", tuple(sorted(set(_strings(self.evidence, "evidence", nonempty=True)))))
        object.__setattr__(self, "path", _strings(self.path or (self.name,), "field path", nonempty=True))
        if self.path[-1] != self.name:
            raise ValueError("Field path must end in the field name")
        if not isinstance(self.removal_allowed, bool):
            raise ValueError("removal_allowed must be a boolean")
        if self.removal_allowed and self.usage is not Usage.CANDIDATE_UNUSED:
            raise ValueError("Only candidate fields are eligible for removal")
        if self.api_action is APIAction.REMOVE and not self.removal_allowed:
            raise ValueError("REMOVE requires an eligible candidate field")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "usage": self.usage.value, "sensitivity": self.sensitivity.value,
            "api_action": self.api_action.value, "log_action": self.log_action.value,
            "evidence": list(self.evidence), "path": list(self.path),
            "removal_allowed": self.removal_allowed,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FieldPolicy:
        data = _object(value)
        try:
            return cls(
                name=data["name"], usage=data["usage"], sensitivity=data["sensitivity"],
                api_action=data["api_action"], log_action=data["log_action"], evidence=data["evidence"],
                path=data.get("path", ()), removal_allowed=data.get("removal_allowed", False),
            )
        except KeyError as exc:
            raise ValueError(f"Missing field policy property: {exc.args[0]}") from exc


@dataclass(frozen=True)
class CompiledPolicy:
    revision: PolicyRevision
    fields: tuple[FieldPolicy, ...]
    warnings: tuple[str, ...]
    approval: ReviewerDecision | None
    log_mapping: dict[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, PolicyRevision):
            raise ValueError("Compiled policy requires a validated revision")
        if not isinstance(self.fields, (tuple, list)) or not all(isinstance(field, FieldPolicy) for field in self.fields):
            raise ValueError("Compiled policy fields must contain validated FieldPolicy models")
        ordered = tuple(sorted(self.fields, key=lambda field: field.name))
        if len({field.name for field in ordered}) != len(ordered):
            raise ValueError("Compiled policy field names must be unique")
        if len({field.path for field in ordered}) != len(ordered):
            raise ValueError("Compiled policy paths must be unique")
        for parent in ordered:
            if parent.api_action is APIAction.REMOVE and any(
                child.api_action is APIAction.KEEP and len(child.path) > len(parent.path)
                and child.path[:len(parent.path)] == parent.path for child in ordered
            ):
                raise ValueError("A removal cannot contain an explicitly retained field")
        object.__setattr__(self, "fields", ordered)
        object.__setattr__(self, "warnings", tuple(sorted(set(_strings(self.warnings, "warnings")))))
        if not isinstance(self.log_mapping, Mapping):
            raise ValueError("Log mapping must be an object")
        try:
            mapping = {Sensitivity(key).value: LogAction(value).value for key, value in self.log_mapping.items()}
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid sensitivity-to-log-action mapping") from exc
        if set(mapping) != {label.value for label in Sensitivity}:
            raise ValueError("Compiled log mapping must cover every sensitivity")
        object.__setattr__(self, "log_mapping", dict(sorted(mapping.items())))
        if any(field.log_action.value != mapping[field.sensitivity.value] for field in ordered):
            raise ValueError("Field log action must follow the independent sensitivity mapping")
        selected: set[str] = set()
        expected_status = RevisionStatus.REVIEW_REQUIRED
        if self.approval is not None:
            if not isinstance(self.approval, ReviewerDecision):
                raise ValueError("Approval must be a validated reviewer decision")
            if any(getattr(self.approval, key) != getattr(self.revision, key) for key in (
                "revision_id", "analysis_digest", "inputs_digest",
            )):
                raise ValueError("Reviewer decision does not match the policy revision/digests")
            expected_status = RevisionStatus.APPROVED if self.approval.decision == "APPROVE" else RevisionStatus.REJECTED
            selected = set(self.approval.approved_fields)
        if self.revision.status is not expected_status:
            raise ValueError("Revision status does not match its reviewer decision")
        by_name = {field.name: field for field in ordered}
        for name in selected:
            if name not in by_name or not by_name[name].removal_allowed:
                raise ValueError(f"Field {name!r} is not eligible for removal")
        removed = {field.name for field in ordered if field.api_action is APIAction.REMOVE}
        if removed != selected:
            raise ValueError("Removed fields must exactly match this revision's approved selection")

    def to_dict(self) -> dict[str, Any]:
        before = len(self.fields)
        removed = sum(field.api_action is APIAction.REMOVE for field in self.fields)
        return {
            "revision": self.revision.to_dict(), "fields": [field.to_dict() for field in self.fields],
            "warnings": list(self.warnings),
            "approval": None if self.approval is None else self.approval.to_dict(),
            "log_mapping": dict(self.log_mapping),
            "summary": {
                "fields_before": before, "fields_after": before - removed, "fields_removed": removed,
                "api_actions": {action.value: sum(field.api_action is action for field in self.fields) for action in APIAction},
                "log_actions": {action.value: sum(field.log_action is action for field in self.fields) for action in LogAction},
            },
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> CompiledPolicy:
        data = _object(value)
        try:
            return cls(
                revision=PolicyRevision.from_dict(data["revision"]),
                fields=tuple(FieldPolicy.from_dict(field) for field in data["fields"]),
                warnings=data["warnings"],
                approval=None if data["approval"] is None else ReviewerDecision.from_dict(data["approval"]),
                log_mapping=data["log_mapping"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("Malformed compiled policy document") from exc
