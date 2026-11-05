# Phase 9 end-to-end verification and operator runbook

Client date: 5 November 2026 (Asia/Dubai).

## What changed

The original live response inspector correctly captured already-constructed customer DTOs. It never had the rich pre-DTO producer and therefore could not prove per-consumer minimization. The database had not been overwritten with masked JSON. Data Flow Explorer now builds a canonical producer from persisted opt-in DEMO enrichment and the selected actual sandbox account/ledger, applies separate currently reviewed policies, then executes real in-process consumer handlers. Baseline/protected views share a source hash and trace. The existing Live bank traffic modal remains available for inspecting served responses and display masking, explicitly separate from this producer comparison.

No customer UI, operational routing IDs, INR balances, transfer logic or historical bank policy approvals were replaced. Migration is additive. SQLite backups are recorded in baseline-verification.md. Comparison does not mutate bank records or approval state; explicit profile attachment and reviewer decisions are clearly separate write actions.

## Repeatable walkthrough

1. Start Docker: `docker compose up -d --build --wait`. Open localhost:8080 on the host and the existing /bank/ customer URL on port 8081 on the customer laptop.
2. Register/login and use existing CLI `bank fund --account ACCOUNT_ID --amount-minor 100000 --reference UNIQUE --sandbox-funds` for simulated funds. Use a second fictional customer and a beneficiary to generate actual transfers if desired. No silent seed funding occurs.
3. In Live bank traffic, select a real request and inspect the response. In Standard mode, **Explore consumer policies for this account** links the account to Data Flow Explorer; verified event account metadata also supports that link from masked mode. If a record lacks an account link, select its account explicitly.
4. Select the producer account in Data Flow Explorer. **Attach fictional DEMO profile** adds generated .example contact and explicitly fictional internal states, with origin DEMO. Canonical fields persist across restart; customer responses still use their authorized DTO.
5. Select Payments. Open **Consumer Policy Studio**, prepare a revision, inspect source evidence, select eligible candidates, enter a reviewer label and confirm. Do not expect removals before this explicit review completes.
6. Invoke consumer with ENFORCE. Global Standard/VEILMINT toggles the frozen producer and actual enforced output without invoking another scenario or altering DB state. OBSERVE/WARN deliberately retain the source and identify their actual runtime mode.
7. Repeat review independently for Notifications, Overview and Risk. **Compare all consumers** invokes each handler and rejects comparisons if source versions differ during the run.
8. Open a field's evidence and inspect why an email is USED for Notifications but removable for Payments. Risk legitimately retains its required sensitive risk signals; sensitivity alone does not justify API deletion.
9. Run scoped canaries. PASS requires a current valid approval, candidate markers absent from the enforced body, a HIGH log marker dropped before persistence, and matching correlation. Inspect the actual protected record returned alongside the trace. The original golden canary remains in Demo examples.
10. Customer credentials cannot call operator lab endpoints. Consumer choice is authorized operator scenario dispatch, not a public service/admin bypass.

## Measured consumer results

These are actual executions in an isolated, explicitly reviewed verification database, using one fictional account with one explicit funding ledger entry. They do not imply that live pending policies were approved. Live policies remain REVIEW_REQUIRED until the operator reviews them.

| Consumer | Policy top-level fields (32 baseline) | Emitted leaf occurrences (38 baseline) | UTF-8 JSON bytes (1250 baseline) | Scoped canary |
|---|---:|---:|---:|---|
| overview | 7 | 13 | 404 | PASS |
| payments | 5 | 5 | 129 | PASS |
| notifications | 3 | 3 | 109 | PASS |
| risk | 6 | 12 | 412 | PASS |

Counts: top-level AST/policy inventory differs from emitted JSON leaf occurrences. Empty containers and nulls count as one emitted leaf. Array indices are normalized to '*' for the separate unique-path count. Required arrays are conservatively retained as whole containers; no nested AST proof is claimed. JSON byte sizes use compact UTF-8 serialization before transport compression, not display whitespace. Different account names, balances or transaction counts legitimately change sizes. Field reduction is not a privacy-risk or compliance score.

## Executed checks

- `.venv\Scripts\python.exe -m pytest -q`: 274 passed, one existing adapter deprecation warning. Relevant final backend changes also passed the 50-test bank/operator/consumer/inspection subset.
- `npm --prefix frontend run typecheck`: exit 0.
- `npm --prefix frontend test`: 28 passed; three opt-in HTTP tests excluded from the normal suite after adding the approval walkthrough.
- `npm --prefix frontend run build`: exit 0.
- `.venv\Scripts\python.exe scripts/verify_bank_ui.py`: three actual-HTTP React workflows passed: original bank flow, selected live-response masking, and explicit consumer preparation/review/enforcement/canary UI.
- `docker compose build --quiet` and `docker compose up -d --wait --wait-timeout 90`: successful; all three services healthy.
- Deployed HTTP smoke: opt-in DEMO seed on a clearly fictional verification customer, four policy preparations (no approvals), actual matrix, pending baseline retention, customer proxy denial and HTTP/trace/log correlation all passed. Evidence: ignored data/phase9-live-smoke.json.
- Docker backend restart: DEMO canonical data and pending policies survived; no fabricated activation.
- Backup preservation comparison: all original 13 customer/account rows, 12 ledger rows, 3 transfers, 3 beneficiaries and original golden/bank/log policy and reviewer rows remain identical as subsets of the live DB. Foreign key checks passed.

## Limits and phase coverage

Phases 1–6 and 8 regressions are covered by the full existing suites. The original 10 → 5/4/1 → approved 4 removals / 6 retained behavior remains. Phase 7 prompt is NOT FOUND and was previously postponed. See the full implementation-coverage matrix.

The AST inventory remains intentionally top-level; nested runtime filtering is supported separately. A USED array preserves its contents. Four consumers are logical services inside one process, not separate deployments or independent workload credentials. Live operator authentication is a trusted-host secret boundary, not enterprise RBAC. SQLite is local trusted sandbox storage, not an encrypted production PII platform.

Browser automation was attempted and rejected by Work settings: visual browser QA is NOT VERIFIED. Physical second-laptop operation is NOT VERIFIED in this run. Manual checks: inspect Data Flow Explorer at desktop/mobile widths, switch consumers and modes, complete each explicit review, inspect field evidence/canaries, and generate a real transfer from the second laptop. No screenshots were produced or claimed. Existing LAN binding was preserved.
