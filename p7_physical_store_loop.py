#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json, os, re, shutil, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'src'
sys.path.insert(0,str(SRC))
from promo_intelligence.contract import validate_offer

OFFERS=ROOT/'output'/'promo_offer_v1.jsonl'
SOURCES=ROOT/'config'/'sources.json'
RAW=ROOT/'data'/'raw'
CONSUMER=ROOT/'promo_consumer.html'
MANIFEST=ROOT/'output'/'published'/'manifest.json'

SELECTED_PATTERNS=[
    re.compile(r"(?:valid|available|redeemable|use|usable).{0,80}(?:at|in)?\s*(?:participating|selected)\s+(?:branches|stores|locations|outlets)",re.I|re.S),
    re.compile(r"(?:participating|selected)\s+(?:branches|stores|locations|outlets)",re.I),
    re.compile(r"(?:เฉพาะ|ที่|ณ)?\s*สาขาที่ร่วมรายการ",re.I),
    re.compile(r"(?:ใช้ได้|ร่วมรายการ|รับสิทธิ์ได้).{0,80}(?:เฉพาะ)?\s*(?:บางสาขา|สาขาที่ร่วมรายการ)",re.I|re.S),
]
NATIONWIDE_PATTERNS=[
    re.compile(r"(?:valid|available|redeemable|use|usable).{0,80}(?:at|in)?\s*(?:all branches|all stores|nationwide)",re.I|re.S),
    re.compile(r"(?:all branches|all stores)\s+nationwide",re.I),
    re.compile(r"(?:ใช้ได้|ร่วมรายการ|รับสิทธิ์ได้).{0,80}(?:ทุกสาขา|ทั่วประเทศ)",re.I|re.S),
    re.compile(r"ทุกสาขาทั่วประเทศ",re.I),
]
GENERIC={"promotion","promotions","campaign","campaigns","offer","offers","promo","promos"}
LOCALES={"th","en","thai","english"}

class TextParser(HTMLParser):
    BLOCK={"p","div","li","br","h1","h2","h3","h4","section","article","span","a","button"}
    def __init__(self): super().__init__(); self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower() in self.BLOCK:self.parts.append("\n")
    def handle_endtag(self,tag):
        if tag.lower() in self.BLOCK:self.parts.append("\n")
    def handle_data(self,data): self.parts.append(data)

def html_text(raw):
    p=TextParser(); p.feed(raw)
    text=unescape("".join(p.parts)).replace("\xa0"," ")
    return " | ".join(re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip())

