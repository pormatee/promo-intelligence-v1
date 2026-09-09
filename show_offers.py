#!/usr/bin/env python3
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "output" / "promo_offer_v1.jsonl"
if not path.is_absolute():
    path = root / path
if not path.exists():
    raise SystemExit(f"ไม่พบ {path} — รัน: python promo_intel.py run")
rows=[]
with path.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))

print(f"\nโปรโมชั่นทั้งหมด: {len(rows)} รายการ")
counts = {}
for x in rows:
    name = (x.get('merchant') or {}).get('name') or '-'
    counts[name] = counts.get(name, 0) + 1
if counts:
    print("แยกตามร้าน/แหล่ง:")
    for name, count in sorted(counts.items(), key=lambda z: (-z[1], z[0])):
        print(f"  {name}: {count}")
print()
for i,x in enumerate(rows,1):
    merchant=x.get('merchant') or {}
    item=x.get('item') or {}
    price=x.get('pricing') or {}
    validity=x.get('validity') or {}
    verify=x.get('verification') or {}
    source=x.get('source') or {}
    app=x.get('applicability') or {'scope':'unknown','provinces':[],'branches':[]}
    geo=x.get('geography') or {'detail_state':'unknown','best_granularity':'unknown','locations':[]}
    print('='*52)
    print(f"โปรโมชั่น #{i}")
    print(f"ร้าน         : {merchant.get('name') or '-'}")
    print(f"สินค้า/บริการ : {item.get('name') or '-'}")
    print(f"ประเภทโปร     : {x.get('offer_type') or '-'}")
    print(f"ราคาปกติ     : {price.get('regular_price') if price.get('regular_price') is not None else '-'} บาท")
    print(f"ราคาโปร      : {price.get('promo_price') if price.get('promo_price') is not None else '-'} บาท")
    if price.get('discount_percent') is not None:
        print(f"ส่วนลด       : {price['discount_percent']:.1f}%")
    print(f"เริ่มโปร      : {validity.get('start') or '-'}")
    print(f"หมดโปร       : {validity.get('end') or '-'}")
    print(f"สถานะโปร     : {verify.get('expiry_state') or '-'}")
    print(f"พื้นที่ใช้สิทธิ์: {app.get('scope') or 'unknown'}")
    if app.get('provinces'):
        print("จังหวัด       : " + ', '.join(app['provinces']))
    if app.get('branches'):
        print("สาขา          : " + ', '.join(app['branches']))
    print(f"ช่องทาง       : {app.get('channel') or 'unknown'}")
    print(f"หลักฐานพื้นที่ : {app.get('verification_state') or 'unknown'} / {app.get('basis') or 'none'}")
    print(f"Geo detail   : {geo.get('detail_state') or 'unknown'} / {geo.get('best_granularity') or 'unknown'}")
    for j,loc in enumerate(geo.get('locations') or [],1):
        label = f"ตำแหน่ง {j}" if len(geo.get('locations') or []) > 1 else "ตำแหน่ง"
        parts=[]
        if loc.get('province'): parts.append(f"จังหวัด={loc['province']}")
        if loc.get('district'): parts.append(f"อำเภอ/เขต={loc['district']}")
        if loc.get('subdistrict'): parts.append(f"ตำบล/แขวง={loc['subdistrict']}")
        if loc.get('branch_name'): parts.append(f"สาขา={loc['branch_name']}")
        if loc.get('postal_code'): parts.append(f"รหัส={loc['postal_code']}")
        if loc.get('address'): parts.append(f"ที่อยู่={loc['address']}")
        if loc.get('latitude') is not None and loc.get('longitude') is not None:
            parts.append(f"พิกัด={loc['latitude']},{loc['longitude']}")
        if parts: print(f"{label:<12}: " + ' · '.join(parts))
    corr=(x.get('evidence') or {}).get('corroborating_sources') or []
    if corr:
        print(f"หลักฐานเสริม   : {len(corr)} source")
    print(f"Reliability  : {verify.get('source_reliability') or '-'}")
    print(f"Source       : {source.get('source_id') or '-'}")
print('='*52)
