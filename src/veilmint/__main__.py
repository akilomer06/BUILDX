"""Command-line entry point. Consumer input is always read as text."""

import argparse
import json
import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from .analyzer.report import generate_report
from .analyzer.schema_inventory import load_json
from .analyzer.sensitivity import load_sensitivity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veilmint",
        description="Analyze API field usage without executing the consumer.",
    )
    parser.add_argument("--schema", type=Path, help="Producer JSON Schema file")
    parser.add_argument("--payload", type=Path, help="Payload JSON file to validate")
    parser.add_argument("--consumer", type=Path, help="Python consumer source file")
    parser.add_argument("--sensitivity", type=Path, help="JSON sensitivity mapping file")
    parser.add_argument("--root-name", default="payload", help="Consumer payload variable name")
    parser.add_argument("--output", type=Path, help="Write report to this file instead of stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Return a process exit status; errors never expose a traceback."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == 'bank':
        from .bank.cli import main as bank_main
        return bank_main(arguments[1:])
    if arguments and arguments[0] == "demo":
        from .demo_cli import main as demo_main
        return demo_main(arguments[1:])
    if arguments and arguments[0] == "policy":
        from .policy.cli import main as policy_main

        return policy_main(arguments[1:])
    parser = _parser()
    args = parser.parse_args(arguments)
    provided = sum(
        value is not None
        for value in (args.schema, args.payload, args.consumer, args.sensitivity)
    )
    if provided not in (0, 4):
        parser.error("provide --schema, --payload, --consumer and --sensitivity together")

    try:
        if provided:
            input_paths = [args.schema, args.payload, args.consumer, args.sensitivity]
            schema = load_json(args.schema)
            payload = load_json(args.payload)
            consumer_source = args.consumer.read_text(encoding="utf-8")
            sensitivity_mapping = load_sensitivity(args.sensitivity)
            filename = str(args.consumer)
        else:
            fixture_dir = files("veilmint").joinpath("fixtures")
            input_paths = (
                [
                    fixture_dir.joinpath(name)
                    for name in (
                        "nexus_bank_schema.json", "nexus_bank_payload.json",
                        "nexus_bank_consumer.py", "sensitivity.json",
                    )
                ]
                if isinstance(fixture_dir, Path) else []
            )
            schema = json.loads(
                fixture_dir.joinpath("nexus_bank_schema.json").read_text(encoding="utf-8")
            )
            payload = json.loads(
                fixture_dir.joinpath("nexus_bank_payload.json").read_text(encoding="utf-8")
            )
            consumer_source = fixture_dir.joinpath("nexus_bank_consumer.py").read_text(
                encoding="utf-8"
            )
            sensitivity_mapping = json.loads(
                fixture_dir.joinpath("sensitivity.json").read_text(encoding="utf-8")
            )
            filename = "nexus_bank_consumer.py"

        if args.output is not None:
            for input_path in input_paths:
                if args.output.resolve() == input_path.resolve() or (
                    args.output.exists() and input_path.exists()
                    and args.output.samefile(input_path)
                ):
                    raise ValueError(f"Output path must not overwrite an input file: {input_path}")

        report = generate_report(
            schema,
            payload,
            consumer_source,
            sensitivity_mapping,
            root_name=args.root_name,
            filename=filename,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, ValueError, TypeError) as exc:
        print("veilmint: input analysis failed; check JSON, schema, source paths and root name; output must not overwrite input files.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
