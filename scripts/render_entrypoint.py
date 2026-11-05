"""Initialize ephemeral demo storage, then run the API as its non-root user."""
import os
from pathlib import Path

def main():
    port=os.environ.get('PORT','10000')
    if not port.isascii() or not port.isdigit() or not 1<=int(port)<=65535:
        raise SystemExit('Invalid service port.')
    data=Path('/data')
    data.mkdir(exist_ok=True)
    if os.getuid()==0:
        os.chown(data,10001,10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
        os.environ['HOME']='/home/veilmint'
    os.execvp('python',['python','-m','uvicorn','veilmint.server:create_app','--factory','--host','0.0.0.0','--port',port,'--no-access-log'])

if __name__=='__main__':main()
