def consume(payload):
    return {"destination": payload["email"], "language": payload["preferred_language"], "account_suffix": payload["masked_account_reference"], "message_kind": "SANDBOX_ACCOUNT_NOTICE"}
