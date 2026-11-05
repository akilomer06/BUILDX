# VEILMINT — Local synthetic workbench

**Phase 8 adds NEXUS BANK:** real registration/login, customer-owned accounts,
beneficiaries, atomic sandbox transfers and a live traffic view using the shared
VEILMINT protection engine. No real money or real banking integrations are used.

- Customer app: **http://localhost:8081/bank/**
- Host-only operator workbench: **http://localhost:8080**
- Setup, funding, architecture, LAN instructions and limits: [Phase 8 guide](docs/phase8.md).

```powershell
python scripts/configure_bank.py
docker compose build
docker compose up -d --wait --wait-timeout 90
```

The customer app starts with zero funds and an empty ledger. Funding is an
explicit operator CLI action documented in the guide. Use fictional identities
and unique demo passwords. The customer port stays loopback-only unless
`python scripts/configure_bank.py --lan` is explicitly run. A physical second
laptop test is **not verified**; existing data and original golden APIs are preserved.

VEILMINT analyzes a producer's JSON Schema and a Python consumer to identify top-level fields with direct usage evidence, potentially unused fields, and uncertain fields. Phase 1 produces an explainable JSON report. Consumer source is parsed with Python `ast`; it is never imported or executed. See the official [Python AST documentation](https://docs.python.org/3/library/ast.html) for the parsing API.

The repository includes a synthetic NEXUS BANK example. Its values are obvious demo placeholders, with no real customer data or credentials. The existing `VEILMINT_Final_Implementation_Plan.pdf` was preserved; there was no existing application code to reuse.

## Setup

For reproducible native/Compose startup, initialization, secrets and restart
checks, see [docs/deployment.md](docs/deployment.md). Docker images, container
health, Nginx connectivity, canary and SQLite persistence across restart are
verified. No public deployment was attempted. Browser visual QA is unverified because local browser use
is disabled in Work settings.

Requires Python 3.12 or later. From the repository directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If PowerShell activation is unavailable, use `.\.venv\Scripts\python.exe` wherever the commands below use `python`.

Run all tests with one command:

```powershell
python -m pytest
```

## Run the analysis

Analyze the packaged synthetic example and print the report:

```powershell
python -m veilmint
```

The installed `veilmint` command provides the same interface. To save the report:

```powershell
python -m veilmint --output analysis-report.json
```

For your own local inputs, provide all four paths together:

```powershell
python -m veilmint --schema schema.json --payload payload.json --consumer consumer.py --sensitivity sensitivity.json
```

Use `--root-name response` when the payload variable is named `response` instead of `payload`. Sensitivity configuration is a JSON object mapping field names to `GENERAL`, `FINANCIAL`, `MEDIUM`, `HIGH`, or `INTERNAL`. Missing entries default to `INTERNAL` and produce a warning. Sensitivity never determines usage.

The schema and payload are validated before analysis using `Draft202012Validator.check_schema` and `iter_errors`, as described in the official [jsonschema validation documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/). Phase 1 accepts Draft 2020-12 object schemas with explicit top-level `properties`. Schema references and top-level composition/conditional property definitions are rejected rather than partially inventoried; validation stays offline. Invalid inputs fail with a nonzero exit status and a clear error on stderr. Identical inputs produce the same report, with sorted fields, stable warnings, and no timestamps. The output path must differ from every input path.

## Golden example

| Fields | Usage | Sensitivity |
| --- | --- | --- |
| `account_id` | `USED` | `INTERNAL` |
| `account_type`, `currency` | `USED` | `GENERAL` |
| `available_balance`, `recent_transactions` | `USED` | `FINANCIAL` |
| `account_number`, `aadhaar_number` | `CANDIDATE_UNUSED` | `HIGH` |
| `customer_phone`, `customer_address` | `CANDIDATE_UNUSED` | `MEDIUM` |
| `internal_risk_flag` | `UNKNOWN` | `INTERNAL` |

