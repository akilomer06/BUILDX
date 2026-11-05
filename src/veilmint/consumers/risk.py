def consume(payload):
    return {"account": payload["account_id"], "review_state": payload["fraud_review_state"], "flagged": payload["internal_risk_flag"], "case": payload["internal_case_reference"], "transaction_count": len(payload["recent_transactions"]), "kyc_state": payload["kyc_demo_status"]}
