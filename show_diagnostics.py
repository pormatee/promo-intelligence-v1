#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parent
path = root / "output" / "promo_offer_v1.diagnostics.json"
if not path.exists():
    raise SystemExit("ไม่พบ diagnostics — รัน: python promo_intel.py run")
x = json.loads(path.read_text(encoding="utf-8"))
s = x.get("summary", {})
q = x.get("quality", {})
print("\n=== Promo Intelligence Diagnostics ===")
print(f"Sources       : {s.get('sources',0)}")
print(f"Fetched       : {s.get('fetched',0)}")
print(f"Fetch failed  : {s.get('fetch_failed',0)}")
print(f"Retried       : {s.get('fetch_retried',0)}")
print(f"Recovered     : {s.get('fetch_recovered',0)}")
print(f"Hard blockers : {s.get('hard_block_sources',0)}")
print(f"Zero recovered: {s.get('zero_offer_recovered',0)}")
print(f"Exported      : {s.get('exported',0)}")
print(f"Location unk. : {s.get('location_unknown',0)}")
print(f"Actionable unk: {q.get('location_unknown_actionable',0)}")
print(f"Online offers : {q.get('online',0)}")
print(f"Corroborated  : {q.get('corroborated',0)}")
print(f"Price verified: {q.get('price_verified',0)}")
print(f"Price partial : {q.get('price_partial',0)}")
print(f"Price rejected: {q.get('price_rejected',0)}")
print(f"Price anomalies: {q.get('price_anomaly_offers',0)}")
print(f"Geo known     : {s.get('geography_known',0)}")
print(f"District known: {s.get('district_known',0)}")
print(f"Subdist. known: {s.get('subdistrict_known',0)}")
print(f"Address known : {s.get('address_known',0)}")
print(f"Postal known  : {s.get('postal_code_known',0)}")
print(f"Coords known  : {s.get('coordinates_known',0)}")

hard=x.get('hard_block_sources') or []
if hard:
    print("\nExternal hard blockers (public official fallbacks exhausted):")
    for sid in hard:
        print(f"  - {sid}")

errors=x.get('source_errors') or []
if errors:
    print("\nแหล่งที่มีปัญหา:")
    for row in errors:
        hb=' HARD_BLOCK' if row.get('hard_block') else ''
        print(f"  - {row.get('source_id')} [{row.get('stage')}] {row.get('error_type')}: {row.get('error')}{hb}")

zero=x.get('zero_offer_source_ids') or []
if zero:
    print("\nFetch ได้แต่ยัง extract 0 offer:")
    for sid in zero:
        print(f"  - {sid}")

methods=x.get('fetch_recovery_methods') or {}
recovered={k:v for k,v in methods.items() if v!='urllib'}
if recovered:
    print("\nRecovered sources:")
    for sid,method in sorted(recovered.items()):
        print(f"  - {sid}: {method}")

counts=x.get('family_offer_counts') or {}
if counts:
    print("\nOffers ตาม source family:")
    for name,n in sorted(counts.items(), key=lambda z:(-z[1],z[0])):
        print(f"  {name}: {n}")

unknown=x.get('location_unknown_by_source') or {}
unknown={k:v for k,v in unknown.items() if v}
if unknown:
    print("\nLocation unknown สูงสุด:")
    for name,n in sorted(unknown.items(), key=lambda z:(-z[1],z[0]))[:10]:
        print(f"  {name}: {n}")
print()
