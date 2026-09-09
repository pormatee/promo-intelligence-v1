from __future__ import annotations
import hashlib

CONTRACT = "promo_offer_v1"


def build_offer(candidate: dict, source: dict, observed_at: str, content_hash: str, verification: dict) -> dict:
    key = "|".join([
        source["source_id"], candidate.get("merchant_name") or "", candidate.get("item_name") or "",
        str(candidate.get("promo_price")), str(candidate.get("start")), str(candidate.get("end")),
    ]).encode("utf-8")
    offer_id = "promo_" + hashlib.sha256(key).hexdigest()[:20]
    regular = candidate.get("regular_price")
    promo = candidate.get("promo_price")
    if regular is not None and promo is not None and promo < regular:
        offer_type = "price_discount"
    elif promo is not None:
        offer_type = "special_price"
    else:
        offer_type = "other"
    return {
        "contract": CONTRACT,
        "offer_id": offer_id,
        "offer_type": offer_type,
        "merchant": {"name": candidate.get("merchant_name"), "branch": None},
        "item": {"name": candidate.get("item_name"), "brand": None, "category": None},
        "pricing": {
            "currency": candidate.get("currency", "THB"),
            "regular_price": regular,
            "promo_price": promo,
            "discount_amount": candidate.get("discount_amount"),
            "discount_percent": candidate.get("discount_percent"),
        },
        "validity": {"start": candidate.get("start"), "end": candidate.get("end")},
        "conditions": candidate.get("conditions", []),
        "verification": verification,
        "source": {
            "source_id": source["source_id"],
            "source_type": source["source_type"],
            "url": source["url"],
            "observed_at": observed_at,
        },
        "evidence": {
            "content_hash": content_hash,
            "source_offer_id": None,
            "extracted_text": candidate.get("evidence_excerpt", ""),
        },
    }


def validate_offer(o: dict) -> list[str]:
    errors: list[str] = []
    if o.get("contract") != CONTRACT: errors.append("contract")
    for key in ["offer_id","offer_type","merchant","item","pricing","validity","conditions","verification","source","evidence"]:
        if key not in o: errors.append(key)
    if o.get("pricing", {}).get("currency") != "THB": errors.append("pricing.currency")
    if o.get("verification", {}).get("verification_state") not in {"verified","partial","unverified","rejected"}: errors.append("verification_state")
    if not o.get("source", {}).get("url"): errors.append("source.url")
    if not o.get("evidence", {}).get("content_hash"): errors.append("evidence.content_hash")
    if not o.get("evidence", {}).get("extracted_text"): errors.append("evidence.extracted_text")
    return errors
