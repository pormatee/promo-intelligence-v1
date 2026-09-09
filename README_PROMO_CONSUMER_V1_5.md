# Promo Finder V1.5 — Static Region/Province Options

Fixes Android native `<select>` showing only the default values (`ทุกภูมิภาค` / `ทุกจังหวัด`) while the large Published snapshot is still initializing.

## Changes
- Region options (7 groups) are rendered into HTML at build time.
- Province options (77 provinces) are rendered into HTML at build time, grouped by region.
- Merchant and offer-type options are also rendered at build time from the Published snapshot.
- JavaScript option population is now duplicate-safe and preserves the current selected province when initialization completes.
- No backend, Published Read Model, Promo Intelligence contract, or LocalLife dependency change.

This is a consumer-frontend-only patch.
