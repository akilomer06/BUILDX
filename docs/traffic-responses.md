# Inspect responses in Live bank traffic

Open http://localhost:8080. The initial page is **Live bank traffic**. Refresh the
account page on the customer bank website, then click that request's green GET
endpoint in the traffic table. A centered **API response** dialog opens with the
complete formatted JSON body first. Standard / VEILMINT controls are inside the
dialog and share the dashboard mode. HTTP headers are collapsed below the JSON.
Use **Copy JSON**, **Close response**, Escape, or the backdrop to close the box.
Long values wrap, and long responses scroll vertically within the dialog.

The global toggle has exactly two choices:

- **Standard** returns the captured customer response with its original identifiers.
- **VEILMINT** returns a server-masked projection of that same captured response.

There is no separate comparison page, unrelated customer fixture or standalone
demo account-summary endpoint. Changing mode or selecting a different request
does not reload the page or replay a bank operation. The UI checks correlation,
endpoint, method and status before displaying the selected response.

## Existing bank behavior

The customer website, login, accounts, numeric IDs, INR, transfers, balances and
response schemas are unchanged. The operator mode affects only the response
inspection endpoint. It does not change operational IDs delivered to the bank
frontend or override the bank's existing policy approvals.

JSON uses the bank's existing field names and units: for example,
`available_balance_minor` remains integer paise. No reference-example balance,
`lastUpdated` value, success wrapper or additional personal fields are invented.
The response's actual capture time appears separately below the JSON.

The current account response includes account ID, holder display name, type,
currency, status, available balance and recent transactions. It does not contain
PAN, home address or CIBIL. Inspector removal rules handle those fields if present
in a captured response; the metrics correctly show zero removals when absent.

## Accurate response snapshots

The backend marks the actual returned DTO on supported bank routes. After the
existing audit succeeds, middleware saves an opt-in memory-only copy associated
with the server's request/correlation ID and final status. An audit failure that
replaces a success response does not expose an unsent success body.

Snapshots are bounded to 100 responses, at most 64 KiB each, and expire after
15 minutes. They are worker-local and disappear on backend restart. They are not
written to SQLite, protected logs or policy stores. Previously stored traffic
metadata is preserved; old rows without a snapshot show **Response body
unavailable** and ask for a new customer request.

Authentication responses, passwords, request bodies, cookies, authorization
values and session headers are excluded. Only Content-Type,
X-Content-Type-Options, Cache-Control and X-Request-ID are carried into the viewer.

The two operator endpoints read the same frozen snapshot:

- `GET /api/operator/responses/{correlation_id}/standard`
- `GET /api/operator/responses/{correlation_id}/veilmint`

Masking uses the existing pure API identifier helper and explicit recursive
response-view rules. Balances, currencies, statuses and timestamps are retained.
Removal and masking counts are actual JSON paths. Sizes measure UTF-8 JSON body
bytes before compression; they can show 0% size savings when masking preserves
string lengths. Protection is still applied in that case.

The endpoints are operator-authorized, use no-store and are blocked by the LAN
customer proxy. They are disabled by default outside the local demo. Set
`VEILMINT_RESPONSE_INSPECTION_DEMO=true` in the host's ignored .env and restart
Compose to enable; the current host already has this enabled. Native Python runs
must set the process environment explicitly. No bank data migration is needed.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/verify_bank_ui.py
```

The HTTP tests verify exact Standard bytes against a customer response, frozen
history after a later balance change, recursive masking, expiry/eviction,
credentials exclusion, unchanged bank behavior and no inspection log writes.
React tests cover five mode cycles, response dialog selection, stale-response races,
unavailable old bodies and copying valid JSON. The original customer registration,
beneficiary and transfer UI flow is tested alongside the live-response inspector.
