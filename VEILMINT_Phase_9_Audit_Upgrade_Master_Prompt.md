# VEILMINT — Phase 9 Master Prompt
## Comprehensive Implementation Audit, Real Consumer-Specific Data Minimization, Standard vs VEILMINT Comparison Repair, and Security Console Redesign

> **COPY THIS ENTIRE FILE INTO CODEX IN THE ROOT OF THE EXISTING PROJECT.**
>
> You are an autonomous senior engineer, application security architect, banking-domain engineer, QA engineer, and product designer working on the **existing** VEILMINT + NEXUS BANK repository. Your job is **not** to write an aspirational review, generate decorative mockups, or produce a list of suggestions and stop. **Inspect the real code, verify what exists, identify gaps, repair broken workflows, and implement the next highest-value improvements end-to-end.** The work must remain truthful, safe, tested, and compatible with existing features.
>
> **Do not include estimates of effort, hours, days, or deadlines in your plan or reports.**

---

# 0. Context: what the project is supposed to do

The hackathon problem is **preventing sensitive customer-data leakage in financial institutions**, especially when customer data is unnecessarily exposed through API responses, inter-service traffic, application error logs, and observability systems.

**VEILMINT — Evidence-Compiled Least-Data Firewall** comprises:

1. **Consumer-aware API minimization**: inspect producer response schemas and actual Python consumer code using conservative static AST analysis; classify usage as `USED`, `CANDIDATE_UNUSED`, or `UNKNOWN`, separately classify sensitivity; obtain explicit reviewer approval for removals; compile a validated versioned, consumer-scoped policy.
2. **Runtime response enforcement (Boundary Veilgate)**: apply approved policies to real outgoing API responses in modes `OBSERVE`, `WARN`, and `ENFORCE`. Required and unknown fields are conservatively retained; stale/invalid approval does not authorize deletion.
3. **Independent structured-log protection**: apply `ALLOW`, `MASK`, `DROP`, and keyed `HMAC_PSEUDONYM` policies before logs are stored. Log protection is separate from API response minimization.
4. **Canary verification and auditable decisions**: inject deliberately synthetic canaries through controlled paths and verify resulting protected responses and persisted logs, with honest PASS/FAIL claims bounded to tested paths.
5. **NEXUS BANK banking sandbox**: customer registration/login, persistent fictional customer records and accounts, balances/transactions, beneficiaries, atomic internal sandbox transfers, live API traffic from another laptop on LAN, and VEILMINT operator workbench.

Earlier reported progress includes Phases 1–6 with existing backend/frontend tests, policy revisions and SQLite persistence, API/log protection, React/TypeScript/Vite/Tailwind workbench, Docker/Nginx/Compose, and Phase 8 NEXUS BANK development. **Do not assume any of these are complete just because they were reported**. Independently verify the actual repository. Do not regress the prior golden scenario of **10 producer fields → 5 USED / 4 CANDIDATE_UNUSED / 1 UNKNOWN → 4 approved REMOVE / 6 KEEP**.

## Current pain points, which MUST be investigated and solved

- The VEILMINT **operator/backend dashboard is visually boring and feels like a fake analytics dashboard**. Create a credible, distinctive **security operations console** focused on real requests, field evidence, data flow, policy actions, and verification rather than meaningless charts/cards.
- The current response shown in the application is already reduced/masked and lacks enough fields to convincingly demonstrate per-consumer data minimization:

```json
{
  "account_id": "********9251",
  "display_name": "A***",
  "account_type": "SANDBOX_CURRENT",
  "currency": "INR",
  "status": "ACTIVE",
  "masked_account_reference": "•••• 23F4",
  "available_balance_minor": 0,
  "recent_transactions": [],
  "legacy_display_label": "NEXUS sandbox account"
}
```

- The **Standard vs VEILMINT toggle** does not reliably show the intended comparison. The database or its UI seems to contain only already-filtered data, so the supposedly unprotected side cannot display the full original producer representation.
- The project must demonstrate that **different downstream banking services receive different minimum field sets from the same rich upstream producer record**, and show that behavior using real application calls and honest evidence.
- The implementation must be systematically checked against **every implementation-plan phase**, including any additional features already built, so that no planned requirement is silently omitted.
- After the audit and must-fix work, **proactively identify and IMPLEMENT the most valuable remaining project improvements** supported by the existing architecture. Do not stop at a recommendation list unless blocked by a genuine unresolvable constraint.

### Important terminology correction

The JSON object above is a **JSON response body**, not an HTTP header. **Do not put sensitive banking data into HTTP headers** to make the demo richer. Expand the controlled **producer JSON body and canonical bank data model**, then minimize it at the appropriate authorized consumer boundary.

