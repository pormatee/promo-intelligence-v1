# Promo Finder V1.8 — Province Semantics Fix

Frontend-only patch for the standalone Promo Intelligence consumer.

## What changed
- Province/region filters no longer infer offer applicability merely because a merchant has a branch in that province.
- Local province evidence comes only from explicit offer geography or direct `place_refs`.
- `nationwide` remains a separate explicit applicability class and is included safely for every selected province/region.
- Online offers are counted separately and are not automatically treated as offers of a selected province.
- Area result summary shows: local-confirmed / nationwide / online.
- Published Read Model, Promo contracts, backend, LocalLife/PrachinLife are unchanged.

## Expected behavior
When selecting Prachinburi, the UI may show for example:
`ปราจีนบุรี · ยืนยันในพื้นที่ 0 · ทั่วประเทศ 9 · ออนไลน์ 404`
The displayed province results are local-confirmed + nationwide. Online is informational unless the user selects the Online quick filter separately.

## Run
```bash
cd ~/promo-intelligence-v1
unzip -o ~/storage/downloads/promo-intelligence-consumer-v1-8-province-semantics-overlay.zip
python build_promo_consumer.py
```
If a server is already running, rebuild + refresh with `?v=1.8`. Otherwise:
```bash
python serve_promo_consumer.py --port 8083
```
Open:
`http://127.0.0.1:8083/promo_consumer.html?v=1.8`
