# P5F Offer Applicability Evidence Discovery

Purpose: reduce the small backlog of store/omnichannel offers whose local area is still unknown **without using merchant branch existence as offer applicability**.

Safety rules:
- Existing explicit applicability is never overwritten.
- Online offers are not converted into physical local province applicability.
- First use evidence already attached directly to the offer.
- Raw HTML is used only when the offer title has exactly one conservative match; applicability terms must be inside that anchored context.
- Strong explicit terms only: nationwide/all branches, explicit province markers, or explicit branch wording.
- Ambiguous title/context remains unknown.
- No fuzzy merchant→province inference and no geocoding.

Run one command:

```bash
python applicability_discovery_loop.py
```

Key metrics: `ACTIONABLE_UNKNOWN_BEFORE/AFTER`, `APPLICABILITY_DISCOVERED`, `DISCOVERED_NATIONWIDE/PROVINCE/BRANCH`.