---

# 1. Operating rules and execution discipline

1. **First inspect, then modify.** Inventory all code, services, modules, tests, migrations, seeders, Compose/Nginx routes, policy/approval stores, frontend routes, auth, docs, and implementation-plan files.
2. **Establish a baseline**: run the existing backend test suite, frontend tests, typecheck, build, Docker/Compose health checks and relevant end-to-end tests where environment permits. Record real commands, exit status, pass/fail count, and blockers. Do not manufacture results.
3. **Read every accessible implementation plan**: master/final plan, Phase 1 fresh-start prompt, Phases 2–8 and subsequent amendments, README, docs/verification, architecture notes, and actual acceptance criteria. If a plan is absent, mark it `NOT FOUND` and reconstruct only from verifiable repo documents. Do not pretend a missing plan was inspected.
4. **Create a coverage audit matrix** mapping every major promised requirement to actual files, entry points, tests, and functional result: `VERIFIED`, `PARTIAL`, `BROKEN`, `NOT IMPLEMENTED`, `NOT TESTED`, or `SUPERSEDED WITH EXPLANATION`. Extra useful implemented functionality is welcome; do not remove it merely because a past plan did not mention it.
5. **Preserve existing functionality and data**. Make a backup strategy for existing local SQLite data, use additive safe migrations, do not silently wipe accounts or policy history, and avoid destructive seed resets.
6. **Fix root causes, not symptoms**. Specifically trace response DTO construction, database persistence, policy enforcement, event serialization, frontend fetching, and rendering before touching the toggle or field views.
7. **Do not duplicate VEILMINT**: reuse the existing AST analyzer, policy compiler, human-review revision binding, runtime Veilgate and log sanitizer. Improve them in place behind tests rather than creating mock versions or a parallel ad hoc filter.
8. **Do not fabricate proof**: no fake traffic, random security scores, hardcoded counters, misleading PASS badges, placeholder policy decisions, or static response objects presented as live.
9. **No real-bank operations or real people's sensitive data**. The bank remains an explicitly labeled fictional sandbox. No real card networks, UPI/NEFT, KYC integrations, government-identity capture, actual money transfers, or external banking integrations.
10. **Autonomously proceed**: make sensible repo-compatible implementation choices; prioritize and implement. Do not stop to ask for generic design preferences or permission for routine edits. If a change is genuinely destructive or requires unavailable credentials/external systems, implement the safe alternative and document the exact limitation.
11. **Preserve correct security boundaries**: do not weaken authentication, authorization, masking, log sanitization, bank ledger integrity, human approvals, or fail-safe semantics merely to make the demo easier.
12. Work in reviewable, logically separated changes with tests and docs updated alongside code. No effort/time estimates in output.

---

# 2. Stage A — Full-system audit and test baseline

## Audit the entire application

Inspect and verify, at minimum:

### Analysis and classification
- JSON Schema parsing/validation, path enumeration including nested and array paths.
- Non-executing Python AST field access and its conservative limits.
- `USED`, `CANDIDATE_UNUSED`, `UNKNOWN` semantics and evidence traceability.
- Independent sensitivity classification and rationale.
- Dynamic, computed, aliased, delegated or indirect accesses: must not be mislabeled as confidently unused.
- Producer/consumer contract identity, versioning, digest/staleness behavior.

### Approval and policy compilation
- Reviewer identity, notes, approval semantics, required revisions and input digests.
- Deterministic compile and correct `KEEP`/`REMOVE` actions.
- Safety invariant: `USED` and `UNKNOWN` not auto-removed; unapproved candidates not removed.
- Per-destination policy matching, correct schema scope, stale approval rejection.
- Policy storage, history, integrity checks and restart persistence.

### Runtime Veilgate and logs
- Real FastAPI response enforcement path for `OBSERVE`, `WARN`, `ENFORCE`.
- Correct placement between business logic and network serialization.
- Nested JSON/array support, unknown fields, policy mismatch handling, failure behavior.
- Structured log `ALLOW`/`MASK`/`DROP`/keyed `HMAC_PSEUDONYM` **before** persistence.
- Raw PII/secrets never written by error handlers, request middleware, debugging or observability fallback.
- Actual correlation ID continuity and protection decision audit records.
- Canary verification against protected real paths and stored log records.

### NEXUS BANK
- Registration, login/logout, password hashing, token/session handling and authorization.
- Customer-owned accounts, beneficiaries, source/destination ownership checks.
- Balance/ledger correctness, integer minor units or exact decimals.
- Atomic double-entry transfers, rollback on failure, sufficient funds, currency, idempotency and concurrency protections.
- Persistent customer-generated activity versus optional seeded fictional demonstration data.
- Bank domain schema and migration safety; survival after container restart.
- Two-laptop LAN entrypoint, API base URL, ports, CORS/proxy routing, operator/admin separation.

