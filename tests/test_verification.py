"""Canaries must inspect real component output and the actual SQLite record."""

from dataclasses import replace
import json
import sqlite3

import pytest

from veilmint.demo import golden_analysis
from veilmint.policy.compiler import analysis_digest
from veilmint.policy.store import PolicyStore
from veilmint.runtime.api import APIEnforcer
from veilmint.runtime.logs import LogSink
from veilmint.verification import verify_paths


CANDIDATES = ("account_number", "aadhaar_number", "customer_phone", "customer_address")


@pytest.fixture
def approved(tmp_path):
    path = tmp_path / "verification.sqlite3"
    report = golden_analysis()
    with PolicyStore(path) as store:
        pending = store.create_revision(report)
        current = store.review(pending.revision.revision_id, "Synthetic reviewer", CANDIDATES)

    def loader():
        with PolicyStore(path) as store:
            return store.get()

    return path, loader, current, analysis_digest(report)


def test_golden_verification_inspects_runtime_output_and_actual_persisted_event(approved):
    path, loader, current, digest = approved
    sink = LogSink(path)
    result = verify_paths(loader, sink, expected_analysis_digest=digest)
    assert result["status"] == "PASS"
    assert result["scope"] == "Synthetic, path-scoped verification"
    assert result["synthetic"] is True
    assert all(check["passed"] for check in result["checks"])
    assert result["policy_revision"] == current.revision.revision_id
    assert len(result["api"]["original"]) == 10
    assert len(result["api"]["output"]) == 6
    assert "internal_risk_flag" in result["api"]["output"]
    # USED financial values may legitimately remain in the API.
    assert result["api"]["output"]["available_balance"] == result["api"]["original"]["available_balance"]
    assert result["log"]["persisted"]["event"] == result["log"]["sanitized"]
    record_id = result["log"]["persisted"]["id"]
    with sqlite3.connect(path) as db:
        stored = json.loads(db.execute("SELECT event_json FROM veilmint_protected_logs WHERE id=?", (record_id,)).fetchone()[0])
    assert stored == result["log"]["sanitized"]
    disk = path.read_bytes()
    for name in ("account_number", "aadhaar_number", "available_balance", "customer_phone", "customer_address"):
        assert result["api"]["original"][name].encode() not in disk
    assert result["api"]["original"]["recent_transactions"][0]["synthetic_marker"].encode() not in disk
    kinds = [record["kind"] for record in sink.audits()]
    assert "CANARY_API" in kinds and "STRUCTURED_LOG" in kinds and "CANARY_VERIFY" in kinds
    assert "VEILMINT_SYNTHETIC_CANARY" not in json.dumps(sink.audits())


def test_each_verification_run_is_fresh_with_unique_markers(approved):
    path, loader, _, digest = approved
    first = verify_paths(loader, LogSink(path), expected_analysis_digest=digest)
    second = verify_paths(loader, LogSink(path), expected_analysis_digest=digest)
    assert first["status"] == second["status"] == "PASS"
    assert first["run_id"] != second["run_id"]
    assert first["api"]["original"]["account_number"] != second["api"]["original"]["account_number"]
    assert first["log"]["persisted"]["id"] != second["log"]["persisted"]["id"]


@pytest.mark.parametrize("failure", ["missing", "stale", "requested_revision"])
def test_missing_stale_or_requested_revision_mismatch_fails_without_false_success(approved, failure):
    path, loader, _, digest = approved

    def missing():
        raise RuntimeError("RAW_SYNTHETIC_LOADER_EXCEPTION")

    sink = LogSink(path)
    result = verify_paths(
        missing if failure == "missing" else loader, sink,
        expected_analysis_digest="f" * 64 if failure == "stale" else digest,
        revision_id="does-not-match" if failure == "requested_revision" else None,
    )
    assert result["status"] == "FAIL"
    assert any(not check["passed"] for check in result["checks"])
    assert result["log"]["persisted"] == {}
    assert "RAW_SYNTHETIC_LOADER_EXCEPTION" not in json.dumps(result)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM veilmint_protected_logs").fetchone()[0] == 0


def test_unapproved_latest_revision_is_not_replaced_by_an_older_approval(approved):
    path, loader, _, digest = approved
    with PolicyStore(path) as store:
        store.create_revision(golden_analysis(), force_new=True)
    result = verify_paths(loader, LogSink(path), expected_analysis_digest=digest)
    assert result["status"] == "FAIL"
    assert result["policy_revision"] is None


