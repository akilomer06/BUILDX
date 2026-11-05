# VEILMINT — Phase 2 Master Prompt
## Policy Review, Approval, Compilation, and Versioning

You are continuing **VEILMINT — Evidence-Compiled Least-Data Firewall** from Phase 1.

## Critical Starting Rule

This is a sequential build. **Do not assume Phase 1 is complete or correct.**

Before implementing:
1. Inspect the repository and read its README, source, tests, and generated analysis report.
2. Run the existing Phase 1 tests and golden NEXUS BANK analysis.
3. Verify the expected result: **5 USED / 4 CANDIDATE_UNUSED / 1 UNKNOWN**.
4. If Phase 1 is missing, broken, or differs materially from the expected behavior, repair only the necessary foundation and report the issue. Do not silently build on a broken analyzer.
5. Preserve existing working code. Do not recreate the project or overwrite files blindly.

---

## 1. Phase 2 Objective

Turn Phase 1 analysis evidence into a **reviewable, explicit, versioned policy**.

Implement:
- policy data models and validation;
- a reviewer workflow for candidate field removals;
- policy compilation from analysis results + reviewer decisions;
- policy persistence and revision history;
- tests proving conservative behavior.

Phase 2 must not enforce policies on API traffic or logs yet. Runtime enforcement belongs to Phase 3.

---

## 2. Core Policy Rules

Keep **usage classification** and **sensitivity classification** independent.

### API response action
- `USED` → `KEEP` (cannot be removed through the candidate-removal workflow).
- `CANDIDATE_UNUSED` → default `KEEP`; may become `REMOVE` only after explicit reviewer approval for that policy revision.
- `UNKNOWN` → `KEEP`; removal must be disabled.
- Unmapped/new fields → `KEEP` and emit a warning.

### Telemetry/log action
Sensitivity determines the log action independently of API usage:
- `GENERAL` → `ALLOW`
- `INTERNAL` → `MASK`
- `MEDIUM` → `MASK`
- `FINANCIAL` → `DROP`
- `HIGH` → `DROP`

Use these defaults as the initial policy mapping, but keep them configurable and clearly documented. Do not use log actions to decide API field removal.

### Approval semantics
- Approval is **one-time per policy revision**, not per API request.
- A reviewer approves specific candidate field removals in the policy review.
- Store reviewer identity as a simple supplied label for the local demo; do not build authentication/RBAC.
- Store approval decision, selected fields, timestamp, policy revision, and reason/notes.
- If analysis is regenerated or policy inputs change, create a new revision that requires review before candidate removals are applied.
- No approval means all candidate fields remain `KEEP`.
- Unknown fields cannot be approved for removal in this phase.

---

## 3. Required Deliverables

### A. Policy models
Define validated models for:
- field policy: field name, usage, sensitivity, API action, log action, evidence;
- policy revision: revision ID/number, source analysis reference or digest, created timestamp, status;
- reviewer decision: reviewer label, approved candidate fields, decision timestamp, notes;
- compiled policy: revision, per-field actions, warnings, approval metadata.

Use the project's existing model conventions if Phase 1 already established them. Avoid unnecessary dependencies.

### B. Policy compiler
Compile a policy deterministically from:
1. Phase 1 analysis output;
2. configured sensitivity-to-log-action mapping;
3. reviewer decision (if present).

Compiler behavior:
- `USED` fields always compile to API `KEEP`.
- `CANDIDATE_UNUSED` fields compile to API `REMOVE` only if explicitly approved in the current revision; otherwise `KEEP`.
- `UNKNOWN` fields always compile to API `KEEP`, with removal disabled.
- Unknown/unmapped fields default to API `KEEP` and warning.
- Log actions are derived independently from sensitivity.
- Reject approval references to nonexistent fields, USED fields, or UNKNOWN fields.
- Reject approval decisions tied to a different analysis digest/revision.
- Stable ordering and deterministic output.

