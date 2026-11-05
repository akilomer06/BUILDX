"""Prove values are protected before they ever reach the SQLite log sink."""

from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

from veilmint.analyzer.ast_analyzer import Usage
from veilmint.analyzer.sensitivity import Sensitivity
from veilmint.policy.compiler import DEFAULT_LOG_MAPPING
from veilmint.policy.models import (
    APIAction, CompiledPolicy, FieldPolicy, LogAction, PolicyRevision, ReviewerDecision, RevisionStatus,
)
from veilmint.runtime.logs import LogProtectionError, LogSink, MASK, StructuredLogPipeline


NOW = "2026-11-04T12:00:00+00:00"


def policy(specs, *, mapping=None):
    mapping = {**DEFAULT_LOG_MAPPING, **(mapping or {})}
    revision = PolicyRevision("r1-synthetic", 1, "0" * 64, "1" * 64, NOW, RevisionStatus.APPROVED)
    approval = ReviewerDecision(revision.revision_id, revision.analysis_digest, revision.inputs_digest, "test-reviewer", (), NOW)
    return CompiledPolicy(
        revision=revision,
        fields=tuple(FieldPolicy(
            name=path[-1], usage=Usage.USED, sensitivity=Sensitivity(sensitivity), api_action=APIAction.KEEP,
            log_action=LogAction(mapping[sensitivity]), evidence=("synthetic test policy",), path=path,
        ) for name, sensitivity, path in specs),
        warnings=(), approval=approval, log_mapping=mapping,
    )


@pytest.fixture
def golden_policy():
    return policy([
        ("account_id", "INTERNAL", ("account_id",)),
        ("account_type", "GENERAL", ("account_type",)),
        ("available_balance", "FINANCIAL", ("available_balance",)),
        ("account_number", "HIGH", ("account_number",)),
        ("customer_phone", "MEDIUM", ("customer_phone",)),
        ("aadhaar_number", "HIGH", ("aadhaar_number",)),
        ("internal_risk_flag", "INTERNAL", ("internal_risk_flag",)),
    ])


def test_golden_actions_are_applied_before_sink_and_never_write_sensitive_values(tmp_path, golden_policy):
    raw_values = ["RAW_SYNTHETIC_ACCOUNT", "RAW_SYNTHETIC_BALANCE", "RAW_SYNTHETIC_PHONE", "RAW_SYNTHETIC_AADHAAR"]

    class CheckingSink(LogSink):
        def append(self, event, **kwargs):
            assert all(value not in json.dumps(event) for value in raw_values)
            return super().append(event, **kwargs)

    db = tmp_path / "logs.sqlite3"
    sink = CheckingSink(db)
    event = {
        "account_id": "RAW_SYNTHETIC_ID", "account_type": "DEMO_CHECKING",
        "available_balance": raw_values[1], "account_number": raw_values[0],
        "customer_phone": raw_values[2], "aadhaar_number": raw_values[3],
        "internal_risk_flag": False, "harmless_unmapped": "SYNTHETIC_UNKNOWN",
    }
    result = StructuredLogPipeline(lambda: golden_policy, sink).process(event)
    expected = {
        "account_id": MASK, "account_type": "DEMO_CHECKING", "customer_phone": MASK,
        "internal_risk_flag": MASK, "harmless_unmapped": MASK,
    }
    assert result.event == expected
    assert sink.get(result.record_id)["event"] == expected
    assert result.policy_revision == golden_policy.revision.revision_id
    assert result.warnings == ("Unmapped log field was masked.",)
    assert event["account_number"] == raw_values[0]  # Input was never mutated.
    disk = db.read_bytes()
    assert all(value.encode() not in disk for value in raw_values)
    assert b"RAW_SYNTHETIC_ID" not in disk
    assert b"SYNTHETIC_UNKNOWN" not in disk
    audits = sink.audits()
    assert audits[0]["policy_revision"] == golden_policy.revision.revision_id
    assert audits[0]["mode"] == "PROTECT"
    assert "event" not in audits[0]
    trace = json.dumps(result.to_dict()["actions"])
    assert all(value not in trace for value in raw_values)


