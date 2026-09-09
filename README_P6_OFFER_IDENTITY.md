# P6 — Offer Identity / Campaign Boundary Integrity Gate

Purpose: prevent terms, disclaimers, navigation CTAs, technical payloads, and parser-boundary fragments from being published as promotion identities.

## Rules
- Conservative and fail-closed only for strong structural non-offer evidence.
- Explicit price disclaimers, availability-only conditions, terms/exclusions, action-only CTAs, and technical runtime payloads => `offer_identity.state=rejected`.
- Description-like titles without price evidence => `review`, not hard-rejected.
- Existing `promo_offer_v1` remains additive/backward compatible via optional `offer_identity` metadata.
- Published Read Model excludes only `offer_identity.state=rejected`.
- P5F/P5G/P5H applicability discovery ignores identity-rejected rows so false fragments no longer inflate the geographic backlog.
- Future pipeline rows are identity-annotated automatically before export.

## One-command loop
```bash
python offer_identity_loop.py
```

The loop runs targeted P6 tests, repairs historical output with backup, runs bounded P5H applicability closure on the cleaned set, rebuilds Published/Consumer, then prints the P6 report.

Unknown is allowed to remain. P6 does not invent campaign parents, provinces, branches, prices, or merchant names.
