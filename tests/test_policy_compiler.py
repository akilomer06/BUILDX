"""Conservative approval and deterministic policy compilation regressions."""

from copy import deepcopy
from dataclasses import replace
import json
from importlib.resources import files

import pytest

from veilmint.analyzer.ast_analyzer import Usage
from veilmint.analyzer.report import generate_report
from veilmint.analyzer.sensitivity import Sensitivity
from veilmint.policy.compiler import (
    DEFAULT_LOG_MAPPING, analysis_digest, compile_policy, normalize_log_mapping, policy_inputs_digest,
)
from veilmint.policy.models import (
    APIAction, CompiledPolicy, FieldPolicy, LogAction, PolicyRevision, ReviewerDecision, RevisionStatus,
)


NOW = "2026-11-04T12:00:00+00:00"
CANDIDATES = ("aadhaar_number", "account_number", "customer_address", "customer_phone")


@pytest.fixture
def report():
    fixtures = files("veilmint").joinpath("fixtures")
    return generate_report(
        json.loads(fixtures.joinpath("nexus_bank_schema.json").read_text(encoding="utf-8")),
        json.loads(fixtures.joinpath("nexus_bank_payload.json").read_text(encoding="utf-8")),
        fixtures.joinpath("nexus_bank_consumer.py").read_text(encoding="utf-8"),
        json.loads(fixtures.joinpath("sensitivity.json").read_text(encoding="utf-8")),
    )


def revision(report, *, mapping=None, known=None, number=1):
    return PolicyRevision(
        f"r{number}-demo", number, analysis_digest(report), policy_inputs_digest(report, mapping, known),
        NOW, RevisionStatus.REVIEW_REQUIRED,
    )


def decision(rev, selected=CANDIDATES, **kwargs):
    return ReviewerDecision(
        rev.revision_id, rev.analysis_digest, rev.inputs_digest, "local-reviewer", tuple(selected), NOW, **kwargs,
    )


def test_golden_default_keeps_all_fields_and_maps_logs_independently(report):
    result = compile_policy(report, revision(report))
    assert len(result.fields) == 10
    assert all(field.api_action is APIAction.KEEP for field in result.fields)
    assert result.revision.status is RevisionStatus.REVIEW_REQUIRED
    assert {field.name for field in result.fields if field.removal_allowed} == set(CANDIDATES)
    assert {field.name: field.log_action.value for field in result.fields} == {
        "account_id": "MASK", "account_type": "ALLOW", "currency": "ALLOW",
        "available_balance": "DROP", "recent_transactions": "DROP", "account_number": "DROP",
        "customer_phone": "MASK", "customer_address": "MASK", "aadhaar_number": "DROP",
        "internal_risk_flag": "MASK",
    }


def test_explicit_approval_removes_only_four_selected_candidates(report):
    rev = revision(report)
    result = compile_policy(report, rev, decision(rev))
    assert {field.name for field in result.fields if field.api_action is APIAction.REMOVE} == set(CANDIDATES)
    assert result.revision.status is RevisionStatus.APPROVED
    assert result.to_dict()["summary"]["fields_before"] == 10
    assert result.to_dict()["summary"]["fields_after"] == 6
    assert result.to_dict()["summary"]["fields_removed"] == 4
    assert result.approval.reviewer == "local-reviewer"


@pytest.mark.parametrize("field", ["account_id", "internal_risk_flag", "does_not_exist"])
def test_used_unknown_and_nonexistent_approvals_are_rejected(report, field):
    rev = revision(report)
    with pytest.raises(ValueError):
        compile_policy(report, rev, decision(rev, [field]))


@pytest.mark.parametrize("change", [
    {"revision_id": "r2-other"}, {"analysis_digest": "f" * 64}, {"inputs_digest": "a" * 64},
])
def test_decision_must_match_revision_and_both_digests(report, change):
    rev = revision(report)
    with pytest.raises(ValueError, match="Stale"):
        compile_policy(report, rev, replace(decision(rev), **change))


def test_mapping_changes_invalidate_revision_and_change_only_log_actions(report):
    original = compile_policy(report, revision(report))
    mapping = {"HIGH": "MASK", "GENERAL": "DROP"}
    with pytest.raises(ValueError, match="digest"):
        compile_policy(report, original.revision, log_mapping=mapping)
    changed = compile_policy(report, revision(report, mapping=mapping), log_mapping=mapping)
    assert [(field.name, field.api_action) for field in changed.fields] == [(field.name, field.api_action) for field in original.fields]
    assert next(field for field in changed.fields if field.name == "account_number").log_action is LogAction.MASK
    assert next(field for field in changed.fields if field.name == "account_type").log_action is LogAction.DROP


