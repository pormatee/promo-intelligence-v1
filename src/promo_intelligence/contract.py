from __future__ import annotations
import hashlib

CONTRACT = "promo_offer_v1"
VALID_SCOPES = {"nationwide", "selected_branches", "branch_specific", "unknown"}
VALID_LOCATION_STATES = {"explicit", "unknown"}
VALID_CHANNELS = {"online", "store", "omnichannel", "unknown"}
VALID_GEO_STATES = {"explicit", "partial", "nationwide", "unknown"}
VALID_GEO_GRANULARITIES = {"coordinates", "address", "subdistrict", "district", "province", "branch", "nationwide", "unknown"}
VALID_GEO_BASES = {"offer_text", "source_config", "applicability", "none"}


def build_offer(candidate: dict, source: dict, observed_at: str, content_hash: str, verification: dict, applicability: dict, geography: dict | None = None) -> dict:
    key = "|".join([
        source["source_id"], candidate.get("merchant_name") or "", candidate.get("item_name") or "",
        str(candidate.get("promo_price")), str(candidate.get("start")), str(candidate.get("end")),
        applicability.get("scope", "unknown"),
        ",".join(sorted(applicability.get("provinces") or [])),
        ",".join(sorted(applicability.get("branches") or [])),
    ]).encode("utf-8")
    offer_id = "promo_" + hashlib.sha256(key).hexdigest()[:20]
    regular = candidate.get("regular_price")
    promo = candidate.get("promo_price")
    hint = candidate.get("offer_type_hint")
    if hint in {"coupon", "bundle", "other"}:
        offer_type = hint
    elif regular is not None and promo is not None and promo < regular:
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
            "verification_state": (candidate.get("price_integrity") or {}).get("state", "not_applicable"),
            "anomalies": list((candidate.get("price_integrity") or {}).get("anomalies", [])),
            "pair_same_product_block": bool((candidate.get("price_integrity") or {}).get("pair_same_product_block", False)),
        },
        "validity": {"start": candidate.get("start"), "end": candidate.get("end")},
        "conditions": candidate.get("conditions", []),
        "applicability": applicability,
        "geography": geography or {"country": applicability.get("country", "TH"), "detail_state": "unknown", "best_granularity": "unknown", "locations": []},
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
            "price_fields": (candidate.get("price_integrity") or {}).get("fields", {}),
        },
    }


