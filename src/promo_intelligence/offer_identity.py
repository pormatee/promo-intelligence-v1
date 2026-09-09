from __future__ import annotations

import copy
import re
from typing import Any

IDENTITY_VERSION = "offer_identity_v1"
VALID_STATES = {"accepted", "review", "rejected"}

# Strong condition/terms signals. These are intentionally narrow: the gate only
# rejects text that is structurally not an offer identity, not merely a weak or
# generic promotion title.
_PRICE_DISCLAIMER_RE = re.compile(
    r"^(?:prices?\s+(?:are\s+)?subject\s+to|price\s+includes?|ราค(?:า|าสินค้า).*?(?:ภาษี|vat)|"
    r"ราคาดังกล่าว.*?(?:ภาษี|vat))",
    re.I,
)
_AVAILABILITY_CONDITION_RE = re.compile(
    r"^(?:available\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|daily|on|from|during)|"
    r"valid\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|only)|"
    r"(?:ใช้ได้|จำหน่าย|ให้บริการ)\s*(?:เฉพาะ)?\s*(?:วัน|ช่วงเวลา))",
    re.I,
)
_TERMS_RE = re.compile(
    r"^(?:(?:\d+\s*[.)]\s*)?(?:terms?(?:\s+and\s+conditions?)?|conditions?\s+apply|"
    r"ข้อกำหนด|เงื่อนไข(?:การใช้|และข้อกำหนด)?|หมายเหตุ)\b)",
    re.I,
)
_EXCLUSION_RE = re.compile(
    r"^(?:\d+\s*[.)]\s*)?(?:สินค้ายกเว้น|รายการยกเว้น|ยกเว้นการใช้|ไม่รวมรายการ|ไม่สามารถใช้(?:ร่วม|คูปอง)|"
    r"excluded\s+(?:items?|products?)|exclusions?\b|not\s+valid\s+(?:for|with))",
    re.I,
)
_ACTION_ONLY_RE = re.compile(
    r"^(?:ดาวน์โหลด(?:แอป|แอปพลิเคชัน)|download\s+(?:the\s+)?app|คลิก(?:ที่นี่)?|click\s+here|"
    r"สมัครสมาชิก|ลงทะเบียน|register\s+now|sign\s+up|เข้าสู่ระบบ|log\s*in)\b",
    re.I,
)
_DESCRIPTION_PREFIX_RE = re.compile(
    r"^(?:includes?|including|ประกอบด้วย|ภายในชุด(?:ประกอบด้วย)?|ในเซ็ต(?:ประกอบด้วย)?)\b",
    re.I,
)