### User experience and infrastructure
- Every existing frontend route/view, API integration, loading/error/empty states, responsiveness and accessibility.
- Standard vs VEILMINT toggle and exact backend effect.
- Policy approval from UI/CLI and end-to-end runtime linkage.
- Live-traffic updates from actual persisted events or streamed events.
- Docker Compose, Nginx, health checks, persistent volumes and configuration.
- Existing tests vs actual features; find assertions that only test mocks rather than behavior.
- Docs, setup, operator workflow, security limitations and reproducible demo sequence.

## Audit deliverables — write them into the repo

- `docs/audit/implementation-coverage.md`: requirement → source plan → source file(s) → test(s) → state → evidence → remediation; include all available phases and extras.
- `docs/audit/baseline-verification.md`: actual commands and baseline results, identified regressions and environment limitations.
- `docs/audit/architecture-trace.md`: real source-of-truth data flow and boundary locations, including what the database stores vs what the customer/consumer gets vs what logs store.
- `docs/audit/critical-findings.md`: prioritized findings by severity/impact with reproduction, root cause and fix status. Do not report unverified assumptions as facts.

**Continue from audit to implementation in the same task.** Do not stop after writing audit files.

---

# 3. Stage B — Diagnose and fix the incomplete producer data / database path

## Expected model

We need **three clearly separated data representations**:

1. **Canonical producer/business data**: the bank's authorized, reasonably complete data model required for its legitimate operations. Stored only in appropriately protected bank-domain tables, not as a public dump of arbitrary PII.
2. **Consumer-specific outbound API body**: a DTO constructed by the producer, routed through approved VEILMINT policy enforcement for the identified downstream consumer; returns only data allowed for that consumer.
3. **Protected event/log data**: sanitized operational metadata recorded after log protection; never the raw banking DTO or credentials.

These are not interchangeable. **API minimization must not erase canonical bank records.** Conversely, storing sensitive data just for a flashy side-by-side view is not justified.

## Determine why the current JSON is already masked and incomplete

Trace and document:
- database schema and saved records;
- initial registration/seed data source;
- ORM/model conversions;
- producer DTO and its serialization;
- any masking that occurs before VEILMINT;
- global FastAPI middleware that might modify responses;
- backend endpoints serving the Standard and VEILMINT screens;
- frontend state, transforms, cache keys, route params and rendering.

Identify whether missing fields are absent in the database, never populated, prematurely redacted, overwritten during persistence, removed by an incorrectly scoped policy, or hidden only by UI. Fix the **actual root cause**.

## Rich but controlled banking record

Construct a purposeful **expanded synthetic NEXUS BANK producer schema**, using coherent examples appropriate to an Indian banking sandbox, while keeping each field in its legitimate bank domain. Suggested candidates (adapt to actual data model, do not dump everything into one giant customer table):

**Customer/profile fields**
- `customer_id`, `display_name`, `legal_name` (fictional), `email` (example-only), `phone` (fictional), `address` (fictional), `city`, `state`, `postal_code`, `country`, `customer_segment`, `preferred_language`, `customer_status`.

**Account fields**
- `account_id`, `account_reference`, `account_number` (fictional sandbox identifier), `masked_account_reference`, `account_type`, `currency` (`INR`), `status`, `branch_code` (fictional), `opened_at`, `available_balance_minor`, `ledger_balance_minor`, `interest_plan` (if business-relevant).

**Transaction fields**
- `recent_transactions[]`: `transaction_id`, `posted_at`, `direction`, `amount_minor`, `currency`, `merchant_or_counterparty_label` (fictional), `reference`, `category`, `status`, `channel`.

**Internal-only / confidential fields**
- `internal_risk_flag` / `fraud_review_state`, `internal_case_reference`, `source_system`, `support_notes`, `kyc_demo_status` (explicitly fictional state), `last_reviewed_at`.

**Derived/compatibility fields**
- `legacy_display_label` or versioned aliases only where justified for demonstrating migration or unnecessary fields; never invent dozens of irrelevant fields just to inflate removal percentages.

