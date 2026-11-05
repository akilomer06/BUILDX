"""Policy-loaded response minimisation with exact, array-aware field paths."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..analyzer.ast_analyzer import Usage
from ..policy.models import APIAction, CompiledPolicy, RevisionStatus


class RuntimeMode(str, Enum):
    OBSERVE = "OBSERVE"
    WARN = "WARN"
    ENFORCE = "ENFORCE"


@dataclass(frozen=True)
class APIResult:
    payload: dict[str, Any] | list[Any]
    mode: RuntimeMode
    policy_revision: str | None
    policy_valid: bool
    warnings: tuple[str, ...]
    removed_paths: tuple[str, ...]
    would_remove_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return payload and separate internal trace metadata for a demo inspector."""
        return {
            "payload": deepcopy(self.payload),
            "mode": self.mode.value,
            "policy_revision": self.policy_revision,
            "policy_valid": self.policy_valid,
            "warnings": list(self.warnings),
            "removed_paths": list(self.removed_paths),
            "would_remove_paths": list(self.would_remove_paths),
        }


def _matches(pattern: tuple[str, ...], actual: tuple[str | int, ...]) -> bool:
    if len(pattern) != len(actual):
        return False
    return all(
        (segment in ("*", str(value))) if isinstance(value, int) else segment == value and segment != "*"
        for segment, value in zip(pattern, actual)
    )


def _pointer(path: tuple[str | int, ...]) -> str:
    return "/" + "/".join(str(value).replace("~", "~0").replace("/", "~1") for value in path)


def _validate_paths(policy: CompiledPolicy) -> None:
    paths = [field.path for field in policy.fields]
    if len(paths) != len(set(paths)):
        raise ValueError("Policy field paths must be unique")
    for field in policy.fields:
        if field.path[-1] != field.name or field.path[-1] == "*":
            raise ValueError("Policy field paths must end in their own field name")
        if field.api_action is APIAction.REMOVE:
            if field.usage is not Usage.CANDIDATE_UNUSED or not field.removal_allowed:
                raise ValueError("Only an approved candidate can be removed")
            for other in policy.fields:
                if other.api_action is APIAction.KEEP and len(other.path) > len(field.path):
                    if all(a == b or a == "*" or b == "*" for a, b in zip(field.path, other.path)):
                        raise ValueError("A removal cannot contain an explicitly retained field")


class APIEnforcer:
    """Load the latest policy server-side for every call; never accept caller policy.

    The loader must return the latest revision, including pending revisions. It
    must not select an older approval when a newer revision requires review.
    JSON objects use exact paths; '*' matches array indices only. A root array
    also applies ordinary root-object rules independently to each direct item.
    """

    def __init__(self, policy_loader: Callable[[], CompiledPolicy]):
        self._policy_loader = policy_loader

    def enforce(
        self,
        payload: dict[str, Any] | list[Any],
        mode: RuntimeMode = RuntimeMode.OBSERVE,
        *,
        expected_analysis_digest: str | None = None,
    ) -> APIResult:
        if not isinstance(payload, (dict, list)):
            raise ValueError("API response must be a JSON object or array")
        invalid_mode = False
        try:
            selected_mode = RuntimeMode(mode)
        except (ValueError, TypeError):
            selected_mode = RuntimeMode.OBSERVE
            invalid_mode = True
        try:
            original = deepcopy(payload)
        except Exception:
            # No mutation has occurred; preserve the supplied response even if
            # copying an unsupported object or deeply nested input fails.
            return APIResult(payload, selected_mode, None, False,
                             ("Response could not be inspected; original response retained.",), (), ())
        if invalid_mode:
            return APIResult(original, selected_mode, None, False,
                             ("Invalid runtime mode; original response retained.",), (), ())
        revision_id: str | None = None

        def retain(message: str) -> APIResult:
            return APIResult(original, selected_mode, revision_id, False, (message,), (), ())

        try:
            loaded = self._policy_loader()
            if not isinstance(loaded, CompiledPolicy):
                return retain("Active policy is unavailable or invalid; original response retained.")
            policy = CompiledPolicy.from_dict(loaded.to_dict())
            _validate_paths(policy)
            revision_id = policy.revision.revision_id
            if policy.revision.status is not RevisionStatus.APPROVED or policy.approval is None or policy.approval.decision != "APPROVE":
                return retain("Latest policy is not approved; original response retained.")
            if expected_analysis_digest is not None and policy.revision.analysis_digest != expected_analysis_digest:
                return retain("Active policy does not match current analysis; original response retained.")
        except Exception:
            return retain("Active policy is unavailable or invalid; original response retained.")

        warnings: set[str] = set()
        would_remove: list[str] = []
        root_array = isinstance(original, list)

        def scopes(path: tuple[str | int, ...]) -> tuple[tuple[str | int, ...], ...]:
            # Retain concrete indices for trace paths. Strip the initial index
            # only for root-array object rules; explicit wildcard paths can also
            # match the full concrete path.
            if root_array and path and isinstance(path[0], int):
                return (path, path[1:])
            return (path,)

        def find(path: tuple[str | int, ...]):
            matching = [field for field in policy.fields if any(_matches(field.path, candidate) for candidate in scopes(path))]
            if len(matching) > 1:
                raise ValueError("Ambiguous policy field path")
            return matching[0] if matching else None

        def is_container_prefix(path: tuple[str | int, ...]) -> bool:
            return any(
                len(field.path) > len(candidate) and _matches(field.path[:len(candidate)], candidate)
                for field in policy.fields for candidate in scopes(path)
            )

        def walk(value: Any, path: tuple[str | int, ...]) -> Any:
            if isinstance(value, list):
                return [walk(item, path + (index,)) for index, item in enumerate(value)]
            if not isinstance(value, dict):
                return value
            result: dict[str, Any] = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError("API object keys must be strings")
                child_path = path + (key,)
                field = find(child_path)
                if field is not None and field.api_action is APIAction.REMOVE:
                    would_remove.append(_pointer(child_path))
                    continue
                if field is None and not is_container_prefix(child_path):
                    # Keys and values of unmapped input are intentionally absent
                    # from warning text; retain the complete unknown subtree.
                    warnings.add("Unmapped API field retained; policy has no exact field-path rule.")
                    result[key] = child
                else:
                    result[key] = walk(child, child_path)
            return result

        try:
            minimized = walk(original, ())
            planned = tuple(sorted(set(would_remove)))
            return APIResult(
                payload=minimized if selected_mode is RuntimeMode.ENFORCE else original,
                mode=selected_mode, policy_revision=revision_id, policy_valid=True,
                warnings=tuple(sorted(warnings)),
                removed_paths=planned if selected_mode is RuntimeMode.ENFORCE else (),
                would_remove_paths=planned,
            )
        except Exception:
            return retain("Response minimisation failed safely; original response retained.")
