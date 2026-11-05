# VEILMINT — Phase 4 Master Prompt
## Frontend Workbench + End-to-End Canary Verification

You are continuing **VEILMINT — Evidence-Compiled Least-Data Firewall** from Phases 1–3.

## Critical Starting Rule

Do not assume earlier phases are complete.

Before implementing:
1. Inspect the repository and read the existing documentation.
2. Run all Phase 1–3 tests.
3. Confirm the analysis engine, approved policy workflow, API enforcement, and pre-persistence log sanitizer work.
4. Verify the golden NEXUS BANK policy and runtime behavior.
5. Repair only necessary foundations if something is missing or broken. Preserve working code; do not rewrite blindly.

---

## 1. Phase 4 Objective

Deliver the **usable VEILMINT workbench** and a **repeatable end-to-end verification flow**.

The frontend must connect to real backend capabilities. Do not create mock-only screens, fake metrics, or buttons that do nothing.

This phase includes:
- a compact React/TypeScript workbench;
- field evidence and policy review;
- API before/after inspection;
- structured log before/after inspection;
- synthetic canary verification against actual runtime paths;
- clear pass/fail evidence.

Keep the experience demo-focused and coherent, not a generic analytics dashboard.

---

## 2. Frontend Stack and Design Direction

Use the existing frontend if one exists. Otherwise establish:
- React + TypeScript + Vite;
- Tailwind CSS;
- shadcn/ui where useful;
- Motion only for purposeful, restrained transitions.

### Visual direction
Premium dark API-forensics workbench:
- Canvas: `#0C1017`
- Panel: `#141B25`
- Raised: `#1C2733`
- Border: `#303C49`
- USED: mint `#55C7A5`
- CANDIDATE_UNUSED: amber `#E9AE58`
- UNKNOWN: slate `#9AA8B8`
- Geist/Inter typography; JetBrains Mono for field names, JSON, traces.

Design requirements:
- clear hierarchy and readable density;
- status labels and evidence, not decorative charts;
- responsive enough for a laptop demo;
- keyboard-accessible controls and visible focus states;
- respect reduced-motion preferences;
- no neon/glow effects, fake activity, or AI-generated dashboard clutter;
- no React Flow unless already present and genuinely needed.

---

## 3. Required Workbench Views

Build the smallest coherent navigation or tab structure for these views.

### A. Field Evidence Map
Show all fields from the latest analysis:
- field name;
- usage classification;
- sensitivity;
- evidence/reason;
- warnings or uncertainty.

Use the agreed visual distinction:
- USED = mint;
- CANDIDATE_UNUSED = amber;
- UNKNOWN = slate.

Do not imply CANDIDATE_UNUSED is proven unnecessary. Label it as a review candidate.

### B. Policy Review
Connect to the real Phase 2 review/compiler/persistence flow:
- show current policy revision and review status;
- allow selection only for CANDIDATE_UNUSED fields;
- show proposed API action and independent log action;
- require reviewer label;
- allow optional notes;
- show a clear approval summary;
- save and display the resulting compiled policy;
- display revision/history where supported.

Approval must be one-time per revision, not per API request. USED and UNKNOWN fields must not be selectable for removal.

### C. API Minimisation Inspector
Connect to the real Phase 3 runtime:
- show synthetic original NEXUS BANK response;
- show actual output under OBSERVE/WARN/ENFORCE;
- display active policy revision and mode;
- show removed fields and retained UNKNOWN field;
- explain fail-safe behavior if policy is unavailable or stale.

Do not hard-code the expected six-field output as if it came from the backend.

### D. Structured Log Inspector
Connect to the actual log sanitizer and SQLite sink:
- show synthetic event before protection;
- show sanitized event after protection;
- show the persisted sanitized record;
- show actions applied (`ALLOW`, `MASK`, `DROP`, `HMAC_PSEUDONYM`);
- make it visually obvious that raw sensitive values are not stored.

Never expose real secrets or raw production data.

### E. Canary Verification
Implement a synthetic canary workflow that tests the actual protected paths.

Canary design:
- generate unique synthetic marker values for selected HIGH/FINANCIAL fields;
- send them through the API response enforcement path;
- send them through the structured log protection path;
- inspect the actual returned response and persisted log record;
- assert that approved API-removal fields are absent;
- assert that configured DROP/MASK log actions protect the marker;
- assert that the UNKNOWN field remains in API output;
- assert that the raw canary marker is absent from protected storage/output where required;
- return explicit PASS/FAIL with test details and policy revision.

Do not claim broad system security from this test. Label it **synthetic, path-scoped verification**. A canary passes only if the actual backend result is checked—not if a frontend mock says so.

---

## 4. Backend/API Integration

- Add only the endpoints needed by the workbench and canary flow.
- Keep endpoint contracts documented and typed where practical.
- Reuse existing analysis, policy, runtime, and log components; do not duplicate their logic in route handlers.
- Handle loading, empty, success, and error states.
- Never return secrets, HMAC keys, or raw persisted sensitive values.
- Ensure frontend errors do not display sensitive payloads or stack traces.
- Use a simple local development configuration and documented startup commands.

---

## 5. Golden NEXUS BANK Demonstration

The demo must use the existing synthetic 10-field scenario.

Expected visible story:
1. **Evidence:** 5 USED, 4 CANDIDATE_UNUSED, 1 UNKNOWN.
2. **Review:** reviewer approves the four candidate removals.
3. **Compiled policy:** 4 API REMOVE, 6 API KEEP; UNKNOWN remains KEEP.
4. **API runtime:** approved policy transforms 10 fields into 6.
5. **Log runtime:** sensitive values are MASKed or DROPPED before persistence according to the mapping.
6. **Canary:** actual API output and SQLite log record are inspected and a scoped PASS/FAIL result is displayed.

The UI must show real results returned by backend components. If any step fails, display the failure honestly.

---

## 6. Tests and Quality Checks

Add or update tests for:
- frontend/backend API contract integration;
- policy review controls and invalid selections;
- API inspector showing actual backend output;
- log inspector showing sanitized persisted data;
- canary success and failure cases;
- UNKNOWN retention;
- policy revision mismatch;
- no raw canary markers in protected log storage;
- loading/error states where practical.

Run all Phase 1–3 tests and relevant frontend checks:
- type checking;
- linting if configured;
- production build.

---

## 7. Scope Exclusions

Do not implement:
- production authentication or RBAC;
- real customer integrations;
- cloud deployment or multi-tenant hosting;
- external log platforms;
- claims of complete compliance/security certification;
- broad automated security testing beyond the defined synthetic paths.

Keep the MVP local, synthetic, reproducible, and honest.

---

## 8. Completion Gate

Phase 4 is complete only when:
- the workbench is connected to real backend endpoints;
- field evidence and policy review work end-to-end;
- API and log inspectors display actual runtime/storage results;
- canary verification checks actual protected paths and returns evidence;
- all prior tests pass;
- frontend typecheck/lint/build checks pass as configured;
- the complete NEXUS BANK demo can be run from documented commands;
- errors and failures are shown honestly;
- documentation explains startup, workflow, canary scope, and limitations.

At completion, report:
1. views and backend endpoints implemented;
2. exact commands to start the application and run checks;
3. the demo sequence from analysis to canary;
4. test/build results;
5. known limitations and what the canary does not prove.

**Stop after Phase 4. Do not begin deployment or presentation work unless requested.**
