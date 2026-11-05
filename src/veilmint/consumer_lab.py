"""Operator-authorized scenarios using persistent DEMO enrichment and real consumers."""
import hashlib
import inspect
import json
from uuid import uuid4
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, ConfigDict
from jsonschema import Draft202012Validator
from .bank.service import Bank, BankError, now
from .consumers import overview, payments, notifications, risk
from .analyzer.report import generate_report
from .policy.compiler import analysis_digest
from .policy.store import PolicyStore
from .runtime.api import APIEnforcer, RuntimeMode
from .runtime.logs import StructuredLogPipeline, LogSink

CONSUMERS={'overview':overview,'payments':payments,'notifications':notifications,'risk':risk}
PROFILE={'legal_name':'FICTIONAL DEMO CUSTOMER','email':'demo@example.example','phone':'DEMO-PHONE-0000',
         'address':'FICTIONAL DEMO ADDRESS','city':'DEMO CITY','state':'DEMO STATE','postal_code':'DEMO-000',
         'country':'IN','customer_segment':'DEMO_RETAIL','preferred_language':'en','customer_status':'ACTIVE'}
INTERNAL={'internal_risk_flag':False,'fraud_review_state':'DEMO_CLEAR','internal_case_reference':'DEMO-CASE-000',
          'source_system':'NEXUS_SANDBOX','support_notes':'FICTIONAL DEMO SUPPORT NOTE',
          'kyc_demo_status':'FICTIONAL_NOT_VERIFIED','last_reviewed_at':'DEMO-NOT-REVIEWED'}
ACCOUNT={'branch_code':'DEMO-BRANCH-001','interest_plan':'DEMO_NON_INTEREST'}
SENSITIVITY={**{key:'MEDIUM' for key in PROFILE},**{key:'HIGH' for key in INTERNAL},
             'account_id':'INTERNAL','account_number':'HIGH','available_balance_minor':'FINANCIAL',
             'ledger_balance_minor':'FINANCIAL','recent_transactions':'FINANCIAL','display_name':'MEDIUM'}

def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()

def paths(value,prefix='',normalize=False):
    if isinstance(value,dict) and value:
        return sorted({p for key,item in value.items() for p in paths(item,prefix+'/'+key.replace('~','~0').replace('/','~1'),normalize)})
    if isinstance(value,list) and value:
        return sorted({p for i,item in enumerate(value) for p in paths(item,prefix+'/'+('*' if normalize else str(i)),normalize)})
    return [prefix or '/']  # empty containers count as one emitted leaf

