# P5E Explicit Branch → Province Linkage

Purpose: improve local province evidence without guessing.

Safety rule: merchant branch existence alone never means an offer applies there. P5E links an offer to an official branch record only when the offer itself explicitly names the branch and merchant + branch match is exact/unambiguous after conservative alias normalization.

Outputs add `area_linkage` metadata and may fill missing structured province/district/address on an already-explicit branch location from the verified official branch directory. Nationwide and online semantics are unchanged.

Run after installing:

```bash
bash run_tests.sh
python build_place_publish.py
python build_promo_consumer.py
python show_area_coverage.py
```

One-command live rebuild:

```bash
python area_enrichment_loop.py
```

Key metrics to inspect:

- `OFFERS_WITH_EXPLICIT_BRANCH_NAMES`
- `OFFERS_BRANCH_LINKED`
- `EXPLICIT_BRANCH_MATCHES`
- `EXPLICIT_BRANCH_UNMATCHED`
- `OFFERS_WITH_LOCAL_PROVINCE`
- per-province local-confirmed counts from `show_area_coverage.py`

If these remain low, that is evidence that current promotion sources do not state branch applicability explicitly enough; the system does not fill province from merchant branch existence alone.