def test_log_action_is_independent_of_used_api_keep(tmp_path, golden_policy):
    field = next(field for field in golden_policy.fields if field.name == "available_balance")
    assert field.usage is Usage.USED and field.api_action is APIAction.KEEP
    result = StructuredLogPipeline(lambda: golden_policy, LogSink(tmp_path / "logs.db")).process({"available_balance": "RAW_SYNTHETIC"})
    assert result.event == {}
    assert result.actions[0]["action"] == "DROP"


def test_nested_objects_and_array_wildcards_are_path_aware(tmp_path):
    compiled = policy([
        ("profile.name", "GENERAL", ("profile", "name")),
        ("profile.secret", "HIGH", ("profile", "secret")),
        ("transactions.note", "GENERAL", ("transactions", "*", "note")),
        ("transactions.amount", "FINANCIAL", ("transactions", "*", "amount")),
    ])
    event = {
        "profile": {"name": "SYNTHETIC_DISPLAY", "secret": "RAW_SYNTHETIC_SECRET", "extra": "RAW_UNKNOWN"},
        "transactions": [{"note": "DEMO_ONE", "amount": 11}, {"note": "DEMO_TWO", "amount": 12}],
        "unrelated": {"name": "RAW_UNMAPPED_NAME"},
    }
    sink = LogSink(tmp_path / "nested.db")
    result = StructuredLogPipeline(lambda: compiled, sink).process(event)
    assert result.event == {
        "profile": {"name": "SYNTHETIC_DISPLAY", "extra": MASK},
        "transactions": [{"note": "DEMO_ONE"}, {"note": "DEMO_TWO"}],
        "unrelated": MASK,
    }
    assert {tuple(action["path"]) for action in result.actions if action["action"] == "DROP"} == {
        ("profile", "secret"), ("transactions", 0, "amount"), ("transactions", 1, "amount"),
    }


def test_allow_containers_recurse_and_never_blanket_allow_unknown_children(tmp_path):
    compiled = policy([
        ("profile", "GENERAL", ("profile",)),
        ("profile.safe", "GENERAL", ("profile", "safe")),
        ("list", "GENERAL", ("list",)),
    ])
    result = StructuredLogPipeline(lambda: compiled, LogSink(tmp_path / "allow.db")).process({
        "profile": {"safe": "DEMO", "unknown": "RAW_SYNTHETIC"},
        "list": ["RAW_ARRAY_ITEM", {"nested": "RAW_NESTED"}],
    })
    assert result.event == {"profile": {"safe": "DEMO", "unknown": MASK}, "list": [MASK, MASK]}


def test_equally_specific_overlapping_array_paths_never_choose_allow_arbitrarily(tmp_path):
    compiled = policy([
        ("first", "GENERAL", ("matrix", "*", "0")),
        ("second", "HIGH", ("matrix", "0", "*")),
    ])
    result = StructuredLogPipeline(lambda: compiled, LogSink(tmp_path / "overlap.db")).process({
        "matrix": [["RAW_SYNTHETIC_OVERLAPPING_RULE"]],
    })
    assert result.event == {"matrix": [[MASK]]}
    assert any("Ambiguous" in warning for warning in result.warnings)


def test_hmac_is_stable_canonical_and_key_sensitive_without_persisting_secret(tmp_path):
    compiled = policy([("identifier", "INTERNAL", ("identifier",))], mapping={"INTERNAL": "HMAC_PSEUDONYM"})
    value = {"z": "RAW_SYNTHETIC_ID", "a": 1}
    sink = LogSink(tmp_path / "hmac.db")
    first = StructuredLogPipeline(lambda: compiled, sink, b"SYNTHETIC_TEST_KEY_ONE").process({"identifier": value})
    same = StructuredLogPipeline(lambda: compiled, sink, b"SYNTHETIC_TEST_KEY_ONE").process({"identifier": {"a": 1, "z": "RAW_SYNTHETIC_ID"}})
    other_key = StructuredLogPipeline(lambda: compiled, sink, b"SYNTHETIC_TEST_KEY_TWO").process({"identifier": value})
    other_value = StructuredLogPipeline(lambda: compiled, sink, b"SYNTHETIC_TEST_KEY_ONE").process({"identifier": "OTHER_SYNTHETIC_ID"})
    assert first.event == same.event
    assert first.event != other_key.event
    assert first.event != other_value.event
    assert first.event["identifier"].startswith("hmac-sha256:")
    disk = sink.path.read_bytes()
    assert b"RAW_SYNTHETIC_ID" not in disk
    assert b"SYNTHETIC_TEST_KEY_ONE" not in disk


