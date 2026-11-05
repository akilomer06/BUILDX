# VEILMINT — Phase 3 Master Prompt
## Runtime API Minimisation + Structured Log Protection

You are continuing **VEILMINT — Evidence-Compiled Least-Data Firewall** from Phases 1 and 2.

## Critical Starting Rule

Do not assume earlier phases are complete.

Before implementing:
1. Inspect the repository and read the Phase 1/2 documentation.
2. Run all existing tests.
3. Load the approved NEXUS BANK policy from SQLite and verify its revision and approval metadata.
4. Confirm the approved policy marks the four approved candidate fields as `REMOVE`, all five `USED` fields as `KEEP`, and `internal_risk_flag` as `KEEP`.
5. If any foundation is missing or incorrect, repair only what is necessary and explain it. Preserve working code and avoid blind rewrites.

---

## 1. Phase 3 Objective

Make the compiled policy **actually protect data at runtime**, through two narrowly scoped paths:

1. **API response minimisation:** filter outgoing JSON responses using the active approved policy.
2. **Structured application log protection:** apply configured `ALLOW`, `MASK`, `DROP`, or `HMAC_PSEUDONYM` actions before events reach the SQLite log sink.

This phase is backend/runtime focused. Do not build the final frontend or canary verification experience yet.

---

## 2. API Runtime Enforcement

Implement a reusable response-minimisation component and expose it through a minimal FastAPI demonstration endpoint.

### Rules
- Load the active, approved compiled policy. Do not accept a policy supplied by the request caller.
- Apply `REMOVE` only to fields explicitly approved in the active policy revision.
- Preserve `KEEP` fields.
- Preserve unknown/unmapped fields and emit a warning; never silently discard them.
- Handle nested JSON objects safely. Apply policy to known fields at the correct object path; do not accidentally remove unrelated fields with the same name in another object.
- Arrays of objects must be handled consistently.
- If the policy is missing, invalid, unapproved, or stale, fail safely: **do not minimise the response**. Return the original response (or a clearly defined safe error for the demo), and record a warning. Never default to removing fields.
- Keep the enforcement component separate from endpoint business logic.
- Provide a demonstration endpoint that returns the synthetic NEXUS BANK response before/after minimisation, clearly labelled as synthetic.
- Include policy revision metadata in an internal trace/audit record, not in sensitive customer response content.

### Runtime mode
Support:
- `OBSERVE`: calculate/report would-be removals but return the original response.
- `WARN`: preserve response while emitting warnings for policy issues.
- `ENFORCE`: apply approved removals.

Use explicit configuration and safe defaults. Local demo may enable ENFORCE only after loading a valid approved policy.

---

## 3. Structured Log Protection

Build a small structured logging pipeline that protects events **before they are persisted**.

### Required behavior
- Accept structured log events as dictionaries/JSON objects.
- Apply sensitivity-derived actions from the compiled policy:
  - `ALLOW`: retain value.
  - `MASK`: replace value with a safe fixed mask (e.g. `[REDACTED]`).
  - `DROP`: remove field entirely.
  - `HMAC_PSEUDONYM`: replace value with a stable keyed pseudonym.
- HMAC pseudonymisation must use a secret supplied through environment/configuration; never hard-code a production key or log the secret.
- Keep pseudonym stable for the same value under the same key, and different for different values. Use a standard HMAC construction and safe encoding.
- For unknown/unmapped fields, use a conservative default (`MASK`) and emit a warning.
- Apply recursively to nested objects and arrays, using field-path-aware policy lookup where available.
- Protect the event before writing it to SQLite. Do not write raw event data first and sanitize afterward.
- Add a test-only sink or inspection helper to prove raw sensitive values never reach persisted logs.

### Log pipeline
Keep it simple:
1. receive structured event;
2. sanitize according to policy;
3. persist sanitized event;
4. return a safe summary/trace.

Do not add external log services.

---

## 4. Golden NEXUS BANK Runtime Demonstration

Use only synthetic data.

### API output
Input contains all 10 fields. With the approved Phase 2 policy in ENFORCE mode:
- remove `account_number`;
- remove `customer_phone`;
- remove `customer_address`;
- remove `aadhaar_number`;
- retain the five USED fields;
- retain `internal_risk_flag` because it is UNKNOWN.

Expected response shape: **10 → 6 fields**.

### Log event
Create a synthetic structured event containing:
- `account_id`;
- `account_type`;
- `available_balance`;
- `account_number`;
- `customer_phone`;
- `aadhaar_number`;
- `internal_risk_flag`;
- a harmless unmapped field.

Expected behavior under the golden mapping:
- GENERAL → ALLOW;
- INTERNAL/MEDIUM → MASK;
- FINANCIAL/HIGH → DROP;
- unmapped log fields → MASK + warning.

Ensure usage classification does not override log sensitivity: a USED financial field may still be dropped from logs.

---

## 5. Persistence, Audit, and Safety

- Persist only sanitized structured log events.
- Record policy revision and runtime mode with an internal audit entry.
- Keep audit metadata separate from customer payload/log values.
- Ensure errors and exceptions do not include raw sensitive values.
- Avoid logging request bodies, response bodies, secrets, or raw event dictionaries in debug output.
- Keep the implementation local and synthetic; no real customer integration.

---

## 6. Tests

Add tests for:
- approved candidate removal in ENFORCE;
- unchanged response in OBSERVE/WARN;
- USED fields never removed;
- UNKNOWN fields retained;
- unapproved/stale/missing policy fails safe;
- nested objects and arrays;
- unknown API fields retained + warning;
- log ALLOW/MASK/DROP behavior;
- HMAC stability and key sensitivity;
- nested log sanitation;
- unknown log fields masked;
- persisted log contains sanitized values only;
- exceptions/warnings do not expose raw values;
- API and log policy actions remain independent.

Run all previous phase tests as well.

---

## 7. Scope Exclusions — Do Not Build Yet

Do not implement:
- final React dashboard or policy-review UI;
- canary injection or canary verification;
- external log providers;
- production customer integrations;
- authentication/RBAC;
- distributed deployment or advanced observability;
- broad automatic schema discovery across arbitrary services.

These belong to later phases or are outside the MVP.

---

## 8. Completion Gate

Phase 3 is complete only when:
- Phase 1 and Phase 2 tests still pass;
- an approved policy is loaded by revision, not caller-provided input;
- ENFORCE produces the expected synthetic **10 → 6** API output;
- OBSERVE/WARN never remove fields;
- UNKNOWN and unmapped API fields are retained;
- structured logs are sanitized before SQLite persistence;
- the persisted event contains no raw HIGH/FINANCIAL values;
- HMAC works without exposing its key;
- tests cover nested structures, fail-safe behavior, and independent API/log actions;
- documentation explains configuration, runtime modes, demo endpoints, and limitations;
- no UI or canary verification is falsely claimed.

At completion, report:
1. runtime components and endpoints added;
2. exact commands to run the demo and tests;
3. before/after synthetic API output summary;
4. sanitized log example;
5. test results and limitations;
6. confirmation that Phase 4 UI/canary verification is not implemented.

**Stop after Phase 3. Do not begin Phase 4.**
