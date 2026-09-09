#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "promo_offer_v1.jsonl"
DIAG = ROOT / "output" / "promo_offer_v1.diagnostics.json"
CONFIG = ROOT / "config" / "sources.json"

# Verified P4 Wave B baseline on Android + Termux.
BASELINE = {
    "sources": 23,
    "fetched": 20,
    "fetch_failed": 3,
    "exported": 430,
    "location_unknown_actionable": 20,
    "families_with_offers": 11,
}
MAX_LIVE_ITERATIONS = 3
MIN_EXPORTED_GUARD = 400


def _stream(cmd: list[str]) -> int:
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert p.stdout is not None
    for line in p.stdout:
        print(line, end="", flush=True)
    return p.wait()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _offers() -> list[dict]:
    if not OUTPUT.exists():
        return []
    rows=[]
    for line in OUTPUT.read_text(encoding="utf-8").splitlines():
        if line.strip(): rows.append(json.loads(line))
    return rows


def _contract_errors(offers: list[dict]) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from promo_intelligence.contract import validate_offer
    return sum(bool(validate_offer(x)) for x in offers)


def _coverage(offers: list[dict]) -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    from promo_intelligence.coverage import coverage_summary
    return coverage_summary(offers)


def _snapshot(iteration: int) -> tuple[Path, Path]:
    out=ROOT/'output'/f'wave_c_iter{iteration}.jsonl'
    dg=ROOT/'output'/f'wave_c_iter{iteration}.diagnostics.json'
    if OUTPUT.exists(): shutil.copy2(OUTPUT,out)
    if DIAG.exists(): shutil.copy2(DIAG,dg)
    return out,dg


def _facts(diag: dict, offers: list[dict]) -> dict:
    s=diag.get('summary',{})
    q=diag.get('quality',{})
    errs=diag.get('source_errors') or []
    internal_fetch=[e for e in errs if e.get('stage')=='fetch' and not e.get('hard_block')]
    extract=[e for e in errs if e.get('stage')=='extract']
    cov=_coverage(offers)
    return {
        'sources':s.get('sources',0), 'fetched':s.get('fetched',0), 'fetch_failed':s.get('fetch_failed',0),
        'fetch_recovered':s.get('fetch_recovered',0), 'hard_block_count':len(diag.get('hard_block_sources') or []),
        'zero_offer_sources':s.get('zero_offer_sources',0), 'zero_offer_recovered':s.get('zero_offer_recovered',0),
        'exported':s.get('exported',len(offers)), 'families_with_offers':s.get('families_with_offers',0),
        'actionable_unknown':q.get('location_unknown_actionable',0), 'corroborated':q.get('corroborated',0),
        'contract_errors':_contract_errors(offers), 'internal_fetch_errors':internal_fetch,
        'extract_errors':extract, 'hard_block_sources':diag.get('hard_block_sources') or [],
        'national_reach':bool(cov.get('national_geographic_reach')),
    }


def _closed(f: dict) -> bool:
    return (
        f['sources']==BASELINE['sources'] and
        f['exported']>=MIN_EXPORTED_GUARD and
        f['families_with_offers']>=BASELINE['families_with_offers'] and
        f['fetch_failed']<=BASELINE['fetch_failed'] and
        f['zero_offer_sources']==0 and
        not f['internal_fetch_errors'] and
        not f['extract_errors'] and
        f['contract_errors']==0 and
        f['actionable_unknown']<=BASELINE['location_unknown_actionable'] and
        f['national_reach']
    )


def _score(f: dict) -> tuple:
    return (
        1 if not f['internal_fetch_errors'] else 0,
        1 if not f['extract_errors'] else 0,
        1 if f['zero_offer_sources']==0 else 0,
        -f['fetch_failed'],
        f['exported'],
        f['corroborated'],
        -f['actionable_unknown'],
    )


def _adaptive_fix(diag: dict) -> list[str]:
    rows=json.loads(CONFIG.read_text(encoding='utf-8'))
    by_id={r['source_id']:r for r in rows}
    changed=[]
    for e in diag.get('source_errors') or []:
        if e.get('stage')!='fetch' or e.get('hard_block'):
            continue
        sid=e.get('source_id')
        src=by_id.get(sid)
        if not src: continue
        text=(e.get('error_type','')+' '+e.get('error','')).lower()
        if 'timeout' in text or 'timed out' in text or 'urlerror' in text:
            old=int(src.get('timeout_seconds',12))
            new=min(40, old+8)
            if new>old:
                src['timeout_seconds']=new
                src['recovery_budget_seconds']=max(int(src.get('recovery_budget_seconds',new)), new+6)
                src['curl_fallback']=True
                changed.append(f'{sid}:timeout {old}->{new}')
    if changed:
        CONFIG.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return changed


