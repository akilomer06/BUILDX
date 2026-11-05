# Local synthetic API contracts

The original routes below cover the local synthetic golden scenario. Phase 8
also exposes authenticated banking routes, endpoint-specific policies and safe
live traffic; see [the bank API and access boundary](phase8.md).
Policy and runtime logic live in the reusable Python components; routes do not
accept caller-supplied compiled policies. Validation errors return a generic
`422` response. Invalid, stale, or repeated review attempts return `409`.
Operational failures return a generic `503`, without stack traces or input
values. Operator routes require the private proxy credential in Docker; native
development without one permits only loopback operator requests. Customer bank
sessions never grant operator access.

| Route | Request | Result |
| --- | --- | --- |
| `GET /health` | None | `{status: "ok", synthetic: true}` |
| `GET /api/analysis` | None | Current deterministic Phase 1 analysis report, including fields, evidence, sensitivity, warnings and counts |
| `GET /api/policy` | None | `{synthetic: true, policy: CompiledPolicy \| null, history: PolicyRevision[], current_analysis_digest: string}` |
| `POST /api/policy/revisions` | `{new_revision?: boolean}` | The same policy wrapper; unchanged inputs reuse the latest revision, while `true` creates a fresh revision requiring review |
| `POST /api/policy/review` | Revision-bound review described below | The same wrapper with the persisted decision and compiled policy |
| `GET /api/demo/account?mode=OBSERVE\|WARN\|ENFORCE` | Optional mode | `{synthetic: true, original: object, output: object, trace: APITrace}` from actual runtime enforcement |
| `GET /api/demo/account/response` | None | The actual synthetic response only, under configured `VEILMINT_MODE` |
| `POST /api/demo/log` | None | `{synthetic: true, original: object, sanitized: object, persisted: ProtectedLog, trace: LogTrace}` |
| `POST /api/verify` | `{revision_id?: string \| null}` | Fresh path-scoped verification with `run_id`, `checked_at`, `policy_revision`, `status`, checks, actual API results and sanitized persisted log results |

`original` values are synthetic fixtures or unique synthetic canary markers.
They are displayed for the local inspection flow, never written to the log sink
before protection. HMAC secrets are never returned by these routes.

## Review request

```json
{
  "revision_id": "r1-<input-digest-prefix>",
  "analysis_digest": "<64-character SHA-256 digest from current revision>",
  "inputs_digest": "<64-character SHA-256 digest from current revision>",
  "reviewer": "Synthetic Reviewer",
  "approved_fields": ["account_number", "customer_phone"],
  "notes": "Optional rationale for this local demo decision",
  "decision": "APPROVE"
}
```

`decision` defaults to `APPROVE`; `notes` defaults to an empty string. `REJECT`
requires an empty `approved_fields` list. Only eligible `CANDIDATE_UNUSED` fields
can be selected. `USED`, `UNKNOWN`, nonexistent fields, stale revision IDs, and
mismatched digests are rejected without changing persisted state. A reviewer
label is supplied local metadata, not an authenticated identity. Each revision
accepts exactly one decision; create a new revision to review again.

## Returned records

`CompiledPolicy` contains `revision`, `fields`, `warnings`, `approval`,
`log_mapping` and `summary`. Each field includes `name`, `usage`, `sensitivity`,
`evidence`, `path`, `removal_allowed`, `api_action` and independent `log_action`.
The summary has `fields_before`, `fields_after`, `fields_removed`, and action
counts. `PolicyRevision` contains `revision_id`, `number`, `analysis_digest`,
`inputs_digest`, `created_at` and `status`.

`APITrace` contains `mode`, `policy_revision`, `policy_valid`, `warnings`,
`removed_paths`, and `would_remove_paths`. The trace remains outside the customer
response. `OBSERVE` and `WARN` preserve the response; `ENFORCE` only applies
approved removals. Missing, unapproved, stale, or malformed policy data retains
the original response and reports a warning.

`ProtectedLog` contains `id`, protected `event`, `policy_revision`, `mode`, and
`created_at`. `LogTrace` contains `record_id`, `policy_revision`, `warnings`, and
path/action entries. Unmapped log fields are masked. Runtime storage contains
only protected events, alongside separate value-free audit metadata.

## Verification scope

Every verification request generates a fresh run identifier and synthetic
markers, invokes the actual API enforcer and structured-log pipeline, then
checks their returned output and the actual SQLite log record. Each check has
`name`, `passed`, and `detail`; `status` is `PASS` only when required checks pass.
A requested revision mismatch, pending review, missing policy, or protection
failure yields an explicit `FAIL`. No prior `PASS` is reused.

This verifies the configured synthetic paths only. It does not establish broad
system security, exhaustiveness, production readiness, or compliance.