def validate_offer(o: dict) -> list[str]:
    errors: list[str] = []
    if o.get("contract") != CONTRACT:
        errors.append("contract")
    for key in ["offer_id","offer_type","merchant","item","pricing","validity","conditions","verification","source","evidence"]:
        if key not in o:
            errors.append(key)
    if o.get("pricing", {}).get("currency") != "THB":
        errors.append("pricing.currency")
    if "verification_state" in o.get("pricing", {}) and o.get("pricing", {}).get("verification_state") not in {"verified","partial","rejected","not_applicable"}:
        errors.append("pricing.verification_state")
    if "anomalies" in o.get("pricing", {}) and not isinstance(o.get("pricing", {}).get("anomalies"), list):
        errors.append("pricing.anomalies")
    if o.get("verification", {}).get("verification_state") not in {"verified","partial","unverified","rejected"}:
        errors.append("verification_state")
    if "price_verification_state" in o.get("verification", {}) and o.get("verification", {}).get("price_verification_state") not in {"verified","partial","rejected","not_applicable"}:
        errors.append("verification.price_verification_state")
    if not o.get("source", {}).get("url"):
        errors.append("source.url")
    if not o.get("evidence", {}).get("content_hash"):
        errors.append("evidence.content_hash")
    if not o.get("evidence", {}).get("extracted_text"):
        errors.append("evidence.extracted_text")

    # P1 additive field: optional for backward compatibility with promo_offer_v1,
    # but validated strictly whenever present.
    if "applicability" in o:
        a = o["applicability"]
        if a.get("scope") not in VALID_SCOPES:
            errors.append("applicability.scope")
        if a.get("verification_state") not in VALID_LOCATION_STATES:
            errors.append("applicability.verification_state")
        if not isinstance(a.get("provinces"), list):
            errors.append("applicability.provinces")
        if not isinstance(a.get("branches"), list):
            errors.append("applicability.branches")
        if "channel" in a and a.get("channel") not in VALID_CHANNELS:
            errors.append("applicability.channel")
        if "channel_basis" in a and a.get("channel_basis") not in {"offer_text", "source_config", "none"}:
            errors.append("applicability.channel_basis")

    # P5A additive structured geography. Optional for backward compatibility,
    # strict whenever present. No field is inferred by validation.
    if "geography" in o:
        g = o["geography"]
        if g.get("detail_state") not in VALID_GEO_STATES:
            errors.append("geography.detail_state")
        if g.get("best_granularity") not in VALID_GEO_GRANULARITIES:
            errors.append("geography.best_granularity")
        if not isinstance(g.get("locations"), list):
            errors.append("geography.locations")
        else:
            for row in g.get("locations", []):
                if not isinstance(row, dict):
                    errors.append("geography.locations.item")
                    break
                if row.get("verification_state") not in {"explicit"}:
                    errors.append("geography.locations.verification_state")
                    break
                if row.get("basis") not in VALID_GEO_BASES:
                    errors.append("geography.locations.basis")
                    break
                if row.get("granularity") not in VALID_GEO_GRANULARITIES - {"nationwide"}:
                    errors.append("geography.locations.granularity")
                    break
                pc = row.get("postal_code")
                if pc is not None and (not isinstance(pc, str) or len(pc) != 5 or not pc.isdigit()):
                    errors.append("geography.locations.postal_code")
                    break
                lat, lon = row.get("latitude"), row.get("longitude")
                if lat is not None and (not isinstance(lat, (int, float)) or not -90 <= lat <= 90):
                    errors.append("geography.locations.latitude")
                    break
                if lon is not None and (not isinstance(lon, (int, float)) or not -180 <= lon <= 180):
                    errors.append("geography.locations.longitude")
                    break

    # P5A.1 additive Place Foundation references. Optional for backward
    # compatibility; strict whenever present.
    if "merchant_place_ref" in o:
        ref = o.get("merchant_place_ref")
        if ref is not None and (not isinstance(ref, str) or not ref.startswith("place_")):
            errors.append("merchant_place_ref")
    if "place_refs" in o:
        refs = o.get("place_refs")
        if not isinstance(refs, list) or any(not isinstance(x, str) or not x.startswith("place_") for x in refs):
            errors.append("place_refs")

    price_fields = (o.get("evidence") or {}).get("price_fields")
    if price_fields is not None:
        if not isinstance(price_fields, dict):
            errors.append("evidence.price_fields")
        else:
            for key in ("promo_price", "regular_price"):
                if key in price_fields:
                    row = price_fields[key]
                    if not isinstance(row, dict) or not isinstance(row.get("supported"), bool):
                        errors.append(f"evidence.price_fields.{key}")
                        break

    # P6 additive Offer Identity gate. Optional for backward compatibility,
    # strict whenever present.
    if "offer_identity" in o:
        ident = o.get("offer_identity") or {}
        if ident.get("contract") != "offer_identity_v1":
            errors.append("offer_identity.contract")
        if ident.get("state") not in {"accepted", "review", "rejected"}:
            errors.append("offer_identity.state")
        if not isinstance(ident.get("reason_codes"), list):
            errors.append("offer_identity.reason_codes")
        if ident.get("merchant_state") not in {"accepted", "review", "rejected"}:
            errors.append("offer_identity.merchant_state")
        if ident.get("item_state") not in {"accepted", "review", "rejected"}:
            errors.append("offer_identity.item_state")

    corroborating = (o.get("evidence") or {}).get("corroborating_sources")
    if corroborating is not None:
        if not isinstance(corroborating, list):
            errors.append("evidence.corroborating_sources")
        else:
            for row in corroborating:
                if not isinstance(row, dict) or not row.get("source_id") or not row.get("url") or not row.get("content_hash"):
                    errors.append("evidence.corroborating_sources.item")
                    break
    return errors
