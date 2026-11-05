"""Local, explicit policy review. Nothing is approved just by displaying it."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from ..analyzer.ast_analyzer import Usage
from ..analyzer.schema_inventory import load_json
from .compiler import compile_policy
from .models import CompiledPolicy, ReviewerDecision, RevisionStatus
from .store import PolicyStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veilmint policy",
        description="Review and persist local policy revisions; no API traffic is processed.",
    )
    parser.add_argument("--db", type=Path, default=Path("data/synthetic-demo.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create or load a revision from Phase 1 evidence")
    create.add_argument("--analysis", required=True, type=Path)
    create.add_argument("--log-mapping", type=Path, help="Sensitivity-to-log-action JSON object")
    create.add_argument("--known-fields", type=Path, help="Current schema inventory as a JSON list")
    create.add_argument("--new-revision", action="store_true", help="Require a fresh review even for identical inputs")
    create.add_argument("--output", type=Path, help="Also save compiled policy JSON")
    show = commands.add_parser("show", help="Display the stored compiled policy")
    show.add_argument("--revision")
    show.add_argument("--output", type=Path)
    commands.add_parser("history", help="Display revision history")
    review = commands.add_parser("review", help="Interactively review eligible candidate removals")
    review.add_argument("--revision", help="Defaults to latest revision")
    review.add_argument("--reject", action="store_true", help="Record a rejection with no removals")
    return parser


def _guard_output(output: Path | None, inputs: Sequence[Path]) -> None:
    if output is None:
        return
    for path in inputs:
        if output.resolve() == path.resolve() or (
            output.exists() and path.exists() and output.samefile(path)
        ):
            raise ValueError("Output path collides with a protected input")


def _emit(value: object, output: Path | None = None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is not None:
        output.write_text(rendered, encoding="utf-8", newline="\n")
    sys.stdout.write(rendered)


def _show_fields(policy: CompiledPolicy) -> None:
    print(f"Policy {policy.revision.revision_id} | {policy.revision.status.value}")
    print("Field | Usage | Sensitivity | Proposed API | Log action")
    for field in policy.fields:
        print(
            f"{field.name} | {field.usage.value} | {field.sensitivity.value} | "
            f"{field.api_action.value} | {field.log_action.value}"
        )
        for evidence in field.evidence:
            print(f"  Evidence: {evidence}")
    for warning in policy.warnings:
        print(f"Warning: {warning}")


def _selected_fields(choice: str, candidates: Sequence[str]) -> tuple[str, ...]:
    normalized = choice.strip().lower()
    if normalized == "all":
        return tuple(sorted(candidates))
    if normalized in ("", "none"):
        return ()
    indices = [part.strip() for part in choice.split(",")]
    if not all(part.isdecimal() for part in indices):
        raise ValueError("Select candidate numbers only")
    numbers = [int(part) for part in indices]
    if any(number < 1 or number > len(candidates) for number in numbers):
        raise ValueError("Select candidate numbers only")
    return tuple(sorted({candidates[number - 1] for number in numbers}))


def _review(store: PolicyStore, revision_id: str | None, reject: bool) -> int:
    policy = store.get(revision_id)
    if policy.revision.revision_id != store.get().revision.revision_id:
        raise ValueError("Only the latest revision can be reviewed")
    if policy.revision.status != RevisionStatus.REVIEW_REQUIRED:
        raise ValueError("This revision already has a reviewer decision")
    _show_fields(policy)
    print("\nThis review compiles a future runtime policy; it does not call or change a live API.")
    print("USED and UNKNOWN fields cannot be selected for removal.")
    candidates = [
        field.name for field in policy.fields
        if field.usage == Usage.CANDIDATE_UNUSED and field.removal_allowed
    ]
    selected: tuple[str, ...] = ()
    if not reject:
        print("Eligible review candidates (not proof of non-use):")
        for number, name in enumerate(candidates, 1):
            print(f"  {number}. {name}")
        selected = _selected_fields(
            input("Candidate numbers to remove, comma-separated; all or none: "), candidates,
        )
    reviewer = input("Reviewer label (required): ").strip()
    if not reviewer:
        raise ValueError("A reviewer label is required")
    notes = input("Notes (optional): ").strip()
    decision_name = "REJECT" if reject else "APPROVE"
    decision = ReviewerDecision(
        revision_id=policy.revision.revision_id,
        analysis_digest=policy.revision.analysis_digest,
        inputs_digest=policy.revision.inputs_digest,
        reviewer=reviewer,
        approved_fields=selected,
        decided_at=datetime.now(timezone.utc).isoformat(),
        notes=notes,
        decision=decision_name,
    )
    inputs = store.load_inputs(policy.revision.revision_id)
    preview = compile_policy(
        inputs["report"], policy.revision, decision,
        log_mapping=inputs["log_mapping"], known_fields=inputs["known_fields"],
    )
    print("\nPreview - no decision has been saved:")
    _show_fields(preview)
    summary = preview.to_dict()["summary"]
    print(
        f"Planned API shape: {summary['fields_before']} -> {summary['fields_after']} fields; "
        f"{summary['fields_removed']} removal(s)."
    )
    print(f"Reviewer: {reviewer}; decision: {decision_name}.")
    if input(f"Type {decision_name} exactly to save, or anything else to cancel: ").strip() != decision_name:
        print("Cancelled. No reviewer decision was saved.")
        return 0
    saved = store.review(
        policy.revision.revision_id, reviewer, selected, notes=notes, decision=decision_name,
    )
    print("Saved reviewer decision and compiled policy:")
    _emit(saved.to_dict())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    # JSON exports and piped reviewer input use the same encoding on Windows
    # and Unix, including reviewer labels and notes outside the locale charset.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        output = getattr(args, "output", None)
        protected = [args.db, Path(str(args.db) + "-wal"), Path(str(args.db) + "-shm")]
        if args.command == "create":
            protected.extend(path for path in (args.analysis, args.log_mapping, args.known_fields) if path is not None)
        _guard_output(output, protected)
        with PolicyStore(args.db) as store:
            if args.command == "create":
                report = load_json(args.analysis)
                mapping = load_json(args.log_mapping) if args.log_mapping is not None else None
                known_fields = load_json(args.known_fields) if args.known_fields is not None else None
                if known_fields is not None and (
                    not isinstance(known_fields, list)
                    or any(not isinstance(name, str) for name in known_fields)
                ):
                    raise ValueError("Known fields must be a JSON list of names")
                policy = store.create_revision(
                    report, log_mapping=mapping, known_fields=known_fields,
                    force_new=args.new_revision,
                )
                _emit(policy.to_dict(), output)
            elif args.command == "show":
                _emit(store.get(args.revision).to_dict(), output)
            elif args.command == "history":
                _emit(store.history())
            else:
                return _review(store, args.revision, args.reject)
    except (EOFError, KeyboardInterrupt):
        print("Cancelled. No reviewer decision was saved.")
        return 0
    except (OSError, ValueError, TypeError):
        print(
            "veilmint policy: operation failed; check the input files, latest revision, "
            "candidate selection, reviewer label and database availability.",
            file=sys.stderr,
        )
        return 1
    return 0
