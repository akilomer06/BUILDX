# Sequential verification record

All checks below are actual local runs, using Python 3.14 on Windows. Each phase
is verified before implementation of the next phase begins.

## Phase 1 baseline

- `python -m pytest -q`: **90 passed** before Phase 2 changes.
- `python -m veilmint`: **5 USED / 4 CANDIDATE_UNUSED / 1 UNKNOWN**.
- Read the existing source, tests, README and generated analysis report.
- Preserved the original PDF and working analyzer implementation.

## Phase 2

Added input fingerprints to the analysis metadata so changed schema, consumer,
payload or sensitivity inputs invalidate approval even if usage counts match.
The fingerprint is deterministic and contains no raw input values.

- `python -m pytest -q`: **144 passed** after Phase 2 implementation.
- Executed the interactive CLI against the synthetic-only database, with an
  explicitly labelled `synthetic-demo-verification` reviewer.
- Revision `r1-eb6439992d5f` persisted with approval metadata. Before approval:
  **10 KEEP / 0 REMOVE**; after: **6 KEEP / 4 REMOVE**, UNKNOWN retained.
- Compiled snapshots and the CLI transcript are in ignored `data/` for local
  inspection; tests independently verify persistence, stale decisions and history.
- Fixed a Windows CLI encoding failure; UTF-8 reviewer labels now roundtrip.

## Phase 3

Started only after the Phase 2 gate above passed and its approved policy was
loaded back from SQLite and checked.

- `python -m pytest -q`: **194 passed** at the final Phase 3 gate, with one non-failing Starlette TestClient
  deprecation warning about its httpx adapter.
- Actual HTTP handlers loaded revision `r1-eb6439992d5f` from SQLite: ENFORCE
  returned **10 → 6**, retained UNKNOWN, and kept metadata outside the payload.
- Protected log readback contained only `account_type: DEMO_CHECKING` plus fixed
  masks for account ID, phone, risk flag and the unknown demo note. Balance,
  account number and Aadhaar placeholder were dropped before insertion.
- Tests cover nested paths/arrays, HMAC, modes, malformed/stale/missing policy,
  value-free diagnostics and no raw fallback on sanitizer failures.
- Fixed ASGI exception containment at the service boundary so unexpected
  exceptions cannot be re-raised to a server logger with raw values.

## Phase 4

Started after the Phase 3 tests and persisted golden runtime checks passed.

- Backend: **217 passed**. Frontend: typecheck passed, **3 tests passed**, production
  build passed. Interrupted frontend work was completed (stylesheet and tests).
- HTTP integration checks cover real analysis, review, persistence, inspectors,
  fresh canary success/failure and revision mismatch.
- Browser visual QA unavailable: local browser use is disabled in Work settings.

## Phase 5

- Added snapshot read transactions for revision/decision consistency.
- Aligned numeric array-index matching across API and log protection.
- Removed raw validation exception text from analysis CLI errors.
- Added idempotent synthetic-only demo initialization and fresh check commands.
- Added tests for unavailable SQLite, parallel readers, preserving unrelated
  records, refusing unrelated databases and protection across app restart.
- `npm audit` and `npm audit --omit=dev`: **0 vulnerabilities**.
- `python -m pip check`: **no broken requirements**.
- Final backend gate: **222 passed**; frontend typecheck, tests and build pass.
- Fixed a compatibility regression found when aligning path semantics; numeric
  array indices now match consistently while conflicting log rules stay masked.
- The upstream non-failing Starlette/httpx TestClient deprecation remains.

## Phase 6

- Added backend/frontend Dockerfiles, Compose, Nginx proxy, .env.example,
  Docker context exclusions, pinned Python dependencies and deployment docs.
- Docker is unavailable: no image build, Compose execution or container restart
  test is claimed. Public hosting was not attempted for this unauthenticated
  SQLite local demo.
- Executed a fresh native database initialization and two real Uvicorn process
  starts on port 8123. Both health checks passed, both returned six API fields,
  approval survived restart, and both fresh canaries passed with distinct IDs.
  Evidence is in ignored `data/deployment-check.json`.