Expected counts: **5 USED / 4 CANDIDATE_UNUSED / 1 UNKNOWN**. The consumer directly reads the five used fields. A documented variable-key access is bounded to `internal_risk_flag`, producing uncertainty for that field without accessing the four candidates.

Each report includes field names, usage, independent sensitivity, evidence/reasons, analyzer and sensitivity warnings, usage counts, and the schema/payload validation result.

## Analyzer limits

This is a conservative demo of top-level field analysis in one supplied Python source file. Direct string-key indexing and ordinary `.get()` reads on the configured root variable are supported. A variable key is bounded only for one earlier unconditional string assignment in the same scope; it still produces `UNKNOWN`. Aliases are not followed. Unbounded keys, broad forwarding/iteration/reflection, or unsupported access can make the entire scope uncertain. An explicit syntax allowlist makes unreviewed constructs and new Python AST node kinds uncertain rather than silently treating fields as unused. Supported direct usage evidence remains `USED` alongside other ambiguous access when the payload's identity is intact; rebinding or deleting the root variable makes all fields `UNKNOWN`.

The analyzer does not execute imports, resolve external functions, prove branch reachability, perform complete interprocedural analysis, or track nested schema fields. `CANDIDATE_UNUSED` means no supported access was found in the scanned scope; it is not proof that a field is safe to remove. `UNKNOWN` fields must be preserved. Policy review requires explicit approval before any candidate receives a planned removal action.

## Policy review and SQLite revisions (Phase 2)

Generate the analysis, create a review-required policy, inspect it, then review:

```powershell
python -m veilmint --output analysis-report.json
python -m veilmint policy --db data/synthetic-demo.sqlite3 create --analysis analysis-report.json
python -m veilmint policy --db data/synthetic-demo.sqlite3 show
python -m veilmint policy --db data/synthetic-demo.sqlite3 review
python -m veilmint policy --db data/synthetic-demo.sqlite3 history
```

The interactive review shows evidence and independent API/log actions. Select
only numbered review candidates, supply a reviewer label and optional notes,
inspect the summary, and type the requested confirmation to save. USED and
UNKNOWN fields cannot be approved for removal. Empty approval keeps all fields.
Approval labels are local demo metadata, with no identity verification.

Each revision binds the complete analysis digest, log mapping and optional known
field inventory. Analysis includes source-input fingerprints. Changed inputs
create a new review-required revision; unchanged latest inputs load without
changing approval. Use `create --new-revision` for an explicit fresh review of
identical inputs. Only the latest revision can be reviewed, once; earlier history
is preserved. SQLite initialization is automatic. Its schema uses a simple
version marker, separate revision/decision records and a stored compiled JSON
snapshot; reads verify the snapshot against its persisted inputs and decision.

Default log actions are GENERAL→ALLOW, INTERNAL/MEDIUM→MASK,
FINANCIAL/HIGH→DROP. `create --log-mapping mapping.json` accepts overrides by
sensitivity label, independently of usage. A JSON list passed with
`--known-fields fields.json` includes newly discovered fields as UNKNOWN/KEEP
with warnings. Fields missing valid sensitivity also remain ineligible for
removal. Policy output is deterministically ordered; timestamps are generated
only when a revision or review is stored, never during compilation.

Before approval the golden policy plans **10 KEEP / 0 REMOVE**. Approving all
four candidates plans **6 KEEP / 4 REMOVE (10 → 6)**, preserving the five USED
fields and the UNKNOWN risk flag. Compiling a policy alone changes no response
or log event.

## Runtime demonstration (Phase 3)

Start the backend from the same environment used for tests:

```powershell
python -m uvicorn veilmint.server:create_app --factory --host 127.0.0.1 --port 8000
```

