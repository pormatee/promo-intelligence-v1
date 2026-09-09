# Promo Intelligence P5A — Structured Geography Foundation

Additive, non-breaking extension of `promo_offer_v1`.

## New optional `geography` block

Each newly generated offer carries:

- `country`
- `detail_state`: `explicit | partial | nationwide | unknown`
- `best_granularity`: `coordinates | address | subdistrict | district | province | branch | nationwide | unknown`
- `locations[]` with `province`, `province_raw`, `district`, `subdistrict`, `branch_name`, `address`, `postal_code`, `latitude`, `longitude`, evidence basis and excerpt.

Multiple location records are supported. Missing fields remain `null`; no geocoding or address inference is performed. Nationwide offers do not receive fake branch/address records.

## Diagnostics

Live/fixture runs now report:

- `GEO_KNOWN_OFFERS`
- `DISTRICT_KNOWN_OFFERS`
- `SUBDISTRICT_KNOWN_OFFERS`
- `ADDRESS_KNOWN_OFFERS`
- `POSTAL_CODE_KNOWN_OFFERS`
- `COORDINATES_KNOWN_OFFERS`
- `BRANCH_NAME_KNOWN_OFFERS`

The frontend search/evidence detail also includes structured geography.

## One-command workflow

```bash
python autonomous_promo.py
```

This runs the existing bounded backend autonomous recovery loop, validates geography/contract output, and rebuilds the offline frontend.
