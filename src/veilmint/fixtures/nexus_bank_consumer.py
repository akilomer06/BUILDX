"""Synthetic consumer source, scanned as text and never imported or executed."""


def build_account_summary(payload):
    account_id = payload["account_id"]
    account_type = payload["account_type"]
    currency = payload.get("currency")
    available_balance = payload["available_balance"]
    recent_transactions = payload.get("recent_transactions")

    # A variable key is intentionally dynamic. Its bounded value identifies only
    # internal_risk_flag as affected, but this is not supported direct-use proof.
    risk_key = "internal_risk_flag"
    risk = payload.get(risk_key)

    return {
        "id": account_id,
        "type": account_type,
        "currency": currency,
        "balance": available_balance,
        "transactions": recent_transactions,
        "risk": risk,
    }