- Frontend: typecheck passed, **4 tests passed**, production build passed.
- Browser visual QA remains unavailable due to Work settings; HTTP connectivity
  and frontend/backend contracts are checked separately.
- Final full backend gate: **222 passed**, Python dependency check passed, and
  `veilmint-0.6.0-py3-none-any.whl` built successfully. Vite served the workbench
  HTML and proxied a live analysis request with the expected 5/4/1 counts.
- Installed that wheel into a new isolated virtual environment, initialized a
  new synthetic database and ran a fresh canary: **PASS**. Its dependency check
  also passed. No editable/source checkout import was used for that check.

### Docker installation recheck

- Docker Desktop is now installed under the user's local Programs directory.
  CLI **29.9.2**, Compose **5.6.1**; the existing terminal has a stale PATH, so
  these checks used the executable's absolute path.
- `docker compose config --quiet`: passed.
- Engine unavailable: `docker version` reports **Docker Desktop is unable to
  start**. Both `wsl --status` and `wsl --list --verbose` report that Windows
  Subsystem for Linux is not installed. Docker is configured for WSL2.
- Container builds and runtime checks remain blocked until WSL is installed
  and Docker's engine starts. No Windows feature or installation settings were
  changed during this check.

### Docker engine restored — successful deployment

- Docker Desktop Linux/amd64 engine **29.9.2** is now available; Compose **5.6.1**.
- `docker compose build`: both images built successfully, including the frontend
  production build and pinned Python dependencies.
- `docker compose up -d --wait --wait-timeout 90`: both services healthy.
- Initialized only the named synthetic-demo database inside `buildx_demo-data`.
- HTTP checks through Nginx at `http://127.0.0.1:8080`: workbench HTML served,
  health OK, approved revision loaded, ENFORCE **10→6**, UNKNOWN retained, log
  readback sanitized and a fresh canary **PASS**.
- `docker compose restart` followed by readiness and HTTP checks: approval and
  revision survived, ENFORCE still returned six fields, and a distinct fresh
  canary **PASS** confirmed protected runtime/storage paths after restart.
- Local evidence is in ignored `data/docker-demo-check.json`,
  `data/docker-http-before-restart.json` and `data/docker-after-restart.json`.
- Services remain running locally; no public deployment or exposure was added.
- Linux container backend tests: **222 passed**, with the same non-failing
  Starlette/httpx deprecation warning. The initial test bind at `/tests` was
  corrected to `/app/tests` so the two source-relative fixture tests resolve
  `/app/src` as designed. No product or test source change was required.
- Container `python -m pip check`: **no broken requirements**.

## Phase 8 — authenticated banking sandbox

Baseline reverified before edits: 222 backend tests, 4 frontend tests, frontend
 typecheck and build passed. NEXUS BANK now adds persistent authenticated customer
workflows, an atomic integer ledger, scoped existing-engine integration, safe
real traffic and a separate customer proxy. See [Phase 8 implementation and
verification](phase8-verification.md) for exact checks, real correlation trace,
fixes and limitations; [the Phase 8 guide](phase8.md) has commands and architecture.
Physical two-laptop acceptance and browser visual QA are explicitly unverified.

Final Phase 8 Linux container suite: **251 passed**, frontend **17 regular tests
passed**, separate real-HTTP React-form test **passed**. Typecheck/build, Docker
health, persistence and original golden canary passed. See phase8-verification.md
for the recorded safe correlation trace and remaining unverified physical-device
and browser-visual checks.

## Unified review, Accounts Explorer and protection inspection follow-up

- Before changes: **251 backend tests**, **17 frontend tests** passed; the
  opt-in real-HTTP integration was intentionally skipped in the regular command.
  Typecheck/build passed. Working files and existing runtime data were preserved.
- One Policy review now serves destination-specific bank and original example
  policies. Changing destination clears unsaved selection/reviewer input.
  Original API/log/canary views are grouped under Demo examples. Bank evidence
  explicitly identifies the maintained contract and does not claim TS analysis.
- Read-only operator projections use whitelisted columns and bounded parameterized
  search. Password/session hashes and credentials are never selected. Default
  masking, explicit 45-second UI reveal and no-store responses were tested.
