# Promo Intelligence P5B — Place Foundation + Update Strategy V1 + Published Read Model

This upgrade keeps Promo Intelligence standalone and adds three foundations without coupling to any downstream decision engine.

## 1) Generic Place Foundation

- New contract: `promo_place_v1`
- Generic merchant/branch records; no brand-specific schema.
- Stable `place_id` values.
- Offer fields added non-breakingly to `promo_offer_v1`:
  - `merchant_place_ref`
  - `place_refs[]`
- Physical branch records are created only from explicit branch name, explicit postal address, or explicit coordinates.
- Province-only/nationwide/online applicability does not create fake physical branches.
- Supports operator-maintained aliases through `config/place_aliases.json`.
- Preserves evidence and source counts for every place record.

Outputs:

- `output/promo_place_v1.jsonl`
- enriched `output/promo_offer_v1.jsonl`

## 2) Update Strategy V1

Policy file: `config/update_policy.json`

Default policy:

- scheduled refresh interval: 24 hours
- on-demand minimum published age: 15 minutes
- on-demand failure cooldown: 5 minutes
- single-flight lock: only one refresh may run at a time

Commands:

```bash
python promo_service.py scheduled
python promo_service.py on-demand --requester external_consumer --reason fresh_data_requested
python promo_service.py manual
python promo_service.py status
```

When many requests arrive together, only the first request may start a refresh. Others receive `UPDATE_DECISION=JOIN_EXISTING` and should continue reading the current published snapshot until the new publication appears.

## 3) Published Read Model

The publisher writes an atomic, versioned read-only snapshot under:

```text
output/published/
  manifest.json
  promo_offer_v1.jsonl
  promo_place_v1.jsonl
```

Publication policy:

- verification state must be `verified` or `partial`
- expired offers excluded
- stale offers excluded
- manifest written last after both data files

Consumers read this snapshot only. Promo Intelligence remains the owner of refresh/extraction/verification/publishing.

## Immediate upgrade of existing offers

This does **not** fetch the web again. It converts the current `output/promo_offer_v1.jsonl` into Place Master + Published Read Model:

```bash
python build_place_publish.py
```

Expected final markers:

```text
PLACE_PUBLISH_RESULT=PASS
PUBLISHED_READ_MODEL=PASS
CONTRACT_ERRORS=0
PLACE_CONTRACT_ERRORS=0
```

## One-loop full refresh

```bash
python autonomous_promo.py
```

Full flow:

```text
backend autonomous refresh
→ structured geography
→ Place Master
→ offer ↔ place references
→ trusted published snapshot
→ frontend rebuild
```

For scheduled/on-demand service refreshes the coordinator uses core refresh mode and does not rebuild the 30 MB frontend on every request.

## Scheduler hook

`daily_update.sh` is the daily-safe entry point. An Android/Termux scheduler can invoke this command repeatedly; the internal 24-hour due check prevents unnecessary refreshes.

## Verified development gate

```text
Ran 75 tests
OK
fixture pipeline PASS
national fixture PASS
CONTRACT_ERRORS=0
Place Foundation unit tests PASS
single-flight tests PASS
Published Read Model tests PASS
```
