# Promo Intelligence P3 — Nationwide Source Expansion

P3 moves from proof-of-concept toward higher real offer volume while preserving the standalone boundary and `promo_offer_v1` contract.

## Added official source families
- Lotus's (existing)
- Tops Online: product campaign grid + monthly coupon page
- Big C Online: September coupon/terms pages

Current registry: 9 official URLs.

## New robustness
- Thai Buddhist Era date normalization (full and abbreviated month names)
- Tops price-discount and bundle extraction
- Tops coupon extraction
- Big C coupon-tier extraction
- bundle offers can verify without pretending a unit promo price exists
- one failed website no longer stops all other sources; failures are counted as `FETCH_FAILED`

## Run
```bash
bash run_tests.sh
python promo_intel.py run
python show_offers.py
```

P3 regression baseline: 28 tests PASS in the development environment. The actual live offer count must be proven on Termux because websites can change HTML or block automated requests.
