#!/usr/bin/env python3
from __future__ import annotations
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(cmd):
    print('STEP='+' '.join(cmd),flush=True)
    p=subprocess.run(cmd,cwd=ROOT)
    if p.returncode:
        print('P5G_RESULT=FAIL'); print('FAILED_STEP='+' '.join(cmd)); raise SystemExit(p.returncode)

def main():
    run([sys.executable,'discover_applicability_details.py'])
    run([sys.executable,'build_place_publish.py'])
    run([sys.executable,'build_promo_consumer.py'])
    run([sys.executable,'show_area_coverage.py'])
    run([sys.executable,'show_detail_discovery_backlog.py'])
    print('P5G_RESULT=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
