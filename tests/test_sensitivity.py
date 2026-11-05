from pathlib import Path

import pytest

from veilmint.analyzer.sensitivity import (
    Sensitivity,
    classify_sensitivity,
    load_sensitivity,
)


FIXTURES = Path(__file__).parents[1] / "src" / "veilmint" / "fixtures"


def test_fixture_mapping_is_complete_and_independent_of_usage():
    mapping = load_sensitivity(FIXTURES / "sensitivity.json")
    result = classify_sensitivity(mapping, mapping)
    assert len(result.labels) == 10
    assert result.warnings == ()
    assert result.labels["available_balance"] is Sensitivity.FINANCIAL
    assert result.labels["account_number"] is Sensitivity.HIGH
    assert result.labels["account_id"] is Sensitivity.INTERNAL
    assert result.labels["account_type"] is Sensitivity.GENERAL
    assert result.labels["customer_phone"] is Sensitivity.MEDIUM


def test_unmapped_fields_default_to_internal_with_sorted_warnings():
    result = classify_sensitivity(["z", "a", "known"], {"known": "GENERAL"})
    assert list(result.labels) == ["a", "known", "z"]
    assert result.labels["a"] is Sensitivity.INTERNAL
    assert result.labels["z"] is Sensitivity.INTERNAL
    assert len(result.warnings) == 2
    assert "'a'" in result.warnings[0]
    assert "'z'" in result.warnings[1]


def test_invalid_sensitivity_label_fails_clearly():
    with pytest.raises(ValueError, match="Invalid sensitivity label"):
        classify_sensitivity(["a"], {"a": "USED"})


@pytest.mark.parametrize("text", ['[]', '{"a": 1}', '{"a": "USED"}'])
def test_invalid_sensitivity_configuration_fails(tmp_path, text):
    path = tmp_path / "sensitivity.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_sensitivity(path)
