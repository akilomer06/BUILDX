"""Real local Docker HTTP verification; creates clearly fictional verification customers."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from uuid import uuid4
import httpx

root=Path(__file__).resolve().parents[1]
docker=shutil.which('docker')
if not docker and os.name=='nt':
    candidate=Path(os.environ['LOCALAPPDATA'])/'Programs/DockerDesktop/resources/bin/docker.exe'
    if candidate.exists():docker=str(candidate)
if not docker:raise RuntimeError('Docker CLI unavailable')

def command(*args):
    subprocess.run([docker,'compose',*args],cwd=root,check=True,stdout=subprocess.DEVNULL)

suffix=uuid4().hex[:12]
password=secrets.token_urlsafe(24)
with httpx.Client(base_url='http://127.0.0.1:8081',headers={'X-Nexus-Request':'1'},timeout=30) as alice, httpx.Client(base_url='http://127.0.0.1:8081',headers={'X-Nexus-Request':'1'},timeout=30) as bob, httpx.Client(base_url='http://127.0.0.1:8080',timeout=30) as operator:
    assert alice.get('/bank/').status_code==200
    assert operator.get('/health').json()['status']=='ready'
    golden=operator.get('/api/policy').json()['policy']['revision']['revision_id']
    for path in ('/api/policy','/api/traffic','/api/bank-policy','/.env','/docs','/index.html'):
        assert alice.get(path,headers={'X-VEILMINT-Operator':'forged-customer-header'}).status_code==404,path
    accounts=[]
    for client,name in ((alice,'Alice'),(bob,'Bob')):
        username='phase8verify.'+name.lower()+'.'+suffix
        r=client.post('/api/bank/auth/register',json={'display_name':'Fictional verification '+name,'username':username,'password':password})
        assert r.status_code==201,r.text
        assert client.post('/api/bank/auth/login',json={'username':username,'password':password}).status_code==200
        account=client.get('/api/bank/accounts').json()[0]['account_id']
        assert client.get('/api/bank/accounts/'+account+'/transactions').json()==[]
        assert client.get('/api/bank/accounts/'+account).json()['available_balance_minor']==0
        accounts.append(account)
    source,destination=accounts
    assert alice.get('/api/bank/accounts/'+destination).status_code==404
    command('exec','-T','backend','python','-m','veilmint','bank','fund','--account',source,'--amount-minor','10000','--reference','phase8-verification-'+suffix,'--sandbox-funds')
    assert alice.post('/api/bank/beneficiaries',json={'destination_account_id':destination,'label':'Fictional verification recipient'}).status_code==201
    transfer={'source_account_id':source,'destination_account_id':destination,'amount_minor':1234,'currency':'INR','idempotency_key':str(uuid4())}
    assert all(len(value)==12 and value.isascii() and value.isdigit() for value in (source,destination))
    first=alice.post('/api/bank/transfers',json=transfer)
    second=alice.post('/api/bank/transfers',json=transfer)
    assert first.status_code==second.status_code==201 and first.json()==second.json()
    receipt=first.json()
    assert receipt['currency']=='INR' and receipt['source']==source and receipt['destination']==destination
    assert alice.get('/api/bank/accounts/'+source).json()['available_balance_minor']==8766
    assert bob.get('/api/bank/accounts/'+destination).json()['available_balance_minor']==1234
    assert bob.get('/api/bank/accounts/'+destination+'/transactions').json()[0]['amount_minor']==1234
    state=operator.get('/api/bank-policy').json()
    if state['policy'] is None:
        state=operator.post('/api/bank-policy/revisions',json={}).json()
    policy_before=state['policy']['revision']['revision_id']
    # No automatic bank candidate approval: operator review is still required.
    account_response=alice.get('/api/bank/accounts/'+source)
    correlation=account_response.headers['x-request-id']
    events=operator.get('/api/traffic').json()['events']
    event=next(e for e in events if e['correlation_id']==correlation)
    assert event['endpoint']=='/api/bank/accounts/{account_id}'
    assert event['destination']=='nexus_bank.account_summary.v1' and event['log_outcome']=='SANITIZED'
    assert 'password' not in json.dumps(event).lower()
    inspection="import json; from veilmint.runtime.logs import LogSink; print(json.dumps(LogSink('/data/synthetic-demo.sqlite3').get("+str(event['log_record_id'])+")))"
    persisted=json.loads(subprocess.check_output([docker,'compose','exec','-T','backend','python','-c',inspection],cwd=root))
    assert persisted['event']['correlation_id']==correlation
    assert persisted['event']['customer_reference']=='[REDACTED]'
    assert password not in json.dumps(persisted)
    assert alice.cookies.get('nexus_session') not in json.dumps(persisted)
    evidence={'customer_url':'http://localhost:8081/bank/','operator_url':'http://localhost:8080',
              'http_workflow':'PASS','idempotency':'PASS','ledger_pair':'PASS','customer_operator_boundary':'PASS',
              'correlation_id':correlation,'endpoint':event['endpoint'],'destination':event['destination'],
              'policy_revision':event['policy_revision'],'bank_review_revision':policy_before,
              'bank_review_status':state['policy']['revision']['status'],
              'api_field_count':len(account_response.json()),'removed_paths':event['removed_paths'],
              'log_record_id':event['log_record_id'],'log_outcome':event['log_outcome'],
              'sanitized_customer_reference':persisted['event']['customer_reference'],
              'two_physical_devices':'NOT VERIFIED'}
    command('restart')
    command('up','-d','--wait','--wait-timeout','90')
    assert alice.get('/api/bank/accounts/'+source).json()['available_balance_minor']==8766
    assert bob.get('/api/bank/accounts/'+destination).json()['available_balance_minor']==1234
    assert alice.get('/api/bank/transfers/'+receipt['id']).json()==receipt
    assert operator.get('/api/bank-policy').json()['policy']['revision']['revision_id']==policy_before
    assert operator.get('/api/policy').json()['policy']['revision']['revision_id']==golden
    canary=operator.post('/api/verify',json={}).json()
    assert canary['status']=='PASS'
    evidence.update({'restart_sessions_ledger_and_policy':'PASS','original_golden_canary':'PASS','canary_run_id':canary['run_id']})
    (root/'data'/'phase8-docker-verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence,indent=2))
