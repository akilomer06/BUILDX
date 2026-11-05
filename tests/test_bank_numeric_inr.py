"""Upgrade coverage with populated legacy UUID/AED sandbox records."""
import hashlib
import json
from uuid import uuid4

import pytest
import sqlite3
from fastapi.testclient import TestClient

from veilmint.bank.explorer import AccountExplorer
from veilmint.bank.protection import BankProtection
from veilmint.bank.service import Bank, HASHER, now
from veilmint.config import Settings
from veilmint.server import create_app


def test_populated_uuid_aed_upgrade_keeps_ledger_sessions_and_retry(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    bank=Bank(path)
    owners=[str(uuid4()),str(uuid4())]
    accounts=[str(uuid4()),str(uuid4())]
    transfer=str(uuid4())
    token='SYNTHETIC-EXISTING-SESSION'
    password='SYNTHETIC-Existing-Password'
    stamp=now()
    with bank.connection(True) as db:
        # Construct the previous supported schema's data, before public ID mapping.
        db.execute('DELETE FROM nexus_schema WHERE version=3')
        for index,(owner,account) in enumerate(zip(owners,accounts)):
            db.execute('INSERT INTO nexus_customers VALUES(?,?,?,?,?,?)',
                       (owner,'Fictional legacy '+str(index),'legacy.'+str(index),HASHER.hash(password),'ACTIVE',stamp))
            db.execute('INSERT INTO nexus_accounts VALUES(?,?,?,?,?,?,?)',
                       (account,owner,'NXS-LEGACY-'+str(index),'SANDBOX_CURRENT','AED','ACTIVE',stamp))
        db.execute('INSERT INTO nexus_sessions VALUES(?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(),owners[0],4_000_000_000))
        db.execute('INSERT INTO nexus_transfers VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (transfer,owners[0],*accounts,2500,'AED','legacy-transfer','COMPLETED','legacy-retry-key',stamp))
        for account,value,kind,ref,tid in ((accounts[0],10000,'SANDBOX_FUNDING','legacy-funding',None),
                                           (accounts[0],-2500,'TRANSFER','legacy-transfer',transfer),
                                           (accounts[1],2500,'TRANSFER','legacy-transfer',transfer)):
            db.execute('INSERT INTO nexus_ledger VALUES(?,?,?,?,?,?,?,?)',
                       (str(uuid4()),account,tid,value,'AED',ref,kind,stamp))
        db.execute('INSERT INTO nexus_beneficiaries VALUES(?,?,?,?,?)',
                   (str(uuid4()),owners[0],accounts[1],'Fictional recipient',stamp))
        db.execute('INSERT INTO nexus_demo_profiles VALUES(?,?,?,?,?)',
                   (accounts[0],'demo-legacy@example.invalid','DEMO-PHONE','FICTIONAL ADDRESS','GENERATED_SYNTHETIC'))
        before=[tuple(row) for row in db.execute('SELECT * FROM nexus_ledger ORDER BY id')]
        db.execute('CREATE TABLE nexus_security_events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_json TEXT NOT NULL)')
        db.execute('INSERT INTO nexus_security_events(event_json) VALUES(?)',
                   (json.dumps({'account_id':accounts[0],'correlation_id':'legacy-evidence'}),))

    upgraded=Bank(path)
    public=[upgraded.accounts(owner)[0]['account_id'] for owner in owners]
    assert len(set(public))==2 and all(len(value)==12 and value.isascii() and value.isdigit() for value in public)
    assert upgraded.authenticate(token)['id']==owners[0]
    assert upgraded.authenticate(upgraded.login('legacy.0',password))['id']==owners[0]
    detail=upgraded.account(owners[0],public[0],source=True)
    assert detail['currency']=='INR' and detail['available_balance_minor']==7500
    assert detail['contact_email']=='demo-legacy@example.invalid'
    assert all(row['currency']=='INR' for row in upgraded.transactions(owners[0],public[0]))
    assert upgraded.beneficiaries(owners[0])[0]['destination_account_id']==public[1]
    receipt=upgraded.receipt(owners[0],transfer)
    assert (receipt['source'],receipt['destination'],receipt['currency'])==(*public,'INR')
    assert upgraded.transfer(owners[0],*public,2500,'INR','legacy-retry-key')==receipt
    assert Bank(path).accounts(owners[0])[0]['account_id']==public[0]
    settings=Settings(database_path=path)
    explorer=AccountExplorer(settings)
    assert explorer.accounts(search=public[0])['total']==1
    projection=explorer.account(public[0],reveal=True)
    assert projection['transfers'][0]['source']==public[0]
    assert projection['transfers'][0]['currency']=='INR'
    assert projection['events'][0]['account_id']==public[0]
    assert BankProtection(settings).events(account_id=public[0])[0]['correlation_id']=='legacy-evidence'
    with upgraded.connection() as db:
        # No ledger rewrite, deleted history or duplicate retry entries.
        assert [tuple(row) for row in db.execute('SELECT * FROM nexus_ledger ORDER BY id')]==before
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE nexus_ledger SET currency='INR'")
    upgraded.fund(public[0],100,'new-inr-funding')
    new=upgraded.transfer(owners[0],*public,100,'INR','new-inr-transfer')
    assert new['currency']=='INR' and new['source']==public[0]
    assert upgraded.account(owners[0],public[0])['available_balance_minor']==7500
    assert upgraded.account(owners[1],public[1])['available_balance_minor']==2600


def test_numeric_ids_and_inr_are_validated_at_http_boundary(tmp_path):
    settings=Settings(database_path=tmp_path/'http.sqlite3')
    bank=Bank(settings.database_path)
    a=bank.register('Fictional A','numeric.a','SYNTHETIC-Password-A')
    b=bank.register('Fictional B','numeric.b','SYNTHETIC-Password-B')
    bank.fund(a['account_id'],10000,'numeric-http-funding')
    with TestClient(create_app(settings)) as client:
        client.headers['X-Nexus-Request']='1'
        assert client.post('/api/bank/auth/login',json={'username':'numeric.a','password':'SYNTHETIC-Password-A'}).status_code==200
        body={'source_account_id':a['account_id'],'destination_account_id':b['account_id'],
              'amount_minor':1234,'currency':'INR','idempotency_key':'numeric-http-key'}
        for invalid in (str(uuid4()),'12345','１２３４５６７８９０１２',123456789012,'12345678901a'):
            assert client.post('/api/bank/transfers',json={**body,'destination_account_id':invalid}).status_code==422
            assert client.post('/api/bank/beneficiaries',json={'destination_account_id':invalid,'label':'Fictional'}).status_code==422
        assert client.post('/api/bank/transfers',json={**body,'currency':'AED'}).status_code==422
        result=client.post('/api/bank/transfers',json=body)
        assert result.status_code==201 and result.json()['currency']=='INR'
        assert client.get('/api/bank/accounts/'+a['account_id']).json()['available_balance_minor']==8766
