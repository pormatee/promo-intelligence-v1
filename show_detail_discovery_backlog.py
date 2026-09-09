#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=ROOT/'output'/'promo_offer_v1.jsonl'
rows=[]
if p.exists():
    rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
unknown=[o for o in rows if (o.get('applicability') or {}).get('scope')=='unknown' and (o.get('applicability') or {}).get('channel')!='online' and (o.get('offer_identity') or {}).get('state')!='rejected']
print('=== P5G Detail Discovery Backlog ===')
print(f'ACTIONABLE_UNKNOWN={len(unknown)}')
for o in unknown[:50]:
    s=o.get('source') or {}; item=o.get('item') or {}; merchant=o.get('merchant') or {}
    print(f"  - {s.get('source_id','-')} | {merchant.get('name','-')} | {item.get('name','-')}")
