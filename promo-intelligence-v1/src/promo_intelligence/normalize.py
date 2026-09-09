from __future__ import annotations
from datetime import date
import re

MONTHS = {
    "jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,"apr":4,"april":4,
    "may":5,"jun":6,"june":6,"jul":7,"july":7,"aug":8,"august":8,"sep":9,"sept":9,
    "september":9,"oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12,
}


def _year(y: str) -> int:
    n = int(y)
    if n < 100:
        return 2000 + n
    if n > 2400:
        return n - 543
    return n


def _iso(day: str, month: str, year: str) -> str:
    return date(_year(year), MONTHS[month.lower()], int(day)).isoformat()


def normalize_validity(raw: str) -> tuple[str | None, str | None]:
    s = raw.strip()
    # 1–30 September 2026
    m = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})", s)
    if m:
        d1,d2,mon,y = m.groups()
        return _iso(d1,mon,y), _iso(d2,mon,y)
    # 3 September – 31 October 2026 (year attached to end)
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})", s)
    if m:
        d1,m1,d2,m2,y = m.groups()
        return _iso(d1,m1,y), _iso(d2,m2,y)
    # From 1 September 2026 onwards
    m = re.search(r"From\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})\s+onwards", s, re.I)
    if m:
        d,mn,y = m.groups()
        return _iso(d,mn,y), None
    return None, None


def normalize_candidate(c: dict) -> dict:
    regular = c.get("regular_price_raw")
    promo = c.get("promo_price_raw")
    start, end = normalize_validity(c.get("validity_raw", ""))
    discount_amount = None
    discount_percent = None
    if regular is not None and promo is not None and regular > 0 and promo <= regular:
        discount_amount = round(regular - promo, 2)
        discount_percent = round((discount_amount / regular) * 100, 2)
    return {
        **c,
        "regular_price": regular,
        "promo_price": promo,
        "currency": "THB",
        "start": start,
        "end": end,
        "discount_amount": discount_amount,
        "discount_percent": discount_percent,
    }
