from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from veilmint.bank.service import Bank, BankError
from veilmint.bank.protection import BankProtection, account_report, DESTINATION
from veilmint.config import Settings
from veilmint.policy.store import PolicyStore
from veilmint.server import create_app

@pytest.fixture
def domain(tmp_path):
    bank=Bank(tmp_path/'bank.sqlite3')
    alice=bank.register('Fictional Alice','alice.demo','SYNTHETIC-Password-123')
    bob=bank.register('Fictional Bob','bob.demo','SYNTHETIC-Password-456')
    return bank,alice,bob

def test_registration_hash_auth_and_empty_ledger(domain):
    bank,a,b=domain
    assert a['account_id'].isascii() and a['account_id'].isdigit() and len(a['account_id'])==12
    assert a['account_id']!=b['account_id']
    with bank.connection() as db:
        raw=db.execute('SELECT password_hash FROM nexus_customers WHERE id=?',(a['customer_id'],)).fetchone()[0]
        assert raw.startswith('$argon2id$') and 'SYNTHETIC-Password' not in raw
    token=bank.login('ALICE.DEMO','SYNTHETIC-Password-123')
    assert bank.authenticate(token)['id']==a['customer_id']
    assert bank.transactions(a['customer_id'],a['account_id'])==[]
    assert bank.account(a['customer_id'],a['account_id'])['available_balance_minor']==0
    with pytest.raises(BankError): bank.login('alice.demo','Invalid-Password-000')
    with pytest.raises(BankError): bank.register('Other','alice.demo','Different-Password-000')
    bank.logout(token)
    with pytest.raises(BankError): bank.authenticate(token)

def test_transfer_balances_idempotency_and_immutable_ledger(domain):
    bank,a,b=domain
    bank.fund(a['account_id'],10000,'explicit-sandbox-opening')
    bank.fund(a['account_id'],10000,'explicit-sandbox-opening')
    args=(a['customer_id'],a['account_id'],b['account_id'],2500,'INR','same-key-123')
    result=bank.transfer(*args)
    assert bank.transfer(*args)==result
    assert bank.account(a['customer_id'],a['account_id'])['available_balance_minor']==7500
    assert bank.account(b['customer_id'],b['account_id'])['available_balance_minor']==2500
    with bank.connection() as db:
        rows=db.execute('SELECT amount_minor,currency FROM nexus_ledger WHERE transfer_id=?',(result['id'],)).fetchall()
        assert sorted(r[0] for r in rows)==[-2500,2500]
        assert {r[1] for r in rows}=={'INR'}
        with pytest.raises(sqlite3.IntegrityError): db.execute('UPDATE nexus_ledger SET amount_minor=1')
    with pytest.raises(BankError): bank.transfer(a['customer_id'],a['account_id'],b['account_id'],2501,'INR','same-key-123')
    with pytest.raises(BankError): bank.receipt(b['customer_id'],result['id'])

@pytest.mark.parametrize('amount',[0,-1,1.1,True,'10',100_000_001])
def test_invalid_money_never_mutates(domain,amount):
    bank,a,b=domain
    with pytest.raises(BankError): bank.transfer(a['customer_id'],a['account_id'],b['account_id'],amount,'INR',str(uuid4()))
    assert bank.transactions(a['customer_id'],a['account_id'])==[]

def test_concurrent_transfers_cannot_overspend(domain):
    bank,a,b=domain
    bank.fund(a['account_id'],10000,'sandbox-concurrency')
    def transfer(i):
        try: return bank.transfer(a['customer_id'],a['account_id'],b['account_id'],7000,'INR',f'parallel-{i}')
        except BankError: return None
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(transfer,range(2)))
    assert sum(r is not None for r in result)==1
    assert bank.account(a['customer_id'],a['account_id'])['available_balance_minor']==3000
    assert bank.account(b['customer_id'],b['account_id'])['available_balance_minor']==7000

def test_rollback_if_credit_insert_fails(domain):
    bank,a,b=domain
    bank.fund(a['account_id'],10000,'sandbox-rollback')
    with bank.connection(True) as db:
        db.execute("CREATE TRIGGER injected_credit_failure BEFORE INSERT ON nexus_ledger WHEN NEW.amount_minor>0 AND NEW.kind='TRANSFER' BEGIN SELECT RAISE(ABORT,'Injected failure'); END")
    with pytest.raises(sqlite3.IntegrityError): bank.transfer(a['customer_id'],a['account_id'],b['account_id'],5000,'INR','rollback-test')
    assert bank.account(a['customer_id'],a['account_id'])['available_balance_minor']==10000
    with bank.connection() as db: assert db.execute('SELECT count(*) FROM nexus_transfers').fetchone()[0]==0

