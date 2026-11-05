"""Destination-specific policies and safe real-traffic metadata. No raw previews."""
from contextlib import closing
import hashlib
import json
import sqlite3
from jsonschema import Draft202012Validator

from ..policy.compiler import analysis_digest
from ..policy.store import PolicyStore
from ..runtime.api import APIEnforcer
from ..runtime.logs import LogSink, StructuredLogPipeline
from .service import now

DESTINATION = 'nexus_bank.account_summary.v1'
CONTRACT_EXCLUDED_FIELDS={'account_number','contact_email','customer_phone','customer_address'}
CONTRACT = {
    'account_id': ('USED','INTERNAL','Customer account selection and transfer source identity.'),
    'display_name': ('USED','MEDIUM','Customer welcome and account holder display.'),
    'account_type': ('USED','GENERAL','Account type display.'),
    'currency': ('USED','GENERAL','Integer minor-unit currency formatting.'),
    'status': ('USED','GENERAL','Account status and transfer eligibility display.'),
    'masked_account_reference': ('USED','INTERNAL','Masked account reference display; never a full account number.'),
    'available_balance_minor': ('USED','FINANCIAL','Account balance and transfer review display.'),
    'recent_transactions': ('USED','FINANCIAL','Overview displays actual latest ledger rows.'),
    'legacy_display_label': ('CANDIDATE_UNUSED','GENERAL','Deprecated compatibility label; excluded by the explicit customer DTO contract. Removal still requires review.'),
}


def account_report():
    """Explicit maintained consumer contract, NOT TypeScript AST analysis."""
    schema={'type':'object','properties':{name:{'type': 'integer' if name=='available_balance_minor' else 'array' if name=='recent_transactions' else 'string'} for name in CONTRACT},'required':[n for n,v in CONTRACT.items() if v[0]=='USED']}
    Draft202012Validator.check_schema(schema)
    sample={name:0 if name=='available_balance_minor' else [] if name=='recent_transactions' else 'SYNTHETIC_CONTRACT_VALUE' for name in CONTRACT}
    Draft202012Validator(schema).validate(sample)
    return {
        'analysis':{'mode':'explicit_endpoint_contract','destination':DESTINATION,
                    'scope':'NEXUS BANK account details DTO; manually maintained customer contract, not TypeScript analysis.',
                    'consumer':'frontend/src/bank/BankApp.tsx', 'root_name':'account',
                    'contract_digest':hashlib.sha256(json.dumps(CONTRACT,sort_keys=True).encode()).hexdigest(),
                    'schema':schema},
        'schema_validation':{'schema_valid':True,'payload_valid':True},
        'fields':[{'name':name,'usage':v[0],'sensitivity':v[1],'evidence':[v[2]]} for name,v in sorted(CONTRACT.items())],
        'warnings':['Explicit reviewed contract evidence; React/TypeScript has not been statically analyzed.'],
    }


LOG_FIELDS={name:'GENERAL' for name in ('event_type','endpoint','method','http_status','correlation_id','destination','policy_revision','mode','outcome')}
LOG_FIELDS.update({'customer_reference':'INTERNAL','account_reference':'INTERNAL','amount_minor':'FINANCIAL','password':'HIGH','token':'HIGH','account_number':'HIGH'})
LOG_FIELDS.update({'display_name':'MEDIUM','available_balance_minor':'FINANCIAL','recent_transactions':'FINANCIAL',
                   'contact_email':'MEDIUM','customer_phone':'MEDIUM','customer_address':'MEDIUM'})


def header_decisions(request_headers,response_headers):
    """Record presence and exclusion decisions, without reading secret values."""
    rules=(('request','Authorization'),('request','Cookie'),('request','X-API-Key'),
           ('request','X-VEILMINT-Operator'),('response','Set-Cookie'))
    return [{'direction':direction,'name':name,'present':name in (request_headers if direction=='request' else response_headers),
             'action':'EXCLUDE_FROM_LOG','reason':'Credential/header value is never copied into log input; authentication transport is preserved.'}
            for direction,name in rules]


