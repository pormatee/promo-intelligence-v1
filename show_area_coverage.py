#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
P=ROOT/'output'/'published'/'promo_offer_v1.jsonl'

def rows():
    if not P.exists(): return []
    return [json.loads(x) for x in P.read_text(encoding='utf-8').splitlines() if x.strip()]

def main():
    offers=rows(); local=Counter(); nationwide=online=unknown=0; linked=0
    for o in offers:
        a=o.get('applicability') or {}; g=o.get('geography') or {}
        if a.get('channel')=='online': online+=1
        if a.get('scope')=='nationwide': nationwide+=1
        provs={x.get('province_raw') or x.get('province') for x in g.get('locations') or [] if x.get('province_raw') or x.get('province')}
        for p in provs: local[p]+=1
        if (o.get('area_linkage') or {}).get('state')=='linked': linked+=1
        if not provs and a.get('scope')!='nationwide' and a.get('channel')!='online': unknown+=1
    print('=== Area Coverage (Published Read Model) ===')
    print(f'PUBLISHED_OFFERS={len(offers)}')
    print(f'LOCAL_PROVINCES_WITH_OFFERS={len(local)}')
    print(f'EXPLICIT_BRANCH_LINKED_OFFERS={linked}')
    print(f'NATIONWIDE_OFFERS={nationwide}')
    print(f'ONLINE_OFFERS={online}')
    print(f'LOCAL_AREA_UNKNOWN_OFFERS={unknown}')
    print('\nLocal-confirmed by province:')
    if not local: print('  (none)')
    for p,n in local.most_common(): print(f'  {p}: {n}')
    return 0
if __name__=='__main__': raise SystemExit(main())
