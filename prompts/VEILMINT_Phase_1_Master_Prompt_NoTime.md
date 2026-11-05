# VEILMINT — Phase 1 Master Prompt
## Golden Scenario + Core Evidence Analysis

> **Run this prompt for Phase 1 only.** Do not begin later phases or implement runtime enforcement, log protection, UI polish, or canary verification here.

## Role

Act as the senior implementation engineer working in the existing VEILMINT repository through Codex.

Follow the approved **VEILMINT Final Implementation Plan** as the source of truth. Follow the repository's existing conventions where they do not conflict with that plan. Do not redesign the product or broaden scope.

## Product context

**VEILMINT — Evidence-Compiled Least-Data Firewall** discovers what a downstream consumer demonstrably needs, classifies fields conservatively, supports explicit policy review, and ultimately enforces minimisation and log protection at runtime.

This phase establishes the synthetic golden scenario and the evidence-analysis foundation. It does **not** implement the approval workflow or enforcement yet.

## Phase objective

Create a deterministic, testable NEXUS BANK synthetic example and an analysis pipeline that inventories schema fields, inspects a Python consumer without executing it, and reports usage evidence plus uncertainty.

## Required work

### 1. Inspect the repository first
- Review the current directory structure, dependencies, conventions, and existing tests.
- Identify what already exists; reuse it rather than duplicating it.
- Do not overwrite or remove existing work without explaining why.
- If the repository is empty or missing a required structure, create only the minimum needed for this phase.
- Record a concise implementation plan before editing.

### 2. Establish the NEXUS BANK golden scenario
Use synthetic data only—never real customer information.

Create a representative account-overview schema/fixture with these ten fields:

| Field | Expected usage status | Sensitivity |
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

Create a matching synthetic Python consumer that directly accesses the five USED fields and contains a realistic ambiguous/broad-forwarding pattern for `internal_risk_flag`, so the analyzer must classify it as UNKNOWN rather than claiming it is unused.

Keep fixtures clearly labelled as synthetic.

### 3. Implement schema inventory
- Read the supported top-level JSON Schema properties.
- Produce a stable field inventory with field name, schema/type metadata, and source location where available.
- Do not recursively flatten nested objects in this phase unless the existing approved plan explicitly requires it.
- Handle malformed or unsupported schema input with clear errors; do not silently skip it.

### 4. Implement conservative Python AST consumer analysis
- Parse consumer source with Python's `ast` module.
- **Never execute, import, or evaluate scanned consumer code.**
- Detect supported direct field access patterns such as `payload["field"]` and `payload.get("field")`.
- Map evidence to schema fields.
- Mark fields with supported direct access as `USED`.
- Mark fields with no detected access as `CANDIDATE_UNUSED` only when the scanned scope is sufficiently clear.
- Mark fields as `UNKNOWN` when dynamic keys, broad forwarding, reflection, incomplete analysis, or ambiguous patterns prevent a safe conclusion.
- Do not infer that a field is safe to remove merely because no access was found.
- Keep analyzer limitations explicit and testable.

### 5. Implement sensitivity classification
Keep sensitivity independent from usage status.

Use deterministic rules for the golden scenario:
- `GENERAL`: `account_type`, `currency`
- `FINANCIAL`: `available_balance`, `recent_transactions`
- `MEDIUM`: `customer_phone`, `customer_address`
- `HIGH`: `account_number`, `aadhaar_number`
- `INTERNAL`: `account_id`, `internal_risk_flag`

If the existing plan/repository defines a different exact taxonomy, preserve that taxonomy and document the mapping. Do not use an LLM or claim that heuristic classification is universally accurate.

### 6. Expose a simple analysis result
Provide a callable module/function or minimal CLI that accepts the fixture schema and consumer source and returns a deterministic structured result containing:
- field name
- schema/type metadata
- usage status (`USED`, `CANDIDATE_UNUSED`, `UNKNOWN`)
- sensitivity label
- evidence/reason
- analyzer limitations or warnings

Do not build the full frontend in this phase.

## Expected golden result

The NEXUS BANK scenario should produce:

- **5 USED**
- **4 CANDIDATE_UNUSED**
- **1 UNKNOWN**

The sensitivity labels must match the scenario table. The UNKNOWN field must remain unknown because of the deliberately ambiguous consumer pattern.

If this expected result cannot be achieved, explain the mismatch and fix the fixture/analyzer rather than weakening the classification rules.

## Tests and quality gates

Add automated tests for at least:

1. Correct top-level schema inventory of all ten fields.
2. Direct bracket access detection.
3. `.get("field")` access detection.
4. Candidate-unused detection for fields with no access in a clear scan.
5. UNKNOWN classification for dynamic access or broad forwarding.
6. Sensitivity mapping for all golden fields.
7. Malformed schema handling.
8. Consumer syntax errors and incomplete-analysis warnings.
9. Deterministic output across repeated runs.
10. No scanned consumer code execution (use a test fixture that would visibly fail if executed).

Run the relevant test suite and report actual results. Do not claim tests passed unless they were run.

## Deliverables

At the end of Phase 1, provide:

- NEXUS BANK synthetic schema/fixture.
- Matching synthetic consumer source.
- Schema inventory implementation.
- AST usage analyzer.
- Sensitivity classifier.
- Structured analysis output example.
- Automated tests.
- Brief README/documentation explaining how to run the analysis and its limitations.
- A concise list of files created/modified and key design decisions.

## Explicit exclusions

Do **not** implement in this phase:
- Human approval/review UI or policy approval persistence.
- Policy compiler.
- API response filtering/enforcement.
- Log sanitisation or sink integration.
- Canary injection or verification.
- Full React workbench.
- Authentication, multi-tenancy, production deployment, or external integrations.
- Real financial/customer data.
- LLM-based classification.
- Claims of complete leak prevention.

## Working rules

- Make small, coherent changes and keep the repository runnable.
- Prefer simple, deterministic code over abstractions that do not help this phase.
- Keep interfaces clear for later phases; do not prematurely implement them.
- Add or update tests with each meaningful change.
- Do not fabricate validation, metrics, or test outcomes.
- If a requirement is ambiguous, inspect the approved plan and repository first; make the narrowest safe interpretation and document it.
- Do not stop at a plan: implement this phase, test it, and summarize the actual result.
- Do not proceed to Phase 2 automatically.

## Phase 1 completion gate

Phase 1 is complete only when:
- The golden scenario contains all ten fields.
- The analyzer produces the expected `5 USED / 4 CANDIDATE_UNUSED / 1 UNKNOWN` result.
- Sensitivity labels are correct and independent from usage labels.
- The analyzer never executes scanned code.
- Tests pass and the run instructions work.
- Known limitations are documented.

**Stop after this gate. Report completion and wait for the user to request Phase 2.**
