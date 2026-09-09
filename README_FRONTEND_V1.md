# Promo Intelligence — Frontend V1

Standalone mobile-first frontend for `promo_offer_v1`.

## Build from current live output

```bash
cd ~/promo-intelligence-v1
python build_frontend.py
```

Output:

```text
~/promo-intelligence-v1/promo_frontend.html
```

The HTML is a single offline file. The current `output/promo_offer_v1.jsonl` data is embedded at build time; no server or external JS/CSS is required.

## Open on Android

```bash
termux-open promo_frontend.html
```

If `termux-open` is unavailable, copy to Downloads and open with Chrome/your browser:

```bash
cp promo_frontend.html ~/storage/downloads/
```

## Refresh

After `python autonomous_wave_c.py` creates a newer `promo_offer_v1.jsonl`, run `python build_frontend.py` again.

## Frontend filters

- Search item / merchant / brand / condition
- Merchant
- Offer type
- Channel
- Verification state
- All / Active / Nationwide / Verified Prachinburi / Online / Discount >= 30%
- Sort by discount, promo price, expiry, merchant
- Source/evidence details and official source link

This frontend does not rank merchants or choose A/B/C. It only displays Promo Intelligence evidence.
