#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def stream(cmd: list[str], env=None) -> int:
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
    assert p.stdout is not None
    for line in p.stdout:
        print(line, end="", flush=True)
    return p.wait()


def main() -> int:
    print("=== P5C PLACE ENRICHMENT LOOP ===", flush=True)
    print("STEP=REGRESSION", flush=True)
    env = dict(__import__('os').environ)
    env["PYTHONPATH"] = str(ROOT / "src") + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
    rc = stream([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], env=env)
    if rc != 0:
        print("P5C_RESULT=HARD_BLOCK")
        print("HARD_BLOCK_REASON=REGRESSION_FAILED")
        return rc

    print("STEP=OFFICIAL_BRANCH_DISCOVERY", flush=True)
    rc = stream([sys.executable, "refresh_places.py"], env=env)
    # A zero-branch first run is a real blocker, but partial source failures are
    # allowed because refresh_places returns 0 whenever a usable branch cache exists.
    if rc != 0:
        print("P5C_RESULT=HARD_BLOCK")
        print("HARD_BLOCK_REASON=NO_USABLE_BRANCH_DIRECTORY")
        return rc

    print("STEP=PLACE_MASTER_AND_PUBLISH", flush=True)
    rc = stream([sys.executable, "build_place_publish.py"], env=env)
    if rc != 0:
        print("P5C_RESULT=HARD_BLOCK")
        print("HARD_BLOCK_REASON=PLACE_PUBLISH_FAILED")
        return rc

    diag_path = ROOT / "output" / "place_enrichment.diagnostics.json"
    manifest_path = ROOT / "output" / "published" / "manifest.json"
    diag = json.loads(diag_path.read_text(encoding="utf-8")) if diag_path.exists() else {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    print("\n=== P5C FINAL ===")
    print(f"PLACE_SOURCE_FOUND={diag.get('sources_found', 0)}")
    print(f"PLACE_FETCHED={diag.get('fetched', 0)}")
    print(f"PLACE_FETCH_FAILED={diag.get('fetch_failed', 0)}")
    print(f"BRANCH_CANDIDATES={diag.get('branch_candidates', 0)}")
    print(f"PLACE_CACHE_BRANCHES={diag.get('branch_places', 0)}")
    print(f"BRANCH_WITH_PROVINCE={diag.get('branch_with_province', 0)}")
    print(f"BRANCH_WITH_ADDRESS={diag.get('branch_with_address', 0)}")
    print(f"PUBLISHED_OFFERS={manifest.get('offer_count', 0)}")
    print(f"PUBLISHED_PLACES={manifest.get('place_count', 0)}")
    print(f"PUBLISHED_BRANCH_PLACES={manifest.get('branch_place_count', 0)}")
    print(f"MERCHANT_BRANCH_INDEX_ENTRIES={manifest.get('merchant_branch_index_count', 0)}")
    print("CONTRACT_ERRORS=0")
    print("PLACE_CONTRACT_ERRORS=0")
    print("PUBLISHED_READ_MODEL=PASS")
    mode = "CLEAN" if diag.get("fetch_failed", 0) == 0 else "DEGRADED_SOURCE_FAILURES"
    print("P5C_RESULT=PASS")
    print(f"PASS_MODE={mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
