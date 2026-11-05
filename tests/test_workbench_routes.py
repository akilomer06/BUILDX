"""HTTP contract integration: actual analysis, review, runtime, sink and canary."""

import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from veilmint.config import Settings
from veilmint.policy.compiler import analysis_digest
from veilmint.server import create_app


CANDIDATES = ["aadhaar_number", "account_number", "customer_address", "customer_phone"]


@pytest.fixture
def workbench(tmp_path):
    settings = Settings(database_path=tmp_path / "workbench.sqlite3")
    with TestClient(create_app(settings)) as client:
        yield client, settings


def create_revision(client, *, force_new=False):
    response = client.post("/api/policy/revisions", json={"new_revision": force_new})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["synthetic"] is True
    return body["policy"]


def review_body(policy, selected=None):
    revision = policy["revision"]
    return {
        "revision_id": revision["revision_id"],
        "analysis_digest": revision["analysis_digest"],
        "inputs_digest": revision["inputs_digest"],
        "reviewer": "Synthetic Integration Reviewer",
        "approved_fields": CANDIDATES if selected is None else selected,
        "notes": "Synthetic HTTP integration test",
        "decision": "APPROVE",
    }


def test_empty_workbench_reports_real_analysis_and_no_policy(workbench):
    client, _ = workbench
    analysis = client.get("/api/analysis")
    assert analysis.status_code == 200
    assert analysis.json()["counts"] == {"USED": 5, "CANDIDATE_UNUSED": 4, "UNKNOWN": 1}
    assert all(field["evidence"] for field in analysis.json()["fields"])
    policy_state = client.get("/api/policy").json()
    assert policy_state["synthetic"] is True
    assert policy_state["policy"] is None
    assert policy_state["history"] == []
    assert policy_state["current_analysis_digest"] == analysis_digest(analysis.json())
    unchanged = client.get("/api/demo/account?mode=ENFORCE").json()
    assert unchanged["output"] == unchanged["original"]
    assert unchanged["trace"]["policy_valid"] is False


def test_full_workbench_http_flow_persists_real_review_runtime_and_canary(workbench):
    client, settings = workbench
    analysis = client.get("/api/analysis").json()
    pending = create_revision(client)
    assert pending["revision"]["status"] == "REVIEW_REQUIRED"
    assert pending["summary"]["fields_after"] == 10
    assert {field["api_action"] for field in pending["fields"]} == {"KEEP"}
    assert [field["name"] for field in pending["fields"] if field["removal_allowed"]] == CANDIDATES
    assert len(analysis["fields"]) == len(pending["fields"])

    approved_response = client.post("/api/policy/review", json=review_body(pending))
    assert approved_response.status_code == 200, approved_response.text
    approved = approved_response.json()["policy"]
    revision_id = approved["revision"]["revision_id"]
    assert approved["revision"]["status"] == "APPROVED"
    assert approved["approval"]["approved_fields"] == CANDIDATES
    assert approved["approval"]["reviewer"] == "Synthetic Integration Reviewer"
    assert approved["summary"]["fields_before"] == 10
    assert approved["summary"]["fields_after"] == 6
    assert client.get("/api/policy").json()["policy"] == approved

    actual_api = client.get("/api/demo/account?mode=ENFORCE").json()
    assert len(actual_api["original"]) == 10
    assert len(actual_api["output"]) == 6
    assert all(field not in actual_api["output"] for field in CANDIDATES)
    assert "internal_risk_flag" in actual_api["output"]
    assert actual_api["trace"]["policy_revision"] == revision_id

    protected_log = client.post("/api/demo/log").json()
    assert protected_log["sanitized"] == protected_log["persisted"]["event"]
    assert protected_log["persisted"]["policy_revision"] == revision_id
    assert protected_log["sanitized"]["account_id"] == "[REDACTED]"
    assert protected_log["sanitized"]["customer_phone"] == "[REDACTED]"
    assert protected_log["sanitized"]["account_type"] == protected_log["original"]["account_type"]
    for field in ("available_balance", "account_number", "aadhaar_number"):
        assert field not in protected_log["persisted"]["event"]

    verified = client.post("/api/verify", json={"revision_id": revision_id})
    assert verified.status_code == 200, verified.text
    verification = verified.json()
    assert verification["status"] == "PASS"
    assert verification["policy_revision"] == revision_id
    assert verification["run_id"]
    assert verification["checked_at"]
    assert verification["checks"] and all(check["passed"] for check in verification["checks"])
    assert "internal_risk_flag" in verification["api"]["output"]
    assert all(field not in verification["api"]["output"] for field in CANDIDATES)
    assert verification["log"]["sanitized"] == verification["log"]["persisted"]["event"]
    persisted_json = json.dumps(verification["log"]["persisted"], sort_keys=True)
    for field in ("account_number", "aadhaar_number", "available_balance"):
        assert str(verification["api"]["original"][field]) not in persisted_json
    # Inspect SQLite itself, rather than trusting a display-only sanitized view.
    with sqlite3.connect(settings.database_path) as database:
        stored = database.execute(
            "SELECT event_json FROM veilmint_protected_logs WHERE id = ?",
            (verification["log"]["persisted"]["id"],),
        ).fetchone()[0]
        assert json.loads(stored) == verification["log"]["sanitized"]
        assert str(verification["api"]["original"]["account_number"]) not in stored

    # A separate app/connection sees the same approval after a browser refresh.
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get("/api/policy").json()["policy"] == approved
        assert len(reopened.get("/api/demo/account?mode=ENFORCE").json()["output"]) == 6


