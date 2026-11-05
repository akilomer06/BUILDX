# Operator workbench: accounts and protection evidence

The localhost:8080 workbench now has a single **Policy review** page. Its
**Policy destination** selector chooses either the real NEXUS BANK account
summary contract or the original golden example. Their revisions, digests and
approval histories remain separate. Switching destination clears unsaved review
selections. Field evidence uses the same selector and identifies explicit bank
contract evidence versus Python AST evidence. The original API/log/canary demo
views are under **Demo examples**.

## Inspect account records

1. Open http://localhost:8080 and choose **Accounts Explorer**.
2. Search by an 12-digit account ID, customer display name or username. Search is bounded
   and parameterized; Nginx API access logging is disabled so search terms do not
   enter ordinary URL logs.
3. Select an account. It shows selected customer/source fields, ledger-derived
   balance, recent ledger entries, transfers and beneficiaries. Sensitive values
   are masked by default. There is no SQL console, balance editor or write route.
4. To inspect this local sandbox record, explicitly enable **Reveal sandbox
   fields for 45 seconds**. The UI clears revealed data and reloads masked
   projections on expiry or when switching accounts. Responses use no-store.
   Revealed values can still be copied manually; this is a trusted-host operator
   feature, not an access mechanism for customer browsers.
5. Passwords, password hashes, session tokens/hashes and operator/HMAC secrets
   are never selected by the explorer, including under reveal.

Opening these views generates no customer traffic and inserts no bank/log events.
The current response panel is labelled **read-only policy preview**, rather than
being presented as a previously served customer response.

## See real protection decisions

While a customer is signed in on port 8081 (or the enabled LAN customer URL),
refresh their account overview. Then either:

- open **Protection inspector**, select the account and a recorded request.

For the HTTP response body itself, click the request in **Live bank traffic**.
The global Standard / VEILMINT toggle now controls that request's inline JSON
viewer. See [live response inspection](traffic-responses.md). Existing protected
log evidence remains in Protection inspector.

The request detail displays the actual correlation ID and three separate stages:

1. **Source → response contract:** private source fields such as the full internal
   account reference and optional fictional contacts are excluded when building
   the intentional customer DTO. They are labelled EXCLUDED BY RESPONSE CONTRACT.
   They are not counted as VEILMINT policy removals.
2. **DTO → VEILMINT:** the existing minimizer applies only valid current approved
   removals. The compatibility label remains the review candidate; required
   balance and account fields stay KEEP. Unknown public DTO fields stay present.
3. **Structured audit input → persisted log:** selected actual account audit fields
   enter the existing sanitizer in memory. Display name and optional generated
   contact fields are MASKed. Financial balance and recent transaction fields
   are DROPPED. The actual SQLite protected record is fetched and its correlation
   ID checked before display. No raw pre-sanitization event is persisted.

Header evidence is separate from JSON field policy. Cookie, Authorization,
X-API-Key, the private operator header and Set-Cookie have presence/exclusion
metadata only. Values are not copied into log input. Authentication still receives
its required cookie and sets its required session cookie; the UI does not claim
those headers were removed from transport. Absent headers are shown as absent,
not counted as successfully filtered values.

Older traffic records have no new stage/header evidence. They are labelled as
older records rather than being retroactively given invented protection details.

## Optional fictional contact fields

Customer registration still asks for no phone/address. To add an explicitly
fictional profile for a selected sandbox account, run on Laptop 1:

```powershell
docker compose exec backend python -m veilmint bank demo-profile --account ACCOUNT_ID --synthetic-only
```

This idempotently stores generated `demo-...@example.invalid`, `DEMO-PHONE-...`
and `FICTIONAL DEMO ADDRESS ...` values in `nexus_demo_profiles`. It does not change
customer identity, credentials, funds, ledger or existing contact rows. No HTTP
profile-write route was added. Refresh the customer account afterward to produce
a real request with profile MASK actions and financial DROP actions.

The bank schema advances non-destructively to version 3 using its independent
`nexus_schema` marker; original policies, customer records and ledger entries are
preserved. The account response contract itself is unchanged, so its existing
approvals are not silently replaced. The expanded log-only metadata mapping
creates a new validated configuration revision without candidate API approvals.

Account IDs are now stable 12-digit numeric identifiers, including for existing
accounts. Copy the ID from the refreshed customer overview or Accounts Explorer
when adding a beneficiary or using the CLI. IDs travel as strings to preserve
their exact digits. Existing login credentials and saved beneficiaries still work.

All bank balances, transfers and receipts use INR. One minor unit is one paise;
`--amount-minor 100000` adds INR 1,000.00. Existing simulated amounts retain their
numeric value, with no foreign-exchange conversion. The version 3 migration adds
an ID mapping and updates account denomination. Original ledger rows, amounts,
internal references and historical currency labels remain untouched on disk;
the bank presents legacy AED entries and receipts as INR under this explicit
sandbox redenomination. Previously persisted protection evidence remains intact.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/verify_bank_ui.py
.\.venv\Scripts\python.exe scripts/verify_operator_inspection.py
```

The last command is opt-in: it creates a clearly fictional verification customer
via the real Docker HTTP API, attaches a fictional profile, explicitly funds the
sandbox account and checks operator masking, reveal projections, actual stored
log protection and customer access restrictions. It does not approve any bank
candidate removal. Summary evidence is stored under ignored
`data/operator-inspection-verification.json`, with no credentials.

The real-HTTP React test also opens the operator Explorer after its banking flow,
checks masking and explicitly reveals the sandbox record. Its local operator
context is loopback; Docker proxy restrictions are tested independently.

Physical two-device acceptance and browser visual inspection remain separate
unverified items; jsdom tests and localhost HTTP checks are not a substitute.
