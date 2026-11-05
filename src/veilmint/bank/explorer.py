"""Read-only operator projections. Credentials and credential hashes are never selected."""
from .service import Bank, BankError
from .protection import BankProtection, CONTRACT_EXCLUDED_FIELDS
from ..runtime.logs import LogSink

MASK='[REDACTED]'
SENSITIVE={'display_name','username','account_number','contact_email','customer_phone','customer_address',
           'available_balance_minor','amount_minor','recent_transactions','label'}


def redact(value,reveal=False):
    if isinstance(value,list): return [redact(item,reveal) for item in value]
    if isinstance(value,dict):
        return {key:MASK if key in SENSITIVE and not reveal else redact(item,reveal) for key,item in value.items()}
    return value


class AccountExplorer:
    def __init__(self,settings):
        self.settings=settings
        self.bank=Bank(settings.database_path)
        self.protection=BankProtection(settings)

    def accounts(self,search='',limit=25,offset=0,reveal=False):
        query='%'+search+'%'
        with self.bank.connection() as db:
            condition='p.public_id LIKE ? OR c.display_name LIKE ? OR c.username LIKE ?'
            joins=' FROM nexus_accounts a JOIN nexus_customers c ON c.id=a.owner JOIN nexus_account_ids p ON p.account=a.id WHERE '
            total=db.execute('SELECT count(*)'+joins+condition,(query,query,query)).fetchone()[0]
            rows=db.execute('''SELECT p.public_id AS account_id,a.owner AS customer_id,c.display_name,c.username,
                a.account_type,a.currency,a.status,a.created_at,substr(a.account_number,-4) AS last_four,
                coalesce((SELECT sum(l.amount_minor) FROM nexus_ledger l WHERE l.account=a.id),0) AS available_balance_minor
                '''+joins+condition+
                ' ORDER BY a.created_at DESC,a.id LIMIT ? OFFSET ?',(query,query,query,limit,offset)).fetchall()
        items=[{**dict(row),'masked_account_reference':'•••• '+row['last_four']} for row in rows]
        for row in items:row.pop('last_four')
        return {'accounts':redact(items,reveal),'total':total,'limit':limit,'offset':offset,
                'read_only':True,'sensitive_reveal':reveal}

    def account(self,account_id,reveal=False):
        with self.bank.connection() as db:
            internal=self.bank._internal_id(db,account_id)
            row=db.execute('SELECT owner FROM nexus_accounts WHERE id=?',(internal,)).fetchone()
            if not row:raise BankError('Account unavailable.',404)
            owner=row['owner']
            identity=db.execute('SELECT id AS customer_id,display_name,username,status,created_at FROM nexus_customers WHERE id=?',(owner,)).fetchone()
            beneficiaries=[{**dict(r),'destination_account_id':self.bank._public_id(db,r['destination_account_id'])} for r in db.execute('SELECT id,destination AS destination_account_id,label,created_at FROM nexus_beneficiaries WHERE owner=? ORDER BY created_at DESC LIMIT 25',(owner,))]
            transfers=[self.bank._receipt(db,r) for r in db.execute('SELECT id,source,destination,amount_minor,currency,reference,status,created_at FROM nexus_transfers WHERE source=? OR destination=? ORDER BY created_at DESC LIMIT 25',(internal,internal))]
            ledger=self.bank._transactions(db,internal,25,0)
        source=self.bank.account(owner,account_id,source=True)
        dto={key:value for key,value in source.items() if key not in CONTRACT_EXCLUDED_FIELDS}
        preview=self.protection.protect(dto)
        trace=preview.to_dict();trace.pop('payload')
        events=self.protection.events(account_id=account_id)
        return {'read_only':True,'sensitive_reveal':reveal,'reveal_scope':'Explicit local operator view; no credentials are available.',
                'customer':redact(dict(identity),reveal),'source_record':redact(source,reveal),
                'source_field_paths':['/'+key for key in sorted(source)],
                'contract_excluded_paths':['/'+key for key in sorted(source.keys()-dto.keys())],
                'customer_dto':redact(dto,reveal),'current_policy_preview':{'output':redact(preview.payload,reveal),'trace':trace,
                    'label':'Read-only preview of the current policy; no customer request or log is generated.'},
                'ledger':redact(ledger,reveal),'beneficiaries':redact(beneficiaries,reveal),
                'transfers':redact(transfers,reveal),'events':events,
                'demo_profile_present':'contact_email' in source}

    def event(self,event_id):
        from contextlib import closing
        import sqlite3,json
        with closing(sqlite3.connect(self.settings.database_path)) as db:
            row=db.execute('SELECT event_json FROM nexus_security_events WHERE id=?',(event_id,)).fetchone()
        if not row:raise BankError('Request evidence unavailable.',404)
        event=json.loads(row[0])
        with self.bank.connection() as db:
            if event.get('account_id'):
                event['account_id']=self.bank._public_id(db,event['account_id'])
        persisted=LogSink(self.settings.database_path).get(event['log_record_id'])
        if persisted['event'].get('correlation_id')!=event['correlation_id']:
            raise BankError('Request evidence failed correlation validation.',409)
        # Only the sanitizer's actual stored result is exposed; no raw input copy.
        return {'event':{'id':event_id,**event},'persisted':persisted,'read_only':True}
