# Promo Finder V1.2 — Android Interaction Fix

Fixes Android Chrome touch/click reliability without changing Promo Intelligence backend or Published Read Model.

- hardens pointer-events/z-index for toolbar, quick filters, native selects, bottom nav, card actions
- keeps hidden drawer backdrop non-interactive until shown
- uses addEventListener wiring consistently
- adds small interaction status text so users can see that a filter selection registered
- preserves V1.1 display-quality and P5D price-evidence integrity behavior

Build as before with `python build_promo_consumer.py` and serve with `python serve_promo_consumer.py`.
