# Phase 9 baseline — 5 November 2026, Asia/Dubai

Before application edits:
- `.venv\Scripts\python.exe -m pytest -q`: exit 0, 266 passed, one existing Starlette/httpx deprecation warning.
- `npm --prefix frontend run typecheck`: exit 0.
- `npm --prefix frontend test`: exit 0, 27 passed, two opt-in tests skipped.
- `npm --prefix frontend run build`: exit 0.
- `python scripts/verify_bank_ui.py`: exit 0, two real-HTTP React tests passed separately.
- `docker compose ps`: backend, frontend and customer healthy.

SQLite backup directory in the persistent Docker volume: `/data/phase9-backup-20261104T211858`. UTC filename corresponds to the client-local audit date. SQLite backup API copied every current policy/main database consistently; no data reset was performed.

The final PDF was text-extracted using pypdf into ignored data/phase9-final-plan-extracted.txt. PDF layout was not relevant to requirements extraction and was not visually validated. Twenty-three Markdown documents were read; source paths, SHA256 hashes and headings are captured in ignored data/phase9-plan-inventory.json. No Phase 7 prompt was found. All available Phase 1–6, Phase 8, Phase 9 and amendment documents were included. pypdf was installed as a local audit utility, not an application runtime dependency.

Browser automation is disabled in Work settings (confirmed in preceding implementation work). Browser visual and physical two-laptop acceptance remain NOT VERIFIED. No images or screenshots were fabricated.
