"""Compose a deterministic, analysis-only report from independent classifiers."""

from collections.abc import Mapping
import hashlib
import json
from typing import Any

from .ast_analyzer import Usage, analyze_source
from .schema_inventory import inventory_fields, validate_payload
from .sensitivity import classify_sensitivity


def generate_report(
    schema: Mapping[str, Any],
    payload: Any,
    consumer_source: str,
    sensitivity_mapping: Mapping[str, str],
    *,
    root_name: str = "payload",
    filename: str = "<consumer>",
) -> dict[str, Any]:
    """Validate inputs and analyze source without importing or executing it.

    Invalid schemas and payloads raise ``SchemaInventoryError``. A report's
    successful validation result applies only to the supplied synthetic input.
    No timestamp is included, so identical inputs produce identical reports.
    """
    field_names = inventory_fields(schema)
    validate_payload(schema, payload)
    analysis = analyze_source(
        consumer_source, field_names, root_name=root_name, filename=filename
    )
    sensitivity = classify_sensitivity(field_names, sensitivity_mapping)
    counts = {usage.value: 0 for usage in Usage}
    fields = []
    for field in sorted(analysis.fields, key=lambda item: item.name):
        counts[field.usage.value] += 1
        fields.append(
            {
                "name": field.name,
                "usage": field.usage.value,
                "sensitivity": sensitivity.labels[field.name].value,
                "evidence": list(field.evidence),
            }
        )

    analyzer_warnings = sorted(set(analysis.warnings))
    sensitivity_warnings = sorted(set(sensitivity.warnings))
    return {
        "analysis": {
            "mode": "static_ast",
            "root_name": root_name,
            "consumer": filename,
            "scope": "Top-level schema fields in the supplied Python source only.",
            "input_digests": {
                "schema": hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
                "payload": hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
                "consumer": hashlib.sha256(consumer_source.encode("utf-8")).hexdigest(),
                "sensitivity": hashlib.sha256(json.dumps(sensitivity_mapping, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
            },
            "limitations": [
                "Static access evidence does not establish runtime reachability.",
                "Dynamic or unsupported access is conservatively uncertain.",
                "Candidate unused means no supported access in this scanned scope; "
                "it does not prove a field can be removed.",
            ],
        },
        "schema_validation": {"schema_valid": True, "payload_valid": True},
        "fields": fields,
        "counts": counts,
        "analyzer_warnings": analyzer_warnings,
        "sensitivity_warnings": sensitivity_warnings,
        "warnings": sorted(set(analyzer_warnings + sensitivity_warnings)),
    }