_BENEFIT_RE = re.compile(
    r"(?:\b(?:thb|baht|save|discount|cashback|free|reward|deal|special|coupon|points?)\b|"
    r"฿|\d+\s*(?:บาท|%|ชิ้น|แถม)|ลด|ส่วนลด|ราคาพิเศษ|คืนเงิน|รับฟรี|ของแถม|แลกคะแนน|พอยด์|คูปอง|โปรโมชั่น)",
    re.I,
)
_TECH_RE = re.compile(
    r"(?:__next_data__|window\.__|self\.__next|\"props\"\s*:|\"pageprops\"\s*:|"
    r"<!doctype\s+html|<html|webpack|runtimeconfig|redis_uri|amazonaws\.com|cloudfront\.net)",
    re.I,
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _looks_technical(text: str) -> bool:
    s = _clean(text)
    if not s:
        return False
    if _TECH_RE.search(s):
        return True
    if len(s) > 100 and s[:1] in "{[" and re.search(r'\"[^\"]+\"\s*:', s):
        return True
    return False


def _classify_field(text: str, field: str, *, pricing: dict | None = None) -> tuple[str, list[str]]:
    s = _clean(text)
    low = s.lower()
    pricing = pricing or {}
    if not s:
        return "rejected", [f"{field}_missing"]
    if _looks_technical(s):
        return "rejected", [f"{field}_technical_payload"]
    if _PRICE_DISCLAIMER_RE.search(s):
        return "rejected", [f"{field}_price_disclaimer"]
    if _AVAILABILITY_CONDITION_RE.search(s):
        return "rejected", [f"{field}_availability_condition"]
    if _TERMS_RE.search(s):
        return "rejected", [f"{field}_terms_fragment"]
    if _EXCLUSION_RE.search(s):
        return "rejected", [f"{field}_exclusion_fragment"]

    # A CTA by itself is navigation/instructional copy, not a promotion. If the
    # same title contains an explicit benefit/value, retain it as a real offer.
    action_match = _ACTION_ONLY_RE.search(s)
    if action_match:
        # Evaluate benefits only after the CTA phrase itself; Thai words such as
        # "ดาวน์โหลด" contain the characters "ลด" and must not be mistaken for
        # a discount signal.
        remainder = s[action_match.end():].strip()
        if not _BENEFIT_RE.search(remainder):
            return "rejected", [f"{field}_action_only_cta"]

    # Description-only prefixes are suspicious but not automatically removed:
    # they can be legitimate meal/set names when backed by a verified price.
    if field == "item" and _DESCRIPTION_PREFIX_RE.search(s):
        has_price = pricing.get("promo_price") is not None
        if not has_price:
            return "review", ["item_description_fragment"]

    # Sentence-like merchant labels are frequently parser-boundary shifts. Only
    # mark for review here; hard rejection is reserved for the explicit rules
    # above so real tenant/brand names are not lost.
    if field == "merchant" and len(s) > 90 and re.search(r"[.!?。]$", s):
        return "review", ["merchant_sentence_like"]

    # Bare numbered clauses that are long and contain rule-oriented language are
    # treated as terms even when the source omits a conventional heading.
    if re.match(r"^\d+\s*[.)]\s+", s) and len(s) > 60 and re.search(
        r"(?:คูปอง|สิทธิ์|ยกเว้น|เงื่อนไข|valid|eligible|exclude|cannot|not\s+valid)", low, re.I
    ):
        return "rejected", [f"{field}_numbered_terms_fragment"]

    return "accepted", []


def evaluate_offer_identity(offer: dict) -> dict:
    merchant = _clean((offer.get("merchant") or {}).get("name"))
    item = _clean((offer.get("item") or {}).get("name"))
    pricing = offer.get("pricing") or {}
    m_state, m_reasons = _classify_field(merchant, "merchant", pricing=pricing)
    i_state, i_reasons = _classify_field(item, "item", pricing=pricing)

    reasons = m_reasons + i_reasons
    if "rejected" in {m_state, i_state}:
        state = "rejected"
    elif "review" in {m_state, i_state}:
        state = "review"
    else:
        state = "accepted"

    return {
        "contract": IDENTITY_VERSION,
        "state": state,
        "basis": "conservative_structural_rules",
        "reason_codes": reasons,
        "merchant_state": m_state,
        "item_state": i_state,
    }


def annotate_offer_identity(offer: dict) -> dict:
    out = copy.deepcopy(offer)
    out["offer_identity"] = evaluate_offer_identity(out)
    return out


def annotate_offers_identity(offers: list[dict]) -> tuple[list[dict], dict[str, int]]:
    rows = [annotate_offer_identity(o) for o in offers]
    stats: dict[str, int] = {
        "offers_scanned": len(rows),
        "accepted": 0,
        "review": 0,
        "rejected": 0,
    }
    for row in rows:
        ident = row.get("offer_identity") or {}
        state = ident.get("state") or "review"
        stats[state] = stats.get(state, 0) + 1
        for reason in ident.get("reason_codes") or []:
            stats[reason] = stats.get(reason, 0) + 1
    return rows, stats


def identity_is_rejected(offer: dict) -> bool:
    return (offer.get("offer_identity") or {}).get("state") == "rejected"
