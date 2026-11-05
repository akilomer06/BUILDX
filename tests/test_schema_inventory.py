from pathlib import Path

import pytest

from veilmint.analyzer.schema_inventory import (
    SchemaInventoryError,
    inventory_fields,
    load_json,
    validate_payload,
)


FIXTURES = Path(__file__).parents[1] / "src" / "veilmint" / "fixtures"


def test_synthetic_inventory_and_payload_validate():
    schema = load_json(FIXTURES / "nexus_bank_schema.json")
    payload = load_json(FIXTURES / "nexus_bank_payload.json")
    assert inventory_fields(schema) == tuple(sorted(payload))
    assert len(inventory_fields(schema)) == 10
    assert validate_payload(schema, payload) is None


def test_inventory_order_does_not_depend_on_properties_order():
    schema = {"type": "object", "properties": {"z": {}, "a": {}}}
    assert inventory_fields(schema) == ("a", "z")
    assert inventory_fields({**schema, "properties": {"a": {}, "z": {}}}) == ("a", "z")


@pytest.mark.parametrize("payload", [{}, {"currency": 42}, {"currency": "AED", "extra": True}])
def test_invalid_payload_is_rejected(payload):
    schema = {
        "type": "object",
        "properties": {"currency": {"type": "string"}},
        "required": ["currency"],
        "additionalProperties": False,
    }
    with pytest.raises(SchemaInventoryError, match="Invalid payload"):
        validate_payload(schema, payload)


@pytest.mark.parametrize("schema", [
    [],
    {"type": "object", "properties": {"x": {"type": "not-a-type"}}},
    {"type": "object", "properties": {1: {}}},
    {"type": "array", "items": {}},
    {"type": "object"},
    {"type": "object", "properties": {}, "allOf": [{"properties": {"hidden": {}}}]},
    {"type": "object", "properties": {"x": {"$ref": "https://example.invalid/schema"}}},
    {"$schema": "https://example.invalid/draft", "type": "object", "properties": {}},
])
def test_invalid_or_unsupported_schema_is_rejected(schema):
    with pytest.raises(SchemaInventoryError):
        inventory_fields(schema)


def test_json_load_errors_have_input_context(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{broken", encoding="utf-8")
    with pytest.raises(SchemaInventoryError, match="invalid.json"):
        load_json(invalid)
    with pytest.raises(SchemaInventoryError, match="missing.json"):
        load_json(tmp_path / "missing.json")


def test_ref_in_property_names_and_annotation_data_is_not_a_reference():
    schema = {
        "type": "object",
        "properties": {"$ref": {"type": "object", "default": {"$ref": "ordinary data"}}},
    }
    assert inventory_fields(schema) == ("$ref",)
    validate_payload(schema, {"$ref": {"$ref": "ordinary data"}})


@pytest.mark.parametrize("nested_schema", [
    {"items": {"$ref": "https://example.invalid/schema"}},
    {"anyOf": [{"$ref": "https://example.invalid/schema"}]},
    {"properties": {"nested": {"$dynamicRef": "https://example.invalid/schema"}}},
])
def test_nested_schema_references_are_rejected_before_validation(nested_schema):
    schema = {"type": "object", "properties": {"x": nested_schema}}
    with pytest.raises(SchemaInventoryError, match="references are unsupported"):
        validate_payload(schema, {})


def test_nested_dialect_cannot_hide_a_remote_dependency(monkeypatch):
    attempted_urls = []

    def reject_network(request, *args, **kwargs):
        attempted_urls.append(request.full_url)
        raise AssertionError("Schema validation must not retrieve remote resources")

    monkeypatch.setattr("urllib.request.urlopen", reject_network)
    schema = {
        "type": "object",
        "properties": {
            "nested": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "dependencies": {"trigger": {"$ref": "https://example.invalid/remote"}},
            }
        },
    }
    with pytest.raises(SchemaInventoryError, match="Draft 2020-12"):
        validate_payload(schema, {"nested": {"trigger": True}})
    assert attempted_urls == []
