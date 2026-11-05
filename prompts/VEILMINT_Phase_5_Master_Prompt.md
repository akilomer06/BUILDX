# VEILMINT — Phase 5 Master Prompt
## Integration Hardening, Reliability, and Security Checks

You are continuing VEILMINT after Phases 1–4. This phase is for hardening the existing MVP—not adding new product features.

## Starting Rule
Inspect the actual repository and run all existing tests/build checks first. Do not assume previous phases were implemented correctly. Preserve working code, identify failures, and repair them transparently. Do not fabricate test results.

## Objective
Make the complete analysis → review → compile → API enforcement → log protection → canary workflow reliable, safe, and reproducible.

## Work Items

### 1. End-to-end integration
- Verify the complete NEXUS BANK workflow from a clean local setup.
- Check that frontend actions call real backend routes and persisted state is reflected after refresh.
- Confirm policy revision and approval metadata remain consistent across views and runtime.
- Remove duplicate business logic between UI, routes, and core modules.
- Fix broken states, inconsistent contracts, and misleading UI labels.

### 2. Fail-safe behavior
Test and repair behavior when:
- policy is missing, malformed, unapproved, or stale;
- analysis fails or consumer syntax is unsupported;
- schema changes or a new field appears;
- SQLite is unavailable or a write fails;
- API enforcement or log sanitization raises an exception.

Safe defaults:
- API: retain data rather than remove fields if policy validity cannot be established.
- Logs: never persist the raw event after sanitizer failure; reject or safely quarantine it without exposing values.
- Unknown fields: retain in API output with warning; mask in logs by default.
- Never silently bypass protection.

### 3. Security and privacy checks
- Search code for accidental logging of request/response bodies, raw structured events, secrets, HMAC keys, or exception payloads.
- Verify scanned Python consumer code is never executed.
- Verify HMAC keys are configuration/environment supplied and not committed.
- Verify synthetic fixtures contain no real personal/financial data.
- Ensure UI/API error messages do not reveal raw sensitive values or stack traces.
- Add tests for the findings; do not merely write a checklist.

### 4. Data and policy integrity
- Verify approval is tied to the correct analysis digest and policy revision.
- Ensure changed analysis cannot inherit stale candidate approvals.
- Verify policy history is append-preserving.
- Ensure corrupted policy data fails closed for minimisation.
- Confirm policy actions are deterministic and field-path aware.

### 5. Demo reliability
- Add one documented command or concise command sequence to reset/load synthetic demo data.
- Make repeated demo runs deterministic and safe.
- Avoid deleting user data; reset only explicitly identified synthetic demo records.
- Provide a pre-demo health/check command if practical.
- Ensure canary verification produces fresh results rather than displaying stale PASS status.

### 6. Automated checks
Run and document:
- all backend tests;
- frontend typecheck/lint/build, if configured;
- integration tests;
- dependency/configuration checks available in the repository.

Fix critical failures. Report noncritical failures and limitations honestly.

## Exclusions
Do not add features, production authentication, multi-tenancy, external integrations, or a new architecture. Do not claim certification, complete security, or exhaustive leak prevention.

## Completion Gate
Phase 5 is complete when:
- the full golden workflow works from a clean state;
- fail-safe cases are tested;
- raw sensitive data and secrets are not emitted in logs/errors;
- policy revision and approval integrity are verified;
- repeated synthetic demo runs are reproducible;
- all checks and unresolved failures are documented.

At completion, provide the actual commands run, their real results, fixes made, and remaining limitations.

**Stop after Phase 5.**