def _restore_best(best: dict) -> None:
    if best.get('out') and Path(best['out']).exists(): shutil.copy2(best['out'],OUTPUT)
    if best.get('diag') and Path(best['diag']).exists(): shutil.copy2(best['diag'],DIAG)


def main() -> int:
    print('=== Promo Intelligence P4 Wave C Autonomous Loop ===', flush=True)
    print('STEP=REGRESSION', flush=True)
    rc=_stream(['bash','run_tests.sh'])
    if rc!=0:
        print('WAVE_C_RESULT=HARD_BLOCK')
        print('HARD_BLOCK_REASON=REGRESSION_FAILED')
        return 2

    backup=ROOT/'output'/'wave_c_sources.before.json'
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(CONFIG,backup)
    best=None

    for iteration in range(1,MAX_LIVE_ITERATIONS+1):
        print(f'\nSTEP=LIVE ITERATION={iteration}/{MAX_LIVE_ITERATIONS}', flush=True)
        rc=_stream([sys.executable,'promo_intel.py','run'])
        if rc!=0 or not DIAG.exists():
            print(f'ITERATION_RESULT={iteration}:RUNTIME_FAIL', flush=True)
            continue
        diag=_load_json(DIAG)
        offers=_offers()
        f=_facts(diag,offers)
        out_snap,diag_snap=_snapshot(iteration)
        candidate={'facts':f,'out':str(out_snap),'diag':str(diag_snap),'iteration':iteration}
        if best is None or _score(f)>_score(best['facts']): best=candidate

        print(f"ITERATION_SUMMARY={iteration} FETCHED={f['fetched']} FAILED={f['fetch_failed']} HARD_BLOCKS={f['hard_block_count']} ZERO={f['zero_offer_sources']} EXPORTED={f['exported']} ACTIONABLE_UNKNOWN={f['actionable_unknown']} CORROBORATED={f['corroborated']}")
        if _closed(f):
            best=candidate
            break

        fixes=_adaptive_fix(diag)
        if fixes:
            for fix in fixes: print(f'AUTOFIX={fix}',flush=True)
        else:
            # No safe internal adjustment remains. Further identical runs would
            # only add traffic without a new recovery strategy.
            if f['internal_fetch_errors'] or f['extract_errors'] or f['zero_offer_sources']:
                print('NO_MORE_SAFE_AUTOFIX=TRUE',flush=True)
                break

    if best is None:
        print('WAVE_C_RESULT=HARD_BLOCK')
        print('HARD_BLOCK_REASON=NO_VALID_LIVE_RESULT')
        return 3

    _restore_best(best)
    f=best['facts']
    mode='CLEAN' if f['hard_block_count']==0 else 'DEGRADED_EXTERNAL_BLOCKERS'
    print('\n=== WAVE C FINAL ===')
    print(f"BEST_ITERATION={best['iteration']}")
    print(f"SOURCE_FOUND={f['sources']}")
    print(f"FETCHED={f['fetched']}")
    print(f"FETCH_FAILED={f['fetch_failed']}")
    print(f"EXTERNAL_HARD_BLOCKERS={f['hard_block_count']}")
    for sid in f['hard_block_sources']: print(f'HARD_BLOCK_SOURCE={sid}')
    print(f"ZERO_OFFER_SOURCES={f['zero_offer_sources']}")
    print(f"EXPORTED={f['exported']}")
    print(f"CORROBORATED_OFFERS={f['corroborated']}")
    print(f"LOCATION_UNKNOWN_ACTIONABLE={f['actionable_unknown']}")
    print(f"CONTRACT_ERRORS={f['contract_errors']}")
    print(f"NATIONAL_GEOGRAPHIC_REACH={'TRUE' if f['national_reach'] else 'FALSE'}")
    print(f"DELTA_EXPORTED={f['exported']-BASELINE['exported']:+d}")
    print(f"DELTA_FETCH_FAILED={f['fetch_failed']-BASELINE['fetch_failed']:+d}")

    if _closed(f):
        print('WAVE_C_RESULT=PASS')
        print(f'PASS_MODE={mode}')
        return 0

    unresolved=[e.get('source_id') for e in f['internal_fetch_errors']+f['extract_errors']]
    print('WAVE_C_RESULT=HARD_BLOCK')
    print('HARD_BLOCK_REASON=SAFE_AUTONOMOUS_RECOVERY_EXHAUSTED')
    for sid in sorted(set(x for x in unresolved if x)): print(f'UNRESOLVED_SOURCE={sid}')
    for sid in (_load_json(DIAG).get('zero_offer_source_ids') or []): print(f'UNRESOLVED_ZERO_SOURCE={sid}')
    return 4


if __name__=='__main__':
    raise SystemExit(main())
