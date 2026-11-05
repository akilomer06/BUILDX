"""HTTP integration checks exercise real policy, runtime and SQLite paths."""

import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from veilmint.config import Settings
from veilmint.demo import golden_analysis, golden_log_event, golden_payload
from veilmint.policy.store import PolicyStore
from veilmint.server import create_app


CANDIDATES = {"aadhaar_number", "account_number", "customer_address", "customer_phone"}


def _seed(db, *, approve=True):
    with PolicyStore(db) as store:
        pending = store.create_revision(golden_analysis())
        if not approve:
            return pending
        return store.review(
            pending.revision.revision_id, "Synthetic integration reviewer", sorted(CANDIDATES),
            notes="Synthetic fixture only",
        )


def _client(db, *, mode="OBSERVE"):
    return TestClient(create_app(Settings(database_path=db, mode=mode)))


def test_health_is_synthetic_and_does_not_require_an_approved_policy(tmp_path):
    with _client(tmp_path / "policies.sqlite3") as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["synthetic"] is True


def test_enforced_demo_loads_real_approved_policy_and_keeps_unknown(tmp_path):
    db = tmp_path / "policies.sqlite3"
    approved = _seed(db)
    with _client(db) as client:
        response = client.get("/api/demo/account", params={"mode": "ENFORCE"})
    assert response.status_code == 200
    body = response.json()
    assert body["synthetic"] is True
    assert body["original"] == golden_payload()
    assert len(body["original"]) == 10
    assert len(body["output"]) == 6
    assert set(body["original"]) - set(body["output"]) == CANDIDATES
    assert body["output"]["internal_risk_flag"] == body["original"]["internal_risk_flag"]
    assert body["output"]["available_balance"] == body["original"]["available_balance"]
    assert body["trace"]["policy_revision"] == approved.revision.revision_id
    assert body["trace"]["policy_valid"] is True
    assert body["trace"]["mode"] == "ENFORCE"


@pytest.mark.parametrize("mode", ["OBSERVE", "WARN"])
def test_non_enforcing_modes_return_original_response(tmp_path, mode):
    db = tmp_path / "policies.sqlite3"
    _seed(db)
    with _client(db) as client:
        response = client.get("/api/demo/account", params={"mode": mode})
    assert response.status_code == 200
    body = response.json()
    assert body["output"] == body["original"] == golden_payload()
    assert body["trace"]["removed_paths"] == []
    assert len(body["trace"]["would_remove_paths"]) == 4


def test_customer_response_uses_configured_mode_without_policy_metadata(tmp_path):
    db = tmp_path / "policies.sqlite3"
    _seed(db)
    with _client(db, mode="ENFORCE") as client:
        response = client.get("/api/demo/account/response")
    assert response.status_code == 200
    output = response.json()
    assert len(output) == 6
    assert "internal_risk_flag" in output
    assert "policy_revision" not in output
    assert "mode" not in output
    assert "trace" not in output


def test_default_runtime_mode_observes_instead_of_removing(tmp_path):
    db = tmp_path / "policies.sqlite3"
    _seed(db)
    with _client(db) as client:
        response = client.get("/api/demo/account/response")
    assert response.status_code == 200
    assert response.json() == golden_payload()


@pytest.mark.parametrize("state", ["missing", "unapproved", "stale", "different_analysis"])
def test_missing_unapproved_or_newer_pending_policy_never_removes(tmp_path, state):
    db = tmp_path / "policies.sqlite3"
    if state == "unapproved":
        _seed(db, approve=False)
    elif state == "stale":
        _seed(db)
        with PolicyStore(db) as store:
            store.create_revision(golden_analysis(), force_new=True)
    elif state == "different_analysis":
        report = golden_analysis()
        report["analysis"]["consumer"] = "different_synthetic_consumer.py"
        with PolicyStore(db) as store:
            pending = store.create_revision(report)
            store.review(pending.revision.revision_id, "Synthetic reviewer", sorted(CANDIDATES))
    with _client(db) as client:
        response = client.get("/api/demo/account", params={"mode": "ENFORCE"})
    assert response.status_code == 200
    body = response.json()
    assert body["output"] == body["original"] == golden_payload()
    assert body["trace"]["policy_valid"] is False
    assert body["trace"]["removed_paths"] == []
    assert body["trace"]["warnings"]


