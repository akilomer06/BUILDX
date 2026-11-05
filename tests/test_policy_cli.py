"""Exercise the actual CLI approval flow and on-disk policy state."""

import json
import subprocess
import sys

import pytest


def _run(*args, input_text=None):
    return subprocess.run(
        [sys.executable, "-m", "veilmint", *map(str, args)],
        input=input_text, capture_output=True, text=True, encoding="utf-8", check=False,
    )


@pytest.fixture
def policy_inputs(tmp_path):
    report = tmp_path / "analysis.json"
    generated = _run("--output", report)
    assert generated.returncode == 0, generated.stderr
    return tmp_path / "policies.sqlite3", report


def _create(db, report, *extra):
    result = _run("policy", "--db", db, "create", "--analysis", report, *extra)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _show(db):
    result = _run("policy", "--db", db, "show")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_cli_review_all_candidates_previews_then_persists(policy_inputs):
    db, report = policy_inputs
    before = _create(db, report)
    assert before["revision"]["status"] == "REVIEW_REQUIRED"
    assert {field["api_action"] for field in before["fields"]} == {"KEEP"}
    reviewed = _run(
        "policy", "--db", db, "review",
        input_text="all\nSynthetic reviewer تجربة\nOnly synthetic candidates\nAPPROVE\n",
    )
    assert reviewed.returncode == 0, reviewed.stderr
    assert reviewed.stdout.index("Preview") < reviewed.stdout.index("Saved reviewer decision")
    assert "10 -> 6 fields" in reviewed.stdout
    assert "Evidence:" in reviewed.stdout
    assert "USED and UNKNOWN fields cannot be selected" in reviewed.stdout
    after = _show(db)
    assert after["revision"]["revision_id"] == before["revision"]["revision_id"]
    assert after["revision"]["status"] == "APPROVED"
    assert after["approval"]["reviewer"] == "Synthetic reviewer تجربة"
    assert after["approval"]["notes"] == "Only synthetic candidates"
    assert {field["name"] for field in after["fields"] if field["api_action"] == "REMOVE"} == {
        "aadhaar_number", "account_number", "customer_address", "customer_phone",
    }
    # Reloading the same unchanged inputs does not revoke or silently replace approval.
    assert _create(db, report) == after


def test_cli_review_requires_exact_confirmation(policy_inputs):
    db, report = policy_inputs
    before = _create(db, report)
    result = _run(
        "policy", "--db", db, "review", input_text="all\nDemo\n\napprove\n",
    )
    assert result.returncode == 0
    assert "Cancelled" in result.stdout
    assert _show(db) == before


@pytest.mark.parametrize("selection", ["5", "account_id", "internal_risk_flag", "0", "1,99"])
def test_cli_invalid_or_noncandidate_selection_does_not_save(policy_inputs, selection):
    db, report = policy_inputs
    before = _create(db, report)
    result = _run("policy", "--db", db, "review", input_text=selection + "\n")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert _show(db) == before


def test_cli_empty_reviewer_does_not_save(policy_inputs):
    db, report = policy_inputs
    before = _create(db, report)
    result = _run("policy", "--db", db, "review", input_text="all\n  \n")
    assert result.returncode == 1
    assert _show(db) == before


def test_cli_approval_is_one_time_per_revision(policy_inputs):
    db, report = policy_inputs
    _create(db, report)
    first = _run("policy", "--db", db, "review", input_text="1\nDemo\n\nAPPROVE\n")
    assert first.returncode == 0, first.stderr
    approved = _show(db)
    second = _run("policy", "--db", db, "review", input_text="all\nOther\n\nAPPROVE\n")
    assert second.returncode == 1
    assert _show(db) == approved


def test_cli_new_revision_preserves_history_and_requires_review(policy_inputs):
    db, report = policy_inputs
    first = _create(db, report)
    second = _create(db, report, "--new-revision")
    assert second["revision"]["number"] == first["revision"]["number"] + 1
    assert second["revision"]["status"] == "REVIEW_REQUIRED"
    stale = _run(
        "policy", "--db", db, "review", "--revision", first["revision"]["revision_id"],
        input_text="all\nDemo\n\nAPPROVE\n",
    )
    assert stale.returncode == 1
    history = _run("policy", "--db", db, "history")
    assert history.returncode == 0
    assert len(json.loads(history.stdout)) == 2
    assert _show(db) == second


def test_cli_rejection_records_no_removals(policy_inputs):
    db, report = policy_inputs
    _create(db, report)
    rejected = _run(
        "policy", "--db", db, "review", "--reject",
        input_text="Demo\nKeep current shape\nREJECT\n",
    )
    assert rejected.returncode == 0, rejected.stderr
    after = _show(db)
    assert after["revision"]["status"] == "REJECTED"
    assert after["approval"]["decision"] == "REJECT"
    assert {field["api_action"] for field in after["fields"]} == {"KEEP"}


def test_cli_cannot_overwrite_database_or_analysis(policy_inputs):
    db, report = policy_inputs
    _create(db, report)
    original_db = db.read_bytes()
    result = _run("policy", "--db", db, "show", "--output", db)
    assert result.returncode == 1
    assert db.read_bytes() == original_db
    original_analysis = report.read_text(encoding="utf-8")
    result = _run("policy", "--db", db, "create", "--analysis", report, "--output", report)
    assert result.returncode == 1
    assert report.read_text(encoding="utf-8") == original_analysis


def test_cli_failure_messages_do_not_include_raw_input_values(tmp_path):
    report = tmp_path / "analysis.json"
    report.write_text('{"RAW_SYNTHETIC_PRIVATE_SENTINEL":', encoding="utf-8")
    result = _run("policy", "--db", tmp_path / "p.sqlite3", "create", "--analysis", report)
    assert result.returncode == 1
    assert "RAW_SYNTHETIC_PRIVATE_SENTINEL" not in result.stderr
    assert "Traceback" not in result.stderr
