"""Read-only acceptance using an actual recent bank request already in traffic."""
import json
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
def at(body,path):
    for segment in path.lstrip('/').split('/'):
        key=segment.replace('~1','/').replace('~0','~')
        body=body[int(key)] if isinstance(body,list) else body[key]
    return body

with httpx.Client(base_url='http://127.0.0.1:8080',timeout=15) as operator:
    events=operator.get('/api/traffic').json()['events']
    selected=None
    for event in events:
        if event['endpoint']=='/api/bank/accounts/{account_id}' and event['http_status']==200:
            candidate=operator.get('/api/operator/responses/'+event['correlation_id']+'/standard')
            if candidate.headers.get('x-captured-correlation-id')==event['correlation_id']:
                selected=event;break
    assert selected,'Refresh an account in the customer bank, then run this check again.'
    correlation=selected['correlation_id']
    source=candidate.content
    for _ in range(5):
        standard=operator.get('/api/operator/responses/'+correlation+'/standard')
        protected=operator.get('/api/operator/responses/'+correlation+'/veilmint')
        assert standard.content==source
        assert standard.status_code==protected.status_code==selected['http_status']
        assert standard.headers['x-captured-endpoint']==selected['endpoint']
        assert standard.headers['x-captured-method']==selected['method']
        assert protected.headers['x-captured-correlation-id']==correlation
        assert protected.headers['x-content-type-options']=='nosniff'
        assert protected.headers['cache-control']=='no-store'
        original=standard.json();output=protected.json()
        masks=protected.headers['x-privacy-masked-fields'].split(',') if protected.headers['x-privacy-masked-fields'] else []
        removals=protected.headers['x-privacy-removed-fields'].split(',') if protected.headers['x-privacy-removed-fields'] else []
        for path in masks:
            assert at(original,path)!=at(output,path) and '*' in at(output,path)
        assert output['currency']==original['currency']=='INR'
        assert output['available_balance_minor']==original['available_balance_minor']
        assert int(protected.headers['x-privacy-response-bytes'])==len(protected.content)
        assert int(protected.headers['x-privacy-standard-bytes'])==len(source)
        assert int(protected.headers['x-privacy-reduction-bytes'])==len(source)-len(protected.content)
        assert 'set-cookie' not in protected.headers and 'authorization' not in protected.headers
    with httpx.Client(base_url='http://127.0.0.1:8081',timeout=15) as customer:
        assert customer.get('/api/operator/responses/'+correlation+'/standard').status_code==404
        assert customer.get('/api/operator/responses/'+correlation+'/veilmint').status_code==404
    assert operator.get('/api/demo/standard/account-summary').status_code==404
    evidence={'live_selected_response':'PASS','correlation_id':correlation,'http_status':standard.status_code,
              'http_version':standard.headers['x-captured-http-version'],'mode_cycles':5,
              'masked':len(masks),'removed':len(removals),'standard_bytes':len(source),'veilmint_bytes':len(protected.content),
              'bank_balance_and_currency':'unchanged','customer_operator_boundary':'PASS','standalone_comparison':'removed'}
    (root/'data').mkdir(exist_ok=True)
    (root/'data'/'response-inspection-verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence,indent=2))
