"""Integration checks for reports, packaged fixtures and CLI safety."""

import json
import subprocess
import sys
from importlib.resources import files

import pytest

from veilmint.analyzer.report import generate_report
from veilmint.analyzer.schema_inventory import SchemaInventoryError


@pytest.fixture
def golden_inputs():
    fixture_dir = files("veilmint").joinpath("fixtures")
    return (
        json.loads(fixture_dir.joinpath("nexus_bank_schema.json").read_text(encoding="utf-8")),
        json.loads(fixture_dir.joinpath("nexus_bank_payload.json").read_text(encoding="utf-8")),
        fixture_dir.joinpath("nexus_bank_consumer.py").read_text(encoding="utf-8"),
        json.loads(fixture_dir.joinpath("sensitivity.json").read_text(encoding="utf-8")),
    )


def test_golden_report_is_complete_and_deterministic(golden_inputs):
    first = generate_report(*golden_inputs)
    second = generate_report(*golden_inputs)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["counts"] == {"USED": 5, "CANDIDATE_UNUSED": 4, "UNKNOWN": 1}
    assert first["schema_validation"] == {"schema_valid": True, "payload_valid": True}
    assert [field["name"] for field in first["fields"]] == sorted(golden_inputs[0]["properties"])
    assert all(field["evidence"] for field in first["fields"])
    by_name = {field["name"]: field for field in first["fields"]}
    assert by_name["internal_risk_flag"]["usage"] == "UNKNOWN"
    assert by_name["available_balance"]["usage"] == "USED"
    assert by_name["available_balance"]["sensitivity"] == "FINANCIAL"
    assert by_name["aadhaar_number"]["usage"] == "CANDIDATE_UNUSED"
    assert by_name["aadhaar_number"]["sensitivity"] == "HIGH"
    assert first["analyzer_warnings"]


def test_mapping_changes_do_not_change_usage(golden_inputs):
    schema, payload, source, mapping = golden_inputs
    original = generate_report(schema, payload, source, mapping)
    changed = generate_report(schema, payload, source, {})
    assert changed["counts"] == original["counts"]
    assert [(item["name"], item["usage"]) for item in changed["fields"]] == [
        (item["name"], item["usage"]) for item in original["fields"]
    ]
    assert {item["sensitivity"] for item in changed["fields"]} == {"INTERNAL"}
    assert len(changed["sensitivity_warnings"]) == len(schema["properties"])


def test_report_rejects_invalid_payload(golden_inputs):
    schema, _payload, source, mapping = golden_inputs
    with pytest.raises(SchemaInventoryError):
        generate_report(schema, {}, source, mapping)


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "veilmint", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_cli_default_and_output_file_are_identical(tmp_path):
    first = _run_cli()
    second = _run_cli()
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["counts"] == {
        "USED": 5, "CANDIDATE_UNUSED": 4, "UNKNOWN": 1
    }
    output = tmp_path / "report.json"
    written = _run_cli("--output", output)
    assert written.returncode == 0
    assert written.stdout == ""
    assert output.read_text(encoding="utf-8") == first.stdout


def test_cli_requires_complete_custom_inputs(tmp_path):
    result = _run_cli("--consumer", tmp_path / "consumer.py")
    assert result.returncode == 2
    assert "together" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_custom_source_is_never_executed(tmp_path):
    schema_file = tmp_path / "schema.json"
    payload_file = tmp_path / "payload.json"
    consumer_file = tmp_path / "consumer.py"
    mapping_file = tmp_path / "sensitivity.json"
    sentinel = tmp_path / "executed.txt"
    schema_file.write_text(json.dumps({
        "type": "object", "properties": {"currency": {"type": "string"}},
        "required": ["currency"], "additionalProperties": False,
    }), encoding="utf-8")
    payload_file.write_text('{"currency": "SYNTHETIC"}', encoding="utf-8")
    mapping_file.write_text('{"currency": "GENERAL"}', encoding="utf-8")
    consumer_file.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('EXECUTED')\n"
        'value = payload["currency"]\nraise RuntimeError("must never execute")\n',
        encoding="utf-8",
    )
    result = _run_cli(
        "--schema", schema_file, "--payload", payload_file,
        "--consumer", consumer_file, "--sensitivity", mapping_file,
    )
    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
    assert json.loads(result.stdout)["counts"]["USED"] == 1


def test_cli_invalid_json_is_a_clear_failure(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text("not JSON", encoding="utf-8")
    result = _run_cli(
        "--schema", schema, "--payload", tmp_path / "payload.json",
        "--consumer", tmp_path / "consumer.py", "--sensitivity", tmp_path / "mapping.json",
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "veilmint:" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_refuses_to_overwrite_consumer(tmp_path, golden_inputs):
    schema, payload, source, mapping = golden_inputs
    inputs = [tmp_path / name for name in ("schema.json", "payload.json", "consumer.py", "sensitivity.json")]
    inputs[0].write_text(json.dumps(schema), encoding="utf-8")
    inputs[1].write_text(json.dumps(payload), encoding="utf-8")
    inputs[2].write_text(source, encoding="utf-8")
    inputs[3].write_text(json.dumps(mapping), encoding="utf-8")
    result = _run_cli(
        "--schema", inputs[0], "--payload", inputs[1],
        "--consumer", inputs[2], "--sensitivity", inputs[3], "--output", inputs[2],
    )
    assert result.returncode == 1
    assert "must not overwrite" in result.stderr
    assert inputs[2].read_text(encoding="utf-8") == source


def test_cli_invalid_root_name_is_a_clear_failure():
    result = _run_cli("--root-name", "not an identifier")
    assert result.returncode == 1
    assert "veilmint:" in result.stderr
    assert "Traceback" not in result.stderr
