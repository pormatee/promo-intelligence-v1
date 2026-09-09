from __future__ import annotations
from html import unescape
from html.parser import HTMLParser
import re


MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_LINE_RE = re.compile(rf"\b\d{{1,2}}\s*[-–]\s*\d{{1,2}}\s+{MONTH_RE}\s+\d{{2,4}}\b|\b\d{{1,2}}\s+{MONTH_RE}\s*(?:\d{{2,4}})?\s*[-–]\s*\d{{1,2}}\s+{MONTH_RE}\s+\d{{2,4}}\b|\bFrom\s+\d{{1,2}}\s+{MONTH_RE}\s+\d{{2,4}}\s+onwards\b", re.I)
PRICE_RE = re.compile(r"(?:THB|฿)\s*([0-9][0-9,]*(?:\.\d+)?)", re.I)
REGULAR_RE = re.compile(r"regular\s+price\s+(?:THB|฿)\s*([0-9][0-9,]*(?:\.\d+)?)", re.I)


class _TextParser(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "section", "article"}
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
    # Strip emoji/symbol prefix without damaging letters/numbers.
    return re.sub(r"^[^A-Za-z0-9ก-๙]+", "", s).strip()


def extract_lotus_text_offers_v1(raw_html: str) -> list[dict]:
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


def extract(raw_html: str, extractor: str) -> list[dict]:
    if extractor == "lotus_text_offers_v1":
        return extract_lotus_text_offers_v1(raw_html)
    raise ValueError(f"Unsupported extractor: {extractor}")
