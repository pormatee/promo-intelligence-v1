# Promo Intelligence V1 — P2 National Coverage Foundation

Standalone promotion evidence pipeline for Android + Termux.

## P2 adds
- Thailand 77-province coverage target and coverage metrics.
- Explicit nationwide offer recognition from source text only.
- A second official Lotus's source adapter for a nationwide September 2026 coupon campaign.
- Non-price promotion support (`coupon`) while preserving `promo_offer_v1`.
- `run-national-fixture` regression proof.

## Important meaning of coverage
`NATIONAL_GEOGRAPHIC_REACH=TRUE` means at least one currently active, fresh, trusted/partial offer has explicit applicability covering every Thai province.
It does **not** mean every retailer or every promotion in Thailand has already been discovered. Therefore P2 always reports `MARKET_COVERAGE_COMPLETE=FALSE`.

## Test
```bash
cd ~/promo-intelligence-v1
bash run_tests.sh
```

## Live
```bash
python promo_intel.py run
```

Expected new metrics include:
- `NATIONWIDE_ACTIVE_OFFERS`
- `PROVINCES_REACHED`
- `PROVINCE_TARGET=77`
- `NATIONAL_GEOGRAPHIC_REACH`
- `MARKET_COVERAGE_COMPLETE=FALSE`

Core rules remain: standalone, evidence required, unknown stays unknown, no recommendation/ranking authority.
