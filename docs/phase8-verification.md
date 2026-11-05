# Phase 8 implementation and verification record

## Starting point

The repository already contained Phases 1–6: conservative AST analysis,
sensitivity classification, golden synthetic fixtures, revision-bound review,
deterministic compilation, SQLite persistence, API minimization, structured-log
protection, canaries, the React workbench and Docker deployment. It was an
uncommitted working tree on master; no code, data or original PDF was reset.
There was no banking domain, customer authentication, ledger, customer UI or
LAN entry point. Phase 7 remains intentionally postponed.

Before changing code the existing source, tests, README, runtime/route lifecycle,
policy/store, sanitizer, canary, Compose/Nginx and verification documents were
inspected. Baseline commands and actual results:

- `python -m pytest -q`: **222 passed**.
- `npm run typecheck`: passed.
- `npm test`: **4 passed**.
- `npm run build`: passed.

The existing lifecycle was FastAPI routes → shared core components → separate
policy/log tables in SQLite, with Nginx forwarding `/api/` inside Docker. The
implementation retained that lifecycle and added a bank module, an explicit
endpoint contract and a separate customer proxy.

## Added

- Backend: `bank/service.py` (Argon2id, hashed expiring sessions, accounts,
  beneficiaries, immutable integer-fils ledger, atomic/idempotent transfers);
  `bank/routes.py` (authenticated ownership-checked APIs); `bank/protection.py`
  (shared engine integration, scoped contract/policies, sanitized traffic);
  and `bank/cli.py` (explicit audited simulated funding only).
- Database: additive `nexus_*` schema, independent version marker, foreign keys,
  unique constraints, lookup indexes and immutable-ledger triggers. Existing
  policies/decisions/audits remain intact. Endpoint and log policies use distinct
  database files beside the original database within the same named volume.
- Frontend: NEXUS BANK login/registration, overview, account details, transactions,
  beneficiaries, review/confirm transfer and receipt. All values come from real
  authenticated responses. VEILMINT now opens on real Live Traffic, polls every
  three seconds and exposes request details without raw response values. Bank
  endpoint review reuses the existing review component.
- Integration: authentication/business logic → intentional DTO → existing
  APIEnforcer → serialization. Bank logs use the existing StructuredLogPipeline
  before LogSink. A server-generated correlation ID connects request, decision,
  safe traffic record and protected log. Unknown/stale policy behavior remains
  conservative. The original golden policy is never applied to bank endpoints.
- Networking: host-only operator proxy with private generated credential, origin
  and host checks; separate customer proxy serving only the bank application/API.
  Explicit LAN configuration enables customer binding only; database/backend
  stay private. `/ready` checks database initialization/write availability.
- Tools/docs: idempotent proxy configuration, isolated real-HTTP React-form test,
  Docker HTTP/restart acceptance script and the complete [Phase 8 guide](phase8.md).

## Actual local checks

- Bank domain/integration tests cover registration, hashing, sessions/expiry,
  login throttling, cross-customer authorization, strict money validation,
  beneficiaries, balanced debit/credit, rollback on failed credit, insufficient
  funds, inactive/self destinations, concurrent overspend and same-key retries.
- Protection tests cover required fields, candidate review/rejection, wrong
  destination, unknown fields, stale evidence, modes, safe log failure,
  actual persisted log inspection, correlation and old-data migration.
- Frontend regular command: **17 passed, 1 intentionally skipped**. The opt-in
  real HTTP test is skipped unless explicitly configured, not silently counted
  as passed. Typecheck and production build pass.
- `.venv/Scripts/python.exe scripts/verify_bank_ui.py`: the separately executed
  real HTTP React-form test **passed** with a fresh isolated database and backend.
  It drove two registrations, login/logout, explicit CLI funding, beneficiary
  creation, reviewed transfer and sender/recipient transaction histories. It uses
  jsdom and a test-only HTTP cookie jar, not a physical browser.