Important controls:
- All **synthetic seed identities must be visibly fictional and cannot correspond to real people**. Use `.example` domains, fictional phone/account identifiers, fictional addresses, and clearly prefixed demo identity references; do not generate identifiers that could be mistaken for valid real Aadhaar/PAN/KYC records.
- **Do not collect real Aadhaar/PAN numbers or other government identifiers from users.** The old golden `aadhaar_number` field can remain an intentionally fake fixture for classifier testing; do not make it a mandatory customer onboarding field.
- Prefer genuine customer-entered **non-sensitive sandbox inputs** (display name, sandbox email, beneficiary label, transfer amount) plus realistic fictional seeded profiles for optional fields. A new user should never have to provide unneeded high-risk personal data to make the demo interesting.
- Use actual backend persistence; not hardcoded frontend fixtures. Explicitly mark seed records as `DEMO` and don't present seeded transactions as customer-generated events.
- Sensitive values should be generated only in isolated sandbox fixtures or in-memory producer simulation as necessary; preserve data minimization even while showcasing a rich source schema.
- Include both a clean new-account state and an opt-in populated demo-bank scenario with multiple internal fictional customers/accounts/transactions for meaningful demonstrations.

## Database/UI requirements

- Canonical bank records must persist and survive restart.
- Customer-facing views receive only authorized DTOs, not entire bank rows.
- Operator-facing demo can show a **schema-level field inventory** and optionally a masked/fictional producer-body preview, only with appropriate access checks.
- Existing policy approvals, audit records and canaries must remain intact.
- If the current DB cannot accommodate required business fields, use non-destructive migrations and backfill only appropriate `DEMO` data.
- Add tests proving the canonical record exists, the protected response is smaller per approved policy, the database isn't accidentally overwritten with that minimized response, and sanitized log records do not hold producer secrets.

---

# 4. Stage C — Demonstrate real per-microservice data minimization

**This is a must-have flagship feature.** A single shortened account JSON is insufficient. We must show **one rich producer record yielding different permitted JSON field sets for different downstream consumers**, based on each consumer's actual needs and its separately approved policy.

## Implement three or more distinct, meaningful consumers

Prefer at least **four** well-scoped consumers if this can be built reliably without needless infrastructure:

1. **Customer Banking App / Account Overview** — requires own account display details, account type, currency, current balance, permitted recent transaction summaries.
2. **Internal Payments/Transfer Service** — requires account identifiers needed for routing, status, currency, available balance or funds validation; does **not** require home address, support notes, marketing preferences, full customer profile, etc.
3. **Notification Service** — may require preferred channel/contact destination, language, and a minimal transaction event or masked account suffix; does **not** require entire ledger, full address, internal risk details, or whole account number.
4. **Fraud/Risk Service or Analytics Service** — choose one with a defensible need: fraud may legitimately require risk signals and transactions under restricted service identity; analytics should get aggregates/pseudonyms instead of direct identifiers. Be explicit about which consumer requires which sensitive fields and why.

If the repository already includes service boundaries, reuse them. If not, use real **Python consumer handlers/modules and authenticated internal service adapters or routes** that execute distinct business functions. They can be distinct logical services within the existing FastAPI process to avoid microservice theater. **Do not claim they are independently deployed microservices unless they truly are**. Separate services/containers are optional only when technically justified by the existing architecture.

## Produce a grounded consumer-field matrix

Create `docs/architecture/consumer-field-matrix.md`, with:

- exact producer field path;
- field type and sensitivity;
- actual usage evidence/source path for each consumer;
- consumer purpose;
- original `USED`, `CANDIDATE_UNUSED`, or `UNKNOWN` classification;
- approved `KEEP` / `REMOVE` action per consumer;
- policy revision and digest;
- example of expected final response shape;
- explanation for fields retained despite sensitivity.

**Do not invent `USED` evidence.** Our current static analyzer primarily supports Python AST. Use actual Python consumer code from real service handlers if possible; if React/TypeScript consumers are involved, either use a genuinely supported analysis approach or a truthful explicit consumer contract, not a fake Python AST file written merely to trick the analyzer. Scope every policy to a specific producer/consumer/endpoint/schema revision.

## Build the actual request flow

A supported test/demo should be able to run:

```text
                NEXUS BANK producer (rich record)
                            |
                authenticated service request
                            |
                    VEILMINT Veilgate
          +-----------------+------------------+
          |                 |                  |
     Account UI         Payments          Notifications       (+ Risk/Analytics)
     selected fields     selected fields    selected fields    scoped fields
          |                 |                  |                  |
       policy A           policy B          policy C           policy D
```

Each service must actually **request and consume** its returned fields through a backend code path, not just be a tab that draws manually edited JSON snippets. You may add safe explicit **operator-only scenario triggers** that invoke those real handlers and display their trace. Do not allow arbitrary unauthenticated clients to choose `service=admin` or `policy=none` and retrieve confidential data.

## Required comparison metrics (computed, not invented)

