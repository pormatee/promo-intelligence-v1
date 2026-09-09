from __future__ import annotations
from html import unescape
from html.parser import HTMLParser
import re

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_LINE_RE = re.compile(rf"\b\d{{1,2}}\s*[-–]\s*\d{{1,2}}\s+{MONTH_RE}\s+\d{{2,4}}\b|\b\d{{1,2}}\s+{MONTH_RE}\s*(?:\d{{2,4}})?\s*[-–]\s*\d{{1,2}}\s+{MONTH_RE}\s+\d{{2,4}}\b|\bFrom\s+\d{{1,2}}\s+{MONTH_RE}\s+\d{{2,4}}\s+onwards\b", re.I)
PRICE_RE = re.compile(r"(?:THB|฿)\s*([0-9][0-9,]*(?:\.\d+)?)", re.I)
REGULAR_RE = re.compile(r"regular\s+price\s+(?:THB|฿)\s*([0-9][0-9,]*(?:\.\d+)?)", re.I)
THAI_DATE_RE = re.compile(r"\d{1,2}\s*(?:[-–]\s*\d{1,2})?\s*(?:ม\.?ค\.?|ก\.?พ\.?|มี\.?ค\.?|เม\.?ย\.?|พ\.?ค\.?|มิ\.?ย\.?|ก\.?ค\.?|ส\.?ค\.?|ก\.?ย\.?|ต\.?ค\.?|พ\.?ย\.?|ธ\.?ค\.?|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)\s*\d{2,4}", re.I)


class _TextParser(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "section", "article", "span"}
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")
    def handle_data(self, data):
        self.parts.append(data)


def html_to_lines(raw_html: str) -> list[str]:
    p = _TextParser()
    p.feed(raw_html)
    text = unescape("".join(p.parts)).replace("\xa0", " ")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return lines


def _clean_leading_symbol(s: str) -> str:
    return re.sub(r"^[^A-Za-z0-9ก-๙]+", "", s).strip()


def _source_validity(source: dict | None, fallback: str = "") -> str:
    return ((source or {}).get("validity_raw") or fallback).strip()


def extract_lotus_text_offers_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    lines = html_to_lines(raw_html)
    candidates: list[dict] = []
    start = 0
    for i, line in enumerate(lines):
        if not DATE_LINE_RE.search(line):
            continue
        block = lines[max(start, i - 6): i + 1]
        start = i + 1
        joined = " | ".join(block)
        all_prices = [float(x.replace(",", "")) for x in PRICE_RE.findall(joined)]
        reg_match = REGULAR_RE.search(joined)
        regular = float(reg_match.group(1).replace(",", "")) if reg_match else None
        promo_prices = [p for p in all_prices if regular is None or p != regular]
        promo = promo_prices[0] if promo_prices else None
        if promo is None:
            continue
        nonmeta = [x for x in block[:-1] if "regular price" not in x.lower() and not DATE_LINE_RE.search(x)]
        if not nonmeta:
            continue
        merchant = _clean_leading_symbol(nonmeta[0])
        detail_lines = [_clean_leading_symbol(x) for x in nonmeta[1:]]
        item_name = detail_lines[0] if detail_lines else merchant
        conditions = [x for x in detail_lines[1:] if x]
        candidates.append({
            "merchant_name": merchant,
            "item_name": item_name,
            "regular_price_raw": regular,
            "promo_price_raw": promo,
            "validity_raw": line,
            "conditions": conditions,
            "evidence_excerpt": " | ".join(block[-5:]),
        })
    return candidates


def extract_lotus_nationwide_coupon_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    lines = html_to_lines(raw_html)
    nationwide_line = next((x for x in lines if re.search(r"\bnationwide\b", x, re.I)), None)
    date_line = next((x for x in lines if DATE_LINE_RE.search(x)), None)
    if not nationwide_line or not date_line:
        return []
    title = next((x for x in lines if "Thai Chuay Thai Plus+" in x), None)
    if not title:
        title = next((x for x in lines if "coupon" in x.lower()), "Lotus's coupon promotion")
    conditions = [x for x in lines if "spending amount" in x.lower()]
    evidence = " | ".join([title, nationwide_line, date_line] + conditions[:1])
    return [{
        "merchant_name": "Lotus's",
        "item_name": title,
        "regular_price_raw": None,
        "promo_price_raw": None,
        "offer_type_hint": "coupon",
        "validity_raw": date_line,
        "conditions": [nationwide_line] + conditions,
        "evidence_excerpt": evidence,
    }]


