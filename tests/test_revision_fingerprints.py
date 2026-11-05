"""Input provenance integrates the analyzer with one-time approval revisions."""

import json
from importlib.resources import files

from veilmint.analyzer.report import generate_report
from veilmint.policy.store import PolicyStore


def test_regenerated_source_does_not_inherit_candidate_approval(tmp_path):
    fixtures = files("veilmint").joinpath("fixtures")
    schema = json.loads(fixtures.joinpath("nexus_bank_schema.json").read_text(encoding="utf-8"))
    payload = json.loads(fixtures.joinpath("nexus_bank_payload.json").read_text(encoding="utf-8"))
    source = fixtures.joinpath("nexus_bank_consumer.py").read_text(encoding="utf-8")
    mapping = json.loads(fixtures.joinpath("sensitivity.json").read_text(encoding="utf-8"))
    original = generate_report(schema, payload, source, mapping)
    changed = generate_report(schema, payload, source + "\n# Regenerated evidence\n", mapping)
    assert original["fields"] == changed["fields"]

    with PolicyStore(tmp_path / "synthetic.sqlite3") as store:
        draft = store.create_revision(original)
        candidates = tuple(field.name for field in draft.fields if field.removal_allowed)
        approved = store.review(draft.revision.revision_id, "synthetic-test", candidates)
        new = store.create_revision(changed)
        assert new.revision.revision_id != approved.revision.revision_id
        assert new.approval is None
        assert all(field.api_action.value == "KEEP" for field in new.fields)
        assert sum(field.api_action.value == "REMOVE" for field in store.get(approved.revision.revision_id).fields) == 4