For the same producer schema/version:
- original number of JSON leaf field paths and emitted values;
- allowed/removed/unknown paths per consumer;
- actual original and minimized JSON byte sizes (clear serialization rules);
- per-consumer absolute and percentage field-count reduction;
- per-consumer byte-size reduction;
- reason/evidence for every removal;
- relevant schema/policy revision and enforcement mode.

Make clear that **field count reduction is not automatically equivalent to reduction in bytes, sensitive-data risk, or compliance**. Show both sizes and note limitations. For nested arrays, define counting semantics and avoid inflating counts through repeated list items; distinguish unique schema paths from occurrences where useful.

## Safety rules

- The authentic requesting service identity, not an arbitrary client-supplied query param or spoofable header, determines the policy context.
- The customer-facing account view must never receive the internal risk service's response simply by changing a toggle or endpoint parameter.
- Enforce the current human review, revision/digest, unknown-field retention, and safe-failure rules.
- A field required by an authorized consumer remains `USED`/`KEEP` even if it is sensitive; logging may still mask/drop it independently.
- Unknown/new fields trigger safe retention and review signals. Never auto-delete fields just because one scenario didn't access them.
- No raw full payloads in persistent logs or publicly accessible inspection endpoints.

---

# 5. Stage D — Repair Standard vs VEILMINT toggle completely

Current toggle behavior is unreliable. **Do not patch only the frontend label or swap two hardcoded objects.** Diagnose and rebuild the full comparison contract.

## Define the semantics correctly

- **Standard / Baseline**: represents the same producer response **before VEILMINT data minimization** for an explicitly scoped fictional sandbox scenario. It is an **operator-only comparison preview** or isolated non-production simulation—not a public endpoint permitting a customer to bypass protections.
- **VEILMINT / Protected**: shows the response produced by applying the actual selected consumer's **currently active approved policy** at the real boundary, using the same source record and schema version.
- When runtime mode is `OBSERVE` or `WARN`, do not misleadingly show removals as if ENFORCE occurred. Either show an explicit **policy simulation preview** clearly labeled simulated or execute a controlled isolated enforce evaluation that does not change live mode, with traceable semantics.
- Switching tabs must not mutate policy approvals, service identity, session authorization, bank balances, or persisted customer data.

## Fix the data source and UI state

- Both views must be derived from the **same trace/scenario ID**, canonical producer source/version, consumer identity, and schema revision.
- Use a stable comparison payload structure returned by a privileged backend API, e.g.:

```json
{
  "trace_id": "demo-trace-...",
  "source_version": "...",
  "consumer_id": "...",
  "policy_revision": "...",
  "actual_runtime_mode": "ENFORCE",
  "baseline": { "field_paths": [], "byte_count": 0, "preview": {} },
  "protected": { "field_paths": [], "byte_count": 0, "preview": {} },
  "decisions": [],
  "unknown_fields": [],
  "warnings": []
}
```

This shape is illustrative: adapt to existing backend contracts and **never persist or return raw sensitive values to an unauthorized viewer**. For operator demo, use fully fictional records or redacted previews, while allowing true field-path and count comparison.

- Ensure toggle selection changes what is rendered, not which fields exist in the database.
- Prevent stale React state, stale caches, race conditions, wrong request IDs, mismatched accounts/consumers or mode confusion.
- Selecting a new consumer refreshes both sides together and correctly updates counts/decisions.
- Empty arrays, nulls, nested objects, masked strings and removed fields must display accurately.
- Add a side-by-side **field-path diff** (`KEPT`, `REMOVED`, `MASKED_IN_LOGS`, `UNKNOWN`) and per-service reason/evidence.
- Distinguish `REMOVE` from `MASK`, and response minimization from log protection.
- No fake UI placeholder fields or disconnected demonstration samples.

## Required regression tests

- Toggle shows different results when approved removals exist.
- Toggle baseline/protected use the **same source record**.
- Counts equal parsed JSON output (under documented counting rules).
- Service switch changes the policy and result correctly.
- Toggles do not alter database records or security approvals.
- `OBSERVE`, `WARN`, and `ENFORCE` labels match actual behavior.
- Missing/invalid/stale policy and unknown fields do not produce false success claims.
- Unauthorized customers cannot access baseline confidential previews or invoke a bypass.
- Initial load, rapid toggle, reload, restart, failed fetch, and empty account all behave consistently.

---

# 6. Stage E — Redesign the VEILMINT operator console as a real security product

The present operator UI feels like a generic dashboard. **Retain the bank customer application**; focus this redesign on the **VEILMINT security/admin workbench**.

## Product direction

Design a premium, high-signal **Data Flow Security Operations Console**, not a banking marketing site or an artificial KPI dashboard. Every screen should answer a concrete security-engineering question. Favor clear investigative workflows, live events, traceability, scoped policies, actionable warnings, and evidence.

