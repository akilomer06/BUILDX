"""Sensitivity labels are configuration, independent of consumer usage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .schema_inventory import load_json


class Sensitivity(str, Enum):
    GENERAL = "GENERAL"
    FINANCIAL = "FINANCIAL"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True)
class SensitivityResult:
    labels: dict[str, Sensitivity]
    warnings: tuple[str, ...]


def load_sensitivity(path: str | Path) -> dict[str, str]:
    mapping = load_json(path)
    if not isinstance(mapping, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in mapping.items()):
        raise ValueError("Sensitivity configuration must be an object mapping field names to labels.")
    # Reject invalid entries even if they refer to fields outside the inventory.
    for name, label in sorted(mapping.items()):
        try:
            Sensitivity(label)
        except ValueError as exc:
            raise ValueError(f"Invalid sensitivity label for {name!r}: {label!r}.") from exc
    return mapping


def classify_sensitivity(fields: Iterable[str], mapping: Mapping[str, str]) -> SensitivityResult:
    labels: dict[str, Sensitivity] = {}
    warnings: list[str] = []
    for name in sorted(set(fields)):
        if name not in mapping:
            labels[name] = Sensitivity.INTERNAL
            warnings.append(f"No sensitivity mapping for {name!r}; defaulted to INTERNAL.")
            continue
        try:
            labels[name] = Sensitivity(mapping[name])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid sensitivity label for {name!r}: {mapping[name]!r}.") from exc
    return SensitivityResult(labels=labels, warnings=tuple(warnings))
