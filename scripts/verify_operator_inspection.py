"""Opt-in local Docker acceptance for operator inspection; uses fictional test records."""
import json,os,secrets,shutil,subprocess
from pathlib import Path
from uuid import uuid4
import httpx
root=Path(__file__).resolve().parents[1]
docker=shutil.which('docker') or str(Path(os.environ['LOCALAPPDATA'])/'Programs/DockerDesktop/resources/bin/docker.exe')
suffix=uuid4().hex[:10]
password=secrets.token_urlsafe(24)
marker='SYNTHETIC_HEADER_CHECK_'+uuid4().hex
with httpx.Client(base_url='http://127.0.0.1:8081',headers={'X-Nexus-Request':'1'},timeout=30) as customer,httpx.Client(base_url='http://127.0.0.1:8080',timeout=30) as operator:
    username='inspectionverify.'+suffix
    result=customer.post('/api/bank/auth/register',json={'display_name':'Fictional inspector verification','username':username,'password':password})
    assert result.status_code==201,result.text
    account=result.json()['account_id']
    assert len(account)==12 and account.isascii() and account.isdigit()
    assert customer.post('/api/bank/auth/login',json={'username':username,'password':password}).status_code==200
    for args in (['demo-profile','--account',account,'--synthetic-only'],['fund','--account',account,'--amount-minor','10000','--reference','inspection-'+suffix,'--sandbox-funds']):
        subprocess.run([docker,'compose','exec','-T','backend','python','-m','veilmint','bank',*args],cwd=root,check=True,stdout=subprocess.DEVNULL)
    response=customer.get('/api/bank/accounts/'+account,headers={'Authorization':'Bearer '+marker,'X-API-Key':marker})
    assert response.status_code==200
    correlation=response.headers['x-request-id']
    assert response.json()['available_balance_minor']==10000
    assert response.json()['currency']=='INR'
    assert 'customer_phone' not in response.json() and 'account_number' not in response.json()
    detail=operator.get('/api/operator/accounts/'+account).json()
    assert detail['source_record']['display_name']==detail['source_record']['customer_phone']=='[REDACTED]'
    reveal=operator.get('/api/operator/accounts/'+account+'?reveal=true').json()
    assert reveal['source_record']['contact_email'].endswith('@example.invalid')
    assert reveal['source_record']['customer_phone'].startswith('DEMO-PHONE-')
    assert 'password_hash' not in json.dumps(reveal) and password not in json.dumps(reveal)
    event=next(e for e in detail['events'] if e['correlation_id']==correlation)
    evidence=operator.get('/api/operator/events/'+str(event['id'])).json()
    log=evidence['persisted']['event']
    assert log['display_name']==log['customer_phone']==log['contact_email']=='[REDACTED]'
    assert 'available_balance_minor' not in log and 'recent_transactions' not in log
    assert marker not in json.dumps(evidence) and customer.cookies.get('nexus_session') not in json.dumps(evidence)
    cookie=next(h for h in event['header_actions'] if h['name']=='Cookie')
    authorization=next(h for h in event['header_actions'] if h['name']=='Authorization')
    assert cookie['present'] and authorization['present'] and authorization['action']=='EXCLUDE_FROM_LOG'
    assert customer.get('/api/operator/accounts?reveal=true').status_code==404
    assert operator.post('/api/operator/accounts/'+account,json={'balance':9999}).status_code==405
    summary={'account_id':account,'correlation_id':correlation,'event_id':event['id'],'persisted_log_id':evidence['persisted']['id'],
             'numeric_account_id':'PASS','currency':'INR',
             'default_masking':'PASS','temporary_reveal_projection':'PASS','credential_exclusion':'PASS',
             'profile_masking':'PASS','financial_drop':'PASS','authentication_header_exclusion':'PASS',
             'read_only_and_customer_boundary':'PASS','contract_exclusions':event['contract_excluded_paths'],
             'approved_api_removals':event['removed_paths']}
    (root/'data'/'operator-inspection-verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
