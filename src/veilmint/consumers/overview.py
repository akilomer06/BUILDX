def consume(payload):
    return {"account": payload["account_id"], "holder": payload["display_name"], "type": payload["account_type"], "balance_minor": payload["available_balance_minor"], "currency": payload["currency"], "status": payload["status"], "recent_activity_count": len(payload["recent_transactions"])}
