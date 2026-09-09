from __future__ import annotations
from datetime import datetime, timezone


def _parse_iso_datetime(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def verify_offer(candidate: dict, source: dict, observed_at: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    obs = _parse_iso_datetime(observed_at)
    age_hours = max(0.0, (now - obs).total_seconds() / 3600)
    freshness = "fresh" if age_hours <= 72 else "stale"

    start = candidate.get("start")
    end = candidate.get("end")
    today = now.date().isoformat()
    if end is None:
        expiry = "unknown"
    elif end < today:
        expiry = "expired"
    elif start is not None and start > today:
        expiry = "unknown"
    else:
        expiry = "active"

    regular = candidate.get("regular_price")
    promo = candidate.get("promo_price")
    offer_hint = candidate.get("offer_type_hint")
    price_state = (candidate.get("price_integrity") or {}).get("state", "not_applicable")
    price_valid = promo is not None and promo >= 0 and (regular is None or promo <= regular) and price_state != "rejected"
    non_price_promo_valid = offer_hint in {"coupon", "bundle", "other"} and bool(candidate.get("item_name"))
    offer_value_valid = price_valid or non_price_promo_valid
    has_evidence = bool(candidate.get("evidence_excerpt"))
    has_dates = start is not None

    if not offer_value_valid or not has_evidence:
        state = "rejected"
    elif expiry == "expired":
        state = "verified"
    elif has_dates and source.get("reliability") in {"high", "medium"}:
        state = "verified" if end is not None else "partial"
    else:
        state = "partial"

    if state == "verified" and price_state == "partial" and promo is not None:
        state = "partial"
    return {
        "verification_state": state,
        "freshness_state": freshness,
        "expiry_state": expiry,
        "source_reliability": source.get("reliability", "unknown"),
        "price_verification_state": price_state,
    }
