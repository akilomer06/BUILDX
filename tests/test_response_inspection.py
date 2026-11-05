"""Selected live requests: exact snapshots, server masking, and bank stability."""
from copy import deepcopy
import sqlite3

from fastapi.testclient import TestClient
import pytest

from veilmint.bank.service import Bank
from veilmint.config import Settings
from veilmint.response_inspection import ResponseSnapshots, protect_snapshot
from veilmint.server import create_app

@pytest.fixture
def live(tmp_path):
    settings=Settings(database_path=tmp_path/'live.sqlite3',response_inspection_demo=True,
                      operator_token='SYNTHETIC-OPERATOR-12345678901234567890')
    app=create_app(settings)
    with TestClient(app) as customer,TestClient(app) as operator:
        customer.headers['X-Nexus-Request']='1'
        operator.headers['X-VEILMINT-Operator']=settings.operator_token
        account=customer.post('/api/bank/auth/register',json={'display_name':'Fictional selected holder','username':'live.customer','password':'SYNTHETIC-Password-123'}).json()['account_id']
        login=customer.post('/api/bank/auth/login',json={'username':'live.customer','password':'SYNTHETIC-Password-123'})
        Bank(settings.database_path).fund(account,12345,'explicit-live-test')
        yield customer,operator,settings,account,app,login


def test_selected_snapshot_is_exact_and_frozen_through_five_mode_cycles(live):
    c,o,s,account,app,_=live
    actual=c.get('/api/bank/accounts/'+account)
    correlation=actual.headers['x-request-id']
    # A later balance change must not change this request's recorded response.
    Bank(s.database_path).fund(account,100,'later-explicit-funding')
    with sqlite3.connect(s.database_path) as db:
        event_count=db.execute('SELECT count(*) FROM nexus_security_events').fetchone()[0]
        log_count=db.execute('SELECT count(*) FROM veilmint_protected_logs').fetchone()[0]
    for _ in range(5):
        standard=o.get('/api/operator/responses/'+correlation+'/standard')
        protected=o.get('/api/operator/responses/'+correlation+'/veilmint')
        assert standard.content==actual.content
        assert standard.json()['available_balance_minor']==12345
        assert standard.status_code==protected.status_code==actual.status_code==200
        assert standard.headers['x-captured-correlation-id']==protected.headers['x-captured-correlation-id']==correlation
        assert standard.headers['x-captured-endpoint']=='/api/bank/accounts/{account_id}'
        assert standard.headers['x-captured-method']=='GET'
        assert protected.headers['content-type']=='application/json'
        assert protected.headers['x-content-type-options']=='nosniff'
        assert protected.headers['cache-control']=='no-store'
        data=protected.json()
        assert data['account_id']=='********'+account[-4:]
        assert data['display_name']!='Fictional selected holder'
        assert data['available_balance_minor']==12345 and data['currency']=='INR'
        assert account not in protected.text and 'Fictional selected holder' not in protected.text
        assert '/account_id' in protected.headers['x-privacy-masked-fields']
        assert protected.headers['x-privacy-removed-fields']==''  # no invented PAN/address fields
        for response in (standard,protected):
            assert int(response.headers['x-privacy-response-bytes'])==len(response.content)
            assert int(response.headers['x-privacy-standard-bytes'])==len(actual.content)
            assert int(response.headers['x-privacy-reduction-bytes'])==len(actual.content)-len(response.content)
        for secret in ('SYNTHETIC-Password-123',c.cookies.get('nexus_session'),s.operator_token):
            assert secret not in protected.text+str(dict(protected.headers))
    with sqlite3.connect(s.database_path) as db:
        assert db.execute('SELECT count(*) FROM nexus_security_events').fetchone()[0]==event_count
        assert db.execute('SELECT count(*) FROM veilmint_protected_logs').fetchone()[0]==log_count
    # Operator mode does not mask customer operational IDs or change balances.
    assert c.get('/api/bank/accounts/'+account).json()['account_id']==account
    assert Bank(s.database_path).account(Bank(s.database_path).authenticate(c.cookies.get('nexus_session'))['id'],account)['available_balance_minor']==12445


