"""Fresh synthetic canaries exercising the actual API and persisted log paths.

These checks concern the ten-field local demonstration only. They are neither
a scan of other paths nor a claim about production security or compliance.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any
from uuid import uuid4

from .demo import golden_log_event, golden_payload
from .policy.models import APIAction, CompiledPolicy, LogAction, RevisionStatus
from .runtime.api import APIEnforcer, RuntimeMode
from .runtime.logs import LogSink, MASK, StructuredLogPipeline


_MARKER_FIELDS = (
    "account_number", "aadhaar_number", "available_balance", "recent_transactions",
    "customer_phone", "customer_address",
)


def verify_paths(
    policy_loader: Callable[[], CompiledPolicy], sink: LogSink, *,
    expected_analysis_digest: str, revision_id: str | None = None,
    hmac_key: bytes | None = None,
) -> dict[str, Any]:
    """Return honest PASS/FAIL evidence from this newly executed scoped run.

    The loader is server-owned. Expected analysis and optional revision pin the
    run to current evidence; no policy, event or success flag comes from callers.
    Exception messages are deliberately not copied into results or audit rows.
    """
    run_id = str(uuid4())
    result: dict[str, Any] = {
        "run_id": run_id, "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL", "synthetic": True,
        "scope": "Synthetic, path-scoped verification", "policy_revision": None,
        "checks": [], "api": {"original": {}, "output": {}, "trace": {}},
        "log": {"sanitized": {}, "persisted": {}}, "warnings": [],
    }

    def check(name: str, passed: bool, detail: str) -> None:
        result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})

    def approved_policy() -> CompiledPolicy:
        loaded = policy_loader()
        if not isinstance(loaded, CompiledPolicy):
            raise ValueError
        loaded = CompiledPolicy.from_dict(loaded.to_dict())
        if (
            loaded.revision.status is not RevisionStatus.APPROVED
            or loaded.approval is None or loaded.approval.decision != "APPROVE"
            or loaded.revision.analysis_digest != expected_analysis_digest
        ):
            raise ValueError
        return loaded

    try:
        policy = approved_policy()
        result["policy_revision"] = policy.revision.revision_id
        check("Current approved policy", True, "Active approval matches the expected analysis digest.")
        requested_matches = revision_id is None or revision_id == policy.revision.revision_id
        check("Requested revision", requested_matches, "Requested revision must match the active approved revision.")
        if not requested_matches:
            raise ValueError

        original = golden_payload()
        markers = {
            name: f"VEILMINT_SYNTHETIC_CANARY_{run_id.replace('-', '')}_{name.upper()}"
            for name in _MARKER_FIELDS
        }
        for name, marker in markers.items():
            original[name] = [{"synthetic_marker": marker}] if name == "recent_transactions" else marker
        event = golden_log_event()
        for name in markers:
            event[name] = deepcopy(original[name])
        result["api"]["original"] = deepcopy(original)

        by_name = {field.name: field for field in policy.fields}
        covered = all(name in by_name and by_name[name].path == (name,) for name in original)
        check("Golden fixture coverage", covered, "The fixture must exercise all ten active top-level field rules.")
        if not covered:
            raise ValueError

        api_result = APIEnforcer(policy_loader).enforce(
            original, RuntimeMode.ENFORCE, expected_analysis_digest=expected_analysis_digest,
        )
        api_output = api_result.payload
        trace = api_result.to_dict()
        trace.pop("payload", None)
        result["api"].update({"output": deepcopy(api_output), "trace": trace})
        api_valid = (
            api_result.policy_valid and api_result.mode is RuntimeMode.ENFORCE
            and api_result.policy_revision == policy.revision.revision_id
            and isinstance(api_output, dict)
        )
        check("API active revision", api_valid, "ENFORCE must execute with the checked approved policy revision.")
        sink.record_audit("CANARY_API", policy.revision.revision_id, "ENFORCE", api_result.warnings)
        output = api_output if isinstance(api_output, dict) else {}
        serialized_output = json.dumps(output, sort_keys=True, ensure_ascii=False)
        for name in sorted(original):
            field = by_name[name]
            if field.api_action is APIAction.REMOVE:
                absent = name not in output and (name not in markers or markers[name] not in serialized_output)
                check(f"API removal · {name}", absent, "Approved field and its marker must be absent from actual API output.")
            else:
                check(
                    f"API retention · {name}", name in output and output[name] == original[name],
                    "A retained field must preserve its synthetic value in actual API output.",
                )
        check(
            "UNKNOWN retained", "internal_risk_flag" in output and output["internal_risk_flag"] == original["internal_risk_flag"],
            "The uncertain risk field must remain in the API response.",
        )

        protected = StructuredLogPipeline(policy_loader, sink, hmac_key).process(
            event, expected_analysis_digest=expected_analysis_digest,
        )
        persisted = sink.get(protected.record_id)
        result["log"] = {"sanitized": deepcopy(protected.event), "persisted": deepcopy(persisted)}
        persisted_event = persisted.get("event") if isinstance(persisted, dict) else None
        check(
            "Log persisted result", isinstance(persisted_event, dict) and persisted_event == protected.event,
            "The actual SQLite record must equal the protected event, not an in-memory expectation.",
        )
        check(
            "Log active revision", protected.policy_revision == policy.revision.revision_id
            and persisted.get("policy_revision") == policy.revision.revision_id
            and persisted.get("mode") == "PROTECT",
            "Sanitizer and persisted record must identify the same checked policy revision.",
        )
        stored = persisted_event if isinstance(persisted_event, dict) else {}
        serialized_stored = json.dumps(stored, sort_keys=True, ensure_ascii=False)
        for name in sorted(event):
            field = by_name.get(name)
            action = field.log_action if field is not None else LogAction.MASK
            if action is LogAction.DROP:
                passed = name not in stored and name not in protected.event
                detail = "Configured DROP must omit the field from sanitized and persisted logs."
            elif action is LogAction.MASK:
                passed = stored.get(name) == MASK and protected.event.get(name) == MASK
                detail = "Configured or unknown-field MASK must persist only the fixed redaction marker."
            elif action is LogAction.HMAC_PSEUDONYM:
                expected = None
                if hmac_key:
                    encoded = json.dumps(event[name], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
                    expected = "hmac-sha256:" + hmac.new(hmac_key, encoded, hashlib.sha256).hexdigest()
                passed = expected is not None and stored.get(name) == expected and protected.event.get(name) == expected
                detail = "Configured HMAC must persist the keyed pseudonym without exposing its input or secret."
            else:
                # ALLOW containers still recurse in the real sanitizer; children
                # may therefore be more restricted than the enclosing field.
                passed = name in stored and name in protected.event
                if not isinstance(event[name], (dict, list)):
                    passed = passed and stored[name] == event[name]
                detail = "Configured ALLOW may retain synthetic values; container children remain separately protected."
            if action is not LogAction.ALLOW and name in markers:
                passed = passed and markers[name] not in serialized_stored
            check(f"Log {action.value} · {name}", passed, detail)

        final_policy = approved_policy()
        check(
            "Revision stable through run", final_policy.revision.revision_id == policy.revision.revision_id
            and final_policy.revision.inputs_digest == policy.revision.inputs_digest,
            "The current approved policy must remain unchanged across both checked runtime paths.",
        )
        result["warnings"] = sorted(set(api_result.warnings + protected.warnings))
    except Exception:
        check("Verification completed", False, "A required policy, runtime or storage check could not complete safely.")
        result["warnings"] = sorted(set(result["warnings"] + ["Synthetic path verification failed; inspect the failed checks."]))

    passed = bool(result["checks"]) and all(item["passed"] for item in result["checks"])
    try:
        sink.record_audit(
            "CANARY_VERIFY", result["policy_revision"], "ENFORCE",
            () if passed else ("Synthetic path verification failed.",),
        )
    except Exception:
        check("Verification audit", False, "Verification outcome could not be recorded safely.")
        passed = False
        result["warnings"] = sorted(set(result["warnings"] + ["Verification audit is unavailable."]))
    result["status"] = "PASS" if passed else "FAIL"
    return result