def test_corrupt_policy_fails_safe_without_exposing_exception_data(tmp_path):
    db = tmp_path / "policies.sqlite3"
    _seed(db)
    sentinel = "SYNTHETIC_CORRUPT_PRIVATE_VALUE"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE veilmint_policy_revisions SET compiled_json = ?",
            (json.dumps({"private": sentinel}),),
        )
    with _client(db) as client:
        response = client.get("/api/demo/account", params={"mode": "ENFORCE"})
    assert response.status_code == 200
    body = response.json()
    assert body["output"] == golden_payload()
    assert body["trace"]["policy_valid"] is False
    assert body["trace"]["warnings"]
    assert sentinel not in response.text
    assert "Traceback" not in response.text


def test_log_demo_sanitizes_before_real_sqlite_persistence(tmp_path):
    db = tmp_path / "policies.sqlite3"
    approved = _seed(db)
    with _client(db) as client:
        response = client.post("/api/demo/log")
    assert response.status_code == 200
    body = response.json()
    assert body["synthetic"] is True
    assert body["original"] == golden_log_event()
    sanitized = body["sanitized"]
    assert sanitized == body["persisted"]["event"]
    assert sanitized["account_type"] == body["original"]["account_type"]
    for name in ("account_id", "customer_phone", "internal_risk_flag"):
        assert sanitized[name] == "[REDACTED]"
    for name in ("available_balance", "account_number", "aadhaar_number"):
        assert name not in sanitized
    unknown_names = set(body["original"]) - {field.name for field in approved.fields}
    assert unknown_names
    assert all(sanitized[name] == "[REDACTED]" for name in unknown_names)
    assert body["trace"]["warnings"]
    assert body["persisted"]["policy_revision"] == approved.revision.revision_id
    assert body["trace"]["policy_revision"] == approved.revision.revision_id
    assert "policy_revision" not in sanitized
    database_bytes = db.read_bytes()
    for name in ("account_number", "aadhaar_number", "customer_phone"):
        assert str(body["original"][name]).encode("utf-8") not in database_bytes


def test_request_caller_cannot_supply_a_runtime_policy_or_raw_log_event(tmp_path):
    db = tmp_path / "policies.sqlite3"
    with _client(db) as client:
        account = client.get(
            "/api/demo/account", params={"mode": "ENFORCE", "policy": "REMOVE_EVERYTHING"},
        )
        logged = client.post(
            "/api/demo/log", json={"account_number": "SYNTHETIC_CALLER_RAW_SENTINEL", "policy": "ALLOW"},
        )
    assert account.status_code == 200
    assert account.json()["output"] == golden_payload()
    assert logged.status_code == 200
    assert logged.json()["original"] == golden_log_event()
    assert "SYNTHETIC_CALLER_RAW_SENTINEL" not in db.read_bytes().decode("utf-8", errors="ignore")


def test_invalid_mode_is_rejected_without_echoing_input_or_stack_trace(tmp_path):
    raw_value = "SYNTHETIC_INVALID_MODE_PRIVATE_SENTINEL"
    with _client(tmp_path / "policies.sqlite3") as client:
        response = client.get("/api/demo/account", params={"mode": raw_value})
    assert response.status_code == 422
    assert raw_value not in response.text
    assert "Traceback" not in response.text


@pytest.mark.parametrize(
    ("target", "method", "path"),
    [
        ("veilmint.server.APIEnforcer.enforce", "GET", "/api/demo/account"),
        ("veilmint.server.StructuredLogPipeline.process", "POST", "/api/demo/log"),
        ("veilmint.server.golden_analysis", "GET", "/api/demo/account"),
    ],
)
def test_unexpected_runtime_exceptions_are_contained_at_http_boundary(tmp_path, monkeypatch, caplog, target, method, path):
    db = tmp_path / "policies.sqlite3"
    _seed(db)
    private_value = "SYNTHETIC_RUNTIME_EXCEPTION_PRIVATE_SENTINEL"

    def broken_runtime(*_args, **_kwargs):
        raise RuntimeError(private_value)

    monkeypatch.setattr(target, broken_runtime)
    # Default TestClient re-raises uncontained application exceptions. A generic
    # error handler alone is insufficient: the endpoint must contain failures.
    with _client(db) as client:
        response = client.request(method, path)
    assert response.status_code in (200, 503)
    assert private_value not in response.text
    assert "Traceback" not in response.text
    assert private_value not in caplog.text
    if response.status_code == 200:
        assert method == "GET"
        assert response.json()["output"] == golden_payload()
    assert private_value.encode("utf-8") not in db.read_bytes()
