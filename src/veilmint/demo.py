"""Read-only synthetic scenario shared by analysis, runtime and demo setup."""

from importlib.resources import files
import json

from .analyzer.report import generate_report


def golden_payload() -> dict:
    return json.loads(files("veilmint").joinpath("fixtures/nexus_bank_payload.json").read_text(encoding="utf-8"))


def golden_analysis() -> dict:
    fixture_dir = files("veilmint").joinpath("fixtures")
    return generate_report(
        json.loads(fixture_dir.joinpath("nexus_bank_schema.json").read_text(encoding="utf-8")),
        golden_payload(),
        fixture_dir.joinpath("nexus_bank_consumer.py").read_text(encoding="utf-8"),
        json.loads(fixture_dir.joinpath("sensitivity.json").read_text(encoding="utf-8")),
        filename="nexus_bank_consumer.py",
    )


def golden_log_event() -> dict:
    payload = golden_payload()
    names = ("account_id", "account_type", "available_balance", "account_number", "customer_phone", "aadhaar_number", "internal_risk_flag")
    return {**{name: payload[name] for name in names}, "demo_note": "SYNTHETIC_UNMAPPED_EVENT"}
