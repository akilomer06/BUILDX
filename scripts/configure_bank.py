"""Generate a private proxy credential; enable LAN binding only explicitly."""
import argparse
from pathlib import Path
import secrets

parser=argparse.ArgumentParser()
parser.add_argument('--lan',action='store_true',help='Explicitly expose only the customer entry point to a trusted isolated LAN')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
path=root/'.env'
text=path.read_text(encoding='utf-8-sig') if path.exists() else ''
lines=text.splitlines()
values={line.split('=',1)[0].strip():line.split('=',1)[1].strip() for line in lines if '=' in line and not line.lstrip().startswith('#')}
updates={'VEILMINT_OPERATOR_TOKEN':values.get('VEILMINT_OPERATOR_TOKEN') or secrets.token_hex(32),
         'NEXUS_BIND':'0.0.0.0' if args.lan else '127.0.0.1',
         'LAN_DEMO':'true' if args.lan else 'false'}
remaining=[line for line in lines if line.split('=',1)[0].strip() not in updates]
path.write_text('\n'.join(remaining+[key+'='+value for key,value in updates.items()])+'\n',encoding='utf-8')
print('Private operator proxy credential configured; customer binding: '+updates['NEXUS_BIND']+'. No secret was printed.')
