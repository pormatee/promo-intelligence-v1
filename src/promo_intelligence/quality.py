from __future__ import annotations
from collections import Counter


def quality_summary(offers: list[dict]) -> dict:
    verification = Counter((o.get("verification") or {}).get("verification_state", "unknown") for o in offers)
    expiry = Counter((o.get("verification") or {}).get("expiry_state", "unknown") for o in offers)
    channel = Counter((o.get("applicability") or {}).get("channel", "unknown") for o in offers)
    location_unknown = [o for o in offers if (o.get("applicability") or {}).get("scope", "unknown") == "unknown"]
    # Unknown branch/province is not equally actionable for online-only offers.
    actionable_unknown = [
        o for o in location_unknown
        if (o.get("applicability") or {}).get("channel", "unknown") != "online"
    ]
    corroborated = sum(bool((o.get("evidence") or {}).get("corroborating_sources")) for o in offers)
    price = Counter((o.get("pricing") or {}).get("verification_state", "unknown") for o in offers)
    price_anomalies = sum(bool((o.get("pricing") or {}).get("anomalies")) for o in offers)
    identity = Counter((o.get("offer_identity") or {}).get("state", "legacy") for o in offers)
    return {
        "verified": verification["verified"],
        "partial": verification["partial"],
        "unverified": verification["unverified"],
        "rejected": verification["rejected"],
        "active": expiry["active"],
        "expired": expiry["expired"],
        "expiry_unknown": expiry["unknown"],
        "online": channel["online"],
        "store": channel["store"],
        "omnichannel": channel["omnichannel"],
        "channel_unknown": channel["unknown"],
        "location_unknown_actionable": len(actionable_unknown),
        "corroborated": corroborated,
        "price_verified": price["verified"],
        "price_partial": price["partial"],
        "price_rejected": price["rejected"],
        "price_not_applicable": price["not_applicable"],
        "price_anomaly_offers": price_anomalies,
        "identity_accepted": identity["accepted"],
        "identity_review": identity["review"],
        "identity_rejected": identity["rejected"],
        "identity_legacy": identity["legacy"],
    }