def test_real_api_marker_leak_is_failure_even_if_trace_claims_success(approved, monkeypatch):
    path, loader, _, digest = approved
    original_enforce = APIEnforcer.enforce

    def leak(self, payload, *args, **kwargs):
        protected = original_enforce(self, payload, *args, **kwargs)
        return replace(protected, payload=payload)

    monkeypatch.setattr(APIEnforcer, "enforce", leak)
    result = verify_paths(loader, LogSink(path), expected_analysis_digest=digest)
    assert result["status"] == "FAIL"
    assert any(not check["passed"] and "API removal" in check["name"] for check in result["checks"])


def test_unknown_field_missing_from_actual_api_output_fails(approved, monkeypatch):
    path, loader, _, digest = approved
    original_enforce = APIEnforcer.enforce

    def lose_unknown(self, payload, *args, **kwargs):
        protected = original_enforce(self, payload, *args, **kwargs)
        output = dict(protected.payload)
        output.pop("internal_risk_flag")
        return replace(protected, payload=output)

    monkeypatch.setattr(APIEnforcer, "enforce", lose_unknown)
    result = verify_paths(loader, LogSink(path), expected_analysis_digest=digest)
    assert result["status"] == "FAIL"
    assert next(check for check in result["checks"] if check["name"] == "UNKNOWN retained")["passed"] is False


def test_tampered_actual_sqlite_record_cannot_pass_from_sanitized_memory(approved):
    path, loader, _, digest = approved

    class TamperingSink(LogSink):
        def append(self, event, **kwargs):
            record_id = super().append(event, **kwargs)
            corrupted = {**event, "account_number": "SYNTHETIC_PERSISTENCE_FAILURE_MARKER"}
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE veilmint_protected_logs SET event_json=? WHERE id=?", (json.dumps(corrupted), record_id))
            return record_id

    result = verify_paths(loader, TamperingSink(path), expected_analysis_digest=digest)
    assert result["status"] == "FAIL"
    assert next(check for check in result["checks"] if check["name"] == "Log persisted result")["passed"] is False
    assert next(check for check in result["checks"] if check["name"] == "Log DROP · account_number")["passed"] is False


@pytest.mark.parametrize("mapping", [{"HIGH": "ALLOW"}, {"GENERAL": "DROP"}, {"HIGH": "HMAC_PSEUDONYM"}])
def test_canary_checks_actual_configured_log_actions_without_hardcoded_golden_assumptions(approved, mapping):
    path, loader, _, digest = approved
    with PolicyStore(path) as store:
        pending = store.create_revision(golden_analysis(), log_mapping=mapping)
        store.review(pending.revision.revision_id, "Synthetic reviewer", CANDIDATES)
    key = b"SYNTHETIC_CANARY_TEST_KEY" if mapping.get("HIGH") == "HMAC_PSEUDONYM" else None
    result = verify_paths(loader, LogSink(path), expected_analysis_digest=digest, hmac_key=key)
    assert result["status"] == "PASS"
    if mapping.get("HIGH") == "ALLOW":
        assert result["log"]["persisted"]["event"]["account_number"] == result["api"]["original"]["account_number"]
    if key:
        assert key.decode() not in json.dumps(result)
        assert key not in path.read_bytes()


def test_mid_run_revision_change_is_failure(approved):
    path, loader, _, digest = approved
    calls = 0

    def changing_loader():
        nonlocal calls
        calls += 1
        if calls == 4:
            with PolicyStore(path) as store:
                store.create_revision(golden_analysis(), force_new=True)
        return loader()

    result = verify_paths(changing_loader, LogSink(path), expected_analysis_digest=digest)
    assert result["status"] == "FAIL"


def test_audit_error_is_a_static_failure_without_raw_exception_data(approved):
    path, loader, _, digest = approved

    class FailingAudit(LogSink):
        def record_audit(self, *args, **kwargs):
            raise RuntimeError("RAW_SYNTHETIC_AUDIT_EXCEPTION")

    result = verify_paths(loader, FailingAudit(path), expected_analysis_digest=digest)
    assert result["status"] == "FAIL"
    assert "RAW_SYNTHETIC_AUDIT_EXCEPTION" not in json.dumps(result)