A credible style direction:
- sophisticated deep navy / graphite base with warm neutral surfaces and disciplined teal/cyan/amber accents;
- one clear sidebar with meaningful information architecture;
- strong but restrained typography and consistent spacing;
- excellent JSON/code visualization and readable table density;
- subtle purposeful animation (new events, field transitions) without gimmicks;
- responsive layouts, keyboard accessibility, focus states, contrast, accessible tooltips;
- thoughtful empty, disconnected, loading, denied, error and no-policy states;
- zero fake sparklines, arbitrary danger scores, meaningless progress rings or random numbers.

Adapt exact visual choices to the current frontend, design system and dependencies. Do not install a large UI framework without a compelling reason. Do not destroy functioning customer UI to achieve the redesign.

## Proposed information architecture — select/adapt based on real capability

### 6.1 Operations / Live Flow
- Real request stream with correlation ID, timestamp, route, consumer identity, response status, policy revision and result.
- Filters for consumer, endpoint, mode, time range, policy state and outcome.
- Reliable SSE or polling with clearly labeled connection health.
- Clicking an event opens the actual trace detail, not mock JSON.

### 6.2 Data Flow Explorer / Comparison Lab (**flagship screen**)
- Select producer record/scenario and actual downstream service.
- **Baseline → VEILMINT → Consumer** visualization with real data-path steps.
- Side-by-side schema tree/JSON body comparison and field-level diff.
- Explain why each field was kept, removed, unknown or independently masked in logs.
- Computed field/byte reduction metrics per consumer, not canned percentages.
- Clearly show `OBSERVE`, `WARN`, `ENFORCE`, simulation vs actual enforcement, and policy revision.
- Include a service-to-service comparison matrix for the same producer record.

### 6.3 Field Intelligence
- Evidence from JSON Schema and actual static consumer analysis.
- Sensitivity independent from usage; visible rationale, confidence/uncertainty if available.
- Nested field paths and analyzer limitations.
- New/unmapped fields and schema drift warnings.

### 6.4 Policy Studio
- Reviewer decisions, per-consumer scope, required approvals, revisions/digests.
- Clear compile/activate flow and stale approval errors.
- No UI affordance that implies a policy is active before it has been approved and compiled.

### 6.5 Log Protection
- Actual sanitized structured log events connected by correlation ID.
- `ALLOW`, `MASK`, `DROP`, keyed HMAC actions and safe field-path examples.
- Never persist or publicly render raw sensitive values merely for comparison.

### 6.6 Canary & Verification
- Actual verification runs, scoped pass/fail, reasons, relevant endpoints, policy and known limitations.
- No universal leak-free or legal compliance claims.

### 6.7 System Health / Integration
- Real service health, policy state, event connectivity and database readiness.
- Clearly distinguish connected/disconnected/not-configured from healthy.

You do **not** have to build every proposed screen if it duplicates a good existing view. First evaluate what exists, then consolidate and redesign the highest-value flows so the workbench feels like one coherent product.

## Non-negotiable UX walkthrough

An operator should be able to:
1. See real traffic generated by the customer laptop.
2. Select a particular request or explicit sandbox test scenario.
3. See the producer/consumer service, endpoint, correlation ID and policy revision.
4. Understand the producer field inventory and the actual consumer-protected field inventory.
5. Switch between two downstream consumers and **see different justified field minimization**.
6. Open a field and see the evidence for its decision, not just a colored badge.
7. Open corresponding sanitized logs and the latest relevant canary result.
8. Tell whether the record was a real customer-triggered event, an opt-in seeded demo record or a controlled sandbox verification scenario.

Ship production-quality responsive React/TypeScript components with real data integration. Do not submit only a Figma-like mockup.

---

# 7. Stage F — Dynamic evidence and contextual sensitivity: determine whether to add next

After required repairs, inspect whether there is room to implement a narrowly scoped evidence enhancement. **Do not build an unverified AI classifier just because the project mentions AI/NLP.** Prioritize correctness and proof of value.

Potential high-value upgrades, in recommended order unless the audit suggests otherwise:

1. **Consumer-field lineage and explanation**: for every policy decision, show exact static code path/schema evidence, destination contract, rationale, and reviewer action.
2. **Schema-drift detection**: detect newly introduced producer fields, invalidate stale approvals where needed and surface a review task.
3. **Runtime field-access observations in controlled Python consumer adapters**: instrument actual field reads with explicit consent/test configuration, record safe field paths not raw values, aggregate by consumer and execution scenario, distinguish `OBSERVED_USED` evidence from `NOT_OBSERVED`; **never infer unused from non-observation alone**.
4. **Contextual sensitivity rules**: combine schema metadata, field-path names and constrained format checks with endpoint/consumer purpose; keep explainable evidence and conservative uncertainty. Avoid collecting new raw identity data.
5. **Service identity and policy binding hardening**: authenticate distinct consumers and prove a consumer cannot impersonate another to get a larger payload.
6. **Trace replay / contract regression**: replay fictional scenarios against revisions and report which downstream consumers would break before approval activation.

