"""Actual policy-bound response filtering and conservative fallback behavior."""

from copy import deepcopy
from dataclasses import replace
import json
from importlib.resources import files

import pytest

from veilmint.analyzer.report import generate_report
from veilmint.policy.models import APIAction, CompiledPolicy
from veilmint.policy.store import PolicyStore
from veilmint.runtime.api import APIEnforcer, RuntimeMode


@pytest.fixture
def golden():
    fixture_dir = files("veilmint").joinpath("fixtures")
    schema = json.loads(fixture_dir.joinpath("nexus_bank_schema.json").read_text(encoding="utf-8"))
    payload = json.loads(fixture_dir.joinpath("nexus_bank_payload.json").read_text(encoding="utf-8"))
    source = fixture_dir.joinpath("nexus_bank_consumer.py").read_text(encoding="utf-8")
    sensitivity = json.loads(fixture_dir.joinpath("sensitivity.json").read_text(encoding="utf-8"))
    report = generate_report(schema, payload, source, sensitivity)
    with PolicyStore(":memory:") as store:
        pending = store.create_revision(report)
        approved = store.review(pending.revision.revision_id, "Synthetic Reviewer", [
            field.name for field in pending.fields if field.removal_allowed
        ])
    return payload, approved, pending


def test_enforce_golden_removes_only_four_candidates_and_never_mutates_input(golden):
    payload, approved, _ = golden
    original = deepcopy(payload)
    result = APIEnforcer(lambda: approved).enforce(payload, RuntimeMode.ENFORCE)
    assert result.policy_valid
    assert len(payload) == 10
    assert len(result.payload) == 6
    assert payload == original
    assert "account_id" in result.payload
    assert "available_balance" in result.payload
    assert "internal_risk_flag" in result.payload
    assert result.removed_paths == (
        "/aadhaar_number", "/account_number", "/customer_address", "/customer_phone",
    )
    assert result.policy_revision == approved.revision.revision_id
    assert result.to_dict()["mode"] == "ENFORCE"
    assert "policy_revision" not in result.payload


@pytest.mark.parametrize("mode", [RuntimeMode.OBSERVE, RuntimeMode.WARN])
def test_observe_and_warn_report_plans_without_removing(golden, mode):
    payload, approved, _ = golden
    result = APIEnforcer(lambda: approved).enforce(payload, mode)
    assert result.payload == payload
    assert result.payload is not payload
    assert result.removed_paths == ()
    assert len(result.would_remove_paths) == 4


def test_safe_default_mode_is_observe(golden):
    payload, approved, _ = golden
    result = APIEnforcer(lambda: approved).enforce(payload)
    assert result.mode is RuntimeMode.OBSERVE
    assert result.payload == payload


def test_missing_and_unapproved_policy_keep_original(golden):
    payload, _, pending = golden
    def unavailable():
        raise OSError("SYNTHETIC_PRIVATE_MARKER")
    for loader in (lambda: pending, unavailable, lambda: None):
        result = APIEnforcer(loader).enforce(payload, RuntimeMode.ENFORCE)
        assert result.payload == payload
        assert result.policy_valid is False
        assert result.removed_paths == result.would_remove_paths == ()
        assert result.warnings
        assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(result.warnings)


def test_stale_analysis_keeps_original(golden):
    payload, approved, _ = golden
    result = APIEnforcer(lambda: approved).enforce(
        payload, RuntimeMode.ENFORCE, expected_analysis_digest="f" * 64
    )
    assert result.policy_valid is False
    assert result.payload == payload
    assert "current analysis" in result.warnings[0]


def test_loader_fetches_latest_each_call_so_new_revision_disables_old_approval(golden):
    payload, approved, pending = golden
    current = [approved]
    enforcer = APIEnforcer(lambda: current[0])
    assert len(enforcer.enforce(payload, RuntimeMode.ENFORCE).payload) == 6
    current[0] = pending
    assert enforcer.enforce(payload, RuntimeMode.ENFORCE).payload == payload


