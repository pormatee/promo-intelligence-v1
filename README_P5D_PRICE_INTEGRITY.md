# P5D Price Evidence Integrity Gate

Purpose: prevent unsupported or cross-product price claims from reaching the Published Read Model / LocalLife.

Rules:
- every numeric promo/regular price must be present in candidate evidence;
- generic product grids stop at the next product title (no cross-product pairing);
- unsupported regular price -> null; discount amount/percent -> null;
- unsupported promo price -> rejected for price-only offers;
- >=80% comparative discount without an explicit matching percentage claim -> regular price suppressed;
- `pricing.verification_state`, `pricing.anomalies`, and `evidence.price_fields` expose field-level provenance;
- Published Read Model sanitizes pricing again as defense in depth;
- `repair_price_integrity.py` repairs existing JSONL, keeps a timestamped backup, republishes, and rebuilds Promo Lab.