class ConsumerLab:
    def __init__(self,settings):
        self.settings=settings;self.bank=Bank(settings.database_path)
        with self.bank.connection(True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS nexus_consumer_schema(version INTEGER PRIMARY KEY)')
            db.execute('INSERT OR IGNORE INTO nexus_consumer_schema VALUES(1)')
            if db.execute('SELECT max(version) FROM nexus_consumer_schema').fetchone()[0]!=1:raise BankError('Unsupported consumer schema.',503)
            db.execute('CREATE TABLE IF NOT EXISTS nexus_demo_producer(account TEXT PRIMARY KEY REFERENCES nexus_accounts(id),profile_json TEXT NOT NULL,internal_json TEXT NOT NULL,account_json TEXT NOT NULL,revision INTEGER NOT NULL,origin TEXT NOT NULL CHECK(origin="DEMO"))')
    def policy_path(self,consumer):
        if consumer not in CONSUMERS:raise BankError('Unknown consumer.',404)
        return self.settings.database_path.with_name(self.settings.database_path.stem+'.consumer-'+consumer+'.sqlite3')
    def seed(self,account):
        with self.bank.connection(True) as db:
            internal=self.bank._internal_id(db,account)
            if not db.execute('SELECT 1 FROM nexus_accounts WHERE id=?',(internal,)).fetchone():raise BankError('Account unavailable.',404)
            profile={**PROFILE,'email':'demo-'+account[-6:]+'@bank.example'}
            db.execute('INSERT OR IGNORE INTO nexus_demo_producer VALUES(?,?,?,?,1,?)',(internal,json.dumps(profile),json.dumps(INTERNAL),json.dumps(ACCOUNT),'DEMO'))
        return {'origin':'DEMO','account_id':account,'funds_added':False}
    def producer(self,account):
        with self.bank.connection() as db:
            internal=self.bank._internal_id(db,account)
            row=db.execute('SELECT * FROM nexus_demo_producer WHERE account=?',(internal,)).fetchone()
            owner=db.execute('SELECT owner,created_at FROM nexus_accounts WHERE id=?',(internal,)).fetchone()
            if not row or not owner:raise BankError('Attach the opt-in DEMO profile first.',409)
            profile=json.loads(row['profile_json']);private=json.loads(row['internal_json']);extra=json.loads(row['account_json'])
        source=self.bank.account(owner['owner'],account,source=True)
        source={key:value for key,value in source.items() if key not in ('contact_email','customer_phone','customer_address')}
        return {**source,**profile,**private,**extra,'opened_at':owner['created_at'],'ledger_balance_minor':source['available_balance_minor']}
    def report(self,consumer):
        module=CONSUMERS.get(consumer)
        if module is None:raise BankError('Unknown consumer.',404)
        sample={**{key:'' for key in (*PROFILE,*INTERNAL,*ACCOUNT,'account_id','display_name','account_type','currency','status','masked_account_reference','legacy_display_label','account_number','opened_at')},
                'available_balance_minor':0,'ledger_balance_minor':0,'recent_transactions':[],'internal_risk_flag':False}
        schema={'type':'object','properties':{key:{'type':'boolean' if isinstance(value,bool) else 'integer' if isinstance(value,int) else 'array' if isinstance(value,list) else 'string'} for key,value in sample.items()},'required':list(sample)}
        report=generate_report(schema,sample,inspect.getsource(module),{key:SENSITIVITY.get(key,'GENERAL') for key in sample},filename='src/veilmint/consumers/'+consumer+'.py')
        report['analysis'].update({'destination':'nexus.consumer.'+consumer+'.v1','schema_revision':'producer-v1','producer_schema':schema})
        return report
    def policy(self,consumer):
        with PolicyStore(self.policy_path(consumer)) as store:
            history=store.history()
            return {'report':self.report(consumer),'policy':store.get().to_dict() if history else None,'history':history}
    def prepare(self,consumer,force=False):
        with PolicyStore(self.policy_path(consumer)) as store:store.create_revision(self.report(consumer),force_new=force)
        return self.policy(consumer)
    def review(self,consumer,body):
        with PolicyStore(self.policy_path(consumer)) as store:
            policy=store.get()
            if policy.revision.analysis_digest!=analysis_digest(self.report(consumer)) or any(getattr(policy.revision,k)!=getattr(body,k) for k in ('revision_id','analysis_digest','inputs_digest')):
                raise BankError('Stale consumer review. Reload evidence.',409)
            store.review(body.revision_id,body.reviewer,body.approved_fields,notes=body.notes,decision=body.decision)
        return self.policy(consumer)
    def execute(self,account,consumer,mode,correlation_id=None):
        # Consumer selection is available only to an authenticated operator scenario.
        # No customer endpoint can supply a service identity or bypass its own policy.
        source=self.producer(account);report=self.report(consumer)
        Draft202012Validator(report['analysis']['producer_schema']).validate(source)
        def load():
            with PolicyStore(self.policy_path(consumer)) as store:
                p=store.get()
                if store.load_inputs(p.revision.revision_id)['report']['analysis']['destination']!=report['analysis']['destination']:raise ValueError('Identity mismatch')
                return p
        result=APIEnforcer(load).enforce(source,mode,expected_analysis_digest=analysis_digest(report))
        # Exercise the actual logical service, including required sensitive reads.
        output=CONSUMERS[consumer].consume(result.payload)
        trace_id=correlation_id or str(uuid4());policy=None
        try:
            with PolicyStore(self.policy_path(consumer)) as store:policy=store.get(result.policy_revision) if result.policy_revision else None
        except Exception:pass
        # Shared structured-log protection, not a separate sanitizer. No DTO values.
        from .bank.protection import BankProtection, log_report
        protection=BankProtection(self.settings)
        event={'event_type':'CONSUMER_SCENARIO','endpoint':'/api/operator/consumer-lab/run','method':'POST','http_status':200,
               'correlation_id':trace_id,'destination':report['analysis']['destination'],'policy_revision':result.policy_revision,
               'mode':result.mode.value,'outcome':'EXECUTED'}
        log=StructuredLogPipeline(protection._log_policy,LogSink(self.settings.database_path),self.settings.hmac_key).process(event,expected_analysis_digest=analysis_digest(log_report()))
        baseline_paths=paths(source);protected_paths=paths(result.payload)
        return {'trace_id':trace_id,'origin':'DEMO_ENRICHMENT_WITH_ACTUAL_BANK_LEDGER','account_id':account,'consumer_id':consumer,
                'source_version':hashlib.sha256(encoded(source)).hexdigest(),'schema_revision':'producer-v1',
                'actual_runtime_mode':result.mode.value,'policy_revision':result.policy_revision,'policy_valid':result.policy_valid,
                'baseline':{'preview':source,'field_paths':baseline_paths,'schema_paths':paths(source,normalize=True),'byte_count':len(encoded(source))},
                'protected':{'preview':result.payload,'field_paths':protected_paths,'schema_paths':paths(result.payload,normalize=True),'byte_count':len(encoded(result.payload))},
                'consumer_result':output,'warnings':list(result.warnings),
                'unknown_fields':['/'+key for key in sorted(source.keys()-{f['name'] for f in report['fields']})],
                'decisions':[{'field':f['name'],'usage':f['usage'],'sensitivity':f['sensitivity'],'evidence':f['evidence'],
                              'action':'REMOVED' if '/'+f['name'] in result.removed_paths else 'UNKNOWN' if f['usage']=='UNKNOWN' else 'KEPT',
                              'approved':bool(policy and policy.approval and f['name'] in policy.approval.approved_fields)} for f in report['fields']]+[
                              {'field':key,'usage':'UNKNOWN','sensitivity':'INTERNAL','evidence':['New producer field has no exact consumer evidence; retained conservatively. Review schema drift.'],'action':'UNKNOWN','approved':False}
                              for key in sorted(source.keys()-{f['name'] for f in report['fields']})],
                'log':{'record_id':log.record_id,'protected':LogSink(self.settings.database_path).get(log.record_id)},
                'api_trace':result.to_dict()|{'payload':None}}

    def verify(self,account,consumer):
        source=self.producer(account);report=self.report(consumer)
        marker='VEILMINT_DEMO_CANARY_'+uuid4().hex
        candidates=[f['name'] for f in report['fields'] if f['usage']=='CANDIDATE_UNUSED']
        for key in candidates:source[key]=marker
        def load():
            with PolicyStore(self.policy_path(consumer)) as store:return store.get()
        result=APIEnforcer(load).enforce(source,RuntimeMode.ENFORCE,expected_analysis_digest=analysis_digest(report))
        from .bank.protection import BankProtection,log_report
        correlation=str(uuid4());sink=LogSink(self.settings.database_path)
        protected=StructuredLogPipeline(BankProtection(self.settings)._log_policy,sink,self.settings.hmac_key).process(
            {'event_type':'CONSUMER_CANARY','correlation_id':correlation,'destination':'nexus.consumer.'+consumer+'.v1','password':marker},
            expected_analysis_digest=analysis_digest(log_report()))
        persisted=sink.get(protected.record_id)
        checks={'approved_current_policy':result.policy_valid,'candidate_canaries_removed':marker not in encoded(result.payload).decode(),
                'log_canary_dropped':marker not in encoded(persisted).decode(),
                'correlation_matches':persisted['event'].get('correlation_id')==correlation}
        return {'status':'PASS' if all(checks.values()) else 'FAIL','consumer_id':consumer,'correlation_id':correlation,
                'policy_revision':result.policy_revision,'log_record_id':protected.record_id,'checks':checks,
                'scope':'Controlled candidate-field and HIGH-log-field canaries; not a universal leak scan.'}

class RunInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str=Field(pattern=r'^[0-9]{12}$')
    consumer:str=Field(pattern='^(overview|payments|notifications|risk)$')
    mode:RuntimeMode=RuntimeMode.ENFORCE

class RevisionInput(BaseModel):
    new_revision:bool=False

def router(settings,ReviewRequest):
    routes=APIRouter(prefix='/api/operator/consumer-lab')
    @routes.get('/consumers')
    def consumers():return {'consumers':list(CONSUMERS),'deployment':'in-process logical services','schema_revision':'producer-v1'}
    @routes.get('/policies/{consumer}')
    def policy(consumer:str):return ConsumerLab(settings).policy(consumer)
    @routes.post('/policies/{consumer}/prepare')
    @routes.post('/policies/{consumer}/revisions')
    def prepare(consumer:str,body:RevisionInput):return ConsumerLab(settings).prepare(consumer,body.new_revision)
    @routes.post('/policies/{consumer}/review')
    def review(consumer:str,body:ReviewRequest):return ConsumerLab(settings).review(consumer,body)
    @routes.post('/profiles/{account}')
    def profile(account:str):return ConsumerLab(settings).seed(account)
    @routes.post('/run')
    def run(body:RunInput,request:Request):return ConsumerLab(settings).execute(body.account_id,body.consumer,body.mode,request.state.correlation_id)
    @routes.post('/verify')
    def verify(body:RunInput):return ConsumerLab(settings).verify(body.account_id,body.consumer)
    @routes.post('/matrix')
    def matrix(body:RunInput):
        lab=ConsumerLab(settings)
        results=[lab.execute(body.account_id,c,body.mode) for c in CONSUMERS]
        if len({r['source_version'] for r in results})!=1:raise BankError('Producer changed during comparison; retry.',409)
        return {'source_version':results[0]['source_version'],'results':results}
    return routes
