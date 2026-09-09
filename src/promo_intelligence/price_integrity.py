from __future__ import annotations

from copy import deepcopy
import math
import re

MONEY_RE = re.compile(r"(?:THB|฿)\s*([0-9][0-9,]*(?:\.\d+)?)", re.I)
PERCENT_RE = re.compile(r"(?:ลด|discount|off|save|ประหยัด|เซฟ|-)\s*([0-9]{1,3}(?:\.\d+)?)\s*%", re.I)
EXTREME_DISCOUNT_PERCENT = 80.0


def has_currency_evidence(text: str) -> bool:
    return bool(MONEY_RE.search(text or ""))


def _f(v):
    try:
        if v is None:
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _money_values(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in MONEY_RE.findall(text or "")]


def _has_value(text: str, value: float | None) -> bool:
    if value is None:
        return False
    return any(abs(x - value) < 0.005 for x in _money_values(text))


def _explicit_discount_matches(text: str, regular: float | None, promo: float | None) -> bool:
    if regular is None or promo is None or regular <= 0 or promo > regular:
        return False
    computed = (regular - promo) / regular * 100.0
    for raw in PERCENT_RE.findall(text or ""):
        try:
            if abs(float(raw) - computed) <= 2.0:
                return True
        except ValueError:
            pass
    return False


def evaluate_candidate_price_integrity(candidate: dict) -> dict:
    """Validate price claims against exact numeric source evidence.

    This is deliberately conservative. A comparative regular price is removed
    when its numeric value is not evidenced. Extreme discounts (>=80%) also
    require an explicit matching percentage claim, unless a future extractor
    supplies stronger provenance semantics.
    """
    regular_raw = _f(candidate.get("regular_price_raw"))
    promo_raw = _f(candidate.get("promo_price_raw"))
    if regular_raw is None and promo_raw is None:
        return {
            "state": "not_applicable", "regular_price": None, "promo_price": None,
            "discount_amount": None, "discount_percent": None, "anomalies": [],
            "fields": {
                "promo_price": {"raw_value": None, "supported": False, "sanitized_value": None, "evidence_excerpt": None},
                "regular_price": {"raw_value": None, "supported": False, "sanitized_value": None, "evidence_excerpt": None},
            },
            "pair_same_product_block": False,
        }

    evidence = str(candidate.get("evidence_excerpt") or "")
    pe = candidate.get("price_evidence") or {}
    # Backward-compatible normalization for isolated callers/tests that provide
    # no evidence context at all. Pipeline candidates always carry evidence and
    # therefore cannot use this path to become publishable.
    if not evidence and not pe:
        regular = regular_raw
        promo = promo_raw
        discount_amount = discount_percent = None
        if regular is not None and promo is not None and regular > 0 and 0 <= promo <= regular:
            discount_amount = round(regular - promo, 2)
            discount_percent = round((discount_amount / regular) * 100, 2)
        return {
            "state": "partial",
            "regular_price": regular, "promo_price": promo,
            "discount_amount": discount_amount, "discount_percent": discount_percent,
            "anomalies": ["legacy_candidate_without_evidence_context"],
            "fields": {
                "promo_price": {"raw_value": promo_raw, "supported": False, "sanitized_value": promo, "evidence_excerpt": None},
                "regular_price": {"raw_value": regular_raw, "supported": False, "sanitized_value": regular, "evidence_excerpt": None},
            },
            "pair_same_product_block": False,
        }
    block = str(pe.get("block_text") or evidence)
    promo_text = str(pe.get("promo_price_text") or block)
    regular_text = str(pe.get("regular_price_text") or block)
    pair_same_block = bool(pe.get("same_product_block"))

    promo_supported = promo_raw is not None and _has_value(promo_text, promo_raw)
    regular_supported = regular_raw is not None and _has_value(regular_text, regular_raw)

    # Legacy candidates did not carry structured price provenance. Exact values
    # inside the candidate's own evidence excerpt are accepted for ordinary
    # discounts, but not as strong provenance for extreme comparative claims.
    if not pe:
        promo_supported = promo_raw is not None and _has_value(evidence, promo_raw)
        regular_supported = regular_raw is not None and _has_value(evidence, regular_raw)

    promo = promo_raw if promo_supported else None
    regular = regular_raw if regular_supported else None
    anomalies: list[str] = []
    if promo_raw is not None and not promo_supported:
        anomalies.append("promo_price_without_numeric_evidence")
    if regular_raw is not None and not regular_supported:
        anomalies.append("regular_price_without_numeric_evidence")

    if regular is not None and promo is not None:
        if regular <= 0 or promo < 0 or promo > regular:
            anomalies.append("invalid_price_relationship")
            regular = None
        else:
            disc = (regular - promo) / regular * 100.0
            if disc >= EXTREME_DISCOUNT_PERCENT and not _explicit_discount_matches(block, regular, promo):
                anomalies.append("extreme_discount_without_explicit_percent_evidence")
                # Keep the independently evidenced promo price, but suppress the
                # comparative regular-price claim and computed discount.
                regular = None

    discount_amount = None
    discount_percent = None
    if regular is not None and promo is not None and regular > 0 and promo <= regular:
        discount_amount = round(regular - promo, 2)
        discount_percent = round((discount_amount / regular) * 100, 2)

    if promo_raw is not None and promo is None:
        state = "rejected"
    elif anomalies:
        state = "partial"
    elif promo is not None and (regular_raw is None or regular is not None):
        state = "verified"
    else:
        state = "partial"

    return {
        "state": state,
        "regular_price": regular,
        "promo_price": promo,
        "discount_amount": discount_amount,
        "discount_percent": discount_percent,
        "anomalies": anomalies,
        "pair_same_product_block": pair_same_block,
        "fields": {
            "promo_price": {
                "raw_value": promo_raw,
                "supported": promo_supported,
                "sanitized_value": promo,
                "evidence_excerpt": promo_text[:500] if promo_raw is not None else None,
            },
            "regular_price": {
                "raw_value": regular_raw,
                "supported": regular_supported,
                "sanitized_value": regular,
                "evidence_excerpt": regular_text[:500] if regular_raw is not None else None,
            },
        },
    }