def _previous_product(lines: list[str], i: int) -> tuple[str | None, list[str]]:
    """Find product label and promotion descriptor preceding a Tops price line."""
    promo_markers = ("ซื้อ ", "buy ", "จ่าย 1", "pay 1", "เซฟ ", "save ")
    descriptor: list[str] = []
    for j in range(i - 1, max(-1, i - 6), -1):
        s = lines[j].strip()
        low = s.lower()
        if not s or low in {"เพิ่ม", "add", "ดูทั้งหมด", "view all"}:
            continue
        if any(m in low for m in promo_markers):
            descriptor.insert(0, s)
            continue
        if s.startswith("#") or "ต้องการความช่วยเหลือ" in s or "need help" in low:
            continue
        return s, descriptor
    return None, descriptor


def extract_tops_product_grid_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    lines = html_to_lines(raw_html)
    validity = _source_validity(source)
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for i, line in enumerate(lines):
        prices = [float(x.replace(",", "")) for x in PRICE_RE.findall(line)]
        if not prices:
            continue
        product, descriptors = _previous_product(lines, i)
        if not product:
            continue
        # Avoid footer/contact numbers that happen to use currency signs.
        if len(product) < 3 or product in {"ท็อปส์ ออนไลน์", "Tops Online"}:
            continue
        promo: float | None = None
        regular: float | None = None
        hint: str | None = None
        if descriptors:
            hint = "bundle"
        elif len(prices) >= 2 and prices[0] <= prices[1]:
            promo, regular = prices[0], prices[1]
        else:
            # A single shelf price without explicit promo mechanics is not enough evidence.
            continue
        key = (product, " | ".join(descriptors + [line]))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "merchant_name": "Tops Online",
            "item_name": product,
            "regular_price_raw": regular,
            "promo_price_raw": promo,
            "offer_type_hint": hint,
            "validity_raw": validity,
            "conditions": descriptors,
            "evidence_excerpt": " | ".join([product] + descriptors + [line, validity]),
        })
    return out


def extract_tops_coupon_page_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    lines = html_to_lines(raw_html)
    validity = _source_validity(source)
    out: list[dict] = []
    for line in lines:
        low = line.lower()
        if "ลดทันที" not in line and "ส่วนลด" not in line:
            continue
        if not ("คูปอง" in line or "coupon" in low or "e-coupon" in low or "ครบ" in line):
            continue
        # Skip generic headings with no concrete benefit/value.
        if not re.search(r"\d", line):
            continue
        out.append({
            "merchant_name": "Tops Online",
            "item_name": line[:220],
            "regular_price_raw": None,
            "promo_price_raw": None,
            "offer_type_hint": "coupon",
            "validity_raw": validity,
            "conditions": [line],
            "evidence_excerpt": f"{line} | {validity}",
        })
    return out


def extract_bigc_coupon_terms_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    lines = html_to_lines(raw_html)
    validity = _source_validity(source)
    if not validity:
        # Prefer a line explicitly introduced as the campaign period.
        for line in lines:
            if ("ระหว่างวันที่" in line or "ระยะเวลา" in line) and (THAI_DATE_RE.search(line) or DATE_LINE_RE.search(line)):
                validity = line
                break
    out: list[dict] = []
    seen: set[str] = set()
    for line in lines:
        if "รับส่วนลด" not in line or "รหัสส่วนลด" not in line:
            continue
        cleaned = re.sub(r"^[•*\-\s]+", "", line).strip()
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append({
            "merchant_name": "Big C Online",
            "item_name": cleaned[:240],
            "regular_price_raw": None,
            "promo_price_raw": None,
            "offer_type_hint": "coupon",
            "validity_raw": validity,
            "conditions": [cleaned],
            "evidence_excerpt": f"{cleaned} | {validity}",
        })
    return out



_GENERIC_NOISE = {
    "add", "เพิ่ม", "compare", "เปรียบเทียบ", "delivery", "จัดส่ง", "click & collect",
    "ดูทั้งหมด", "view all", "ช้อปเลย", "shop now", "เก็บโค้ด", "get coupon", "รับสิทธิ์",
}


