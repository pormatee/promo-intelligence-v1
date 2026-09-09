#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.contract import validate_offer
from promo_intelligence.offer_identity import annotate_offers_identity

OFFERS = ROOT / "output" / "promo_offer_v1.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    offers = read_jsonl(OFFERS)
    if not offers:
        print("P6_IDENTITY_REPAIR_RESULT=FAIL"); print("REASON=NO_OFFERS"); return 2
    rows, stats = annotate_offers_identity(offers)
    errors = sum(bool(validate_offer(x)) for x in rows)
    if errors:
        print(f"CONTRACT_ERRORS={errors}"); print("P6_IDENTITY_REPAIR_RESULT=FAIL"); return 3
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "output" / f"promo_offer_v1.pre_offer_identity_{stamp}.jsonl"
    shutil.copy2(OFFERS, backup)
    write_jsonl(OFFERS, rows)

    reason_counts = Counter()
    for row in rows:
        for reason in (row.get("offer_identity") or {}).get("reason_codes") or []:
            reason_counts[reason] += 1

    print(f"OFFERS_SCANNED={len(rows)}")
    print(f"IDENTITY_ACCEPTED={stats.get('accepted',0)}")
    print(f"IDENTITY_REVIEW={stats.get('review',0)}")
    print(f"IDENTITY_REJECTED={stats.get('rejected',0)}")
    print(f"IDENTITY_PRICE_DISCLAIMER={sum(v for k,v in reason_counts.items() if 'price_disclaimer' in k)}")
    print(f"IDENTITY_AVAILABILITY_CONDITION={sum(v for k,v in reason_counts.items() if 'availability_condition' in k)}")
    print(f"IDENTITY_EXCLUSION_FRAGMENT={sum(v for k,v in reason_counts.items() if 'exclusion_fragment' in k)}")
    print(f"IDENTITY_TERMS_FRAGMENT={sum(v for k,v in reason_counts.items() if 'terms_fragment' in k)}")
    print(f"IDENTITY_ACTION_ONLY_CTA={sum(v for k,v in reason_counts.items() if 'action_only_cta' in k)}")
    print(f"IDENTITY_TECHNICAL_PAYLOAD={sum(v for k,v in reason_counts.items() if 'technical_payload' in k)}")
    print(f"IDENTITY_DESCRIPTION_REVIEW={reason_counts.get('item_description_fragment',0)}")
    print("CONTRACT_ERRORS=0")
    print(f"BACKUP={backup}")
    print("P6_IDENTITY_REPAIR_RESULT=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
