def consume(payload):
    return {"routing_account": payload["account_id"], "routing_branch": payload["branch_code"], "currency": payload["currency"], "eligible": payload["status"] == "ACTIVE" and payload["available_balance_minor"] > 0}