def read_jsonl(path):
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def write_jsonl(path,rows):
    with path.open('w',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")

def source_is_campaign_specific(source):
    if 'parent_campaign_inheritance' in source:return bool(source.get('parent_campaign_inheritance'))
    try: parts=[p.casefold() for p in urlparse(str(source.get('url') or '')).path.split('/') if p]
    except Exception:return False
    for i,part in enumerate(parts):
        if part in GENERIC:
            tail=[x for x in parts[i+1:] if x not in LOCALES]
            return bool(tail and tail[0] not in GENERIC and len(tail[0])>=2)
    return False

def first_match(text,patterns):
    hits=[]
    for pat in patterns:
        m=pat.search(text)
        if m:hits.append(m)
    return min(hits,key=lambda m:m.start()) if hits else None

def ex(text,m,r=220):
    return re.sub(r"\s+"," ",text[max(0,m.start()-r):min(len(text),m.end()+r)]).strip()[:600]

def detect_parent_scope(raw,source):
    if not raw or not source_is_campaign_specific(source):return None
    text=html_text(raw)
    sel=first_match(text,SELECTED_PATTERNS); nat=first_match(text,NATIONWIDE_PATTERNS)
    if sel and nat:return {'state':'conflict','scope':None}
    if sel:return {'state':'explicit','scope':'selected_branches','evidence_excerpt':ex(text,sel)}
    if nat:return {'state':'explicit','scope':'nationwide','evidence_excerpt':ex(text,nat)}
    return None

def actionable(o):
    a=o.get('applicability') or {}; i=o.get('offer_identity') or {}
    return a.get('scope')=='unknown' and a.get('channel')!='online' and i.get('state')!='rejected'

def selftest():
    assert source_is_campaign_specific({'url':'https://x.test/promotions/1544/en'})
    assert not source_is_campaign_specific({'url':'https://x.test/promotion'})
    assert detect_parent_scope('<p>Valid at participating branches only</p>',{'url':'https://x.test/promotions/1544/en'})['scope']=='selected_branches'
    assert detect_parent_scope('<p>Valid at all branches nationwide</p>',{'url':'https://x.test/promotions/1544/en'})['scope']=='nationwide'
    assert detect_parent_scope('<p>Valid at participating branches</p><p>Valid at all branches</p>',{'url':'https://x.test/promotions/1544/en'})['state']=='conflict'
    print('P7_SELFTEST=PASS')

def inherit_parent_campaign():
    offers=read_jsonl(OFFERS)
    if not offers: raise RuntimeError('NO_OFFERS')
    rows=json.loads(SOURCES.read_text(encoding='utf-8'))
    sources={x['source_id']:x for x in rows if x.get('enabled',True)}
    raw={}
    for sid in sources:
        p=RAW/f'{sid}.html'
        if p.exists():raw[sid]=p.read_text(encoding='utf-8',errors='replace')
    stats={'before':sum(actionable(o) for o in offers),'checked':0,'generic':0,'missing':0,'explicit':0,'conflicts':0,'inherited':0,'selected':0,'nationwide':0}
    evs={}
    for sid,src in sources.items():
        if not source_is_campaign_specific(src): stats['generic']+=1; continue
        stats['checked']+=1
        if sid not in raw: stats['missing']+=1; continue
        ev=detect_parent_scope(raw[sid],src); evs[sid]=ev
        if ev and ev.get('state')=='conflict':stats['conflicts']+=1
        elif ev and ev.get('state')=='explicit':stats['explicit']+=1
    out=[]
    for offer in offers:
        row=json.loads(json.dumps(offer))
        sid=(row.get('source') or {}).get('source_id') or ''
        src=sources.get(sid) or {}; ev=evs.get(sid)
        if actionable(row) and ev and ev.get('state')=='explicit':
            scope=ev.get('scope'); old=row.get('applicability') or {}; ch=old.get('channel') or src.get('channel') or 'unknown'
            row['applicability']={'scope':scope,'country':old.get('country') or 'TH','provinces':[],'branches':[],'verification_state':'explicit','basis':'parent_campaign','channel':ch,'channel_basis':old.get('channel_basis') or ('source_config' if ch!='unknown' else 'none')}
            if scope=='nationwide':row['geography']={'country':'TH','detail_state':'nationwide','best_granularity':'nationwide','locations':[]}
            row['applicability_evidence']={'state':'explicit','method':'parent_campaign_explicit_scope','source_id':sid,'url':src.get('url'),'content_hash':(row.get('evidence') or {}).get('content_hash'),'evidence_excerpt':str(ev.get('evidence_excerpt') or '')[:600]}
            stats['inherited']+=1; stats['selected' if scope=='selected_branches' else 'nationwide']+=1
        out.append(row)
    errors=sum(bool(validate_offer(x)) for x in out)
    if errors: raise RuntimeError(f'CONTRACT_ERRORS={errors}')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'output'/f'promo_offer_v1.pre_p7_parent_{stamp}.jsonl'
    shutil.copy2(OFFERS,backup); write_jsonl(OFFERS,out)
    stats['after']=sum(actionable(o) for o in out)
    print('=== P7A PARENT CAMPAIGN INHERITANCE ===')
    print(f"ACTIONABLE_UNKNOWN_BEFORE={stats['before']}")
    print(f"CAMPAIGN_SOURCES_CHECKED={stats['checked']}")
    print(f"GENERIC_LISTING_SOURCES_SKIPPED={stats['generic']}")
    print(f"PARENT_RAW_MISSING={stats['missing']}")
    print(f"PARENT_SCOPE_EXPLICIT={stats['explicit']}")
    print(f"PARENT_SCOPE_CONFLICTS={stats['conflicts']}")
    print(f"PARENT_INHERITED_OFFERS={stats['inherited']}")
    print(f"PARENT_INHERITED_SELECTED_BRANCHES={stats['selected']}")
    print(f"PARENT_INHERITED_NATIONWIDE={stats['nationwide']}")
    print(f"ACTIONABLE_UNKNOWN_AFTER_PARENT={stats['after']}")
    print('P7A_RESULT=PASS')

def env():
    e=dict(os.environ); e['PYTHONPATH']=str(SRC)+(os.pathsep+e['PYTHONPATH'] if e.get('PYTHONPATH') else ''); return e

def run_script(script):
    cmd=[sys.executable,script]; print('STEP='+' '.join(cmd),flush=True)
    rc=subprocess.run(cmd,cwd=ROOT,env=env()).returncode
    if rc: print('P7_RESULT=FAIL'); print('FAILED_STEP='+' '.join(cmd)); raise SystemExit(rc)

def regression():
    cmd=[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py']; print('STEP='+' '.join(cmd),flush=True)
    rc=subprocess.run(cmd,cwd=ROOT,env=env()).returncode
    if rc: print('P7_RESULT=FAIL'); print('FAILED_STEP=FULL_REGRESSION'); raise SystemExit(rc)

def patch_consumer():
    if not CONSUMER.exists():return 'MISSING'
    text=CONSUMER.read_text(encoding='utf-8'); original=text
    text=text.replace("if(a.scope==='nationwide')return 'ทั่วประเทศ'; if(gs.length)","if(a.scope==='nationwide')return 'ทั่วประเทศ'; if(a.scope==='selected_branches')return 'หน้าร้าน — ต้องตรวจสาขา'; if(gs.length)")
    text=text.replace("let local=0,nationwide=0,online=0;","let local=0,nationwide=0,online=0,storeCheck=0;")
    text=text.replace("else if(c==='online')online++","else if(c==='online')online++;else if(app(o).scope==='selected_branches')storeCheck++")
    text=text.replace("· ออนไลน์ ${fmt(online)} <span","· หน้าร้านต้องตรวจสาขา ${fmt(storeCheck)} · ออนไลน์ ${fmt(online)} <span")
    if text!=original:CONSUMER.write_text(text,encoding='utf-8'); return 'PATCHED'
    return 'NO_CHANGE'

def metrics():
    published_path = ROOT/'output'/'published'/'promo_offer_v1.jsonl'
    offers = read_jsonl(published_path)
    if not offers:
        raise RuntimeError('NO_PUBLISHED_OFFERS')

    app = lambda o: o.get('applicability') or {}
    physical = [o for o in offers if app(o).get('channel') != 'online']
    online = [o for o in offers if app(o).get('channel') == 'online']

    provinces = set()
    for o in offers:
        for g in ((o.get('geography') or {}).get('locations') or []):
            if g.get('province'):
                provinces.add(str(g['province']))

    total_check = len(physical) + len(online)
    if total_check != len(offers):
        raise RuntimeError(
            f'PUBLISHED_BASIS_MISMATCH offers={len(offers)} '
            f'physical={len(physical)} online={len(online)}'
        )

    return {
        'published': len(offers),
        'physical': len(physical),
        'selected': sum(app(o).get('scope') == 'selected_branches' for o in physical),
        'nationwide': sum(app(o).get('scope') == 'nationwide' for o in physical),
        'branch': sum(app(o).get('scope') == 'branch_specific' for o in physical),
        'unknown': sum(app(o).get('scope') == 'unknown' for o in physical),
        'online': len(online),
        'local_provinces': len(provinces),
    }


def main():
    print('=== P7 PHYSICAL STORE AUTONOMOUS ONE-LOOP ===')
    selftest()
    print('\n=== STAGE 0 REGRESSION ==='); regression()
    print('\n=== STAGE 1 IDENTITY REFRESH ==='); run_script('repair_offer_identity.py')
    print('\n=== STAGE 2 OFFICIAL BRANCH DIRECTORY REFRESH ==='); run_script('refresh_places.py')
    print('\n=== STAGE 3 PARENT CAMPAIGN APPLICABILITY ==='); inherit_parent_campaign()
    print('\n=== STAGE 4 BOUNDED DIRECT/DETAIL DISCOVERY ==='); run_script('discover_applicability.py'); run_script('discover_applicability_details.py')
    print('\n=== STAGE 5 PUBLISHED READ MODEL ==='); run_script('build_place_publish.py')
    print('\n=== STAGE 6 CONSUMER REBUILD ==='); run_script('build_promo_consumer.py'); print('P7_CONSUMER_SELECTED_BRANCHES_UI='+patch_consumer())
    print('\n=== STAGE 7 REAL COVERAGE / BACKLOG ==='); run_script('show_area_coverage.py'); run_script('show_applicability_backlog.py')
    m=metrics()
    print('\n=== P7 FINAL ===')
    print(f"PUBLISHED_OFFERS={m['published']}")
    print(f"PHYSICAL_STORE_OFFERS={m['physical']}")
    print(f"PHYSICAL_SELECTED_BRANCHES={m['selected']}")
    print(f"PHYSICAL_NATIONWIDE={m['nationwide']}")
    print(f"PHYSICAL_BRANCH_SPECIFIC={m['branch']}")
    print(f"PHYSICAL_UNKNOWN={m['unknown']}")
    print(f"ONLINE_OFFERS={m['online']}")
    print(f"LOCAL_CONFIRMED_PROVINCES={m['local_provinces']}")
    print(f"CONSUMER_READY={'TRUE' if CONSUMER.exists() else 'FALSE'}")
    print('P7_STATE=' + ('SAFE_UNKNOWN_REMAINS' if m['unknown'] else 'PHYSICAL_SCOPE_CLOSED'))
    print('P7_RESULT=PASS')
    return 0

if __name__=='__main__':raise SystemExit(main())
