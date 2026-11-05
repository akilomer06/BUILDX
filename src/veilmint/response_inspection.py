"""Opt-in, volatile HTTP response inspection for the local bank sandbox.

Only explicitly supplied customer DTOs are captured. Credentials, request
bodies and session headers never enter this buffer or its operator projections.
Nothing here writes to a log, policy store or bank database.
"""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
import json
from threading import RLock
from time import monotonic

from fastapi import APIRouter, HTTPException, Response

from .runtime.masking import mask_api_identifiers

MASK_RULES={
    'account_id':'account','accountId':'account','customer_id':'account',
    'source':'account','destination':'account','source_account_id':'account','destination_account_id':'account',
    'id':'account','display_name':'name','full_name':'name','fullName':'name','account_holder':'name','label':'name',
    'email':'email','contact_email':'email','phone_number':'phone','phoneNumber':'phone','customer_phone':'phone',
}
REMOVE_FIELDS={'pan_number','panNumber','home_address','homeAddress','customer_address','cibil_score','cibilScore','aadhaar_number'}
SAFE_HEADERS=('content-type','x-content-type-options','cache-control','x-request-id')


def encode(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')


def capture_response(request,payload,status=200):
    """Mark the exact route return value; final middleware confirms its status."""
    if request.app.state.settings.response_inspection_demo and request.url.path.startswith('/api/bank/') and not request.url.path.startswith('/api/bank/auth/'):
        request.state.inspection_payload=payload
        request.state.inspection_status=status
    return payload


class ResponseSnapshots:
    def __init__(self,*,limit=100,ttl=900,max_body_bytes=65536,clock=monotonic):
        self.limit=limit;self.ttl=ttl;self.max_body_bytes=max_body_bytes;self.clock=clock
        self._entries=OrderedDict();self._lock=RLock()

    def _prune(self):
        now=self.clock()
        for key in [key for key,(expiry,_) in self._entries.items() if expiry<=now]:
            del self._entries[key]

    def put(self,correlation_id,endpoint,method,status,http_version,headers,payload):
        body=encode(payload)
        if len(body)>self.max_body_bytes:return False
        safe={name:headers[name] for name in SAFE_HEADERS if name in headers}
        snapshot={'correlation_id':correlation_id,'endpoint':endpoint,'method':method,'http_status':status,
                  'http_version':http_version,'headers':safe,'captured_at':datetime.now(timezone.utc).isoformat(),
                  'body':json.loads(body)}
        with self._lock:
            self._prune()
            self._entries[correlation_id]=(self.clock()+self.ttl,snapshot)
            self._entries.move_to_end(correlation_id)
            while len(self._entries)>self.limit:self._entries.popitem(last=False)
        return True

    def get(self,correlation_id):
        with self._lock:
            self._prune()
            entry=self._entries.get(correlation_id)
            return deepcopy(entry[1]) if entry else None


def protect_snapshot(payload):
    """Apply operator API-view rules recursively, collecting actual JSON paths."""
    masked=[];removed=[];exposed=[]
    def walk(value,path=''):
        if isinstance(value,list):return [walk(item,path+'/'+str(i)) for i,item in enumerate(value)]
        if not isinstance(value,dict):return value
        result={}
        for key,item in value.items():
            pointer=path+'/'+key.replace('~','~0').replace('/','~1')
            if key in REMOVE_FIELDS:
                removed.append(pointer);exposed.append(pointer)
            elif key in MASK_RULES and item is not None:
                result[key]=mask_api_identifiers({key:item},{key:MASK_RULES[key]})[key]
                masked.append(pointer);exposed.append(pointer)
            else:result[key]=walk(item,pointer)
        return result
    return walk(payload),masked,removed,exposed


def snapshot_response(snapshot,mode):
    protected,masked,removed,exposed=protect_snapshot(snapshot['body'])
    original_bytes=encode(snapshot['body']);protected_bytes=encode(protected)
    body=original_bytes if mode=='standard' else protected_bytes
    reduction=len(original_bytes)-len(body)
    try:reason=HTTPStatus(snapshot['http_status']).phrase
    except ValueError:reason='Response'
    headers={**snapshot['headers'],
             'X-Captured-Correlation-ID':snapshot['correlation_id'],'X-Captured-Endpoint':snapshot['endpoint'],
             'X-Captured-Method':snapshot['method'],'X-Captured-At':snapshot['captured_at'],
             'X-Captured-HTTP-Version':snapshot['http_version'],'X-Captured-Status-Text':reason,
             'X-Privacy-Mode':mode,'X-Privacy-Policy':'operator-response-view-v1',
             'X-Privacy-Masked-Fields':','.join(masked) if mode=='veilmint' else '',
             'X-Privacy-Removed-Fields':','.join(removed) if mode=='veilmint' else '',
             'X-Privacy-Exposed-Fields':','.join(exposed) if mode=='standard' else '',
             'X-Privacy-Standard-Bytes':str(len(original_bytes)),'X-Privacy-Protected-Bytes':str(len(protected_bytes)),
             'X-Privacy-Response-Bytes':str(len(body)),'X-Privacy-Reduction-Bytes':str(reduction),
             'X-Privacy-Reduction-Percent':str(round(100*reduction/len(original_bytes),2)),'cache-control':'no-store'}
    return Response(body,status_code=snapshot['http_status'],media_type='application/json',headers=headers)


def router(snapshots):
    routes=APIRouter(prefix='/api/operator/responses',tags=['Sandbox response inspection'])
    def read(correlation_id,mode):
        snapshot=snapshots.get(correlation_id)
        if snapshot is None:
            raise HTTPException(404,'Response body unavailable. Refresh the bank page and select a new request; captures expire after 15 minutes or a backend restart.')
        return snapshot_response(snapshot,mode)

    @routes.get('/{correlation_id}/standard')
    def standard(correlation_id:str):return read(correlation_id,'standard')

    @routes.get('/{correlation_id}/veilmint')
    def veilmint(correlation_id:str):return read(correlation_id,'veilmint')

    return routes