def test_missing_hmac_key_rejects_whole_event_before_persistence(tmp_path):
    compiled = policy([("identifier", "INTERNAL", ("identifier",))], mapping={"INTERNAL": "HMAC_PSEUDONYM"})
    sink = LogSink(tmp_path / "missing-key.db")
    with pytest.raises(LogProtectionError) as exc:
        StructuredLogPipeline(lambda: compiled, sink).process({"identifier": "RAW_SYNTHETIC_ID"})
    assert "RAW_SYNTHETIC_ID" not in str(exc.value)
    assert sink.audits() == []
    with sqlite3.connect(sink.path) as db:
        assert db.execute("SELECT COUNT(*) FROM veilmint_protected_logs").fetchone()[0] == 0


@pytest.mark.parametrize("bad_policy", ["missing", "unapproved", "stale", "invalid"])
def test_policy_failures_mask_every_value_and_do_not_expose_loader_errors(tmp_path, golden_policy, bad_policy):
    def loader():
        if bad_policy == "missing":
            raise RuntimeError("RAW_SYNTHETIC_LOADER_SECRET")
        if bad_policy == "unapproved":
            return CompiledPolicy(
                replace(golden_policy.revision, status=RevisionStatus.REVIEW_REQUIRED),
                golden_policy.fields, (), None, golden_policy.log_mapping,
            )
        if bad_policy == "invalid":
            return {"secret": "RAW_SYNTHETIC_BAD_POLICY"}
        return golden_policy

    sink = LogSink(tmp_path / f"{bad_policy}.db")
    result = StructuredLogPipeline(loader, sink).process(
        {"account_type": "RAW_SYNTHETIC_VALUE", "nested": {"a": "RAW_SYNTHETIC_NESTED"}},
        expected_analysis_digest="f" * 64 if bad_policy == "stale" else None,
    )
    assert result.event == {"account_type": MASK, "nested": MASK}
    assert result.policy_revision is None
    assert result.warnings
    assert "RAW_SYNTHETIC" not in json.dumps(result.to_dict())
    assert b"RAW_SYNTHETIC" not in sink.path.read_bytes()


@pytest.mark.parametrize("exception_type", [RuntimeError, LogProtectionError])
def test_sink_failures_never_expose_raw_exception_values(golden_policy, exception_type):
    class FailingSink:
        def append(self, event, **kwargs):
            assert event == {"account_id": MASK}
            raise exception_type("RAW_SYNTHETIC_EXCEPTION_VALUE")

    with pytest.raises(LogProtectionError) as exc:
        StructuredLogPipeline(lambda: golden_policy, FailingSink()).process({"account_id": "RAW_SYNTHETIC_ID"})
    assert "RAW_SYNTHETIC" not in str(exc.value)
    assert exc.value.__suppress_context__


@pytest.mark.parametrize("event", [[], {"value": object()}, {1: "RAW_SYNTHETIC"}, {"value": float("nan")}])
def test_non_json_events_are_rejected_without_persistence(tmp_path, golden_policy, event):
    sink = LogSink(tmp_path / "invalid-event.db")
    with pytest.raises(LogProtectionError):
        StructuredLogPipeline(lambda: golden_policy, sink).process(event)
    assert sink.audits() == []


def test_log_tables_preserve_existing_policy_schema_version_and_close_connections(tmp_path):
    db_path = tmp_path / "shared.db"
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA user_version=1")
    sink = LogSink(db_path)
    sink.append({"safe": MASK}, policy_revision=None)
    with sqlite3.connect(db_path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        db.execute("BEGIN EXCLUSIVE")
        db.rollback()
    assert LogSink(db_path).get(1)["event"] == {"safe": MASK}
    with pytest.raises(LogProtectionError):
        LogSink(":memory:")
