# Promo Finder V1.7 — Compact Startup Payload

แก้กรณี V1.6 บน Android ยังค้างที่ “กำลังเตรียมรายการโปรโมชั่น…” แม้ startup variable fix แล้ว

## Changes
- Consumer payload ใหม่เป็น compact view แทนการฝัง Published offer/evidence ทั้งก้อน
- ตัด raw technical/source evidence ขนาดใหญ่ออกจาก initial browser payload แต่เก็บต้นฉบับไว้ใน Published Read Model เหมือนเดิม
- เก็บเฉพาะ field-level price evidence excerpt, source URL, display-safe evidence, geography/applicability ที่ Consumer ต้องใช้
- Place payload เก็บ evidence count แทน evidence body ทั้งหมด
- localStorage failure-safe
- server เพิ่ม `Cache-Control: no-store` และ URL มี `?v=1.7` ป้องกัน Chrome ใช้ HTML เก่า
- คง V1.6 startup guard, V1.5 static filters, V1.4 compact UI, Android interaction, Display Quality และ Price Integrity
- Frontend-only; ไม่แตะ Promo Published Read Model และไม่เกี่ยวกับ LocalLife

## Verification
- Overlay regression: 14 tests PASS
- 2,752-offer stress fixture with 20KB raw evidence/offer builds to ~5.0MB HTML instead of embedding ~55MB raw evidence
- Generated JavaScript syntax PASS (`node --check`)
