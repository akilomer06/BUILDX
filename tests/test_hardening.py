import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from veilmint.demo_cli import initialize
from veilmint.config import Settings
from veilmint.server import create_app
from veilmint.policy.store import PolicyStore

def test_demo_initialization_idempotent_and_preserves_unrelated_rows(tmp_path):
    path=tmp_path/'demo.sqlite3'
    first=initialize(path,approved=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE unrelated (value TEXT)')
        db.execute("INSERT INTO unrelated VALUES ('preserve')")
    assert initialize(path,approved=True)==first
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT value FROM unrelated').fetchone()[0]=='preserve'
    with PolicyStore(path) as store:
        assert len(store.history())==1

def test_demo_refuses_unrelated_database(tmp_path):
    path=tmp_path/'unrelated.sqlite3'
    with sqlite3.connect(path) as db: db.execute('CREATE TABLE unrelated (value TEXT)')
    before=path.read_bytes()
    with pytest.raises(ValueError): initialize(path,approved=True)
    assert path.read_bytes()==before

def test_read_snapshots_remain_consistent_across_parallel_readers(tmp_path):
    path=tmp_path/'demo.sqlite3'
    policy=initialize(path,approved=True)
    def read(_):
        with PolicyStore(path) as store: return store.get().to_dict()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(result==policy for result in pool.map(read,range(20)))

def test_storage_unavailable_does_not_expose_error_or_values(tmp_path):
    path=tmp_path/'not-a-database'
    path.mkdir()
    with TestClient(create_app(Settings(database_path=path))) as client:
        response=client.post('/api/demo/log')
        assert response.status_code==503
        assert 'Traceback' not in response.text
        api=client.get('/api/demo/account?mode=ENFORCE').json()
        assert api['output']==api['original']
        assert not api['trace']['policy_valid']

def test_restart_preserves_approval_protection_and_fresh_canary(tmp_path):
    path=tmp_path/'demo.sqlite3'
    initialize(path,approved=True)
    runs=[]
    for _ in range(2):
        with TestClient(create_app(Settings(database_path=path,mode='ENFORCE'))) as client:
            assert len(client.get('/api/demo/account/response').json())==6
            run=client.post('/api/verify',json={}).json()
            assert run['status']=='PASS'
            runs.append(run['run_id'])
    assert len(set(runs))==2