def test_ownership_beneficiary_and_destination_rules(domain):
    bank,a,b=domain
    for func in (bank.account,bank.transactions):
        with pytest.raises(BankError):func(a['customer_id'],b['account_id'])
    with pytest.raises(BankError):bank.add_beneficiary(a['customer_id'],a['account_id'],'Self')
    bank.add_beneficiary(a['customer_id'],b['account_id'],'Demo recipient')
    with pytest.raises(BankError):bank.add_beneficiary(a['customer_id'],b['account_id'],'Again')
    assert len(bank.beneficiaries(a['customer_id']))==1 and bank.beneficiaries(b['customer_id'])==[]
    with pytest.raises(BankError):bank.transfer(a['customer_id'],b['account_id'],a['account_id'],10,'INR','invalid-owner')
    with pytest.raises(BankError):bank.transfer(a['customer_id'],a['account_id'],b['account_id'],10,'USD','invalid-currency')

@pytest.fixture
def web(tmp_path):
    settings=Settings(database_path=tmp_path/'http.sqlite3',operator_token='SYNTHETIC-OPERATOR-TEST-TOKEN-12345678')
    with TestClient(create_app(settings)) as client:
        client.headers['X-Nexus-Request']='1'
        yield client,settings

def register_login(c,username='alice.demo'):
    r=c.post('/api/bank/auth/register',json={'display_name':'Fictional customer','username':username,'password':'SYNTHETIC-Password-123'})
    assert r.status_code==201,r.text
    r=c.post('/api/bank/auth/login',json={'username':username,'password':'SYNTHETIC-Password-123'})
    assert r.status_code==200,r.text
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    return c.get('/api/bank/accounts').json()[0]['account_id']

def test_real_http_protection_requires_new_endpoint_approval_and_correlates_logs(web):
    c,settings=web
    account=register_login(c)
    response=c.get('/api/bank/accounts/'+account)
    assert response.status_code==200 and 'legacy_display_label' in response.json()
    assert 'password_hash' not in response.text and 'account_number' not in response.json()
    assert c.get('/api/policy').status_code==403
    operator={'X-VEILMINT-Operator':settings.operator_token}
    draft=c.post('/api/bank-policy/revisions',json={},headers=operator).json()['policy']
    body={'revision_id':draft['revision']['revision_id'],'analysis_digest':draft['revision']['analysis_digest'],'inputs_digest':draft['revision']['inputs_digest'],'reviewer':'Local test reviewer','approved_fields':['legacy_display_label']}
    approved=c.post('/api/bank-policy/review',json=body,headers=operator)
    assert approved.status_code==200,approved.text
    protected=c.get('/api/bank/accounts/'+account)
    assert 'legacy_display_label' not in protected.json()
    assert protected.json()['account_id']==account
    events=c.get('/api/traffic',headers=operator).json()['events']
    event=next(e for e in events if e['correlation_id']==protected.headers['x-request-id'])
    assert event['destination']==DESTINATION and event['removed_paths']==['/legacy_display_label']
    assert event['log_outcome']=='SANITIZED'
    from veilmint.runtime.logs import LogSink
    persisted=LogSink(settings.database_path).get(event['log_record_id'])['event']
    assert persisted['correlation_id']==event['correlation_id']
    assert persisted['customer_reference']=='[REDACTED]'
    with sqlite3.connect(settings.database_path) as db:
        logs=''.join(r[0] for r in db.execute('SELECT event_json FROM veilmint_protected_logs'))
        assert 'SYNTHETIC-Password-123' not in logs
        assert c.cookies.get('nexus_session') not in logs
        raw_account=db.execute('SELECT account_number FROM nexus_accounts WHERE id=?',(account,)).fetchone()[0]
        assert raw_account not in logs
    c.post('/api/bank-policy/revisions',json={'new_revision':True},headers=operator)
    assert 'legacy_display_label' in c.get('/api/bank/accounts/'+account).json()
    assert c.post('/api/bank-policy/review',json=body,headers=operator).status_code==409

@pytest.mark.parametrize('amount',[0,-1,'10.01',1.01,True,100_000_001])
def test_money_http_strict_validation(web,amount):
    c,s=web; account=register_login(c)
    r=c.post('/api/bank/transfers',json={'source_account_id':account,'destination_account_id':'999999999999','amount_minor':amount,'currency':'INR','idempotency_key':str(uuid4())})
    assert r.status_code==422
    assert 'Traceback' not in r.text

