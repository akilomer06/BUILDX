import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from veilmint.bank.service import Bank
from veilmint.consumer_lab import ConsumerLab, CONSUMERS, paths
from veilmint.config import Settings
from veilmint.policy.store import PolicyStore
from veilmint.server import create_app

@pytest.fixture
def lab(tmp_path):
    settings=Settings(database_path=tmp_path/'bank.sqlite3',operator_token='SYNTHETIC-OPERATOR-12345678901234567890')
    bank=Bank(settings.database_path);account=bank.register('FICTIONAL DEMO HOLDER','demo.holder','SYNTHETIC-Password-123')
    bank.fund(account['account_id'],12345,'explicit-test')
    service=ConsumerLab(settings);service.seed(account['account_id'])
    return settings,bank,account,service

def approve(service,consumer):
    service.prepare(consumer)
    with PolicyStore(service.policy_path(consumer)) as store:
        p=store.get();store.review(p.revision.revision_id,'Explicit synthetic TEST reviewer',[f.name for f in p.fields if f.removal_allowed])

def test_four_consumers_actual_approved_field_sets_and_canonical_persistence(lab):
    settings,bank,account,service=lab;source=service.producer(account['account_id']);results={}
    for consumer in CONSUMERS:
        approve(service,consumer)
        result=service.execute(account['account_id'],consumer,'ENFORCE')
        assert result['policy_valid'] and result['baseline']['preview']==source
        assert result['source_version']==service.execute(account['account_id'],consumer,'OBSERVE')['source_version']
        assert len(result['protected']['field_paths'])<len(result['baseline']['field_paths'])
        assert result['protected']['byte_count']==len(json.dumps(result['protected']['preview'],ensure_ascii=False,separators=(',',':')).encode())
        assert result['log']['protected']['event']['correlation_id']==result['trace_id']
        assert 'FICTIONAL DEMO SUPPORT NOTE' not in json.dumps(result['log'])
        results[consumer]=set(result['protected']['preview'])
        assert service.verify(account['account_id'],consumer)['status']=='PASS'
    assert len({tuple(sorted(keys)) for keys in results.values()})==4
    assert 'email' in results['notifications'] and 'email' not in results['payments']
    assert 'internal_risk_flag' in results['risk'] and 'internal_risk_flag' not in results['overview']
    assert service.producer(account['account_id'])==source
    assert ConsumerLab(settings).producer(account['account_id'])==source
    assert bank.account(account['customer_id'],account['account_id'])['available_balance_minor']==12345

@pytest.mark.parametrize('mode',['OBSERVE','WARN','ENFORCE'])
def test_pending_and_active_modes_are_truthful(lab,mode):
    _,_,account,service=lab
    pending=service.execute(account['account_id'],'payments',mode)
    assert not pending['policy_valid'] and pending['baseline']['preview']==pending['protected']['preview']
    approve(service,'payments');r=service.execute(account['account_id'],'payments',mode)
    assert r['actual_runtime_mode']==mode
    assert (r['baseline']['preview']==r['protected']['preview'])==(mode!='ENFORCE')

def test_stale_policy_unknown_field_and_used_field_safety(lab,monkeypatch):
    _,_,a,service=lab;approve(service,'payments')
    original=service.producer
    monkeypatch.setattr(service,'producer',lambda account:original(account)|{'new_unmapped_field':'DEMO-UNKNOWN'})
    r=service.execute(a['account_id'],'payments','ENFORCE')
    assert r['protected']['preview']['new_unmapped_field']=='DEMO-UNKNOWN' and r['warnings']
    assert '/new_unmapped_field' in r['unknown_fields']
    assert next(d for d in r['decisions'] if d['field']=='new_unmapped_field')['action']=='UNKNOWN'
    service.prepare('payments',True)
    assert not service.execute(a['account_id'],'payments','ENFORCE')['policy_valid']
    with PolicyStore(service.policy_path('payments')) as store:
        with pytest.raises(ValueError):store.review(store.get().revision.revision_id,'TEST reviewer',['account_id'])

def test_http_operator_binding_review_and_customer_denial(lab):
    settings,_,account,service=lab
    with TestClient(create_app(settings)) as operator,TestClient(create_app(settings)) as customer:
        operator.headers['X-VEILMINT-Operator']=settings.operator_token
        assert customer.post('/api/operator/consumer-lab/run',json={'account_id':account['account_id'],'consumer':'risk'}).status_code==403
        assert operator.post('/api/operator/consumer-lab/run',json={'account_id':account['account_id'],'consumer':'admin'}).status_code==422
        prepared=operator.post('/api/operator/consumer-lab/policies/notifications/revisions',json={}).json()
        revision=prepared['policy']['revision']
        body={key:revision[key] for key in ('revision_id','analysis_digest','inputs_digest')}
        body.update(reviewer='Explicit TEST reviewer',approved_fields=[f['name'] for f in prepared['policy']['fields'] if f['removal_allowed']])
        assert operator.post('/api/operator/consumer-lab/policies/notifications/review',json=body).status_code==200
        response=operator.post('/api/operator/consumer-lab/run',json={'account_id':account['account_id'],'consumer':'notifications'} )
        assert response.status_code==200 and response.json()['policy_valid']
        assert response.headers['x-request-id']==response.json()['trace_id']==response.json()['log']['protected']['event']['correlation_id']
        body['analysis_digest']='0'*64
        assert operator.post('/api/operator/consumer-lab/policies/notifications/review',json=body).status_code==409

def test_no_implicit_seed_and_empty_container_counts(lab):
    _,bank,_,service=lab
    fresh=bank.register('DEMO CLEAN','demo.clean','SYNTHETIC-Password-456')
    with pytest.raises(ValueError):service.producer(fresh['account_id'])
    assert bank.transactions(fresh['customer_id'],fresh['account_id'])==[]
    assert paths({'a':[],'b':None})==['/a','/b']

def test_http_matrix_same_source_and_scoped_canary_requires_review(lab):
    settings,_,account,service=lab
    assert service.verify(account['account_id'],'overview')['status']=='FAIL'
    for consumer in CONSUMERS:approve(service,consumer)
    with TestClient(create_app(settings)) as operator:
        operator.headers['X-VEILMINT-Operator']=settings.operator_token
        response=operator.post('/api/operator/consumer-lab/matrix',json={'account_id':account['account_id'],'consumer':'overview'})
        assert response.status_code==200
        rows=response.json()['results']
        assert len(rows)==4 and len({r['source_version'] for r in rows})==1
        assert len({tuple(sorted(r['protected']['preview'])) for r in rows})==4
        verified=operator.post('/api/operator/consumer-lab/verify',json={'account_id':account['account_id'],'consumer':'risk'})
        assert verified.json()['status']=='PASS'