- New synthetic contact profiles are generated only by the opt-in CLI. The bank
  migration advances additively to version 2. Customer DTOs and bank approval
  digests are unchanged. Existing schema/ledger/policy behavior passes all tests.
- Real account requests stage selected audit fields in memory through the
  existing sanitizer: names/fictional contacts MASK, balance/transactions DROP.
  Actual stored log records are fetched and correlation-checked for display.
- Header evidence records only presence and collection exclusions. Cookie and
  Authorization remain available to authentication; values are never logged.
  Contract exclusions are labelled separately from approved API removals.
- API access logging was disabled in both proxies to keep search terms and raw
  route identifiers out of ordinary proxy logs. Safe application event metadata
  continues through the structured protection path.
- Final backend suite: **257 passed** locally and **257 passed in Linux Docker**,
  with the existing single Starlette/httpx adapter deprecation warning.
- Frontend: **20 passed, 1 intentionally skipped opt-in test**. Typecheck and
  production build passed. The opt-in real HTTP React test was executed
  separately via `scripts/verify_bank_ui.py` and passed; it now also opens the
  operator Explorer, checks masking and performs explicit sandbox reveal.
- `scripts/verify_operator_inspection.py`: actual Docker HTTP flow passed for
  masked/revealed projections, financial DROP, fictional profile MASK, header
  exclusion, read-only routes and customer/operator separation. It created an
  explicitly fictional verification account rather than invented traffic rows.
- Verification record: `e33c0255-8a0d-4024-81b1-5028213bd5d5`; correlation
  `d828642c-26e0-45d8-84d0-24eceb19c6b0`; event **68**, persisted protected log
  **74**. Four source fields were excluded by contract, no unapproved API
  removals were applied. Credentials are absent from the evidence artifact.
- Images rebuilt and all three services deployed healthy. The user's existing
  LAN binding was already enabled and was preserved. Physical second-device
  and browser visual verification remain unverified; no claim was added.
- Full instructions: [operator-inspection.md](operator-inspection.md).

## Numeric account IDs and INR follow-up

- Public account IDs are stable 12-digit strings for existing and new accounts.
  Beneficiaries, transfer inputs, receipts, operator search and linked historical
  request evidence resolve to the numeric IDs. Legacy internal references are
  retained so immutable ledger entries need no rewrite.
- The bank uses INR and integer paise, with Indian currency formatting in both
  customer balances and the operator account table. Version 3 preserves numeric
  balances without FX conversion; old AED ledger/receipt labels are projected as
  INR while their original stored rows remain intact. The original golden
  example fixture and policy approvals remain unchanged.
- Backend: **259 passed**. Frontend: **21 passed**, one opt-in test skipped in
  the normal run; the opt-in real HTTP React workflow passed separately.
  Typecheck and production build passed.
- Before deployment, consistent SQLite backups were taken inside the Docker
  data volume at `/data/before-numeric-inr-20261104T180034/`.
- Live upgrade verification preserved all five existing customer accounts and
  balances, seven ledger entries, two transfers, two beneficiaries, five sessions,
  the fictional profile, 79 existing protected logs, and policy history. Foreign
  key checks passed. No original ledger records were changed.
- Updated Docker acceptance passed numeric IDs, INR transfers, idempotency,
  session/ledger/policy persistence after restart, customer/operator separation
  and the original golden canary. Operator inspection passed masking, reveal,
  header exclusions and financial DROP; evidence event 103, protected log 110.
- All three redeployed services are healthy. The existing LAN binding remains
  enabled. Physical second-device and browser visual checks remain unverified.

## Rollback of the live-traffic account-details toggle

The user requested rollback of the latest account-detail columns and Show/Hide
control. The previous six-column live-traffic table and metadata-only API are
restored, including the original request-evidence inspector. Numeric account IDs,
INR, Accounts Explorer, policies, account records and ledger data are preserved.
No database backup was restored and no bank data was deleted.

Validation: 37 relevant backend tests and 19 frontend tests passed; the separate
opt-in HTTP test was not run for this rollback. Typecheck and production build
passed. The restored frontend asset hashes match the earlier numeric-ID/INR build.