def test_csrf_auth_expiry_and_generic_failures(web):
    c,s=web
    assert c.get('/api/bank/accounts').status_code==401
    assert c.post('/api/bank/auth/login',headers={'X-Nexus-Request':''},json={}).status_code==403
    account=register_login(c)
    assert c.get('/api/bank/accounts/'+str(uuid4())).status_code==404
    assert c.post('/api/bank/auth/logout',headers={'Origin':'http://untrusted.invalid'}).status_code==403
    with sqlite3.connect(s.database_path) as db:db.execute('UPDATE nexus_sessions SET expires_at=0')
    assert c.get('/api/bank/accounts').status_code==401

def test_http_transfer_full_flow_two_customers_and_retry(web):
    c,s=web
    alice=register_login(c)
    c.post('/api/bank/auth/logout')
    bob=register_login(c,'bob.demo')
    assert c.get('/api/bank/accounts/'+alice).status_code==404
    c.post('/api/bank/auth/logout')
    c.post('/api/bank/auth/login',json={'username':'alice.demo','password':'SYNTHETIC-Password-123'})
    assert c.post('/api/bank/beneficiaries',json={'destination_account_id':bob,'label':'Fictional Bob'}).status_code==201
    Bank(s.database_path).fund(alice,10000,'explicit-http-test-funding')
    body={'source_account_id':alice,'destination_account_id':bob,'amount_minor':1200,'currency':'INR','idempotency_key':str(uuid4())}
    first=c.post('/api/bank/transfers',json=body)
    second=c.post('/api/bank/transfers',json=body)
    assert first.status_code==second.status_code==201 and first.json()==second.json()
    assert c.get('/api/bank/accounts/'+alice).json()['available_balance_minor']==8800
    assert c.get('/api/bank/transfers/'+first.json()['id']).status_code==200
    c.post('/api/bank/auth/logout')
    c.post('/api/bank/auth/login',json={'username':'bob.demo','password':'SYNTHETIC-Password-123'})
    assert c.get('/api/bank/accounts/'+bob).json()['available_balance_minor']==1200
    assert c.get('/api/bank/accounts/'+bob+'/transactions').json()[0]['amount_minor']==1200
    assert c.get('/api/bank/transfers/'+first.json()['id']).status_code==404

def test_unknown_fields_and_destination_mismatch_never_use_golden_removals(web):
    c,s=web; account=register_login(c)
    bank=Bank(s.database_path); owner=bank.authenticate(c.cookies.get('nexus_session'))['id']
    payload=bank.account(owner,account); payload['new_contract_field']='SYNTHETIC_UNKNOWN'
    from veilmint.demo import golden_analysis
    p=BankProtection(s)
    with PolicyStore(p.policy_path) as store:
        golden=store.create_revision(golden_analysis())
        store.review(golden.revision.revision_id,'Synthetic wrong destination',tuple(f.name for f in golden.fields if f.removal_allowed))
    assert p.protect(payload).payload==payload
    with PolicyStore(p.policy_path) as store:
        current=store.create_revision(account_report())
        store.review(current.revision.revision_id,'Synthetic endpoint review',('legacy_display_label',))
    result=p.protect(payload)
    assert result.payload['new_contract_field']=='SYNTHETIC_UNKNOWN'
    assert result.warnings and 'legacy_display_label' not in result.payload
    assert result.payload['available_balance_minor']==payload['available_balance_minor']

def test_used_field_approval_rejected_for_bank_destination(web):
    c,s=web; register_login(c)
    h={'X-VEILMINT-Operator':s.operator_token}
    draft=c.post('/api/bank-policy/revisions',json={},headers=h).json()['policy']['revision']
    body={k:draft[k] for k in ('revision_id','analysis_digest','inputs_digest')}
    body.update({'reviewer':'Synthetic reviewer','approved_fields':['available_balance_minor']})
    assert c.post('/api/bank-policy/review',json=body,headers=h).status_code==409