Do not implement all of these indiscriminately. **Choose and deliver the highest-value improvements the repo can reliably support**, with tests and clear implementation boundaries.

---

# 8. Stage G — Autonomous backlog selection and implementation

Once the audit and must-fix stages are complete:

1. Create `docs/audit/next-improvements.md` ranking remaining opportunities by **security impact, demonstration value, correctness, architectural fit, regression risk and evidence of need**. No time estimates.
2. Identify the largest remaining credible gap between the original problem statement and our implementation.
3. **Implement the top practical improvements immediately** in the same run, not just propose them. Prefer changes that create a visibly stronger end-to-end demo and close real security gaps.
4. Every automatically selected improvement must include a definition of done, implementation, tests, docs and actual verification.
5. Do not chase novelty for novelty's sake. Avoid adding large infrastructure, untrained AI models, speculative auto-policy approval, real banking integrations, or insecure raw-data visibility.
6. Preserve a clear record of **implemented now / deferred with reason / blocked by environment**.

If choices conflict, prioritize in this order:

**Data safety and correct behavior → broken comparison and real per-service minimization → trustworthy operator UX → verification and robustness → optional innovation.**

---

# 9. Mandatory test scenarios and acceptance criteria

### A. Same producer, different consumers

Prepare a versioned fictional bank producer record with meaningfully more fields than any single consumer needs. Then verify:

- Account Overview gets its legitimate account, balance, and transaction-summary fields.
- Payments gets only its required routing, currency, balance/status fields.
- Notifications gets only permitted notification/contact/transaction-summary fields.
- Fraud/Risk or Analytics gets a genuinely different, documented need-to-know field set.
- Each consumer is associated with an actual policy identity/revision.
- At least one field is `KEEP` for one consumer and `REMOVE` for another **with valid approval**, proven by real backend invocation.
- A field that is `USED` for one consumer remains intact even if sensitive.
- No consumer can impersonate another or bypass its policy through a public parameter.
- Show comparable field count and byte size reductions measured from real serialized payloads.

### B. Standard vs VEILMINT comparison

- The baseline contains the complete fictional producer DTO for the selected controlled scenario (not prematurely minimized).
- The protected view reflects actual VEILMINT enforcement for the same record/destination/revision.
- The toggle or side-by-side diff accurately reveals field presence/removal and changes with consumer selection.
- The customer cannot access the raw baseline; the operator preview is fictional/redacted or appropriately secured.
- Database canonical records remain unchanged; sanitized security logs stay sanitized.

### C. Bank workflows

- Registration/login and authentication restrictions work.
- Persistent account data and explicit sandbox funding work.
- Beneficiary and sandbox transfers work, with atomic ledger entries, idempotency and balance reconciliation.
- Customer reads only own records.
- Real traffic from customer UI generates events in the operator console.
- Local Docker environment and persistent volumes survive restarts.

### D. Security and policy safety

- Existing Phase 1–6 golden 5/4/1 and approved 4 REMOVE/6 KEEP cases still work.
- Policies are bound to producer/consumer/endpoint/schema identities and correct revisions.
- Unapproved, `UNKNOWN`, new, missing-policy, stale-policy and invalid-policy cases retain the correct safe behavior.
- Structured bank logs are protected before persistence; raw secrets, credentials and full sensitive DTOs are not in log records.
- API response protection and log masking rules are independently demonstrable.
- Canary PASS/FAIL reflects actual protected paths and stored sanitized logs.

### E. User interface

- The security operator console is visually redesigned and meaningfully interactive.
- No invented telemetry or unused decorative charts.
- Live events, Policy Studio, evidence, log results and per-service comparison are connected to actual backend data.
- Responsive layout, accessibility, error and empty states are tested.
- Browser-based real workflow is manually inspected if browser tooling is available. If not, say visual QA is unverified and supply reproducible manual steps and screenshots only if actually produced.

### F. Verification commands and quality

Run all existing + new tests and, where available:
- Python unit and integration suites;
- database migration/restart/regression tests;
- typecheck, frontend unit tests and production build;
- end-to-end browser tests for Standard/VEILMINT toggling and consumer switching;
- Docker Compose build/start/health and API smoke tests;
- trace-level tests ensuring requests, decisions and sanitized logs share correlation IDs;
- LAN/two-laptop test if physical devices are genuinely available; otherwise explicitly mark `NOT VERIFIED`.

