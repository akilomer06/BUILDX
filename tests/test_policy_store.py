"""Policy persistence integrity, revision freshness and one-time review."""

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from veilmint.policy.models import APIAction, RevisionStatus
from veilmint.policy.store import PolicyStore, PolicyStoreError


@pytest.fixture
def report():
    return {
        "schema_validation": {"schema_valid": True, "payload_valid": True},
        "analysis": {"scope": "synthetic test source"},
        "fields": [
            {"name": "id", "usage": "USED", "sensitivity": "INTERNAL", "evidence": ["literal read"]},
            {"name": "secret", "usage": "CANDIDATE_UNUSED", "sensitivity": "HIGH", "evidence": ["no supported access"]},
            {"name": "dynamic", "usage": "UNKNOWN", "sensitivity": "INTERNAL", "evidence": ["dynamic key"]},
        ],
        "warnings": [],
    }


def actions(policy):
    return {field.name: field.api_action for field in policy.fields}


def test_revision_and_one_time_decision_survive_reopening(tmp_path, report):
    database = tmp_path / "policies.sqlite3"
    with PolicyStore(database) as store:
        pending = store.create_revision(report)
        assert pending.revision.status == RevisionStatus.REVIEW_REQUIRED
        assert set(actions(pending).values()) == {APIAction.KEEP}
        approved = store.review(pending.revision.revision_id, "Synthetic Reviewer", ["secret"], notes="demo")
        assert actions(approved)["secret"] == APIAction.REMOVE
        assert approved.approval.reviewer == "Synthetic Reviewer"
        assert approved.approval.notes == "demo"
    with PolicyStore(database) as reopened:
        assert reopened.get().to_dict() == approved.to_dict()
        assert reopened.get(pending.revision.revision_id).to_dict() == approved.to_dict()
        assert reopened.load_inputs(pending.revision.revision_id)["report"] == report
        unchanged = reopened.create_revision(report)
        assert unchanged.to_dict() == approved.to_dict()
        with pytest.raises(PolicyStoreError, match="already"):
            reopened.review(pending.revision.revision_id, "Another Reviewer", ["secret"])
        assert len(reopened.history()) == 1


def test_changed_analysis_appends_and_never_inherits_approval(tmp_path, report):
    with PolicyStore(tmp_path / "policies.sqlite3") as store:
        first = store.create_revision(report)
        approved = store.review(first.revision.revision_id, "Reviewer", ["secret"])
        changed = deepcopy(report)
        changed["fields"][1]["evidence"] = ["new scan evidence"]
        second = store.create_revision(changed)
        assert second.revision.number == 2
        assert second.revision.analysis_digest != first.revision.analysis_digest
        assert second.revision.status == RevisionStatus.REVIEW_REQUIRED
        assert actions(second)["secret"] == APIAction.KEEP
        assert store.get(first.revision.revision_id).to_dict() == approved.to_dict()
        assert [item["number"] for item in store.history()] == [1, 2]
        assert store.get().revision.revision_id == second.revision.revision_id
        with pytest.raises(PolicyStoreError, match="stale"):
            store.review(first.revision.revision_id, "Reviewer", ["secret"])
        # Returning to historical input still creates a pending new revision.
        third = store.create_revision(report)
        assert third.revision.number == 3
        assert third.approval is None
        assert actions(third)["secret"] == APIAction.KEEP


def test_mapping_inventory_and_forced_regeneration_require_new_review(tmp_path, report):
    with PolicyStore(tmp_path / "policies.sqlite3") as store:
        first = store.create_revision(report)
        store.review(first.revision.revision_id, "Reviewer", ["secret"])
        mapping_changed = store.create_revision(report, log_mapping={"INTERNAL": "DROP"})
        assert mapping_changed.revision.number == 2
        assert mapping_changed.revision.analysis_digest == first.revision.analysis_digest
        assert mapping_changed.revision.inputs_digest != first.revision.inputs_digest
        assert actions(mapping_changed)["secret"] == APIAction.KEEP
        inventory_changed = store.create_revision(report, known_fields=["id", "secret", "dynamic", "new_field"])
        assert inventory_changed.revision.number == 3
        assert actions(inventory_changed)["new_field"] == APIAction.KEEP
        regenerated = store.create_revision(report, force_new=True)
        assert regenerated.revision.number == 4
        assert regenerated.approval is None


