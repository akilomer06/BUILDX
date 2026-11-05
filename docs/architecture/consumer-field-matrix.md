# Consumer field matrix

Four logical services execute in one FastAPI process. Operator-authenticated dispatch is the service adapter boundary; these are not independently deployed microservices. Source schema is producer-v1. Python AST evidence is top-level; a USED container retains all nested content. No absence of runtime reads implies unused.

| Producer field | Type | Sensitivity | Overview | Payments | Notifications | Risk |
|---|---|---|---|---|---|---|
| account_id | string | INTERNAL | USED | USED | CANDIDATE_UNUSED | USED |
| account_number | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| account_type | string | GENERAL | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| address | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| available_balance_minor | integer | FINANCIAL | USED | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| branch_code | string | GENERAL | CANDIDATE_UNUSED | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| city | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| country | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| currency | string | GENERAL | USED | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| customer_segment | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| customer_status | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| display_name | string | MEDIUM | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| email | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED | CANDIDATE_UNUSED |
| fraud_review_state | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED |
| interest_plan | string | GENERAL | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| internal_case_reference | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED |
| internal_risk_flag | boolean | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED |
| kyc_demo_status | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED |
| last_reviewed_at | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| ledger_balance_minor | integer | FINANCIAL | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| legacy_display_label | string | GENERAL | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| legal_name | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| masked_account_reference | string | GENERAL | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED | CANDIDATE_UNUSED |
| opened_at | string | GENERAL | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| phone | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| postal_code | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| preferred_language | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED | CANDIDATE_UNUSED |
| recent_transactions | array | FINANCIAL | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | USED |
| source_system | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| state | string | MEDIUM | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| status | string | GENERAL | USED | USED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |
| support_notes | string | HIGH | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED | CANDIDATE_UNUSED |

Types are defined by ConsumerLab.report() and its generated JSON Schema. Fields classified CANDIDATE_UNUSED remain KEEP until explicitly reviewed. Per-field line evidence is returned by /policies/{consumer} and displayed by the UI.

## overview

Source: `src/veilmint/consumers/overview.py`. Destination: `nexus.consumer.overview.v1`.

- `account_id`: src/veilmint/consumers/overview.py:2:24: Direct literal field read via payload['account_id'].
- `account_number`: No supported access to 'account_number' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `account_type`: src/veilmint/consumers/overview.py:2:90: Direct literal field read via payload['account_type'].
- `address`: No supported access to 'address' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `available_balance_minor`: src/veilmint/consumers/overview.py:2:132: Direct literal field read via payload['available_balance_minor'].
- `branch_code`: No supported access to 'branch_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `city`: No supported access to 'city' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `country`: No supported access to 'country' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `currency`: src/veilmint/consumers/overview.py:2:180: Direct literal field read via payload['currency'].
- `customer_segment`: No supported access to 'customer_segment' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `customer_status`: No supported access to 'customer_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `display_name`: src/veilmint/consumers/overview.py:2:57: Direct literal field read via payload['display_name'].
- `email`: No supported access to 'email' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `fraud_review_state`: No supported access to 'fraud_review_state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `interest_plan`: No supported access to 'interest_plan' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_case_reference`: No supported access to 'internal_case_reference' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_risk_flag`: No supported access to 'internal_risk_flag' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `kyc_demo_status`: No supported access to 'kyc_demo_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `last_reviewed_at`: No supported access to 'last_reviewed_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `ledger_balance_minor`: No supported access to 'ledger_balance_minor' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legacy_display_label`: No supported access to 'legacy_display_label' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legal_name`: No supported access to 'legal_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `masked_account_reference`: No supported access to 'masked_account_reference' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `opened_at`: No supported access to 'opened_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `phone`: No supported access to 'phone' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `postal_code`: No supported access to 'postal_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `preferred_language`: No supported access to 'preferred_language' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `recent_transactions`: src/veilmint/consumers/overview.py:2:259: Direct literal field read via payload['recent_transactions'].
- `source_system`: No supported access to 'source_system' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `state`: No supported access to 'state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `status`: src/veilmint/consumers/overview.py:2:211: Direct literal field read via payload['status'].
- `support_notes`: No supported access to 'support_notes' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
## payments

Source: `src/veilmint/consumers/payments.py`. Destination: `nexus.consumer.payments.v1`.

