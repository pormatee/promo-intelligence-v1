# P5C Place Enrichment / Branch Discovery

P5C enriches the generic Promo Intelligence Place Master from explicit official store-locator evidence. It stays fully standalone and does not import or mutate any downstream system.

## Core rules

- Official/explicit evidence only. No geocoding or branch/province inference from names.
- Place existence is separate from offer applicability.
- A nationwide offer is **not** expanded into thousands of `place_refs`.
- Published Read Model includes branch descendants for merchants with published offers, plus `merchant_branch_index_v1.json` for efficient downstream lookup.
- Consumers must evaluate each offer's applicability/channel before joining an offer to a physical branch.
- Failed locator sources preserve last-known records from those sources; one temporary outage cannot erase the branch directory.

## Initial official locator families

- Global House store finder
- Makro branch directory by region
- HomePro branch selector/contact page
- Power Buy store locator

## Commands

One-time/current-data enrichment without refetching all promo offers:

```bash
python place_enrichment_loop.py
```

Inspect published places:

```bash
python show_places.py
```

Normal scheduled/on-demand refreshes continue through the existing Promo Intelligence update strategy; `autonomous_promo.py --core-refresh` now refreshes branch evidence as part of the same owned update flow.
