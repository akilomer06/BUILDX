"""Banking domain. Money is integer INR paise; ledger entries are immutable."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import secrets
import sqlite3
import time
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))


def now():
    return datetime.now(timezone.utc).isoformat()


class BankError(ValueError):
    def __init__(self, message="Bank operation could not be completed.", status=400):
        super().__init__(message)
        self.status = status


class Bank:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS nexus_schema(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO nexus_schema VALUES (1);
            CREATE TABLE IF NOT EXISTS nexus_demo_profiles(
              account TEXT PRIMARY KEY REFERENCES nexus_accounts(id),
              contact_email TEXT NOT NULL, customer_phone TEXT NOT NULL,
              customer_address TEXT NOT NULL, origin TEXT NOT NULL CHECK(origin='GENERATED_SYNTHETIC'));
            INSERT OR IGNORE INTO nexus_schema VALUES (2);
            CREATE TABLE IF NOT EXISTS nexus_customers(
              id TEXT PRIMARY KEY, display_name TEXT NOT NULL, username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS nexus_accounts(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES nexus_customers(id),
              account_number TEXT NOT NULL UNIQUE, account_type TEXT NOT NULL DEFAULT 'SANDBOX_CURRENT',
              currency TEXT NOT NULL DEFAULT 'INR', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS nexus_account_ids(
              account TEXT PRIMARY KEY REFERENCES nexus_accounts(id),
              public_id TEXT NOT NULL UNIQUE CHECK(length(public_id)=12 AND public_id NOT GLOB '*[^0-9]*'));
            CREATE INDEX IF NOT EXISTS nexus_account_owner ON nexus_accounts(owner);
            CREATE TABLE IF NOT EXISTS nexus_sessions(
              token_hash TEXT PRIMARY KEY, customer TEXT NOT NULL REFERENCES nexus_customers(id), expires_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS nexus_beneficiaries(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES nexus_customers(id),
              destination TEXT NOT NULL REFERENCES nexus_accounts(id), label TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(owner,destination));
            CREATE TABLE IF NOT EXISTS nexus_transfers(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES nexus_customers(id),
              source TEXT NOT NULL REFERENCES nexus_accounts(id), destination TEXT NOT NULL REFERENCES nexus_accounts(id),
              amount_minor INTEGER NOT NULL CHECK(amount_minor > 0), currency TEXT NOT NULL,
              reference TEXT NOT NULL UNIQUE, status TEXT NOT NULL CHECK(status='COMPLETED'),
              idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(owner,idempotency_key));
            CREATE TABLE IF NOT EXISTS nexus_ledger(
              id TEXT PRIMARY KEY, account TEXT NOT NULL REFERENCES nexus_accounts(id),
              transfer_id TEXT REFERENCES nexus_transfers(id), amount_minor INTEGER NOT NULL CHECK(amount_minor != 0),
              currency TEXT NOT NULL, reference TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(account,reference));
            CREATE INDEX IF NOT EXISTS nexus_ledger_account ON nexus_ledger(account,created_at);
            CREATE TABLE IF NOT EXISTS nexus_login_attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, window INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS nexus_ledger_no_update BEFORE UPDATE ON nexus_ledger BEGIN SELECT RAISE(ABORT,'Immutable ledger'); END;
            CREATE TRIGGER IF NOT EXISTS nexus_ledger_no_delete BEFORE DELETE ON nexus_ledger BEGIN SELECT RAISE(ABORT,'Immutable ledger'); END;
            ''')
            db.execute('BEGIN IMMEDIATE')
            version=db.execute('SELECT max(version) FROM nexus_schema').fetchone()[0]
            if version not in (2,3):
                raise BankError('Unsupported bank schema version.',503)
            # Add public numeric IDs without rewriting immutable ledger references.
            # Sandbox redenomination retains amounts exactly; old ledger currency
            # labels remain intact on disk and are projected as INR at read time.
            if version==2:
                for row in db.execute('SELECT id FROM nexus_accounts ORDER BY created_at,id').fetchall():
                    public=row['id'] if len(row['id'])==12 and row['id'].isascii() and row['id'].isdigit() else self._new_account_id(db)
                    db.execute('INSERT INTO nexus_account_ids VALUES(?,?)',(row['id'],public))
                db.execute("UPDATE nexus_accounts SET currency='INR' WHERE currency='AED'")
                db.execute('INSERT INTO nexus_schema VALUES(3)')

    @staticmethod
    def _new_account_id(db):
        for _ in range(20):
            candidate=str(100_000_000_000+secrets.randbelow(900_000_000_000))
            if not db.execute('SELECT 1 FROM nexus_account_ids WHERE public_id=?',(candidate,)).fetchone() and not db.execute('SELECT 1 FROM nexus_accounts WHERE id=?',(candidate,)).fetchone():
                return candidate
        raise BankError('Account registration temporarily unavailable.',503)

    @staticmethod
    def _internal_id(db,account):
        row=db.execute('SELECT account FROM nexus_account_ids WHERE public_id=?',(account,)).fetchone()
        return row['account'] if row else account

    @staticmethod
    def _public_id(db,account):
        row=db.execute('SELECT public_id FROM nexus_account_ids WHERE account=?',(account,)).fetchone()
        return row['public_id'] if row else account

    @staticmethod
    def _currency(currency):
        return 'INR' if currency=='AED' else currency

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def register(self, display_name, username, password):
        customer = str(uuid4())
        hashed = HASHER.hash(password)
        try:
            with self.connection(True) as db:
                account=self._new_account_id(db)
                db.execute('INSERT INTO nexus_customers(id,display_name,username,password_hash,created_at) VALUES(?,?,?,?,?)',
                           (customer,display_name.strip(),username.strip().lower(),hashed,now()))
                db.execute('INSERT INTO nexus_accounts(id,owner,account_number,currency,created_at) VALUES(?,?,?,?,?)',
                           (account,customer,'NXS'+secrets.token_hex(10).upper(),'INR',now()))
                db.execute('INSERT INTO nexus_account_ids VALUES(?,?)',(account,account))
        except sqlite3.IntegrityError:
            raise BankError('Registration unavailable; use a different sandbox username.',409) from None
        return {'customer_id':customer,'account_id':account}

    def login(self, username, password):
        normalized = username.strip().lower()
        key = hashlib.sha256(normalized.encode()).hexdigest()
        with self.connection(True) as db:
            stamp=int(time.time())
            db.execute('DELETE FROM nexus_login_attempts WHERE window<?',(stamp-3600,))
            attempt=db.execute('SELECT * FROM nexus_login_attempts WHERE key=?',(key,)).fetchone()
            count = attempt['count']+1 if attempt and stamp-attempt['window']<60 else 1
            window = attempt['window'] if attempt and stamp-attempt['window']<60 else stamp
            db.execute('INSERT OR REPLACE INTO nexus_login_attempts VALUES(?,?,?)',(key,count,window))
        if count>10:
            raise BankError('Authentication temporarily unavailable. Try again later.',429)
        with self.connection() as db:
            row=db.execute("SELECT * FROM nexus_customers WHERE username=? AND status='ACTIVE'",(normalized,)).fetchone()
        try:
            HASHER.verify(row['password_hash'] if row else DUMMY_HASH,password)
        except (VerificationError,InvalidHashError):
            raise BankError('Invalid username or password.',401) from None
        if row is None:
            raise BankError('Invalid username or password.',401)
        token=secrets.token_urlsafe(32)
        with self.connection(True) as db:
            db.execute('DELETE FROM nexus_sessions WHERE expires_at<?',(int(time.time()),))
            db.execute('INSERT INTO nexus_sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],int(time.time())+28800))
        return token

    def authenticate(self, token):
        if not token or len(token)>200:
            raise BankError('Please sign in to your sandbox account.',401)
        with self.connection() as db:
            row=db.execute("SELECT c.id,c.display_name FROM nexus_sessions s JOIN nexus_customers c ON c.id=s.customer WHERE s.token_hash=? AND s.expires_at>? AND c.status='ACTIVE'",(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
            if row is None:
                raise BankError('Session expired. Please sign in again.',401)
            return dict(row)

    def logout(self, token):
        with self.connection(True) as db:
            db.execute('DELETE FROM nexus_sessions WHERE token_hash=?',(hashlib.sha256((token or '').encode()).hexdigest(),))

    def _account(self,db,owner,account):
        account=self._internal_id(db,account)
        row=db.execute('SELECT * FROM nexus_accounts WHERE id=? AND owner=?',(account,owner)).fetchone()
        if row is None:
            raise BankError('Account unavailable.',404)
        return row

    @staticmethod
    def _balance(db,account):
        return db.execute('SELECT coalesce(sum(amount_minor),0) FROM nexus_ledger WHERE account=?',(account,)).fetchone()[0]

    def accounts(self, owner):
        with self.connection() as db:
            return [{'account_id':self._public_id(db,r['id']),'account_type':r['account_type'],'currency':r['currency'],
                     'masked_account_reference':'•••• '+r['account_number'][-4:], 'status':r['status']}
                    for r in db.execute('SELECT * FROM nexus_accounts WHERE owner=? ORDER BY created_at',(owner,))]

    def account(self, owner, account, *, source=False):
        with self.connection() as db:
            row=self._account(db,owner,account)
            account=row['id']
            name=db.execute('SELECT display_name FROM nexus_customers WHERE id=?',(owner,)).fetchone()[0]
            result={'account_id':self._public_id(db,account),'display_name':name,'account_type':row['account_type'],
                    'currency':row['currency'],'status':row['status'],
                    'masked_account_reference':'•••• '+row['account_number'][-4:],
                    'available_balance_minor':self._balance(db,account),
                    'recent_transactions':self._transactions(db,account,5,0),
                    'legacy_display_label':'NEXUS sandbox account'}
            if source:
                result['account_number']=row['account_number']
                profile=db.execute('SELECT contact_email,customer_phone,customer_address FROM nexus_demo_profiles WHERE account=?',(account,)).fetchone()
                if profile: result.update(dict(profile))
            return result

    def demo_profile(self,account):
        """Opt-in generated fiction only; never import or collect contact data."""
        with self.connection(True) as db:
            account=self._internal_id(db,account)
            if not db.execute('SELECT 1 FROM nexus_accounts WHERE id=?',(account,)).fetchone():
                raise BankError('Sandbox account unavailable.',404)
            suffix=account.replace('-','')[:10]
            db.execute('INSERT OR IGNORE INTO nexus_demo_profiles VALUES(?,?,?,?,?)',
                       (account,'demo-'+suffix+'@example.invalid','DEMO-PHONE-'+suffix,
                        'FICTIONAL DEMO ADDRESS '+suffix,'GENERATED_SYNTHETIC'))

    def _transactions(self,db,account,limit,offset):
        return [{**dict(r),'currency':self._currency(r['currency'])} for r in db.execute("SELECT id,amount_minor,currency,reference,kind,created_at,'COMPLETED' AS status FROM nexus_ledger WHERE account=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",(account,limit,offset))]

    def transactions(self,owner,account,limit=25,offset=0):
        with self.connection() as db:
            row=self._account(db,owner,account)
            return self._transactions(db,row['id'],limit,offset)

    def beneficiaries(self,owner):
        with self.connection() as db:
            return [{**dict(r),'destination_account_id':self._public_id(db,r['destination_account_id'])} for r in db.execute('SELECT id,destination AS destination_account_id,label,created_at FROM nexus_beneficiaries WHERE owner=? ORDER BY created_at',(owner,))]

    def add_beneficiary(self,owner,destination,label):
        try:
            with self.connection(True) as db:
                destination=self._internal_id(db,destination)
                target=db.execute("SELECT * FROM nexus_accounts WHERE id=? AND status='ACTIVE'",(destination,)).fetchone()
                if not target or target['owner']==owner:
                    raise BankError('Destination is not eligible for an internal transfer.')
                ident=str(uuid4())
                db.execute('INSERT INTO nexus_beneficiaries VALUES(?,?,?,?,?)',(ident,owner,destination,label.strip(),now()))
                return {'id':ident,'destination_account_id':self._public_id(db,destination),'label':label.strip()}
        except sqlite3.IntegrityError:
            raise BankError('Beneficiary already exists.',409) from None

    def transfer(self,owner,source,destination,amount,currency,key):
        if isinstance(amount,bool) or not isinstance(amount,int) or not 0<amount<=100_000_000 or currency!='INR':
            raise BankError('Use a positive whole number of INR paise within sandbox limits.')
        if not isinstance(key,str) or not 8<=len(key)<=128:
            raise BankError('A valid idempotency key is required.')
        with self.connection(True) as db:
            source=self._internal_id(db,source)
            destination=self._internal_id(db,destination)
            old=db.execute('SELECT * FROM nexus_transfers WHERE owner=? AND idempotency_key=?',(owner,key)).fetchone()
            if old:
                if (old['source'],old['destination'],old['amount_minor'],self._currency(old['currency']))!=(source,destination,amount,currency):
                    raise BankError('Idempotency key was already used for different transfer details.',409)
                return self._receipt(db,old)
            src=self._account(db,owner,source)
            dst=db.execute('SELECT * FROM nexus_accounts WHERE id=?',(destination,)).fetchone()
            if not dst or src['status']!='ACTIVE' or dst['status']!='ACTIVE' or dst['owner']==owner or src['currency']!=currency or dst['currency']!=currency:
                raise BankError('Destination or account is not eligible for this transfer.')
            if self._balance(db,source)<amount:
                raise BankError('Insufficient sandbox funds.',409)
            ident=str(uuid4()); reference='NXS-'+uuid4().hex[:16].upper(); stamp=now()
            db.execute('INSERT INTO nexus_transfers VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,owner,source,destination,amount,currency,reference,'COMPLETED',key,stamp))
            for account,value in ((source,-amount),(destination,amount)):
                db.execute('INSERT INTO nexus_ledger VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),account,ident,value,currency,reference,'TRANSFER',stamp))
            return self._receipt(db,db.execute('SELECT * FROM nexus_transfers WHERE id=?',(ident,)).fetchone())

    def _receipt(self,db,row):
        result={key:row[key] for key in ('id','reference','source','destination','amount_minor','currency','status','created_at')}
        result.update(source=self._public_id(db,row['source']),destination=self._public_id(db,row['destination']),currency=self._currency(row['currency']))
        return result

    def receipt(self,owner,ident):
        with self.connection() as db:
            row=db.execute('SELECT * FROM nexus_transfers WHERE id=? AND owner=?',(ident,owner)).fetchone()
            if not row: raise BankError('Transfer unavailable.',404)
            return self._receipt(db,row)

    def fund(self,account,amount,reference):
        if isinstance(amount,bool) or not isinstance(amount,int) or not 0<amount<=100_000_000:
            raise BankError('Invalid sandbox funding amount.')
        if not isinstance(reference,str) or not reference.strip() or len(reference)>128:
            raise BankError('A unique nonempty sandbox funding reference is required.')
        with self.connection(True) as db:
            account=self._internal_id(db,account)
            row=db.execute("SELECT * FROM nexus_accounts WHERE id=? AND status='ACTIVE'",(account,)).fetchone()
            if not row: raise BankError('Sandbox account unavailable.',404)
            old=db.execute('SELECT amount_minor FROM nexus_ledger WHERE account=? AND reference=?',(account,reference)).fetchone()
            if old:
                if old[0]!=amount: raise BankError('Funding reference already used with another amount.',409)
                return
            db.execute('INSERT INTO nexus_ledger VALUES(?,?,NULL,?,?,?,?,?)',(str(uuid4()),account,amount,row['currency'],reference,'SANDBOX_FUNDING',now()))