@pytest.mark.parametrize("selected", [["account_id"], ["internal_risk_flag"], ["nonexistent"]])
def test_review_rejects_used_unknown_and_nonexistent_without_changing_state(workbench, selected):
    client, _ = workbench
    pending = create_revision(client)
    response = client.post("/api/policy/review", json=review_body(pending, selected))
    assert response.status_code == 409
    assert client.get("/api/policy").json()["policy"] == pending


def test_changed_revision_and_mismatched_digests_never_reuse_old_approval(workbench):
    client, _ = workbench
    first = create_revision(client)
    approved = client.post("/api/policy/review", json=review_body(first)).json()["policy"]
    old_id = approved["revision"]["revision_id"]
    second = create_revision(client, force_new=True)
    assert second["revision"]["number"] == 2
    assert second["revision"]["status"] == "REVIEW_REQUIRED"
    assert second["approval"] is None
    stale = client.post("/api/policy/review", json=review_body(first))
    assert stale.status_code == 409
    wrong_digest = review_body(second)
    wrong_digest["analysis_digest"] = "f" * 64
    assert client.post("/api/policy/review", json=wrong_digest).status_code == 409
    wrong_inputs = review_body(second)
    wrong_inputs["inputs_digest"] = "e" * 64
    assert client.post("/api/policy/review", json=wrong_inputs).status_code == 409
    assert client.get("/api/policy").json()["policy"] == second
    assert client.get("/api/policy").json()["history"][0] == approved["revision"]
    api_result = client.get("/api/demo/account?mode=ENFORCE").json()
    assert api_result["output"] == api_result["original"]
    failed = client.post("/api/verify", json={"revision_id": old_id})
    assert failed.status_code == 200
    assert failed.json()["status"] == "FAIL"
    assert any(not check["passed"] for check in failed.json()["checks"])


def test_repeat_review_is_rejected_and_fresh_canary_run_ids_differ(workbench):
    client, _ = workbench
    pending = create_revision(client)
    body = review_body(pending)
    assert client.post("/api/policy/review", json=body).status_code == 200
    assert client.post("/api/policy/review", json=body).status_code == 409
    first = client.post("/api/verify", json={}).json()
    second = client.post("/api/verify", json={}).json()
    assert first["status"] == second["status"] == "PASS"
    assert first["run_id"] != second["run_id"]


def test_request_errors_are_generic_and_caller_cannot_supply_policy(workbench):
    client, _ = workbench
    marker = "SYNTHETIC_PRIVATE_REQUEST_MARKER"
    pending = create_revision(client)
    invalid = review_body(pending)
    invalid["policy"] = {"caller_value": marker}
    rejected = client.post("/api/policy/review", json=invalid)
    assert rejected.status_code == 422
    assert marker not in rejected.text
    malformed = client.post("/api/verify", json={"revision_id": {"value": marker}})
    assert malformed.status_code == 422
    assert marker not in malformed.text
    invalid_selection = review_body(pending, [marker])
    rejected = client.post("/api/policy/review", json=invalid_selection)
    assert rejected.status_code == 409
    assert marker not in rejected.text
    assert "Traceback" not in rejected.text


def test_unapproved_canary_honestly_fails_without_cached_pass(workbench):
    client, _ = workbench
    create_revision(client)
    response = client.post("/api/verify", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "FAIL"
    assert any(not check["passed"] for check in response.json()["checks"])
