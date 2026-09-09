# Promo Finder V1.4 — Compact Header + Fast Startup

Frontend-only update for the standalone Promo Finder.

## Fixes
- The `×` control is the clear-search button. It now stays inside the search field and is hidden when the query is empty.
- Mobile hero/header is much shorter so filtered results remain visible.
- Stats cards are hidden on small screens; counts remain available in the system/about view and compact header summary.
- Main filters are more compact.
- Startup uses safe direct JSON (`<script type="application/json">`) instead of a large Base64 runtime decode, reducing Android startup work and generated HTML size.
- A human-readable loading placeholder is visible until the first result render completes.

## Boundaries
- Frontend-only. Published Read Model is not modified.
- Price Evidence Integrity, Display Quality Gate, Android interaction fixes, region/province logic remain unchanged.
- No LocalLife/PrachinLife/MSB/DQE dependency.
