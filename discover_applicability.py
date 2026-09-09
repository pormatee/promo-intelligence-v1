#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from promo_intelligence.applicability_enrichment import enrich_offers_applicability
from promo_intelligence.contract import validate_offer

OFFERS=ROOT/'output'/'promo_offer_v1.jsonl'
SOURCES=ROOT/'config'/'sources.json'
RAW=ROOT/'data'/'raw'

def read_jsonl(p):
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def write_jsonl(p,rows):
    with p.open('w',encoding='utf-8') as f:
        for x in rows: f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')

def actionable(rows):
    return sum((o.get('applicability') or {}).get('scope')=='unknown'
               and (o.get('applicability') or {}).get('channel')!='online'
               and (o.get('offer_identity') or {}).get('state')!='rejected' for o in rows)

def main():
    offers=read_jsonl(OFFERS)
    if not offers:
        print('P5F_DISCOVERY_RESULT=FAIL'); print('REASON=NO_OFFERS'); return 2
    source_rows=json.loads(SOURCES.read_text(encoding='utf-8'))
    sources={x['source_id']:x for x in source_rows if x.get('enabled',True)}
    raw={}
    for sid in sources:
        p=RAW/f'{sid}.html'
        if p.exists(): raw[sid]=p.read_text(encoding='utf-8',errors='replace')
    before=actionable(offers)
    enriched,stats=enrich_offers_applicability(offers,sources,raw)
    errors=sum(bool(validate_offer(x)) for x in enriched)
    after=actionable(enriched)
    if errors:
        print(f'CONTRACT_ERRORS={errors}'); print('P5F_DISCOVERY_RESULT=FAIL'); return 3
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'output'/f'promo_offer_v1.pre_applicability_discovery_{stamp}.jsonl'
    shutil.copy2(OFFERS,backup)
    write_jsonl(OFFERS,enriched)
    print(f'OFFERS_SCANNED={len(offers)}')
    print(f'ACTIONABLE_UNKNOWN_BEFORE={before}')
    print(f'APPLICABILITY_DISCOVERY_ATTEMPTED={stats["attempted"]}')
    print(f'APPLICABILITY_DISCOVERED={stats["discovered"]}')
    print(f'DISCOVERED_NATIONWIDE={stats["nationwide"]}')
    print(f'DISCOVERED_PROVINCE={stats["province"]}')
    print(f'DISCOVERED_BRANCH={stats["branch"]}')
    print(f'CONTEXT_AMBIGUOUS={stats["context_ambiguous"]}')
    print(f'TITLE_NOT_FOUND_IN_RAW={stats["title_not_found"]}')
    print(f'RAW_SOURCE_MISSING={stats["raw_missing"]}')
    print(f'ACTIONABLE_UNKNOWN_AFTER={after}')
    print('CONTRACT_ERRORS=0')
    print(f'BACKUP={backup}')
    print('P5F_DISCOVERY_RESULT=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