### C. Review interface
Build a **minimal reviewer interface** that fits the existing project structure:
- Show field name, usage, sensitivity, evidence, proposed API action, and log action.
- Clearly distinguish USED, CANDIDATE_UNUSED, and UNKNOWN.
- Allow selection only for `CANDIDATE_UNUSED` fields.
- Require a reviewer label and optional notes.
- Show the policy summary before saving.
- Explain that approving a removal affects a future runtime policy, not a live API yet.
- Avoid a full dashboard or elaborate design.

If Phase 1 has no frontend, create the smallest practical interface consistent with the repository: prefer a simple React/Vite page only if the project already has frontend scaffolding; otherwise implement a clean CLI review flow first and document how it works. Do not introduce a large frontend solely for this phase.

### D. Persistence and revisioning
Use SQLite for local persistence:
- store policy revisions;
- store reviewer decisions;
- store compiled policy JSON;
- preserve earlier revisions instead of overwriting them;
- identify revisions using a deterministic analysis digest plus revision number or equivalent stable scheme;
- ensure a changed analysis creates a new review-required revision;
- ensure unchanged analysis can be loaded without silently changing approval.

Keep database schema and migration/init logic simple and documented.

### E. Tests
Add tests for:
- default candidate behavior is `KEEP`;
- approved candidate fields become `REMOVE`;
- USED cannot be removed;
- UNKNOWN cannot be removed;
- nonexistent field approval is rejected;
- stale/mismatched approval is rejected;
- log action mapping is independent from usage;
- new/unmapped fields default to `KEEP` + warning;
- revision history is preserved;
- changed analysis requires a new approval;
- deterministic compiler output.

---

## 4. Golden NEXUS BANK Expected Policy

For the 10-field synthetic scenario:

| Field | Usage | Sensitivity | API action before approval | Log action |
|---|---|---|---|---|
| `account_id` | USED | INTERNAL | KEEP | MASK |
| `account_type` | USED | GENERAL | KEEP | ALLOW |
| `currency` | USED | GENERAL | KEEP | ALLOW |
| `available_balance` | USED | FINANCIAL | KEEP | DROP |
| `recent_transactions` | USED | FINANCIAL | KEEP | DROP |
| `account_number` | CANDIDATE_UNUSED | HIGH | KEEP | DROP |
| `customer_phone` | CANDIDATE_UNUSED | MEDIUM | KEEP | MASK |
| `customer_address` | CANDIDATE_UNUSED | MEDIUM | KEEP | MASK |
| `aadhaar_number` | CANDIDATE_UNUSED | HIGH | KEEP | DROP |
| `internal_risk_flag` | UNKNOWN | INTERNAL | KEEP | MASK |

After a reviewer explicitly approves all four candidate removals in one policy revision:
- those four fields compile to API `REMOVE`;
- the five USED fields remain `KEEP`;
- the UNKNOWN field remains `KEEP`;
- the policy records the reviewer decision and revision;
- the report shows **10 → 6 fields** as the planned API shape change.

This is a compiled policy only. No actual API response is changed in Phase 2.

---

## 5. Scope Exclusions — Do Not Build Yet

Do not implement:
- FastAPI request/response enforcement middleware;
- actual API field filtering at runtime;
- log sink filtering or masking;
- HMAC pseudonymisation;
- canary injection or verification;
- authentication, RBAC, or multi-user workflows;
- external integrations or real customer data;
- deployment infrastructure.

These belong to later phases.

---

## 6. Completion Gate

Phase 2 is complete only when:
- Phase 1 tests and golden analysis still pass;
- a reviewer can approve candidate removals through the chosen minimal interface;
- approval is tied to a specific analysis/policy revision;
- the compiler produces deterministic, validated policy output;
- all conservative rules are enforced;
- policy revisions and decisions persist in SQLite;
- tests cover approval, rejection, stale revisions, and independent log actions;
- documentation explains review, policy compilation, persistence, and limitations;
- no runtime enforcement is falsely claimed.

At completion, report:
1. what was added and how it connects to Phase 1;
2. commands to run tests and open/use the review flow;
3. the compiled NEXUS BANK policy before and after approval;
4. tests and known limitations;
5. confirmation that Phase 3 runtime enforcement has not been implemented.

**Stop after Phase 2. Do not begin Phase 3.**
