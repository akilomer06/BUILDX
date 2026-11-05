"""Run React forms against a temporary real HTTP backend; keep only demo evidence."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

root=Path(__file__).resolve().parents[1]
folder=root/'data'/('bank-ui-verification-'+uuid4().hex)
folder.mkdir(parents=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0))
    port=sock.getsockname()[1]
env={**os.environ,'VEILMINT_DB':str(folder/'bank.sqlite3'),'VEILMINT_OPERATOR_TOKEN':'',
     'VEILMINT_RESPONSE_INSPECTION_DEMO':'true',
     'NEXUS_MODE':'ENFORCE','NEXUS_E2E_URL':f'http://127.0.0.1:{port}',
     'NEXUS_E2E_DB':str(folder/'bank.sqlite3'),'NEXUS_TEST_PYTHON':sys.executable}
with (folder/'server.log').open('w',encoding='utf-8') as output:
    process=subprocess.Popen([sys.executable,'-m','uvicorn','veilmint.server:create_app','--factory',
                              '--host','127.0.0.1','--port',str(port),'--no-access-log'],
                             cwd=root,env=env,stdout=output,stderr=output,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        for _ in range(100):
            if process.poll() is not None: raise RuntimeError('Temporary backend failed to start')
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/ready',timeout=1).close()
                break
            except OSError: time.sleep(.1)
        else: raise RuntimeError('Temporary backend not ready')
        npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
        if not npm: raise RuntimeError('npm is required')
        result=subprocess.run([npm,'test','--','src/bank/BankApp.e2e.test.tsx'],cwd=root/'frontend',env=env)
        code=result.returncode
    finally:
        process.terminate()
        process.wait(timeout=15)
sys.exit(code)
