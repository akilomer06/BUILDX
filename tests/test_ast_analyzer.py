"""Regression tests for conservative, source-only consumer analysis."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from veilmint.analyzer.ast_analyzer import Usage, analyze_source


FIELDS = ("account_id", "currency", "secret")


def usages(source: str, **kwargs: object) -> dict[str, Usage]:
    return {
        field.name: field.usage
        for field in analyze_source(source, FIELDS, **kwargs).fields
    }


def test_literal_subscript_and_get_are_used_with_explainable_evidence() -> None:
    result = analyze_source(
        'account = payload["account_id"]\ncode = payload.get("currency", "USD")\n',
        FIELDS,
        filename="consumer.py",
    )
    fields = {field.name: field for field in result.fields}

    assert fields["account_id"].usage == Usage.USED
    assert fields["currency"].usage == Usage.USED
    assert fields["secret"].usage == Usage.CANDIDATE_UNUSED
    assert all(field.evidence for field in result.fields)
    assert any("consumer.py" in item for item in fields["account_id"].evidence)


def test_unrelated_mapping_access_does_not_count_as_payload_access() -> None:
    assert usages('other["secret"]\nother.get("currency")\n') == {
        field: Usage.CANDIDATE_UNUSED for field in FIELDS
    }


def test_configurable_root_name() -> None:
    result = usages('response["currency"]\npayload["secret"]\n', root_name="response")
    assert result["currency"] == Usage.USED
    assert result["secret"] == Usage.CANDIDATE_UNUSED


@pytest.mark.parametrize("access", ["payload[key]", "payload.get(key)"])
def test_single_constant_variable_key_is_bounded_but_still_unknown(access: str) -> None:
    assert usages(f'key = "secret"\nvalue = {access}\n') == {
        "account_id": Usage.CANDIDATE_UNUSED,
        "currency": Usage.CANDIDATE_UNUSED,
        "secret": Usage.UNKNOWN,
    }


@pytest.mark.parametrize("access", ["payload[key]", "payload.get(key)"])
def test_unknown_variable_key_preserves_entire_scope(access: str) -> None:
    source = f"def consume(payload, key):\n    return {access}\n"
    assert usages(source) == {field: Usage.UNKNOWN for field in FIELDS}


@pytest.mark.parametrize(
    "source",
    [
        'key = "secret"\nkey = obtain_key()\nvalue = payload[key]\n',
        'key = "secret" if condition else obtain_key()\nvalue = payload[key]\n',
        'def consume(payload, key="secret"):\n    return payload[key]\n',
    ],
)
def test_reassigned_or_external_keys_cannot_be_treated_as_single_constant(source: str) -> None:
    assert usages(source) == {field: Usage.UNKNOWN for field in FIELDS}


@pytest.mark.parametrize(
    "source",
    [
        'value = payload[key]\nkey = "secret"\n',
        'if condition:\n    key = "secret"\nvalue = payload[key]\n',
        'key = "secret"\nvalues = [payload[key] for key in external_keys]\n',
        'key = "secret"\nvalues = {key: payload[key] for key in external_keys}\n',
        'key = "secret"\nvalues = (payload[key] for key in external_keys)\n',
    ],
)
def test_constant_key_bounds_respect_order_control_flow_and_shadowing(source: str) -> None:
    assert usages(source) == {field: Usage.UNKNOWN for field in FIELDS}


@pytest.mark.parametrize(
    "source",
    [
        'eval(\'payload["secret"]\')\n',
        'exec(\'value = payload["secret"]\')\n',
        'namespace = globals()\nvalue = namespace["payload"]["secret"]\n',
        'namespace = locals()\nvalue = namespace["payload"]["secret"]\n',
    ],
)
def test_dynamic_execution_or_namespace_reflection_invalidates_scope(source: str) -> None:
    result = analyze_source(source, FIELDS)
    assert all(field.usage == Usage.UNKNOWN for field in result.fields)
    assert result.warnings


@pytest.mark.parametrize(
    "source",
    [
        'reader = globals\nvalue = reader()["payload"]["secret"]\n',
        'reader = locals\nvalue = reader()["payload"]["secret"]\n',
        'reader = vars\nvalue = reader()["payload"]["secret"]\n',
        'execute = eval\nexecute(\'payload["secret"]\')\n',
        'import builtins\nbuiltins.eval(\'payload["secret"]\')\n',
        'from builtins import globals as namespace\nvalue = namespace()["payload"]["secret"]\n',
        'execute = __builtins__["eval"]\nexecute(\'payload["secret"]\')\n',
        'import builtins\ngetattr(builtins, "eval")(\'payload["secret"]\')\n',
        'import inspect\nvalue = inspect.currentframe().f_locals["payload"]["secret"]\n',
        'import sys\nvalue = sys._getframe().f_globals["payload"]["secret"]\n',
    ],
)
def test_reflection_aliases_and_frames_cannot_hide_field_usage(source: str) -> None:
    result = analyze_source(source, FIELDS)
    assert all(field.usage == Usage.UNKNOWN for field in result.fields)
    assert result.warnings


@pytest.mark.parametrize(
    "source",
    [
        'payload = {}\nvalue = payload["secret"]\n',
        'value = payload["account_id"]\npayload = {}\n',
        'def consume(payload):\n    payload = obtain_other_payload()\n    return payload["secret"]\n',
    ],
)
def test_root_rebinding_makes_direct_access_identity_uncertain(source: str) -> None:
    assert usages(source) == {field: Usage.UNKNOWN for field in FIELDS}


@pytest.mark.parametrize(
    "source",
    [
        'alias = payload\nvalue = alias["secret"]\n',
        "send_elsewhere(payload)\n",
        "send_elsewhere(**payload)\n",
        "for name in payload:\n    print(name)\n",
        "for name, value in payload.items():\n    print(name, value)\n",
        "snapshot = dict(payload)\n",
        "snapshot = {**payload}\n",
        'value = getattr(payload, "secret")\n',
        'value = f"{payload}"\n',
        'value = "secret" in payload\n',
        'payload["secret"] = "replacement"\n',
        'del payload["secret"]\n',
        'payload.update({"secret": "replacement"})\n',
        'match payload:\n    case {"secret": value}:\n        print(value)\n',
    ],
)
def test_ambiguous_whole_payload_operations_preserve_all_fields(source: str) -> None:
    result = analyze_source(source, FIELDS)
    assert {field.name: field.usage for field in result.fields} == {
        field: Usage.UNKNOWN for field in FIELDS
    }
    assert result.warnings
    assert all(field.evidence for field in result.fields)


def test_direct_evidence_wins_when_other_access_is_ambiguous() -> None:
    assert usages('account = payload["account_id"]\nsend_elsewhere(payload)\n') == {
        "account_id": Usage.USED,
        "currency": Usage.UNKNOWN,
        "secret": Usage.UNKNOWN,
    }


@pytest.mark.parametrize(
    "source",
    [
        "payload.get()\n",
        'payload.get("secret", None, "extra")\n',
        'payload.get(key="secret")\n',
        "payload.get(*args)\n",
        "payload.get(**kwargs)\n",
    ],
)
def test_unsupported_get_call_shapes_do_not_claim_unused_or_direct_reads(source: str) -> None:
    assert usages(source) == {field: Usage.UNKNOWN for field in FIELDS}


def test_syntax_error_is_incomplete_analysis_with_warning() -> None:
    result = analyze_source('payload["secret"\n', FIELDS, filename="broken.py")
    assert all(field.usage == Usage.UNKNOWN for field in result.fields)
    assert result.warnings
    assert all(field.evidence for field in result.fields)


def test_scanned_source_is_never_executed(tmp_path) -> None:
    marker = tmp_path / "consumer-was-executed.txt"
    source = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('should never happen')\n"
        'account = payload["account_id"]\n'
        "raise RuntimeError('consumer must never execute')\n"
    )

    result = analyze_source(source, FIELDS)

    assert not marker.exists()
    assert next(field for field in result.fields if field.name == "account_id").usage == Usage.USED


def test_output_is_sorted_deterministic_and_json_compatible() -> None:
    source = 'account = payload["account_id"]\nkey = "secret"\nvalue = payload[key]\n'
    first = analyze_source(source, reversed(FIELDS))
    second = analyze_source(source, FIELDS)

    assert first == second
    assert tuple(field.name for field in first.fields) == tuple(sorted(FIELDS))
    assert json.loads(json.dumps(asdict(first))) == json.loads(json.dumps(asdict(second)))


def test_unaccessed_fields_are_candidates_only_within_scanned_scope() -> None:
    result = analyze_source("# Empty consumer scope.\nvalue = 1\n", FIELDS)
    assert all(field.usage == Usage.CANDIDATE_UNUSED for field in result.fields)
    assert all(field.evidence for field in result.fields)