def _money_values(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in PRICE_RE.findall(text)]


def _looks_title(line: str) -> bool:
    s = line.strip()
    low = s.lower()
    if len(s) < 5 or low in _GENERIC_NOISE:
        return False
    if PRICE_RE.search(s) or DATE_LINE_RE.search(s) or THAI_DATE_RE.search(s):
        return False
    if re.fullmatch(r"[\d% .,/()\-–]+", s):
        return False
    if any(x in low for x in ["copyright", "customer care", "follow us", "นโยบาย", "เงื่อนไขการใช้"]):
        return False
    if re.match(r"^(?:ยอดซื้อขั้นต่ำ|เมื่อช้อปครบ|เมื่อซื้อครบ|ส่วนลด|ลด\s*\d|หมดอายุ|valid until|ระยะเวลา)", s, re.I):
        return False
    return True


def _nearby_validity(lines: list[str], i: int, source: dict | None) -> str:
    configured = _source_validity(source)
    if configured:
        return configured
    for j in range(max(0, i - 8), min(len(lines), i + 12)):
        line = lines[j]
        if DATE_LINE_RE.search(line) or THAI_DATE_RE.search(line) or re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", line):
            return line
    return ""


def extract_generic_dual_price_grid_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    """Product-grid parser with a strict same-product price boundary.

    The old parser used a fixed line window and could accidentally pair a promo
    price from product A with a regular price from product B. This version stops
    at the next plausible product title and records field-level price evidence.
    """
    lines = html_to_lines(raw_html)
    merchant = (source or {}).get("merchant") or "Unknown Merchant"
    out: list[dict] = []
    seen: set[tuple[str, float, float]] = set()
    promo_meta_re = re.compile(r"(?:save|ประหยัด|ลด\s*\d+\s*%|discount|off|ผ่อน\s*0%)", re.I)
    for i, title in enumerate(lines):
        if not _looks_title(title):
            continue
        block: list[str] = []
        for x in lines[i + 1:i + 10]:
            is_meta = bool(PRICE_RE.search(x) or promo_meta_re.search(x))
            if _looks_title(x) and not is_meta:
                break
            block.append(x)
        if not block:
            continue
        joined = " | ".join(block)
        prices = _money_values(joined)
        uniq: list[float] = []
        for v in prices:
            if v not in uniq:
                uniq.append(v)
        if len(uniq) < 2:
            continue
        promo = uniq[0]
        regular = next((v for v in uniq[1:] if v > promo), None)
        if regular is None:
            continue
        key = (title, promo, regular)
        if key in seen:
            continue
        seen.add(key)
        descriptor = []
        prev = " | ".join(lines[max(0, i-2):i])
        if re.search(r"buy\s*1\s*get\s*1|ซื้อ\s*1\s*แถม\s*1|ซื้อ.*แถม|limited time|ฟรีของแถม", prev, re.I):
            descriptor.append(prev[-220:])
        validity = _nearby_validity(lines, i, source)
        promo_line = next((x for x in block if any(abs(v-promo)<0.005 for v in _money_values(x))), joined)
        regular_line = next((x for x in block if any(abs(v-regular)<0.005 for v in _money_values(x))), joined)
        evidence_block = " | ".join([title] + block)[:1200]
        out.append({
            "merchant_name": merchant,
            "item_name": title[:260],
            "regular_price_raw": regular,
            "promo_price_raw": promo,
            "validity_raw": validity,
            "conditions": descriptor,
            "evidence_excerpt": evidence_block,
            "price_evidence": {
                "block_text": evidence_block,
                "promo_price_text": promo_line,
                "regular_price_text": regular_line,
                "same_product_block": True,
                "pairing_method": "bounded_product_block",
            },
        })
    return out