@pytest.mark.parametrize("missing_label", ["usage", "sensitivity"])
def test_missing_or_unrecognized_classification_keeps_field_and_warns(report, missing_label):
    report["fields"][0].pop(missing_label)
    rev = revision(report)
    result = compile_policy(report, rev)
    first = next(field for field in result.fields if field.name == report["fields"][0]["name"])
    assert first.api_action is APIAction.KEEP
    assert not first.removal_allowed
    assert any(missing_label in warning for warning in result.warnings)
    with pytest.raises(ValueError):
        compile_policy(report, rev, decision(rev, [first.name]))


def test_new_inventory_field_kept_without_borrowing_previous_approval(report):
    inventory = [field["name"] for field in report["fields"]] + ["new_secret"]
    rev = revision(report, known=inventory)
    result = compile_policy(report, rev, known_fields=inventory)
    new_field = next(field for field in result.fields if field.name == "new_secret")
    assert new_field.usage is Usage.UNKNOWN
    assert new_field.sensitivity is Sensitivity.INTERNAL
    assert new_field.api_action is APIAction.KEEP
    assert not new_field.removal_allowed
    assert any("new_secret" in warning for warning in result.warnings)
    with pytest.raises(ValueError):
        compile_policy(report, rev, decision(rev, ["new_secret"]), known_fields=inventory)


def test_rejected_revision_keeps_everything_and_records_decision(report):
    rev = revision(report)
    result = compile_policy(report, rev, decision(rev, [], decision="REJECT", notes="Need more evidence"))
    assert result.revision.status is RevisionStatus.REJECTED
    assert all(field.api_action is APIAction.KEEP for field in result.fields)
    assert result.approval.notes == "Need more evidence"


def test_compiler_and_json_roundtrip_are_deterministic(report):
    rev = revision(report)
    approval = decision(rev)
    first = compile_policy(report, rev, approval)
    reordered = deepcopy(report)
    reordered["fields"].reverse()
    reordered["warnings"].reverse()
    second = compile_policy(reordered, rev, approval)
    assert first == second
    assert CompiledPolicy.from_dict(json.loads(json.dumps(first.to_dict()))) == first
    assert PolicyRevision.from_dict(rev.to_dict()) == rev
    assert ReviewerDecision.from_dict(approval.to_dict()) == approval


@pytest.mark.parametrize("bad", [
    {"schema_validation": {"schema_valid": False, "payload_valid": True}},
    {"fields": [{"name": "x", "usage": "USED", "sensitivity": "GENERAL", "evidence": []}]},
    {"fields": [{"name": "x", "evidence": ["e"]}, {"name": "x", "evidence": ["e"]}]},
    {"fields": [{"name": "", "evidence": ["e"]}]},
    {"fields": [{"name": "x", "evidence": [42]}]},
])
def test_invalid_analysis_cannot_receive_digest_or_compile(report, bad):
    report.update(bad)
    with pytest.raises(ValueError):
        analysis_digest(report)


def test_models_reject_forged_unapproved_removal(report):
    rev = revision(report)
    compiled = compile_policy(report, rev)
    forged = compiled.to_dict()
    forged["fields"][0]["api_action"] = "REMOVE"
    with pytest.raises(ValueError, match="approved"):
        CompiledPolicy.from_dict(forged)
    with pytest.raises(ValueError):
        FieldPolicy("a", Usage.USED, Sensitivity.INTERNAL, APIAction.REMOVE, LogAction.MASK, ("direct",), removal_allowed=True)


@pytest.mark.parametrize("mapping", [{"SECRET": "DROP"}, {"HIGH": "DELETE"}, []])
def test_invalid_log_mapping_is_rejected(mapping):
    with pytest.raises(ValueError):
        normalize_log_mapping(mapping)


def test_empty_approval_and_timestamp_and_reviewer_validation(report):
    rev = revision(report)
    result = compile_policy(report, rev, decision(rev, []))
    assert result.revision.status is RevisionStatus.APPROVED
    assert result.to_dict()["summary"]["fields_after"] == 10
    with pytest.raises(ValueError):
        replace(decision(rev), reviewer=" ")
    with pytest.raises(ValueError):
        replace(rev, created_at="2026-11-04T12:00:00")
    with pytest.raises(ValueError):
        decision(rev, ["account_number"], decision="REJECT")
    assert normalize_log_mapping() == dict(sorted(DEFAULT_LOG_MAPPING.items()))