Do not claim complete verification if Docker, browser automation, two laptops or other tools are unavailable. Report exactly what was run and what remains manual.

---

# 10. Evidence-first demonstration to implement

The finished application should support the following **real, repeatable, honest** demonstration, preferably via a clearly marked operator demo/sandbox mode:

1. Start NEXUS BANK + VEILMINT, initialize optional fictional Indian sandbox accounts, and access the bank customer UI.
2. On a separate browser/device, log in or register a fictional customer, view account details and initiate a valid internal transfer; generate real HTTP requests.
3. In the VEILMINT console, select a request's correlation ID and inspect the real trace.
4. Open **Comparison Lab** and select the same producer account record.
5. Select **Payments**: show only payments-required fields under its compiled policy.
6. Select **Notifications**: show a different minimal set of fields under a distinct policy.
7. Select **Account Overview** or **Risk/Analytics**: show another legitimate set and explain why certain sensitive fields are retained or removed.
8. Open **Standard/Baseline** vs **VEILMINT** and show truthful original/processed field-path comparisons, raw/processed JSON sizes and the approved decision trail. If values are masked in the operator preview, say so explicitly.
9. Show that the bank database retains canonical needed data, while the downstream consumer gets only its allowed representation and stored logs contain only sanitized metadata.
10. Show the policy review evidence and a real canary verification result.

The demo must not depend on editing a JSON fixture while pretending a customer action occurred. Explicit fixtures remain valid for classifier unit tests and controlled regression cases; label them accurately.

---

# 11. Deliverables

**Implement code and produce these artifacts in the repository** (adapt naming if equivalent documents already exist):

1. `docs/audit/implementation-coverage.md` — every available implementation plan checked against actual code/tests, noting extra features and missing pieces.
2. `docs/audit/baseline-verification.md` — verified pre-change state and real commands/results.
3. `docs/audit/critical-findings.md` — issues, reproducible symptoms, root causes and actual fixes.
4. `docs/audit/architecture-trace.md` — true banking data, API minimization, logging and frontend data paths.
5. `docs/architecture/consumer-field-matrix.md` — exact per-consumer fields, evidence and policy decisions.
6. `docs/audit/next-improvements.md` — ranked autonomous improvements, what was actually implemented and what was deferred.
7. `docs/verification/phase9-end-to-end.md` — full test results, consumer comparisons, toggle behavior, protected log evidence, UI checks, Docker/LAN status, remaining limitations.
8. Updated README/runbook with startup, migration, fictional data seeding, account testing, operator access, comparison workflow, and real two-device setup.
9. Updated backend code, frontend workbench, DB migrations, tests, and sample `.env.example` configurations.

The final response should include:
- a compact **before/after technical summary**;
- **exact verification commands and results** (not just “all tests pass”);
- a **consumer-specific field-count/byte-size results table** from actual execution;
- a clear **Standard vs VEILMINT toggle root cause and fix**;
- a **UI redesign summary** tied to actual screens and real data;
- a **phase-by-phase completion matrix summary** with explicit missing items;
- **autonomously selected upgrades implemented**;
- known limitations, residual risks and next opportunities;
- truthful statement of whether physical two-laptop testing and browser visual QA occurred.

---

# 12. Final engineering acceptance rules

- **Never confuse a JSON body with HTTP headers.**
- **Never claim the database should contain every possible sensitive field**: collect/store only what banking functions legitimately need; keep fictional demo-only producer data separate and clearly marked.
- **Never make Standard mode a production leak/bypass route.** Baseline access is an operator-controlled fictional/privileged comparison artifact, not a public unfiltered API.
- **Never persist full raw sensitive responses to prove they were removed.** Persist only safe decision metadata; compare controlled fictional payloads and field paths.
- **Never turn `CANDIDATE_UNUSED` into automatic deletion.** Keep human approval, provenance and revision binding.
- **Never reduce response fields in a way that breaks a consumer's required contract.**
- **Never call a service “AI-powered,” a workflow “production-ready,” or a policy “compliant” without technical substantiation.**
- **Never treat in-process consumers as independently deployed microservices**; label the implementation accurately.
- **Never turn planned features or tests into claimed accomplishments.**

**Execute the audit, fix all critical/required defects, build the real per-consumer minimization demonstration, repair the comparison toggle, redesign the operator workbench, and independently implement the most valuable remaining improvements. Do not stop at a report or at a suggestion list. Stop only after you have implemented, tested, documented, and honestly reported what you could verify.**