`VEILMINT_DB` selects the local SQLite file (default
`data/synthetic-demo.sqlite3`). `VEILMINT_MODE` defaults to `OBSERVE`; valid modes
are `OBSERVE`, `WARN`, `ENFORCE`. OBSERVE and WARN preserve the response;
ENFORCE removes only explicitly approved candidate paths. Every operation loads
the latest stored policy and compares it to the current synthetic analysis.
Missing, unapproved, corrupt or stale policies preserve API data with warnings.

- `GET /health`: local process health, no policy required.
- `GET /api/demo/account?mode=ENFORCE`: labelled synthetic original/output
  inspector and a separate trace. With the approved golden policy this is 10→6.
- `GET /api/demo/account/response`: the response payload only, using the
  configured mode. Policy/mode metadata lives in the audit table.
- `POST /api/demo/log`: generates a synthetic event server-side, protects it,
  writes it to SQLite, then reads the persisted protected record for inspection.
  Caller-provided event bodies or policies are not used by these demo endpoints.

Policy paths are explicit segment tuples, with `*` for array items. Root array
items share the root object policy. A top-level removal never removes a
same-named field in an unrelated nested object. The current analyzer emits
top-level paths; nested policies require explicit paths in analyzed input.

Log protection runs before any sink insert. ALLOW retains scalar values, MASK
uses `[REDACTED]`, DROP omits the field, and HMAC_PSEUDONYM returns a keyed SHA-256
pseudonym of canonical JSON. Unknown log fields are masked; invalid policies
mask all values. ALLOW containers still protect unknown descendants recursively.
HMAC requires an externally supplied key: set `VEILMINT_HMAC_KEY` to at least
32 bytes and configure a sensitivity mapping to `HMAC_PSEUDONYM`. No key is
needed for the default golden mapping. A missing required key or a sanitation
failure rejects the event; raw data is never used as a persistence fallback.

The golden sanitized log retains `account_type: "DEMO_CHECKING"`, masks
`account_id`, `customer_phone`, `internal_risk_flag` and the unmapped demo note,
and drops `available_balance`, `account_number` and `aadhaar_number`. A USED
financial field stays in the API while being dropped from logs.

SQLite tables `veilmint_protected_logs` and `veilmint_runtime_audit` keep
protected events and value-free audit metadata separately. API audit write
failure retains the original response with a warning. No raw event or payload
is written to application debug output.

## Workbench and canary (Phase 4)

Keep the backend running on port 8000. In a second PowerShell terminal:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the printed Vite URL. The development proxy sends `/api` requests to the
local backend. Five views share real persisted state:

1. **Evidence** shows the current analysis, counts, evidence and uncertainty.
2. **Policy review** creates a pending revision, selects eligible candidates,
   previews the shape change and saves explicit reviewer approval. History is
   loaded from SQLite; refresh does not discard or silently change decisions.
3. **API inspector** runs the actual response component in OBSERVE/WARN/ENFORCE.
4. **Log inspector** protects a server-generated synthetic event and shows its
   actual SQLite readback alongside the synthetic original.
5. **Canary** generates a fresh unique synthetic run, invokes both protected
   components, reads the stored protected event and reports each PASS/FAIL check.

For the golden story, create a revision, approve the four candidates, inspect
the real 10→6 response and protected log, then run a fresh canary. A stale or
unapproved revision cannot produce a successful canary. Results identify their
run and policy revision; no previous PASS is reused as a new result.

The canary is **synthetic, path-scoped verification**. It checks only the defined
API component and local SQLite log path under the selected policy. It does not
establish broad security, compliance, protection of arbitrary text logs, or
coverage of external services. USED financial markers may remain in the API;
the same markers must be protected from logs according to their log actions.

Backend routes and request contracts are in [docs/api.md](docs/api.md). Frontend
checks are `npm run typecheck`, `npm test`, and `npm run build` from `frontend/`.

## Demo reliability and deployment (Phases 5–6)

```powershell
python -m veilmint demo init --db data/synthetic-demo.sqlite3 --approve-synthetic
python -m veilmint demo check --db data/synthetic-demo.sqlite3
```

