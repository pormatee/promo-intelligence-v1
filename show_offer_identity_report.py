#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "output" / "promo_offer_v1.jsonl"
PUB = ROOT / "output" / "published" / "promo_offer_v1.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    raw = read_jsonl(RAW); pub = read_jsonl(PUB)
    states = Counter((o.get("offer_identity") or {}).get("state", "legacy") for o in raw)
    reasons = Counter(r for o in raw for r in ((o.get("offer_identity") or {}).get("reason_codes") or []))
    pub_rejected = sum((o.get("offer_identity") or {}).get("state") == "rejected" for o in pub)
    actionable = sum(
        (o.get("applicability") or {}).get("scope") == "unknown"
        and (o.get("applicability") or {}).get("channel") != "online"
        and (o.get("offer_identity") or {}).get("state") != "rejected"
        for o in raw
    )
    print("=== P6 Offer Identity Report ===")
    print(f"RAW_OFFERS={len(raw)}")
    print(f"IDENTITY_ACCEPTED={states['accepted']}")
    print(f"IDENTITY_REVIEW={states['review']}")
    print(f"IDENTITY_REJECTED={states['rejected']}")
    print(f"IDENTITY_LEGACY={states['legacy']}")
    print(f"PUBLISHED_OFFERS={len(pub)}")
    print(f"PUBLISHED_IDENTITY_REJECTED={pub_rejected}")
    print(f"ACTIONABLE_UNKNOWN_AFTER_IDENTITY_GATE={actionable}")
    print("Reject/review reasons:")
    if not reasons: print("  (none)")
    for reason, n in reasons.most_common(): print(f"  {reason}: {n}")
    print("Rejected examples:")
    rejected = [o for o in raw if (o.get("offer_identity") or {}).get("state") == "rejected"]
    if not rejected: print("  (none)")
    for o in rejected[:20]:
        src=o.get('source') or {}; m=o.get('merchant') or {}; item=o.get('item') or {}; ident=o.get('offer_identity') or {}
        print(f"  - {src.get('source_id','-')} | {m.get('name','-')} | {item.get('name','-')} | {','.join(ident.get('reason_codes') or [])}")
    print("P6_IDENTITY_REPORT=PASS" if pub_rejected == 0 else "P6_IDENTITY_REPORT=FAIL")
    return 0 if pub_rejected == 0 else 2

if __name__ == "__main__": raise SystemExit(main())
