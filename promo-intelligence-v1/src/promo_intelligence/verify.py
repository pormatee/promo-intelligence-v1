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
    price_valid = promo is not None and promo >= 0 and (regular is None or promo <= regular)
    has_evidence = bool(candidate.get("evidence_excerpt"))
    has_dates = start is not None

    if not price_valid or not has_evidence:
        state = "rejected"
    elif expiry == "expired":
        state = "verified"
    elif has_dates and source.get("reliability") in {"high", "medium"}:
        state = "verified" if end is not None else "partial"
    else:
        state = "partial"

    return {
        "verification_state": state,
        "freshness_state": freshness,
        "expiry_state": expiry,
        "source_reliability": source.get("reliability", "unknown"),
    }
