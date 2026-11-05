"""Idempotent synthetic initialization and a fresh pre-demo verification."""
import argparse
import json
import sqlite3
from pathlib import Path

from .demo import golden_analysis
from .policy.compiler import analysis_digest
from .policy.store import PolicyStore
from .runtime.logs import LogSink
from .verification import verify_paths


def initialize(path, *, approved=False):
    path = Path(path)
    # Refuse to take ownership of an existing unrelated database.
    if path.exists() and path.stat().st_size:
        with sqlite3.connect(path) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "veilmint_policy_revisions" not in tables:
                raise ValueError("Existing database is not a VEILMINT demo database")
    report = golden_analysis()
    with PolicyStore(path) as store:
        history = store.history()
        if history and store.get().revision.analysis_digest != analysis_digest(report):
            raise ValueError("Existing policy is not the current synthetic scenario; choose a new demo file")
        policy = store.create_revision(report)
        if approved and policy.approval is None:
            policy = store.review(policy.revision.revision_id, "synthetic-demo-initializer",
                                  tuple(f.name for f in policy.fields if f.removal_allowed),
                                  notes="Explicit synthetic demo initialization; no real customer data")
        return policy.to_dict()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="veilmint demo")
    parser.add_argument("command", choices=("init", "check"))
    parser.add_argument("--db", type=Path, default=Path("data/synthetic-demo.sqlite3"))
    parser.add_argument("--approve-synthetic", action="store_true", help="Explicitly approve the four synthetic demo candidates")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.db, approved=args.approve_synthetic)
        else:
            from .config import Settings
            settings = Settings.from_env()
            def loader():
                with PolicyStore(args.db) as store:
                    return store.get()
            result = verify_paths(loader, LogSink(args.db), expected_analysis_digest=analysis_digest(golden_analysis()), hmac_key=settings.hmac_key)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") != "FAIL" else 1
    except Exception:
        print('Demo operation failed safely; check configuration and use a dedicated synthetic database.')
        return 1
