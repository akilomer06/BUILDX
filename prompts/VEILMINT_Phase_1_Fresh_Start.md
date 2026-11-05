# VEILMINT — Phase 1 Master Prompt
## Fresh Repository Setup + Core Analysis Engine

You are implementing **VEILMINT — Evidence-Compiled Least-Data Firewall**.

This is a **fresh start**. Assume nothing has been built yet: no repository structure, source code, tests, frontend, backend, configuration, or documentation exists unless you discover it in the working directory.

Your task is to complete **Phase 1 only**. Build the foundation and the first working analysis capability. Do not jump ahead into later phases.

---

## 1. Product Context

VEILMINT helps teams reduce unnecessary sensitive data exposure in API responses and application logs.

Its core workflow is:

1. Inspect a producer's JSON Schema and a downstream Python consumer.
2. Determine which fields are demonstrably used, potentially unused, or uncertain.
3. Let a reviewer approve proposed API field removals (later phase).
4. Compile and enforce a versioned policy at API and logging boundaries (later phases).
5. Verify protected paths using synthetic canaries (later phase).

### Classification Rules

**Usage classification** is separate from **sensitivity classification**.

Usage:
- `USED`: supported direct access in the scanned consumer. Never automatically remove.
- `CANDIDATE_UNUSED`: no supported access found in the scanned scope. This is only a candidate, not proof; human approval is required before removal.
- `UNKNOWN`: dynamic access, broad forwarding/reflection, incomplete analysis, or ambiguity. Preserve the field and disable removal.

Sensitivity:
- `GENERAL`
- `FINANCIAL`
- `MEDIUM`
- `HIGH`
- `INTERNAL`

A field may be `USED` and sensitive. Sensitivity does not determine whether it is required by the consumer.

---

## 2. Phase 1 Objective

Create a clean, runnable repository and implement the **first end-to-end analysis slice**:

- a synthetic NEXUS BANK payload/schema;
- a conservative Python AST consumer analyzer;
- a sensitivity mapping;
- a structured analysis report;
- automated tests;
- concise setup/use documentation.

Phase 1 is analysis-only. It must not remove fields from live API responses, sanitize logs, or enforce policies.

---

## 3. Start by Inspecting the Workspace

Before creating files:

1. Inspect the current working directory and existing files.
2. If the directory is empty, initialize the project from scratch.
3. If files exist, preserve them; do not overwrite blindly. Adapt the structure and report what was reused.
4. Do not assume any previous VEILMINT implementation exists.
5. Keep the implementation small and demo-oriented.

---

## 4. Required Stack

- Python 3.12+
- FastAPI may be added only if needed for a minimal health/analysis endpoint; do not build the full API runtime in this phase.
- `jsonschema` for validating the synthetic payload against its schema.
- Python `ast` for static consumer analysis. **Never execute scanned consumer code.**
- `pytest` for tests.
- SQLite, React, Vite, Tailwind, Docker, and CI are not required in Phase 1; do not add them unless the repository already has them and they are useful without expanding scope.

Use a simple Python package layout, for example:

```text
veilmint/
  pyproject.toml
  README.md
  src/veilmint/
    __init__.py
    analyzer/
      __init__.py
      ast_analyzer.py
      schema_inventory.py
      sensitivity.py
      report.py
    fixtures/
      nexus_bank_schema.json
      nexus_bank_payload.json
      nexus_bank_consumer.py
  tests/
    test_schema_inventory.py
    test_ast_analyzer.py
    test_sensitivity.py
    test_report.py
```

You may adjust names if the resulting structure remains clear and minimal.

---

## 5. Synthetic NEXUS BANK Scenario

Use synthetic data only. Do not use real customer data or credentials.

The schema/payload must contain these 10 fields:

