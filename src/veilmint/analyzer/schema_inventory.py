"""Explicit top-level JSON Schema inventory and offline payload validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable


class SchemaInventoryError(ValueError):
    """A schema, payload, or input file cannot be analyzed safely."""


def load_json(path: str | Path) -> Any:
    """Read a UTF-8 JSON document, preserving useful input-error context."""
    input_path = Path(path)
    try:
        return json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SchemaInventoryError(f"Cannot read JSON from {input_path}: {exc}") from exc


def _check_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        raise SchemaInventoryError("Schema must be a JSON object.")
    document = dict(schema)
    if document.get("$schema", Draft202012Validator.META_SCHEMA["$id"]) != Draft202012Validator.META_SCHEMA["$id"]:
        raise SchemaInventoryError("Phase 1 supports JSON Schema Draft 2020-12 only.")
    try:
        Draft202012Validator.check_schema(document)
    except SchemaError as exc:
        raise SchemaInventoryError(f"Invalid JSON Schema: {exc.message}") from exc
    if document.get("type") != "object":
        raise SchemaInventoryError("Schema must declare a top-level object type.")
    if not isinstance(document.get("properties"), dict):
        raise SchemaInventoryError("Schema must declare explicit top-level properties.")
    if not all(isinstance(name, str) for name in document["properties"]):
        raise SchemaInventoryError("Top-level property names must be strings.")
    unsupported = {
        "$ref", "$dynamicRef", "allOf", "anyOf", "oneOf", "if", "then", "else",
        "not", "dependentSchemas", "patternProperties", "unevaluatedProperties",
    }
    found = sorted(unsupported.intersection(document))
    if found:
        raise SchemaInventoryError(f"Unsupported top-level schema features: {', '.join(found)}.")
    # No reference resolution is attempted, including for nested property schemas.
    # Rejecting references makes validation offline and avoids a partial inventory.
    def check_references(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("$schema", Draft202012Validator.META_SCHEMA["$id"]) != Draft202012Validator.META_SCHEMA["$id"]:
                raise SchemaInventoryError("Phase 1 supports JSON Schema Draft 2020-12 only, including nested schemas.")
            if "$ref" in value or "$dynamicRef" in value:
                raise SchemaInventoryError("Schema references are unsupported in Phase 1; inline property schemas.")
            # Traverse schema locations only: annotations/defaults/const values
            # and a property literally named '$ref' are ordinary JSON data.
            for keyword in (
                "additionalProperties", "items", "contains", "not", "if", "then", "else",
                "propertyNames", "unevaluatedProperties", "unevaluatedItems", "contentSchema",
            ):
                if keyword in value:
                    check_references(value[keyword])
            for keyword in ("$defs", "definitions", "properties", "patternProperties", "dependentSchemas"):
                for child in value.get(keyword, {}).values():
                    check_references(child)
            for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
                for child in value.get(keyword, []):
                    check_references(child)

    check_references(document)
    return document


def inventory_fields(schema: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the sorted, explicitly declared top-level property names."""
    return tuple(sorted(_check_schema(schema)["properties"]))


def validate_payload(schema: Mapping[str, Any], payload: Any) -> None:
    """Validate without resolving remote schemas; raise on the first stable error."""
    # Registry's default retrieval function refuses external resources. This is
    # a second offline boundary in addition to rejecting reference syntax.
    validator = Draft202012Validator(_check_schema(schema), registry=Registry())
    try:
        errors = sorted(validator.iter_errors(payload), key=lambda error: (error.json_path, error.message))
    except Unresolvable as exc:
        raise SchemaInventoryError(f"Schema references cannot be resolved offline: {exc}") from exc
    if errors:
        error = errors[0]
        raise SchemaInventoryError(f"Invalid payload at {error.json_path}: {error.message}")
