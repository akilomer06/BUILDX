"""Read-only operator records and actual pre-persistence protection evidence."""
import json
import sqlite3
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from veilmint.bank.service import Bank
from veilmint.config import Settings
from veilmint.server import create_app

@pytest.fixture
def explorer(tmp_path):
    settings=Settings(database_path=tmp_path/'operator.sqlite3',operator_token='SYNTHETIC-OPERATOR-TOKEN-ONLY-123456789')
    app=create_app(settings)
    with TestClient(app) as customer, TestClient(app) as operator:
        customer.headers['X-Nexus-Request']='1'
        operator.headers['X-VEILMINT-Operator']=settings.operator_token
        body={'display_name':'FICTIONAL PERSON PRIVATE MARKER','username':'operator.demo','password':'SYNTHETIC-PRIVATE-PASSWORD-123'}
        result=customer.post('/api/bank/auth/register',json=body)
        assert result.status_code==201,result.text
        account=result.json()['account_id']
        assert customer.post('/api/bank/auth/login',json={k:body[k] for k in ('username','password')}).status_code==200
        Bank(settings.database_path).demo_profile(account)
        Bank(settings.database_path).fund(account,12345,'explicit-demo-opening')
        yield customer,operator,settings,account


def test_operator_lists_and_details_mask_by_default_never_select_credentials(explorer):
    c,o,s,account=explorer
    response=o.get('/api/operator/accounts').json()
    assert response['read_only'] and response['total']==1
    row=response['accounts'][0]
    assert row['display_name']==row['username']==row['available_balance_minor']=='[REDACTED]'
    detail=o.get('/api/operator/accounts/'+account).json()
    assert detail['source_record']['account_number']=='[REDACTED]'
    assert detail['source_record']['customer_phone']=='[REDACTED]'
    assert detail['ledger'][0]['amount_minor']=='[REDACTED]'
    revealed=o.get('/api/operator/accounts/'+account+'?reveal=true')
    assert revealed.headers['cache-control']=='no-store'
    data=revealed.json()
    assert data['source_record']['available_balance_minor']==12345
    assert data['source_record']['contact_email'].endswith('@example.invalid')
    text=json.dumps(data)
    for forbidden in ('password_hash','token_hash','nexus_sessions','SYNTHETIC-PRIVATE-PASSWORD-123',s.operator_token,c.cookies.get('nexus_session')):
        assert forbidden not in text
    assert '/account_number' in detail['contract_excluded_paths']
    assert '/customer_phone' in detail['contract_excluded_paths']
    assert 'account_number' not in data['customer_dto']
    assert 'contact_email' not in data['current_policy_preview']['output']
    assert data['current_policy_preview']['trace']['removed_paths']==[]


def test_explorer_gets_do_not_create_bank_traffic_change_ledger_or_policy(explorer):
    c,o,s,account=explorer
    def state():
        with sqlite3.connect(s.database_path) as db:
            return {table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('nexus_ledger','nexus_transfers','nexus_customers','nexus_security_events','veilmint_protected_logs')}
    before=state()
    for _ in range(2):
        assert o.get('/api/operator/accounts?reveal=true').status_code==200
        assert o.get('/api/operator/accounts/'+account+'?reveal=true').status_code==200
    assert state()==before
    assert o.post('/api/operator/accounts/'+account,json={'available_balance_minor':999}).status_code==405


def test_actual_account_request_sanitizes_profile_financials_and_header_secrets(explorer):
    c,o,s,account=explorer
    fake='SYNTHETIC_HEADER_SECRET_NEVER_LOG'
    response=c.get('/api/bank/accounts/'+account,headers={'Authorization':'Bearer '+fake,'X-API-Key':fake})
    assert response.status_code==200
    assert response.json()['available_balance_minor']==12345
    assert response.json()['display_name']=='FICTIONAL PERSON PRIVATE MARKER'
    for name in ('contact_email','customer_phone','customer_address','account_number'):
        assert name not in response.json()
    event=next(e for e in o.get('/api/traffic').json()['events'] if e['correlation_id']==response.headers['x-request-id'])
    assert event['account_id']==account
    assert '/customer_phone' in event['contract_excluded_paths'] and '/customer_phone' not in event['removed_paths']
    actions={a['path'][0]:a['action'] for a in event['log_actions']}
    assert actions['display_name']==actions['contact_email']==actions['customer_phone']==actions['customer_address']=='MASK'
    assert actions['available_balance_minor']==actions['recent_transactions']=='DROP'
    headers={a['name']:a for a in event['header_actions']}
    assert headers['Cookie']['present'] and headers['Authorization']['present'] and headers['X-API-Key']['present']
    assert headers['Authorization']['action']=='EXCLUDE_FROM_LOG'
    evidence=o.get('/api/operator/events/'+str(event['id'])).json()
    persisted=evidence['persisted']['event']
    assert persisted['display_name']==persisted['customer_phone']=='[REDACTED]'
    assert 'available_balance_minor' not in persisted and 'recent_transactions' not in persisted
    with sqlite3.connect(s.database_path) as db:
        logs=''.join(r[0] for r in db.execute('SELECT event_json FROM veilmint_protected_logs'))
        events=''.join(r[0] for r in db.execute('SELECT event_json FROM nexus_security_events'))
    for value in (fake,c.cookies.get('nexus_session'),'FICTIONAL PERSON PRIVATE MARKER','SYNTHETIC-PRIVATE-PASSWORD-123'):
        assert value not in logs and value not in events


def test_customer_cannot_access_explorer_or_evidence_even_with_session(explorer):
    c,o,s,account=explorer
    for path in ('/api/operator/accounts','/api/operator/accounts/'+account,'/api/operator/events/1','/api/bank-analysis'):
        assert c.get(path).status_code==403


def test_search_pagination_missing_account_and_no_raw_sql_endpoint(explorer):
    c,o,s,account=explorer
    assert o.get('/api/operator/accounts',params={'search':'operator.demo'}).json()['total']==1
    assert o.get('/api/operator/accounts',params={'search':"' OR 1=1 --"}).json()['accounts']==[]
    assert o.get('/api/operator/accounts?limit=101').status_code==422
    assert o.get('/api/operator/accounts?offset=-1').status_code==422
    assert o.get('/api/operator/accounts/'+str(uuid4())).status_code==404
    assert o.get('/api/operator/events/999999').status_code==404
    assert o.post('/api/operator/query',json={'sql':'SELECT * FROM nexus_sessions'}).status_code==404


def test_synthetic_profile_load_is_idempotent_and_new_customer_data_stays_intact(explorer):
    c,o,s,account=explorer
    bank=Bank(s.database_path)
    bank.demo_profile(account);bank.demo_profile(account)
    with bank.connection() as db:
        assert db.execute('SELECT count(*) FROM nexus_demo_profiles').fetchone()[0]==1
        assert db.execute('SELECT max(version) FROM nexus_schema').fetchone()[0]==3
    assert c.get('/api/bank/accounts/'+account).json()['available_balance_minor']==12345
    assert o.get('/api/bank-analysis').json()['counts']=={'USED':8,'CANDIDATE_UNUSED':1,'UNKNOWN':0}