- `account_id`: src/veilmint/consumers/payments.py:2:32: Direct literal field read via payload['account_id'].
- `account_number`: No supported access to 'account_number' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `account_type`: No supported access to 'account_type' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `address`: No supported access to 'address' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `available_balance_minor`: src/veilmint/consumers/payments.py:2:176: Direct literal field read via payload['available_balance_minor'].
- `branch_code`: src/veilmint/consumers/payments.py:2:73: Direct literal field read via payload['branch_code'].
- `city`: No supported access to 'city' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `country`: No supported access to 'country' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `currency`: src/veilmint/consumers/payments.py:2:109: Direct literal field read via payload['currency'].
- `customer_segment`: No supported access to 'customer_segment' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `customer_status`: No supported access to 'customer_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `display_name`: No supported access to 'display_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `email`: No supported access to 'email' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `fraud_review_state`: No supported access to 'fraud_review_state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `interest_plan`: No supported access to 'interest_plan' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_case_reference`: No supported access to 'internal_case_reference' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_risk_flag`: No supported access to 'internal_risk_flag' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `kyc_demo_status`: No supported access to 'kyc_demo_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `last_reviewed_at`: No supported access to 'last_reviewed_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `ledger_balance_minor`: No supported access to 'ledger_balance_minor' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legacy_display_label`: No supported access to 'legacy_display_label' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legal_name`: No supported access to 'legal_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `masked_account_reference`: No supported access to 'masked_account_reference' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `opened_at`: No supported access to 'opened_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `phone`: No supported access to 'phone' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `postal_code`: No supported access to 'postal_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `preferred_language`: No supported access to 'preferred_language' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `recent_transactions`: No supported access to 'recent_transactions' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `source_system`: No supported access to 'source_system' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `state`: No supported access to 'state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `status`: src/veilmint/consumers/payments.py:2:142: Direct literal field read via payload['status'].
- `support_notes`: No supported access to 'support_notes' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
## notifications

Source: `src/veilmint/consumers/notifications.py`. Destination: `nexus.consumer.notifications.v1`.

- `account_id`: No supported access to 'account_id' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `account_number`: No supported access to 'account_number' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `account_type`: No supported access to 'account_type' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `address`: No supported access to 'address' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `available_balance_minor`: No supported access to 'available_balance_minor' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `branch_code`: No supported access to 'branch_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `city`: No supported access to 'city' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `country`: No supported access to 'country' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `currency`: No supported access to 'currency' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `customer_segment`: No supported access to 'customer_segment' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `customer_status`: No supported access to 'customer_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `display_name`: No supported access to 'display_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `email`: src/veilmint/consumers/notifications.py:2:28: Direct literal field read via payload['email'].
- `fraud_review_state`: No supported access to 'fraud_review_state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `interest_plan`: No supported access to 'interest_plan' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_case_reference`: No supported access to 'internal_case_reference' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_risk_flag`: No supported access to 'internal_risk_flag' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `kyc_demo_status`: No supported access to 'kyc_demo_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `last_reviewed_at`: No supported access to 'last_reviewed_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `ledger_balance_minor`: No supported access to 'ledger_balance_minor' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legacy_display_label`: No supported access to 'legacy_display_label' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legal_name`: No supported access to 'legal_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `masked_account_reference`: src/veilmint/consumers/notifications.py:2:107: Direct literal field read via payload['masked_account_reference'].
- `opened_at`: No supported access to 'opened_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `phone`: No supported access to 'phone' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `postal_code`: No supported access to 'postal_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `preferred_language`: src/veilmint/consumers/notifications.py:2:58: Direct literal field read via payload['preferred_language'].
- `recent_transactions`: No supported access to 'recent_transactions' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `source_system`: No supported access to 'source_system' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `state`: No supported access to 'state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `status`: No supported access to 'status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `support_notes`: No supported access to 'support_notes' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
## risk

Source: `src/veilmint/consumers/risk.py`. Destination: `nexus.consumer.risk.v1`.

- `account_id`: src/veilmint/consumers/risk.py:2:24: Direct literal field read via payload['account_id'].
- `account_number`: No supported access to 'account_number' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `account_type`: No supported access to 'account_type' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `address`: No supported access to 'address' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `available_balance_minor`: No supported access to 'available_balance_minor' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `branch_code`: No supported access to 'branch_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `city`: No supported access to 'city' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `country`: No supported access to 'country' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `currency`: No supported access to 'currency' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `customer_segment`: No supported access to 'customer_segment' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `customer_status`: No supported access to 'customer_status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `display_name`: No supported access to 'display_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `email`: No supported access to 'email' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `fraud_review_state`: src/veilmint/consumers/risk.py:2:63: Direct literal field read via payload['fraud_review_state'].
- `interest_plan`: No supported access to 'interest_plan' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `internal_case_reference`: src/veilmint/consumers/risk.py:2:144: Direct literal field read via payload['internal_case_reference'].
- `internal_risk_flag`: src/veilmint/consumers/risk.py:2:105: Direct literal field read via payload['internal_risk_flag'].
- `kyc_demo_status`: src/veilmint/consumers/risk.py:2:251: Direct literal field read via payload['kyc_demo_status'].
- `last_reviewed_at`: No supported access to 'last_reviewed_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `ledger_balance_minor`: No supported access to 'ledger_balance_minor' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legacy_display_label`: No supported access to 'legacy_display_label' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `legal_name`: No supported access to 'legal_name' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `masked_account_reference`: No supported access to 'masked_account_reference' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `opened_at`: No supported access to 'opened_at' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `phone`: No supported access to 'phone' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `postal_code`: No supported access to 'postal_code' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `preferred_language`: No supported access to 'preferred_language' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `recent_transactions`: src/veilmint/consumers/risk.py:2:205: Direct literal field read via payload['recent_transactions'].
- `source_system`: No supported access to 'source_system' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `state`: No supported access to 'state' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `status`: No supported access to 'status' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
- `support_notes`: No supported access to 'support_notes' in the scanned source for root 'payload'. Candidate only, not proof of non-use; human review is required before removal.
