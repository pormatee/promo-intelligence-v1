# Promo Intelligence Lab Frontend V1

Separate read-only test frontend for the Promo Intelligence **Published Read Model**.

It does not replace `promo_frontend.html` and does not write back to Promo Intelligence or any downstream system.

## Build

```bash
python build_promo_lab.py
```

Output: `promo_lab.html`

## Easiest Android usage

```bash
python serve_promo_lab.py
```

Then open the printed URL (default `http://127.0.0.1:8081/promo_lab.html`) in Chrome.

## Tabs

- Promotions: search/filter published `promo_offer_v1` records.
- Places / Branches: inspect published `promo_place_v1` and branch directory.
- System: inspect publication ID, manifest counts, and read-only policy.

Important: branch existence is not offer applicability. The UI keeps these concepts separate.
