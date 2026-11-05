"""Approval inputs change even if edits preserve the same field evidence."""

from veilmint.analyzer.report import generate_report


def test_source_edit_changes_fingerprint_without_changing_usage():
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    original = generate_report(schema, {"x": "SYNTHETIC"}, 'payload["x"]\n', {"x": "GENERAL"})
    changed = generate_report(schema, {"x": "SYNTHETIC"}, 'payload["x"]\n# Regenerated consumer\n', {"x": "GENERAL"})
    assert original["fields"] == changed["fields"]
    assert original["analysis"]["input_digests"]["consumer"] != changed["analysis"]["input_digests"]["consumer"]
    assert original["analysis"]["input_digests"]["schema"] == changed["analysis"]["input_digests"]["schema"]
