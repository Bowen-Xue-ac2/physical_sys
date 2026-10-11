import argparse
import json
import sys
from pathlib import Path

from . import Vault


def main():
    p=argparse.ArgumentParser(description='physical_sys local lifecycle / memory / wiki / retrieve')
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('ingest','compile','lint'):
        sub.add_parser(name)
    r=sub.add_parser('retrieve')
    r.add_argument('query');r.add_argument('--domain');r.add_argument('--limit',type=int,default=5)
    r.add_argument('--include-history',action='store_true');r.add_argument('--include-reference',action='store_true')
    m=sub.add_parser('remember')
    m.add_argument('text');m.add_argument('--domain',required=True);m.add_argument('--kind',required=True)
    m.add_argument('--evidence-kind',required=True);m.add_argument('--date',required=True);m.add_argument('--source',required=True)
    m.add_argument('--supersedes')
    rev=sub.add_parser('review');rev.add_argument('--start',required=True);rev.add_argument('--end',required=True)
    life=sub.add_parser('lifecycle');life.add_argument('--to');life.add_argument('--reason',default='')
    args=p.parse_args()
    v=Vault(args.root)
    try:
        if args.command=='remember':
            rid=v.remember(args.text,domain=args.domain,kind=args.kind,evidence_kind=args.evidence_kind,
                observed_at=args.date,source_ref=args.source,supersedes=args.supersedes)
            v.ingest();v.compile();result={'id':rid,'status':'recorded-and-indexed'}
        elif args.command=='retrieve':
            result=v.retrieve(args.query,domain=args.domain,include_history=args.include_history,
                include_reference=args.include_reference,limit=args.limit)
        elif args.command=='review':
            result=v.review(args.start,args.end)
        elif args.command=='lifecycle':
            result=v.transition(args.to,args.reason) if args.to else v.lifecycle()
        else:
            result=getattr(v,args.command)()
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.command=='lint' and result['errors']:
            return 1
        return 0
    except (ValueError, OSError) as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False),file=sys.stderr)
        return 2
    finally:
        v.db.close()


if __name__=='__main__':
    raise SystemExit(main())