- Docker image builds and all three services' startup/readiness passed. HTTP
  checks served customer HTML/assets through port 8081 and operator APIs through
  port 8080. Customer attempts to reach policy, traffic, docs, environment and
  raw index paths were blocked, including a forged operator header.
- `scripts/verify_bank_docker.py` passed: real authenticated HTTP workflow,
  idempotency, two ledger sides, correlated protected log, then restart of all
  services. Session hashes, customer balances, receipts, bank policy revision
  and the original policy survived restart. Original golden canary: **PASS**.
- LAN configuration inspection confirmed customer `0.0.0.0` and operator
  `127.0.0.1`. It was restored to host-only mode without starting a LAN listener.
- Native and container `python -m pip check`: no broken requirements.
- `npm audit`: **0 vulnerabilities**.

Implementation fixes found by checks: transient account loading was distinguished
from failure, registration identity state is cleared on logout, UI test selectors
wait for actual asynchronous data, and customer Nginx's internal SPA index route
was corrected. The existing non-failing Starlette/httpx adapter deprecation
warning remains. Final container-suite results are appended after completion.

## One actual request trace

Local Docker evidence: `data/phase8-docker-verification.json` (ignored runtime
artifact; no credentials or raw customer response are stored in it).

- Correlation ID: `b3bf79a2-f826-4d98-b4a4-36e4db7e2fb5`.
- Customer action: authenticated account-detail read after a real sandbox transfer.
- Route template: `GET /api/bank/accounts/{account_id}`.
- Destination: `nexus_bank.account_summary.v1`.
- Bank revision: `r1-75a8dfe4ac84`, **REVIEW_REQUIRED**.
- Decision: all nine DTO fields retained; zero removals without explicit review.
- Protected log record: `26`; log outcome **SANITIZED**; customer reference
  persisted as `[REDACTED]`. Password and session token were absent.
- The matching safe event was retrieved from the actual operator traffic API.
- Separate isolated tests explicitly review the compatibility candidate and prove
  the correct **9→8** response without removing any required field. No bank
  candidate approval was silently created in the running demo.

## Boundaries and unverified acceptance items

**Physical Laptop 2 → Laptop 1 acceptance: NOT VERIFIED.** Configuration and exact
instructions are provided in [phase8.md](phase8.md); localhost Docker HTTP tests
and jsdom integration are not a substitute. Local browser visual QA was attempted
but Work settings report local browser use disabled.

The account contract is explicit and manually maintained; TypeScript was not
analyzed by the Python AST analyzer. Plain HTTP is isolated-LAN demonstration
only; no real credentials/data, real money, banking rails, public hosting,
production security/RBAC, exhaustive security claim or presentation package was
added. SQLite is local and unencrypted at rest; the operator host is trusted.
All required commands (start/stop, automatic non-destructive migration, funding,
review, tests, canary and LAN setup) are in the Phase 8 guide.

## Final gate results

- Final Linux/amd64 Docker backend suite:
  `docker compose run --rm --no-deps --volume LOCAL_TESTS_PATH:/app/tests:ro backend python -m pytest -q -p no:cacheprovider /app/tests`
  → **251 passed**, one existing Starlette/httpx deprecation warning.
- Final regular frontend: **17 passed, 1 opt-in integration test skipped**;
  `npm run typecheck` and `npm run build` passed.
- The opt-in real HTTP React-form test was run separately and **passed** using
  `python scripts/verify_bank_ui.py`, with automatic isolated backend setup and
  teardown. It is not counted as passed by the regular skipped invocation.
- `docker compose build` and `docker compose up -d --wait --wait-timeout 90`
  passed. Backend, customer and operator services healthy. Existing and new
  persistent records survived rebuild/restart. Customer app is left host-only.
- The original golden canary passed after restart. Bank API protection and its
  candidate review are independently exercised by the new integration suite.
- Physical two-laptop acceptance remains **NOT VERIFIED**. Browser visual QA
  was attempted again and explicitly denied by Work's local browser setting.
- Dependency checks passed; npm audit found zero vulnerabilities. No public
  deployment, production money or banking integration was added.