def test_log_failure_never_writes_raw_event(web,monkeypatch,caplog):
    c,s=web; account=register_login(c)
    with sqlite3.connect(s.database_path) as db: before=db.execute('SELECT count(*) FROM veilmint_protected_logs').fetchone()[0]
    def fail(*a,**k):raise RuntimeError('PRIVATE_RAW_EVENT_FAILURE')
    monkeypatch.setattr('veilmint.bank.protection.StructuredLogPipeline.process',fail)
    response=c.get('/api/bank/accounts/'+account)
    assert response.status_code==503 and 'PRIVATE_RAW_EVENT_FAILURE' not in response.text
    assert 'PRIVATE_RAW_EVENT_FAILURE' not in caplog.text
    with sqlite3.connect(s.database_path) as db: assert db.execute('SELECT count(*) FROM veilmint_protected_logs').fetchone()[0]==before

def test_readiness_and_old_policy_history_survive_bank_migration(tmp_path):
    from veilmint.demo import golden_analysis
    path=tmp_path/'upgrade.sqlite3'
    with PolicyStore(path) as store:
        old=store.create_revision(golden_analysis())
        approved=store.review(old.revision.revision_id,'Synthetic old reviewer',())
    Bank(path)
    with PolicyStore(path) as store: assert store.get().to_dict()==approved.to_dict()
    with TestClient(create_app(Settings(database_path=path))) as c:
        assert c.get('/ready').json()['database']=='available'

def test_inactive_destination_insufficient_and_self_transfer_do_not_mutate(domain):
    bank,a,b=domain
    bank.fund(a['account_id'],1000,'limited')
    for destination,amount in ((b['account_id'],1001),(a['account_id'],100),(str(uuid4()),100)):
        with pytest.raises(BankError):bank.transfer(a['customer_id'],a['account_id'],destination,amount,'INR',str(uuid4()))
    with bank.connection(True) as db:db.execute("UPDATE nexus_accounts SET status='CLOSED' WHERE id=?",(b['account_id'],))
    with pytest.raises(BankError):bank.transfer(a['customer_id'],a['account_id'],b['account_id'],100,'INR',str(uuid4()))
    assert bank.account(a['customer_id'],a['account_id'])['available_balance_minor']==1000
    with bank.connection() as db:assert db.execute('SELECT count(*) FROM nexus_transfers').fetchone()[0]==0

def test_concurrent_same_key_posts_only_one_ledger_pair(domain):
    bank,a,b=domain;bank.fund(a['account_id'],10000,'same-key-funding')
    args=(a['customer_id'],a['account_id'],b['account_id'],1000,'INR','same-parallel-key')
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:bank.transfer(*args),range(2)))
    assert results[0]==results[1]
    with bank.connection() as db:
        assert db.execute('SELECT count(*) FROM nexus_transfers').fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM nexus_ledger WHERE kind='TRANSFER'").fetchone()[0]==2

def test_bank_observe_warn_and_stale_analysis_preserve_compatibility_field(domain):
    bank,a,b=domain
    from dataclasses import replace
    from veilmint.runtime.api import RuntimeMode
    settings=Settings(database_path=bank.path)
    protection=BankProtection(settings)
    with PolicyStore(protection.policy_path) as store:
        p=store.create_revision(account_report())
        store.review(p.revision.revision_id,'Synthetic review',('legacy_display_label',))
    payload=bank.account(a['customer_id'],a['account_id'])
    for mode in (RuntimeMode.OBSERVE,RuntimeMode.WARN):
        assert BankProtection(replace(settings,bank_mode=mode)).protect(payload).payload==payload
    changed=account_report();changed['analysis']['contract_digest']='changed-contract'
    with PolicyStore(protection.policy_path) as store:
        p=store.create_revision(changed)
        store.review(p.revision.revision_id,'Synthetic stale review',('legacy_display_label',))
    result=protection.protect(payload)
    assert result.payload==payload and not result.policy_valid

def test_login_throttle_and_session_hash_storage(domain):
    bank,a,b=domain
    token=bank.login('alice.demo','SYNTHETIC-Password-123')
    with bank.connection() as db:
        stored=db.execute('SELECT token_hash FROM nexus_sessions').fetchone()[0]
        assert token!=stored and len(stored)==64
    for _ in range(9):
        with pytest.raises(BankError):bank.login('alice.demo','Incorrect-demo-password')
    with pytest.raises(BankError) as error:bank.login('alice.demo','SYNTHETIC-Password-123')
    assert error.value.status==429

def test_operator_proxy_credential_does_not_allow_foreign_origin(web):
    c,s=web
    response=c.post('/api/bank-policy/revisions',json={},headers={'X-VEILMINT-Operator':s.operator_token,'Origin':'http://untrusted.invalid'})
    assert response.status_code==403