def extract_brand_discount_cards_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    """Extract brand coupon cards: brand + minimum spend + discount + validity."""
    lines = html_to_lines(raw_html)
    merchant = (source or {}).get("merchant") or "Unknown Merchant"
    out: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        if not _looks_title(line):
            continue
        block = lines[i:i+7]
        joined = " | ".join(block)
        if not re.search(r"(?:ยอดซื้อขั้นต่ำ|เมื่อช้อปครบ|เมื่อซื้อครบ|spend)", joined, re.I):
            continue
        if not re.search(r"(?:ลด\s*\d|discount\s*\d|ส่วนลด\s*\d)", joined, re.I):
            continue
        validity = next((x for x in block if DATE_LINE_RE.search(x) or THAI_DATE_RE.search(x)), _source_validity(source))
        item = line[:240]
        key = item + "|" + joined
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "merchant_name": merchant,
            "item_name": item,
            "regular_price_raw": None,
            "promo_price_raw": None,
            "offer_type_hint": "coupon",
            "validity_raw": validity,
            "conditions": [x for x in block[1:] if x][:5],
            "evidence_excerpt": joined[:900],
        })
    return out


def extract_coupon_cards_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    """Generic coupon card parser supporting expiry-only evidence."""
    lines = html_to_lines(raw_html)
    merchant = (source or {}).get("merchant") or "Unknown Merchant"
    out: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        low = line.lower()
        if not ("ลด" in line or "discount" in low or "coupon" in low or "คูปอง" in line):
            continue
        block = lines[max(0, i-2):min(len(lines), i+6)]
        joined = " | ".join(block)
        if not re.search(r"\d", joined):
            continue
        if not re.search(r"(?:หมดอายุ|valid until|ระยะเวลา|ตั้งแต่วันที่|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", joined, re.I):
            continue
        item = line[:240]
        if item in seen:
            continue
        seen.add(item)
        validity = next((x for x in block if "หมดอายุ" in x or "valid until" in x.lower()), "")
        if not validity:
            validity = next((x for x in block if DATE_LINE_RE.search(x) or THAI_DATE_RE.search(x) or re.search(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", x)), _source_validity(source))
        out.append({
            "merchant_name": merchant,
            "item_name": item,
            "regular_price_raw": None,
            "promo_price_raw": None,
            "offer_type_hint": "coupon",
            "validity_raw": validity,
            "conditions": [x for x in block if x != line][:5],
            "evidence_excerpt": joined[:900],
        })
    return out


def extract_campaign_list_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    """Campaign-level extraction when a source publishes named promotions with explicit dates."""
    lines = html_to_lines(raw_html)
    merchant = (source or {}).get("merchant") or "Unknown Merchant"
    out: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        date_match = DATE_LINE_RE.search(line) or THAI_DATE_RE.search(line)
        if not date_match:
            continue
        # Date can be on the same line as the title or immediately after it.
        title = re.sub(r"\([^)]*(?:ก\.|Sep|Aug|Oct|Nov|Dec)[^)]*\)", "", line).strip(" -|:")
        if len(title) < 5 or title == line.strip(" -|:"):
            prev = next((x for x in reversed(lines[max(0, i-3):i]) if _looks_title(x)), "")
            title = prev or line[:220]
        if title in seen:
            continue
        seen.add(title)
        block = lines[max(0, i-2):min(len(lines), i+4)]
        out.append({
            "merchant_name": merchant,
            "item_name": title[:240],
            "regular_price_raw": None,
            "promo_price_raw": None,
            "offer_type_hint": "other",
            "validity_raw": line,
            "conditions": [x for x in block if x != title and x != line][:4],
            "evidence_excerpt": " | ".join(block)[:900],
        })
    return out


def extract_shipping_tiers_v1(raw_html: str, source: dict | None = None) -> list[dict]:
    lines = html_to_lines(raw_html)
    merchant = (source or {}).get("merchant") or "Unknown Merchant"
    validity = _source_validity(source)
    if not validity:
        validity = next((x for x in lines if DATE_LINE_RE.search(x) or THAI_DATE_RE.search(x)), "")
    out: list[dict] = []
    for line in lines:
        if not ("บาทขึ้นไป" in line and "บาท" in line):
            continue
        nums = re.findall(r"([0-9][0-9,]*)\s*บาท", line)
        if len(nums) < 2:
            continue
        out.append({
            "merchant_name": merchant,
            "item_name": f"ส่วนลดค่าจัดส่ง {line}"[:240],
            "regular_price_raw": None,
            "promo_price_raw": None,
            "offer_type_hint": "coupon",
            "validity_raw": validity,
            "conditions": [line],
            "evidence_excerpt": f"{line} | {validity}",
        })
    return out


def extract_tops_product_grid_v2(raw_html: str, source: dict | None = None) -> list[dict]:
    """Tops product parser resilient to prices/descriptors split across DOM lines.

    Requires either an explicit bundle mechanic (e.g. Buy 2 Pay 1) or two
    distinct monetary values where the second is higher than the first.
    """
    lines = html_to_lines(raw_html)
    validity = _source_validity(source)
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    bundle_re = re.compile(r"(?:ซื้อ\s*\d+.*(?:ราคา|จ่าย|แถม)|buy\s*\d+.*(?:for|pay|get))", re.I)
    promo_meta_re = re.compile(r"(?:ซื้อ\s*\d+|buy\s*\d+|ประหยัด|save|เซฟ)", re.I)

    for i, title in enumerate(lines):
        if not _looks_title(title):
            continue
        block: list[str] = []
        for x in lines[i + 1:i + 9]:
            low=x.strip().lower()
            if low in {'เพิ่ม','add'}:
                continue
            is_meta = bool(PRICE_RE.search(x) or promo_meta_re.search(x))
            # Stop at the next plausible product/title once the current block
            # has begun. Promo mechanics themselves may look title-like.
            if _looks_title(x) and not is_meta:
                break
            block.append(x)
        if not block:
            continue
        joined = " | ".join(block)
        descriptors = [x for x in block if promo_meta_re.search(x)]
        prices = _money_values(joined)
        uniq: list[float] = []
        for v in prices:
            if v not in uniq:
                uniq.append(v)
        promo: float | None = None
        regular: float | None = None
        hint: str | None = None
        if any(bundle_re.search(x) for x in descriptors):
            hint = "bundle"
        elif len(uniq) >= 2:
            promo = uniq[0]
            regular = next((v for v in uniq[1:] if v > promo), None)
            if regular is None:
                continue
        else:
            continue
        key = (title, " | ".join(descriptors + [str(promo), str(regular)]))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "merchant_name": "Tops Online",
            "item_name": title[:260],
            "regular_price_raw": regular,
            "promo_price_raw": promo,
            "offer_type_hint": hint,
            "validity_raw": validity or _nearby_validity(lines, i, source),
            "conditions": descriptors[:4],
            "evidence_excerpt": " | ".join([title] + block[:6])[:900],
            "price_evidence": {
                "block_text": " | ".join([title] + block[:6])[:1200],
                "promo_price_text": next((x for x in block if promo is not None and any(abs(v-promo)<0.005 for v in _money_values(x))), " | ".join(block)),
                "regular_price_text": next((x for x in block if regular is not None and any(abs(v-regular)<0.005 for v in _money_values(x))), " | ".join(block)),
                "same_product_block": True,
                "pairing_method": "bounded_product_block",
            },
        })
    return out

def extract(raw_html: str, extractor: str, source: dict | None = None) -> list[dict]:
    if extractor == "lotus_text_offers_v1":
        return extract_lotus_text_offers_v1(raw_html, source)
    if extractor == "lotus_nationwide_coupon_v1":
        return extract_lotus_nationwide_coupon_v1(raw_html, source)
    if extractor == "tops_product_grid_v1":
        return extract_tops_product_grid_v1(raw_html, source)
    if extractor == "tops_product_grid_v2":
        return extract_tops_product_grid_v2(raw_html, source)
    if extractor == "tops_coupon_page_v1":
        return extract_tops_coupon_page_v1(raw_html, source)
    if extractor == "bigc_coupon_terms_v1":
        return extract_bigc_coupon_terms_v1(raw_html, source)
    if extractor == "generic_dual_price_grid_v1":
        return extract_generic_dual_price_grid_v1(raw_html, source)
    if extractor == "brand_discount_cards_v1":
        return extract_brand_discount_cards_v1(raw_html, source)
    if extractor == "coupon_cards_v1":
        return extract_coupon_cards_v1(raw_html, source)
    if extractor == "campaign_list_v1":
        return extract_campaign_list_v1(raw_html, source)
    if extractor == "shipping_tiers_v1":
        return extract_shipping_tiers_v1(raw_html, source)
    raise ValueError(f"Unsupported extractor: {extractor}")
