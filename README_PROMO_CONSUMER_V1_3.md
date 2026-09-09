# Promo Finder V1.3 — Compact Filters + Region/Province UX

Standalone Consumer Frontend only. No LocalLife/PrachinLife/MSB/DQE dependency.

Changes:
- Compact mobile filter controls (40px hit target, smaller padding/font)
- Mobile stats become one horizontal row to expose results sooner
- Region-first filtering with 7 large Thailand regions
- Province selector contains all 77 Thai provinces and narrows by selected region
- Nationwide offers safely match every Thai province/region
- Province aliases normalize common English province names to canonical Thai names
- Advanced filters (type/channel/sort) collapsed by default behind "ตัวกรองเพิ่ม"
- Result count shown inside filter panel so changes are visible immediately
- Existing Android touch hardening, Display Quality Gate, and Price Evidence Integrity stay intact

Verified reconstructed full-chain gate:
- Ran 97 tests ... OK
- CONTRACT_ERRORS=0
- fixture FINAL_RESULT=PASS
- national fixture FINAL_RESULT=PASS
- generated consumer JavaScript syntax PASS