## Live bank traffic: selected HTTP/JSON response inspector

The separate comparison page, fictional comparison fixture and standalone demo
account-summary endpoints were removed following the user's clarification.
Live bank traffic is again the initial view. Clicking a real request expands its
HTTP response inline immediately below that row. The global Standard / VEILMINT
mode controls a server-returned version of that selected request's frozen body.

- Standard is byte-for-byte equal to the captured customer DTO. VEILMINT masks
  explicit identifiers recursively and removes configured sensitive fields only
  if present. No unrelated dataset, fake balance or lastUpdated value is used.
- Response snapshots are opt-in, worker-local memory only: at most 100 bodies,
  64 KiB each, 15-minute TTL, cleared on restart. Existing stored traffic remains
  metadata-only. Older/unavailable bodies show a clear prompt for a new request.
- Authentication responses, request bodies, passwords and session headers are
  excluded. Only four safe response headers are retained. Operator authorization
  and customer-proxy blocking are preserved. There are no inspection log writes.
- Correlation, endpoint, method and status are checked before rendering. Late
  responses cannot replace another request or mode. Status/headers, syntax-colored
  JSON, copy, collapse and actual field/byte metrics are integrated in the row.
- Customer bank UI, login, transfers, numeric IDs, balances, INR and response
  schemas are unchanged. Internal route instrumentation marks the returned DTO;
  middleware only captures it if the final status still matches. Capture failure
  does not affect a customer response or retry a payment.
- Backend: **266 passed**, with the existing adapter deprecation warning.
  Frontend: **24 passed**, two opt-in tests skipped in the normal run. Both
  opt-in real-HTTP React tests passed separately: existing bank workflow and
  selected live response inspection with repeated mode switches.
- Docker acceptance initially found the proxy using HTTP/1.0 and duplicating
  nosniff. Both proxies now use HTTP/1.1 upstream and hide the redundant backend
  nosniff header while retaining the server's single nosniff header. Customer JSON
  bodies are unchanged. The deployed React response-inspection test then passed.
- Read-only Docker acceptance passed five further switches on actual correlation
  efbc49f5-c3a7-4733-88bc-472bf52b67fc: 200, HTTP/1.1, two identifiers masked,
  zero fields removed because no PAN/address/CIBIL was in the source, 286 B in
  both modes (same-length masking), unchanged balance/INR, customer boundary PASS.
- All three containers are healthy. Browser visual checks remain unavailable
  because local browser use is disabled in Work settings.
- Instructions: [traffic-responses.md](traffic-responses.md). Safe aggregate
  evidence: ignored data/response-inspection-verification.json.

## Response dialog and complete JSON visibility

- Fixed the reported clipping: full-width inline JSON rows placed successive
  lines horizontally. The response now opens in a portal dialog outside the
  traffic table's overflow container. Code rows use a vertical grid, preserve
  indentation and wrap long values without forcing a horizontal page layout.
- Complete JSON is the initial content, including braces, nested objects and
  arrays. HTTP headers are collapsed below it. The dialog includes the shared
  Standard / VEILMINT controls, Copy JSON, Close, Escape/backdrop dismissal,
  keyboard focus containment/restoration, inert background and scroll locking.
- Only operator frontend files changed. Customer bank UI, API responses and
  backend masking/capture behavior remain unchanged.
- Frontend: **27 passed**, two opt-in HTTP tests skipped in the normal suite.
  Typecheck and production build passed. Both opt-in customer/operator HTTP
  tests passed separately; the selected-response test also passed against the
  deployed Docker proxy, parsing every displayed JSON line back to the actual
  original response and exercising repeated mode switches.
- Added a computed-style regression check for grid rows, preserved whitespace,
  wrapping and removal of fixed minimum code width. Added nested JSON/Unicode/
  escaping checks and modal keyboard/closing tests. These checks address the
  reported layout cause; they do not substitute for visual browser acceptance.
- Frontend image rebuilt and all three services are healthy. Browser preview was
  attempted but local browser use remains disabled in Work settings.