def test_unknown_fields_and_same_names_at_unrelated_paths_are_preserved(golden):
    payload, approved, _ = golden
    payload["new_unmapped"] = "SYNTHETIC_PRIVATE_MARKER"
    payload["unrelated"] = {"account_number": "SYNTHETIC_UNRELATED"}
    result = APIEnforcer(lambda: approved).enforce(payload, RuntimeMode.ENFORCE)
    assert result.payload["new_unmapped"] == "SYNTHETIC_PRIVATE_MARKER"
    assert result.payload["unrelated"]["account_number"] == "SYNTHETIC_UNRELATED"
    assert result.warnings
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(result.warnings)


def test_root_array_applies_root_object_rules_to_each_item(golden):
    payload, approved, _ = golden
    result = APIEnforcer(lambda: approved).enforce([payload, deepcopy(payload)], RuntimeMode.ENFORCE)
    assert [len(item) for item in result.payload] == [6, 6]
    assert len(result.removed_paths) == 8
    assert "/0/account_number" in result.removed_paths
    assert "/1/account_number" in result.removed_paths


def test_explicit_nested_array_paths_never_apply_by_leaf_name(golden):
    _, approved, _ = golden
    nested_fields = tuple(
        replace(field, path=("accounts", "*", field.name)) for field in approved.fields
    )
    policy = replace(approved, fields=nested_fields)
    payload = {
        "accounts": [
            {"account_number": "SYNTHETIC_ONE", "account_id": "ID_ONE", "internal_risk_flag": False},
            {"account_number": "SYNTHETIC_TWO", "account_id": "ID_TWO", "internal_risk_flag": True},
        ],
        "account_number": "SYNTHETIC_UNRELATED_ROOT",
        "other": {"account_number": "SYNTHETIC_UNRELATED_NESTED"},
    }
    result = APIEnforcer(lambda: policy).enforce(payload, RuntimeMode.ENFORCE)
    assert result.policy_valid
    assert result.payload["accounts"] == [
        {"account_id": "ID_ONE", "internal_risk_flag": False},
        {"account_id": "ID_TWO", "internal_risk_flag": True},
    ]
    assert result.payload["account_number"] == "SYNTHETIC_UNRELATED_ROOT"
    assert result.payload["other"]["account_number"] == "SYNTHETIC_UNRELATED_NESTED"
    assert result.removed_paths == ("/accounts/0/account_number", "/accounts/1/account_number")


def test_corrupted_used_field_action_is_revalidated_and_retained(golden):
    payload, approved, _ = golden
    used = next(field for field in approved.fields if field.name == "account_id")
    # Simulate memory corruption bypassing frozen dataclass initialization.
    object.__setattr__(used, "api_action", APIAction.REMOVE)
    object.__setattr__(used, "removal_allowed", True)
    result = APIEnforcer(lambda: approved).enforce(payload, RuntimeMode.ENFORCE)
    assert result.payload == payload
    assert result.policy_valid is False


def test_invalid_runtime_mode_fails_safe_without_echoing_value(golden):
    payload, approved, _ = golden
    result = APIEnforcer(lambda: approved).enforce(payload, "SYNTHETIC_PRIVATE_MARKER")
    assert result.payload == payload
    assert result.mode is RuntimeMode.OBSERVE
    assert result.policy_valid is False
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(result.warnings)


def test_internal_failure_never_returns_partially_minimized_output(golden, monkeypatch):
    payload, approved, _ = golden
    enforcer = APIEnforcer(lambda: approved)
    import veilmint.runtime.api as runtime_api
    def fail(_path):
        raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")
    monkeypatch.setattr(runtime_api, "_pointer", fail)
    result = enforcer.enforce(payload, RuntimeMode.ENFORCE)
    assert result.payload == payload
    assert result.policy_valid is False
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(result.warnings)