def test_lists_errors_and_auth_exclusion_are_truthful(live):
    c,o,s,account,app,login=live
    for path in ('/api/bank/accounts','/api/bank/accounts/'+account+'/transactions','/api/bank/beneficiaries','/api/bank/customers/me','/api/bank/accounts/999999999999'):
        actual=c.get(path);correlation=actual.headers['x-request-id']
        standard=o.get('/api/operator/responses/'+correlation+'/standard')
        assert standard.status_code==actual.status_code
        assert standard.content==actual.content
        assert o.get('/api/operator/responses/'+correlation+'/veilmint').status_code==actual.status_code
    assert app.state.response_snapshots.get(login.headers['x-request-id']) is None
    assert o.get('/api/operator/responses/'+login.headers['x-request-id']+'/standard').status_code==404
    assert o.get('/api/operator/responses/missing/standard').status_code==404
    assert c.get('/api/operator/responses/missing/standard').status_code==403
    assert o.post('/api/operator/responses/missing/standard',json={}).status_code==405
    assert o.get('/api/demo/standard/account-summary').status_code==404


def test_buffer_expiry_eviction_size_limits_copy_and_safe_headers():
    clock=[0]
    cache=ResponseSnapshots(limit=2,ttl=10,max_body_bytes=100,clock=lambda:clock[0])
    def put(key,body):return cache.put(key,'/api/bank/accounts','GET',200,'1.1',{'content-type':'application/json','set-cookie':'PRIVATE_COOKIE','authorization':'PRIVATE_AUTH'},body)
    assert put('first',{'value':1})
    snapshot=cache.get('first');snapshot['body']['value']=2
    assert cache.get('first')['body']['value']==1
    assert 'PRIVATE_COOKIE' not in str(cache.get('first'))
    assert 'PRIVATE_AUTH' not in str(cache.get('first'))
    assert not put('oversized',{'value':'x'*101})
    put('second',[]);put('third',{})
    assert cache.get('first') is None and cache.get('second') is not None
    clock[0]=11
    assert cache.get('second') is None and cache.get('third') is None


def test_recursive_masking_and_removals_are_actual_and_do_not_mutate_source():
    source={'status':'success','data':{'accountId':'123456781234','availableBalance':45000.50,'currency':'INR',
        'email':'demo@example.invalid','phoneNumber':'+91 00000 00042','panNumber':'FICTIONAL-PAN',
        'homeAddress':'FICTIONAL-ADDRESS','cibilScore':742},'items':[{'account_id':'987654321234','display_name':'Fictional B'}]}
    before=deepcopy(source)
    protected,masked,removed,exposed=protect_snapshot(source)
    assert protected['data']['accountId']=='********1234'
    assert protected['data']['availableBalance']==45000.50 and protected['data']['currency']=='INR'
    assert set(removed)=={'/data/panNumber','/data/homeAddress','/data/cibilScore'}
    assert '/items/0/account_id' in masked
    assert set(exposed)==set(masked+removed)
    assert source==before and 'FICTIONAL-PAN' not in str(protected)


def test_disabled_by_default_and_capture_failure_does_not_change_bank_response(tmp_path,live,monkeypatch):
    with TestClient(create_app(Settings(database_path=tmp_path/'disabled.sqlite3'))) as disabled:
        assert disabled.get('/api/operator/responses/any/standard').status_code==404
    c,o,s,account,app,_=live
    def fail(*args):raise RuntimeError('PRIVATE_CAPTURE_FAILURE')
    monkeypatch.setattr(app.state.response_snapshots,'put',fail)
    response=c.get('/api/bank/accounts/'+account)
    assert response.status_code==200 and response.json()['account_id']==account
    assert o.get('/api/operator/responses/'+response.headers['x-request-id']+'/standard').status_code==404


def test_audit_failure_never_exposes_an_unsent_success_body(live,monkeypatch):
    c,o,s,account,app,_=live
    def fail(*args,**kwargs):raise RuntimeError('PRIVATE_AUDIT_FAILURE')
    monkeypatch.setattr('veilmint.bank.protection.StructuredLogPipeline.process',fail)
    response=c.get('/api/bank/accounts/'+account)
    assert response.status_code==503
    assert app.state.response_snapshots.get(response.headers['x-request-id']) is None


def test_inspection_setting_is_explicit(monkeypatch):
    monkeypatch.delenv('VEILMINT_RESPONSE_INSPECTION_DEMO',raising=False)
    assert not Settings.from_env().response_inspection_demo
    monkeypatch.setenv('VEILMINT_RESPONSE_INSPECTION_DEMO','true')
    assert Settings.from_env().response_inspection_demo
