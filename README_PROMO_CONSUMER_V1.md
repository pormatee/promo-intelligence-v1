# Promo Finder / Standalone Consumer Frontend V1

หน้าบ้านสำหรับผู้ใช้จริงของ Promo Intelligence โดยตรง ไม่ใช่ Promo Lab และไม่เกี่ยวกับ LocalLife/PrachinLife/MSB/DQE

## Data boundary
- อ่านเฉพาะ `output/published/manifest.json`
- อ่าน `promo_offer_v1.jsonl`, `promo_place_v1.jsonl`, `merchant_branch_index_v1.json`
- Read-only ต่อ Promo Intelligence
- ไม่มี LocalLife import/schema/database/ranking
- ไม่เขียนกลับ backend

## User functions
- ค้นหาโปรโมชั่น/สินค้า/ร้าน/แบรนด์
- กรองร้าน ประเภทโปร ช่องทาง จังหวัด
- quick filters: active, ลด 30%+, online, nationwide, price verified, expiring
- แสดงราคาตาม Price Evidence Integrity เท่านั้น
- ถ้าราคาปกติไม่ยืนยัน จะไม่แสดงราคาขีดฆ่าหรือคำนวณ % ส่วนลด
- ดูหลักฐาน field-level และ source
- browse ร้าน/สาขา (branch existence แยกจาก offer applicability)
- บันทึกโปรใน localStorage ของ browser
- Share/Copy offer
- แสดง publication freshness/status

## Build
```bash
python build_promo_consumer.py
```
Output: `promo_consumer.html`

## Open on Android
```bash
python serve_promo_consumer.py
```
แล้วเปิด `http://127.0.0.1:8082/promo_consumer.html`

## GitHub Pages
ไฟล์ `promo_consumer.html` เป็น single-file static frontend สามารถนำไปตั้งชื่อ `index.html` แล้ว deploy เป็น static page ได้ โดย snapshot ถูกฝังในไฟล์ ณ เวลาที่ build

## Verification checkpoint
Full-chain clean gate (P0→P5D + Consumer V1): `Ran 92 tests ... OK`; fixture and national fixture `FINAL_RESULT=PASS`.