Initialization is idempotent, records a clearly synthetic approval label and
preserves existing decisions and unrelated records. Omit `--approve-synthetic`
to review in the workbench instead. Each check runs fresh canaries against the
current policy and persisted logs. For a clean scenario choose a new named demo
database; no reset command deletes user data. Native server restart persistence
and container restart persistence were verified.

The root Dockerfile, frontend Dockerfile, Nginx proxy, Compose volume and health
checks provide a local-only deployment path. Follow [deployment commands](docs/deployment.md).
Dependencies are pinned in `requirements-lock.txt` and `frontend/package-lock.json`.

## Scope and limits

Phases 1–6 and 8 provide analysis, explicit review, policy compilation, API runtime
minimisation, protected local log storage, a connected workbench and scoped
canary verification, plus an authenticated customer sandbox and real traffic
integration. Phase 7 is postponed. This project uses only synthetic data and has
no production authentication/RBAC, external banking integrations or compliance certification.

Source lives in `src/veilmint/analyzer/` and `src/veilmint/policy/`; synthetic fixtures and the independent sensitivity mapping are in `src/veilmint/fixtures/`; tests are in `tests/`. Actual phase gates and limitations are recorded in [docs/verification.md](docs/verification.md).

## Accounts Explorer and unified policy review

The operator console now has one Policy review page with a bank/example
selector, a masked read-only Accounts Explorer and a Protection inspector for
real customer-request evidence. Original fixture tools are under Demo examples.
See [operator inspection instructions](docs/operator-inspection.md) for profile
demo setup, header/log decisions, temporary reveal and validation commands.

## Live bank response inspection

Click a request in Live bank traffic to open a response dialog showing its
complete formatted JSON body. The global Standard / VEILMINT toggle selects the original captured body
or a server-masked projection of that same request. The customer bank website and
its response contract remain unchanged. No standalone comparison page is used.

See [live response inspection](docs/traffic-responses.md) for capture availability,
privacy rules and verification commands.

## Phase 9: consumer-specific Data Flow Explorer

Open http://localhost:8080 and choose **Data Flow Explorer**. Select a sandbox
account and explicitly attach its fictional DEMO profile (no funds are added).
Choose Overview, Payments, Notifications or Risk. In **Consumer Policy Studio**,
prepare a revision, inspect AST evidence, select eligible removals, enter your
reviewer label and confirm. Invoke the consumer in ENFORCE to see actual approved
minimization. Repeat review independently for each consumer, then use **Compare
all consumers**. Pending/stale policies correctly retain the baseline.

The global Standard/VEILMINT toggle switches the two frozen sides of a consumer
trace. Live traffic still opens the exact served-response dialog; its display
masking is not claimed to be consumer-specific policy minimization. Existing
customer registration, CLI funding, beneficiaries and transfers are unchanged.
No real government identity information is collected. The four adapters run in
one backend process, not independently deployed microservices.

Run `docker compose up -d --build --wait` from the repository. Operator remains
localhost:8080; the existing opt-in LAN customer binding remains on 8081. On the
second laptop use the host's current IPv4 address and /bank/ on port 8081; never
expose the operator port. The existing phase8 runbook documents firewall/LAN setup.
Persistent volume and policies are preserved. Phase 9 adds only DEMO enrichment
and its independent schema marker; backups precede deployment.

## Cloud demo hosting

The frontend is hosted at [VEILMINT on Vercel](https://veilmint-buildx.vercel.app).
Backend activation and connection are separate; the hosted setup notice reports
whether a backend URL is configured. The Render blueprint uses **Free** compute
with no paid disk or database. Cloud demo records reset on sleep, restart or
redeploy. See [cloud deployment steps](docs/cloud-deployment.md).

Audit: [coverage](docs/audit/implementation-coverage.md),
[findings](docs/audit/critical-findings.md),
[consumer matrix](docs/architecture/consumer-field-matrix.md),
[verification and walkthrough](docs/verification/phase9-end-to-end.md).