@pytest.mark.parametrize("selection", [["id"], ["dynamic"], ["missing"]])
def test_invalid_review_is_atomic_and_leaves_pending_policy(tmp_path, report, selection):
    database = tmp_path / "policies.sqlite3"
    with PolicyStore(database) as store:
        first = store.create_revision(report)
        with pytest.raises(PolicyStoreError, match="invalid"):
            store.review(first.revision.revision_id, "Reviewer", selection)
        assert store.get().to_dict() == first.to_dict()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM veilmint_reviewer_decisions").fetchone()[0] == 0


def test_rejection_is_recorded_once_and_keeps_every_field(tmp_path, report):
    with PolicyStore(tmp_path / "policies.sqlite3") as store:
        pending = store.create_revision(report)
        rejected = store.review(pending.revision.revision_id, "Reviewer", [], decision="REJECT", notes="insufficient evidence")
        assert rejected.revision.status == RevisionStatus.REJECTED
        assert set(actions(rejected).values()) == {APIAction.KEEP}
        assert store.get().approval.decision == "REJECT"
        with pytest.raises(PolicyStoreError, match="already"):
            store.review(pending.revision.revision_id, "Reviewer", ["secret"])


@pytest.mark.parametrize("corruption", ["compiled", "analysis", "decision", "status"])
def test_corrupted_snapshot_analysis_or_approval_is_not_trusted(tmp_path, report, corruption):
    database = tmp_path / "policies.sqlite3"
    with PolicyStore(database) as store:
        pending = store.create_revision(report)
        store.review(pending.revision.revision_id, "Reviewer", ["secret"])
    with sqlite3.connect(database) as connection:
        if corruption == "compiled":
            connection.execute("UPDATE veilmint_policy_revisions SET compiled_json = '{}' ")
        elif corruption == "analysis":
            changed = deepcopy(report)
            changed["fields"][0]["usage"] = "CANDIDATE_UNUSED"
            connection.execute("UPDATE veilmint_policy_revisions SET analysis_json = ?", (json.dumps(changed),))
        elif corruption == "decision":
            connection.execute("DELETE FROM veilmint_reviewer_decisions")
        else:
            connection.execute("UPDATE veilmint_policy_revisions SET status = 'REVIEW_REQUIRED'")
    with PolicyStore(database) as store:
        with pytest.raises(PolicyStoreError, match="integrity"):
            store.get()


def test_unavailable_invalid_and_missing_database_errors_are_safe(tmp_path):
    marker = "SYNTHETIC_PRIVATE_MARKER"
    invalid = tmp_path / "not_sqlite.db"
    invalid.write_text(marker, encoding="utf-8")
    for path in (tmp_path, invalid):
        with pytest.raises(PolicyStoreError) as error:
            PolicyStore(path)
        assert marker not in str(error.value)
    with PolicyStore(":memory:") as store:
        assert store.history() == []
        with pytest.raises(PolicyStoreError, match="not found"):
            store.get()


def test_policy_store_keeps_unrelated_existing_table(tmp_path, report):
    database = tmp_path / "policies.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated_records(value TEXT)")
        connection.execute("INSERT INTO unrelated_records VALUES ('KEEP_ME')")
    with PolicyStore(database) as store:
        store.create_revision(report)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM unrelated_records").fetchone()[0] == "KEEP_ME"


def test_two_store_instances_do_not_duplicate_matching_latest_revision(tmp_path, report):
    database = tmp_path / "policies.sqlite3"
    with PolicyStore(database) as first, PolicyStore(database) as second:
        first_revision = first.create_revision(report)
        assert second.create_revision(report).revision.revision_id == first_revision.revision.revision_id
        assert len(second.history()) == 1


def test_clean_nested_database_parent_is_created_without_overwriting_files(tmp_path, report):
    database = tmp_path / "data" / "nested" / "synthetic-demo.sqlite3"
    with PolicyStore(database) as store:
        pending = store.create_revision(report)
        assert store.get().revision.revision_id == pending.revision.revision_id
    assert database.is_file()
