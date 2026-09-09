#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
P=ROOT/'output'/'published'/'promo_offer_v1.jsonl'

def main():
    rows=[] if not P.exists() else [json.loads(x) for x in P.read_text(encoding='utf-8').splitlines() if x.strip()]
    backlog=[o for o in rows if (o.get('applicability') or {}).get('scope')=='unknown' and (o.get('applicability') or {}).get('channel')!='online' and (o.get('offer_identity') or {}).get('state')!='rejected']
    bysrc=Counter((o.get('source') or {}).get('source_id','unknown') for o in backlog)
    print('=== Applicability Backlog ===')
    print(f'PUBLISHED_OFFERS={len(rows)}')
    print(f'LOCAL_AREA_UNKNOWN_OFFERS={len(backlog)}')
    print('By source:')
    if not bysrc: print('  (none)')
    for sid,n in bysrc.most_common(): print(f'  {sid}: {n}')
    print('\nSample unresolved offers:')
    for o in backlog[:20]:
        print(f"  - {(o.get('source') or {}).get('source_id','?')} | {(o.get('merchant') or {}).get('name','?')} | {(o.get('item') or {}).get('name','?')[:120]}")
    return 0
if __name__=='__main__': raise SystemExit(main())