def log_report():
    return {'analysis':{'destination':'nexus_bank.operational_metadata.v1','mode':'explicit_metadata_allowlist'},
            'schema_validation':{'schema_valid':True,'payload_valid':True},
            'fields':[{'name':n,'usage':'USED','sensitivity':s,'evidence':['Server-owned minimal operational metadata; sensitivity controls log action independently.']} for n,s in sorted(LOG_FIELDS.items())], 'warnings':[]}


class BankProtection:
    def __init__(self, settings):
        self.settings=settings
        self.path=settings.database_path
        self.policy_path=self.path.with_name(self.path.stem+'.bank-account-policy.sqlite3')
        self.log_policy_path=self.path.with_name(self.path.stem+'.bank-log-policy.sqlite3')

    def load_policy(self):
        with PolicyStore(self.policy_path) as store:
            policy=store.get()
            if store.load_inputs(policy.revision.revision_id)['report']['analysis'].get('destination')!=DESTINATION:
                raise ValueError('Destination mismatch')
            return policy

    def protect(self,payload):
        # Validate the actual service DTO before it enters the shared minimizer.
        Draft202012Validator(account_report()['analysis']['schema']).validate(payload)
        return APIEnforcer(self.load_policy).enforce(payload,self.settings.bank_mode,expected_analysis_digest=analysis_digest(account_report()))

    def _log_policy(self):
        # No API removal approval is granted here: all metadata fields are USED.
        with PolicyStore(self.log_policy_path) as store:
            p=store.create_revision(log_report())
            if p.approval is None:
                try:
                    p=store.review(p.revision.revision_id,'system-metadata-configuration',(),notes='Log-only metadata allowlist; no candidate removals.')
                except ValueError:
                    p=store.get()  # A concurrent first request may have initialized it.
            return p

    def record(self, metadata, *, kept=(), removed=(), warnings=(), latency_ms=0,
               account_id=None,source_paths=(),contract_excluded=(),header_actions=(),policy_valid=None,would_remove=()):
        sink=LogSink(self.path)
        protected=StructuredLogPipeline(self._log_policy,sink,self.settings.hmac_key).process(metadata,expected_analysis_digest=analysis_digest(log_report()))
        # Metadata is constructed exclusively by server middleware. Never persist
        # response values, raw URLs, credentials, headers, query strings or bodies.
        event={k:protected.event.get(k) for k in ('event_type','endpoint','method','http_status','correlation_id','destination','policy_revision','mode','outcome')}
        event.update({'created_at':now(),'kept_paths':list(kept),'removed_paths':list(removed),
                      'warnings':list(warnings),'log_outcome':'SANITIZED','log_record_id':protected.record_id,
                      'log_actions':list(protected.actions),'latency_ms':round(latency_ms,2),
                      'account_id':account_id,'source_field_paths':list(source_paths),
                      'contract_excluded_paths':list(contract_excluded),'header_actions':list(header_actions),
                      'policy_valid':policy_valid,'would_remove_paths':list(would_remove),
                      'log_input_field_paths':['/'+key for key in sorted(metadata)]})
        with closing(sqlite3.connect(self.path,timeout=10)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS nexus_security_events(id INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL)')
            db.execute('INSERT INTO nexus_security_events(event_json) VALUES(?)',(json.dumps(event,sort_keys=True),))
            db.execute('DELETE FROM nexus_security_events WHERE id <= (SELECT coalesce(max(id),0)-1000 FROM nexus_security_events)')
        return protected.record_id

    def events(self,account_id=None):
        with closing(sqlite3.connect(self.path,timeout=10)) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nexus_security_events'").fetchone()
            if not exists: return []
            rows=[{'id':r[0],**json.loads(r[1])} for r in db.execute('SELECT id,event_json FROM nexus_security_events ORDER BY id DESC LIMIT 1000')]
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nexus_account_ids'").fetchone()
            mapping=dict(db.execute('SELECT account,public_id FROM nexus_account_ids')) if exists else {}
            for row in rows:
                row['account_id']=mapping.get(row.get('account_id'),row.get('account_id'))
            account_id=mapping.get(account_id,account_id)
            return [row for row in rows if account_id is None or row.get('account_id')==account_id][:100]