def sanitize_offer_pricing(offer: dict) -> dict:
    """Defense-in-depth sanitizer for existing JSONL / Published Read Model.

    This makes old outputs safe without requiring an immediate refetch. New
    extraction runs also pass through the candidate-level gate.
    """
    o = deepcopy(offer)
    pricing = o.setdefault("pricing", {})
    evidence = o.setdefault("evidence", {})
    extracted = str(evidence.get("extracted_text") or "")
    existing_fields = evidence.get("price_fields") or {}

    candidate = {
        "regular_price_raw": pricing.get("regular_price"),
        "promo_price_raw": pricing.get("promo_price"),
        "evidence_excerpt": extracted,
    }
    # Preserve strong structured provenance when already present.
    if existing_fields:
        candidate["price_evidence"] = {
            "block_text": extracted,
            "promo_price_text": (existing_fields.get("promo_price") or {}).get("evidence_excerpt") or extracted,
            "regular_price_text": (existing_fields.get("regular_price") or {}).get("evidence_excerpt") or extracted,
            "same_product_block": bool(pricing.get("pair_same_product_block", False)),
        }
    result = evaluate_candidate_price_integrity(candidate)

    pricing["regular_price"] = result["regular_price"]
    pricing["promo_price"] = result["promo_price"]
    pricing["discount_amount"] = result["discount_amount"]
    pricing["discount_percent"] = result["discount_percent"]
    pricing["verification_state"] = result["state"]
    pricing["anomalies"] = result["anomalies"]
    pricing["pair_same_product_block"] = result["pair_same_product_block"]
    evidence["price_fields"] = result["fields"]

    verification = o.setdefault("verification", {})
    verification["price_verification_state"] = result["state"]

    if result["promo_price"] is None and o.get("offer_type") in {"price_discount", "special_price"}:
        verification["verification_state"] = "rejected"
    elif result["promo_price"] is not None and result["regular_price"] is None and o.get("offer_type") == "price_discount":
        # The promo price can still be useful, but the comparative claim is no
        # longer evidence-backed.
        o["offer_type"] = "special_price"
        if verification.get("verification_state") == "verified" and result["state"] != "verified":
            verification["verification_state"] = "partial"
    return o
