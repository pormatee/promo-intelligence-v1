#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_capture(script: str) -> str:
    cmd=[sys.executable,script]
    print("STEP="+" ".join(cmd),flush=True)
    p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    out=p.stdout or ""; print(out,end="" if out.endswith("\n") else "\n",flush=True)
    if p.returncode:
        print("P6_RESULT=FAIL"); print("FAILED_STEP="+" ".join(cmd)); raise SystemExit(p.returncode)
    return out


def run_tests() -> None:
    cmd=[sys.executable,"-m","unittest","discover","-s","tests","-p","test_p6_offer_identity.py","-v"]
    print("STEP="+" ".join(cmd),flush=True)
    env = dict(__import__("os").environ)
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + (__import__("os").pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    p=subprocess.run(cmd,cwd=ROOT,env=env)
    if p.returncode:
        print("P6_RESULT=FAIL"); print("FAILED_STEP=P6_TARGETED_TESTS"); raise SystemExit(p.returncode)


def metric(text: str, name: str, default: int=0) -> int:
    m=re.findall(rf"^{re.escape(name)}=(-?\d+)\s*$",text,flags=re.M)
    return int(m[-1]) if m else default


def main() -> int:
    print("=== P6 Offer Identity / Campaign Boundary Integrity Gate ===")
    run_tests()
    repair=run_capture("repair_offer_identity.py")
    # Re-run the bounded applicability closure on the cleaned identity set. P5H
    # now ignores identity-rejected fragments, so only real unresolved offers are
    # sent to P5F/P5G.
    closure=run_capture("applicability_autoclose_loop.py")
    report=run_capture("show_offer_identity_report.py")
    rejected=metric(repair,"IDENTITY_REJECTED")
    review=metric(repair,"IDENTITY_REVIEW")
    published=metric(report,"PUBLISHED_OFFERS")
    actionable=metric(report,"ACTIONABLE_UNKNOWN_AFTER_IDENTITY_GATE")
    pub_rejected=metric(report,"PUBLISHED_IDENTITY_REJECTED",999)
    print("\n=== P6 FINAL ===")
    print(f"IDENTITY_REJECTED={rejected}")
    print(f"IDENTITY_REVIEW={review}")
    print(f"PUBLISHED_OFFERS={published}")
    print(f"PUBLISHED_IDENTITY_REJECTED={pub_rejected}")
    print(f"ACTIONABLE_UNKNOWN_FINAL={actionable}")
    print("IDENTITY_GATE_STATE=FAIL_CLOSED_REJECTED_EXCLUDED")
    print("P6_RESULT=PASS" if pub_rejected==0 else "P6_RESULT=FAIL")
    return 0 if pub_rejected==0 else 3

if __name__=="__main__": raise SystemExit(main())
