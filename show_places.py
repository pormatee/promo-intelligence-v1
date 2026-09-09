#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "output" / "published" / "promo_place_v1.jsonl"

rows=[]
if PATH.exists():
    rows=[json.loads(x) for x in PATH.read_text(encoding="utf-8").splitlines() if x.strip()]
merchants=[x for x in rows if x.get("record_kind")=="merchant"]
branches=[x for x in rows if x.get("record_kind")=="branch"]
print("=== Promo Intelligence Places ===")
print(f"Merchants : {len(merchants)}")
print(f"Branches  : {len(branches)}")
by={}
for b in branches:
    m=(b.get("merchant") or {}).get("name") or "-"
    by.setdefault(m, []).append(b)
for merchant in sorted(by):
    print(f"\n{merchant}: {len(by[merchant])} branches")
    for b in by[merchant][:12]:
        loc=b.get("location") or {}
        parts=[(b.get("branch") or {}).get("name"), loc.get("district"), loc.get("province"), loc.get("postal_code")]
        print("  - " + " | ".join(str(x) for x in parts if x))
    if len(by[merchant]) > 12:
        print(f"  ... +{len(by[merchant])-12} more")
