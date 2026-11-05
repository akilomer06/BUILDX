"""Deterministic analysis-to-policy compilation, without runtime enforcement."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
import hashlib
import json
from typing import Any

from ..analyzer.ast_analyzer import Usage
from ..analyzer.sensitivity import Sensitivity
from .models import APIAction, CompiledPolicy, FieldPolicy, LogAction, PolicyRevision, ReviewerDecision, RevisionStatus


DEFAULT_LOG_MAPPING = {
    "GENERAL": "ALLOW", "INTERNAL": "MASK", "MEDIUM": "MASK",
    "FINANCIAL": "DROP", "HIGH": "DROP",
}


def normalize_log_mapping(mapping: Mapping[str, str] | None = None) -> dict[str, str]:
    result = dict(DEFAULT_LOG_MAPPING)
    if mapping is not None:
        if not isinstance(mapping, Mapping):
            raise ValueError("Log mapping must be an object mapping sensitivity to log action")
        for sensitivity, action in mapping.items():
            try:
                result[Sensitivity(sensitivity).value] = LogAction(action).value
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid log mapping entry: {sensitivity!r}: {action!r}") from exc
    return dict(sorted(result.items()))


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Analysis must contain finite JSON-compatible values") from exc


def _validated_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValueError("Analysis report must be an object")
    canonical = json.loads(_canonical_json(dict(report)))
    validation = canonical.get("schema_validation")
    if not isinstance(validation, dict) or validation.get("schema_valid") is not True or validation.get("payload_valid") is not True:
        raise ValueError("Analysis requires successful schema and payload validation")
    fields = canonical.get("fields")
    if not isinstance(fields, list):
        raise ValueError("Analysis fields must be a list")
    names: set[str] = set()
    paths: set[tuple[str, ...]] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Each analysis field must be an object")
        name = field.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Analysis field names must be nonempty and unique")
        names.add(name)
        path = field.get("path", [name])
        if not isinstance(path, list) or not path or any(not isinstance(part, str) or not part for part in path) or path[-1] != name:
            raise ValueError("Field paths must be explicit segments ending in the field name")
        if tuple(path) in paths:
            raise ValueError("Field policy paths must be unique")
        paths.add(tuple(path))
        evidence = field.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise ValueError(f"Analysis evidence for {name!r} must be a nonempty list of strings")
        field["evidence"] = sorted(set(evidence))
        for label in ("usage", "sensitivity"):
            if label in field and field[label] is not None and not isinstance(field[label], str):
                raise ValueError(f"Analysis {label} for {name!r} must be a string or absent")
    canonical["fields"] = sorted(fields, key=lambda field: field["name"])
    for key in ("warnings", "analyzer_warnings", "sensitivity_warnings"):
        if key in canonical:
            warnings = canonical[key]
            if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
                raise ValueError(f"Analysis {key} must be a list of strings")
            canonical[key] = sorted(set(warnings))
    return canonical


def analysis_digest(report: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(_validated_report(report)).encode("utf-8")).hexdigest()


def _known_fields(report: Mapping[str, Any], known_fields: Iterable[str] | None) -> tuple[str, ...]:
    if known_fields is None:
        return tuple(sorted(field["name"] for field in report["fields"]))
    if isinstance(known_fields, (str, bytes, Mapping)):
        raise ValueError("known_fields must be an iterable of field names")
    names = tuple(known_fields)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Known field names must be nonempty strings")
    return tuple(sorted(set(names)))


def policy_inputs_digest(
    report: Mapping[str, Any], log_mapping: Mapping[str, str] | None = None,
    known_fields: Iterable[str] | None = None,
) -> str:
    canonical = _validated_report(report)
    inputs = {
        "analysis_digest": analysis_digest(canonical),
        "log_mapping": normalize_log_mapping(log_mapping),
        "known_fields": list(_known_fields(canonical, known_fields)),
    }
    return hashlib.sha256(_canonical_json(inputs).encode("utf-8")).hexdigest()


def compile_policy(
    report: Mapping[str, Any], revision: PolicyRevision,
    decision: ReviewerDecision | None = None, *,
    log_mapping: Mapping[str, str] | None = None,
    known_fields: Iterable[str] | None = None,
) -> CompiledPolicy:
    canonical = _validated_report(report)
    mapping = normalize_log_mapping(log_mapping)
    inventory = _known_fields(canonical, known_fields)
    if not isinstance(revision, PolicyRevision):
        raise ValueError("A validated policy revision is required")
    if revision.analysis_digest != analysis_digest(canonical) or revision.inputs_digest != policy_inputs_digest(canonical, mapping, inventory):
        raise ValueError("Policy revision does not match the current analysis or policy input digest")
    if decision is not None:
        if not isinstance(decision, ReviewerDecision):
            raise ValueError("A validated reviewer decision is required")
        if any(getattr(decision, key) != getattr(revision, key) for key in ("revision_id", "analysis_digest", "inputs_digest")):
            raise ValueError("Stale reviewer decision: revision or analysis/policy input digest differs")
    selected = set(decision.approved_fields) if decision is not None and decision.decision == "APPROVE" else set()
    warnings: set[str] = set()
    for key in ("warnings", "analyzer_warnings", "sensitivity_warnings"):
        warnings.update(canonical.get(key, []))
    fields: list[FieldPolicy] = []
    known = set(inventory)
    seen: set[str] = set()
    for field in canonical["fields"]:
        name = field["name"]
        seen.add(name)
        eligible = True
        try:
            usage = Usage(field.get("usage"))
        except (TypeError, ValueError):
            usage = Usage.UNKNOWN
            eligible = False
            warnings.add(f"Field {name!r} has missing/unrecognized usage; defaulted to UNKNOWN and API KEEP.")
        try:
            sensitivity = Sensitivity(field.get("sensitivity"))
        except (TypeError, ValueError):
            sensitivity = Sensitivity.INTERNAL
            eligible = False
            warnings.add(f"Field {name!r} has missing/unrecognized sensitivity; defaulted to INTERNAL and API KEEP.")
        if name not in known:
            eligible = False
            warnings.add(f"Field {name!r} is unmapped in the supplied inventory; defaulted to API KEEP.")
        removal_allowed = eligible and usage is Usage.CANDIDATE_UNUSED
        if name in selected and not removal_allowed:
            raise ValueError(f"Field {name!r} is not an eligible candidate for removal")
        fields.append(FieldPolicy(
            name=name, usage=usage, sensitivity=sensitivity,
            api_action=APIAction.REMOVE if name in selected else APIAction.KEEP,
            log_action=LogAction(mapping[sensitivity.value]), evidence=tuple(field["evidence"]),
            path=tuple(field.get("path", [name])),
            removal_allowed=removal_allowed,
        ))
    for name in sorted(known - seen):
        if name in selected:
            raise ValueError(f"Field {name!r} has no analysis and cannot be approved for removal")
        reason = f"New/unmapped field {name!r} has no analysis evidence; defaulted to UNKNOWN, INTERNAL and API KEEP."
        warnings.add(reason)
        fields.append(FieldPolicy(
            name=name, usage=Usage.UNKNOWN, sensitivity=Sensitivity.INTERNAL,
            api_action=APIAction.KEEP, log_action=LogAction(mapping["INTERNAL"]), evidence=(reason,),
        ))
    nonexistent = selected - seen - known
    if nonexistent:
        raise ValueError(f"Approved fields do not exist: {', '.join(sorted(nonexistent))}")
    status = RevisionStatus.REVIEW_REQUIRED
    if decision is not None:
        status = RevisionStatus.APPROVED if decision.decision == "APPROVE" else RevisionStatus.REJECTED
    return CompiledPolicy(
        revision=replace(revision, status=status), fields=tuple(fields), warnings=tuple(sorted(warnings)),
        approval=decision, log_mapping=mapping,
    )
