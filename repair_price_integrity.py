#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "output" / "promo_offer_v1.jsonl"
sys.path.insert(0, str(ROOT / "src"))
from promo_intelligence.contract import validate_offer
from promo_intelligence.price_integrity import sanitize_offer_pricing


def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    if not SRC.exists():
        print("PRICE_INTEGRITY_RESULT=FAIL")
        print("REASON=NO_PROMO_OFFER_OUTPUT")
        return 2
    rows = read_jsonl(SRC)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = SRC.with_name(f"promo_offer_v1.pre_price_integrity_{stamp}.jsonl")
    shutil.copy2(SRC, backup)
    fixed = [sanitize_offer_pricing(x) for x in rows]
    errors = sum(bool(validate_offer(x)) for x in fixed)
    unsupported_regular = sum(
        (a.get("pricing") or {}).get("regular_price") is not None and (b.get("pricing") or {}).get("regular_price") is None
        for a, b in zip(rows, fixed)
    )
    unsupported_promo = sum(
        (a.get("pricing") or {}).get("promo_price") is not None and (b.get("pricing") or {}).get("promo_price") is None
        for a, b in zip(rows, fixed)
    )
    anomalies = sum(bool((x.get("pricing") or {}).get("anomalies")) for x in fixed)
    rejected = sum((x.get("verification") or {}).get("verification_state") == "rejected" for x in fixed)
    if errors:
        print(f"CONTRACT_ERRORS={errors}")
        print("PRICE_INTEGRITY_RESULT=FAIL")
        return 3
    write_jsonl(SRC, fixed)
    print(f"OFFERS_SCANNED={len(rows)}")
    print(f"REGULAR_PRICE_CLAIMS_REMOVED={unsupported_regular}")
    print(f"PROMO_PRICE_CLAIMS_REMOVED={unsupported_promo}")
    print(f"PRICE_ANOMALY_OFFERS={anomalies}")
    print(f"REJECTED_OFFERS_AFTER_GATE={rejected}")
    print("CONTRACT_ERRORS=0")
    print(f"BACKUP={backup}")
    print("STEP=REBUILD_PLACE_PUBLISHED")
    rc = subprocess.call([sys.executable, "build_place_publish.py"], cwd=ROOT)
    if rc != 0:
        print("PRICE_INTEGRITY_RESULT=FAIL")
        print("REASON=REPUBLISH_FAILED")
        return rc
    if (ROOT / "build_promo_lab.py").exists():
        print("STEP=REBUILD_PROMO_LAB")
        subprocess.call([sys.executable, "build_promo_lab.py"], cwd=ROOT)
    print("PRICE_INTEGRITY_RESULT=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
