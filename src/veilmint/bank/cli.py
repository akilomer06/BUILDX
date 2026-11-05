"""Local operator funding command. There is deliberately no funding HTTP route."""
import argparse
from uuid import uuid4
from ..config import Settings
from .service import Bank
from .protection import BankProtection


def main(argv=None):
    parser=argparse.ArgumentParser(prog='veilmint bank')
    commands=parser.add_subparsers(dest='command',required=True)
    fund=commands.add_parser('fund')
    profile=commands.add_parser('demo-profile')
    profile.add_argument('--account',required=True)
    profile.add_argument('--synthetic-only',action='store_true',required=True)
    fund.add_argument('--account',required=True)
    fund.add_argument('--amount-minor',type=int,required=True)
    fund.add_argument('--reference',required=True,help='Unique explicit funding reference; repeat is idempotent')
    fund.add_argument('--sandbox-funds',action='store_true',required=True,help='Confirm simulated funds only')
    args=parser.parse_args(argv)
    try:
        settings=Settings.from_env()
        if args.command=='demo-profile':
            Bank(settings.database_path).demo_profile(args.account)
            print('Fictional profile attached idempotently; no real contact data or funds were added.')
            return 0
        # Reject an unauditable funding request before touching the ledger.
        protection=BankProtection(settings)
        metadata={'event_type':'SANDBOX_FUNDING_REQUEST','endpoint':'CLI bank fund','method':'CLI',
                  'http_status':200,'correlation_id':str(uuid4()),'destination':'nexus_bank.sandbox_funding',
                  'policy_revision':None,'mode':'ENFORCE','outcome':'REQUESTED','account_reference':args.account}
        protection.record(metadata)
        Bank(settings.database_path).fund(args.account,args.amount_minor,args.reference)
        protection.record({**metadata,'event_type':'SANDBOX_FUNDING_RESULT','outcome':'COMPLETED'},account_id=args.account)
        print('Explicit sandbox funding completed. Reusing the same reference does not add funds twice.')
        return 0
    except Exception:
        print('Sandbox funding unavailable. Check account, integer amount and unique reference; no real money moves.')
        return 1