| Field | Expected usage | Sensitivity |
|---|---|---|
| `account_id` | USED | INTERNAL |
| `account_type` | USED | GENERAL |
| `currency` | USED | GENERAL |
| `available_balance` | USED | FINANCIAL |
| `recent_transactions` | USED | FINANCIAL |
| `account_number` | CANDIDATE_UNUSED | HIGH |
| `customer_phone` | CANDIDATE_UNUSED | MEDIUM |
| `customer_address` | CANDIDATE_UNUSED | MEDIUM |
| `aadhaar_number` | CANDIDATE_UNUSED | HIGH |
| `internal_risk_flag` | UNKNOWN | INTERNAL |

Expected result:
- 5 `USED`
- 4 `CANDIDATE_UNUSED`
- 1 `UNKNOWN`

The synthetic consumer should directly read the five USED fields. It should also contain a clearly documented ambiguous/dynamic operation that causes `internal_risk_flag` to be `UNKNOWN`. The four candidate fields must not be accessed in the consumer.

Do not include actual Aadhaar numbers, phone numbers, addresses, account numbers, tokens, or other real personal/financial information. Use obvious placeholders.

---

## 6. Implementation Requirements

### A. Schema inventory
- Load the JSON Schema.
- Identify top-level object properties.
- Validate the synthetic payload using `jsonschema`.
- Return a deterministic field inventory.
- Fail clearly on invalid schema or payload.

### B. Conservative AST analyzer
- Parse consumer source with `ast.parse`; never import or execute it.
- Detect supported direct field access patterns, such as `payload["account_id"]` and `payload.get("currency")`.
- Detect dynamic or ambiguous access patterns, such as variable-key indexing, broad iteration/forwarding, or reflection, and mark affected fields—or the analysis scope—as `UNKNOWN`.
- Do not claim complete program understanding.
- Keep analyzer output explainable: include evidence/reason for each field classification.
- If analysis is incomplete or ambiguous, prefer `UNKNOWN` over `CANDIDATE_UNUSED`.
- Unsupported syntax must not silently produce confident unused classifications.

### C. Sensitivity mapping
- Store sensitivity labels in a separate mapping/configuration.
- Do not derive usage from sensitivity or sensitivity from usage.
- Ensure all schema fields receive a sensitivity label; unmapped fields should default safely to `INTERNAL` and generate a warning.

### D. Analysis report
Produce a structured JSON-compatible report containing, at minimum:
- field name;
- usage classification;
- sensitivity;
- evidence/reason;
- analyzer warnings;
- total counts by usage class;
- schema validation result.

Report ordering must be deterministic.

### E. Tests
Write tests for:
- schema inventory and payload validation;
- direct field access detection;
- dynamic access/ambiguity behavior;
- correct `USED` / `CANDIDATE_UNUSED` / `UNKNOWN` outcomes;
- independent sensitivity mapping;
- report structure and deterministic output.

Tests must run locally with one documented command.

---

## 7. Scope Exclusions — Do Not Build Yet

Do **not** implement any of the following in Phase 1:

- reviewer approval UI or approval workflow;
- policy compiler or policy version persistence;
- API response minimisation/enforcement middleware;
- log DROP/MASK/HMAC processing or log sink integration;
- canary injection or verification dashboard;
- frontend/dashboard;
- authentication, multi-user accounts, RBAC;
- deployment, Docker Compose, CI/CD;
- real customer integrations or external API calls.

These belong to later phases. Do not create placeholders that pretend they are implemented.

---

## 8. Completion Gate

Phase 1 is complete only when:

- the repository is runnable from a clean setup;
- the synthetic schema and payload validate;
- the analyzer returns exactly **5 USED / 4 CANDIDATE_UNUSED / 1 UNKNOWN** for the golden scenario;
- every field has a sensitivity label;
- all tests pass;
- README explains setup, test command, and how to run the analysis;
- the report is deterministic and explainable;
- no scanned consumer code is executed;
- no later-phase enforcement or UI is falsely claimed.

At completion, provide:
1. a concise summary of files created;
2. the exact setup and test commands;
3. the golden scenario classification counts;
4. known analyzer limitations;
5. confirmation that Phase 1 exclusions were respected.

**Stop after Phase 1. Do not begin Phase 2 or ask the user to approve runtime enforcement yet.**
