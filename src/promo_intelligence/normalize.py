from __future__ import annotations
from datetime import date
import re

from .price_integrity import evaluate_candidate_price_integrity

MONTHS = {
    "jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,"apr":4,"april":4,
    "may":5,"jun":6,"june":6,"jul":7,"july":7,"aug":8,"august":8,"sep":9,"sept":9,
    "september":9,"oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12,
    "ม.ค.":1,"ม.ค":1,"มกราคม":1,"ก.พ.":2,"ก.พ":2,"กุมภาพันธ์":2,"มี.ค.":3,"มี.ค":3,"มีนาคม":3,
    "เม.ย.":4,"เม.ย":4,"เมษายน":4,"พ.ค.":5,"พ.ค":5,"พฤษภาคม":5,"มิ.ย.":6,"มิ.ย":6,"มิถุนายน":6,
    "ก.ค.":7,"ก.ค":7,"กรกฎาคม":7,"ส.ค.":8,"ส.ค":8,"สิงหาคม":8,"ก.ย.":9,"ก.ย":9,"กันยายน":9,
    "ต.ค.":10,"ต.ค":10,"ตุลาคม":10,"พ.ย.":11,"พ.ย":11,"พฤศจิกายน":11,"ธ.ค.":12,"ธ.ค":12,"ธันวาคม":12,
}
MONTH_TOKEN = r"(?:[A-Za-z]+|ม\.ค\.?|ก\.พ\.?|มี\.ค\.?|เม\.ย\.?|พ\.ค\.?|มิ\.ย\.?|ก\.ค\.?|ส\.ค\.?|ก\.ย\.?|ต\.ค\.?|พ\.ย\.?|ธ\.ค\.?|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)"


def _year(y: str) -> int:
    n = int(y)
    if n < 100:
        # Thai pages commonly abbreviate Buddhist years (69 => 2569).
        return 1957 + n if n >= 40 else 2000 + n
    if n > 2400:
        return n - 543
    return n


def _month(m: str) -> int:
    key = m.strip().lower()
    if key in MONTHS:
        return MONTHS[key]
    # tolerate trailing punctuation differences in Thai abbreviations
    key2 = key.rstrip('.')
    for k, v in MONTHS.items():
        if k.rstrip('.').lower() == key2:
            return v
    raise ValueError(f"unknown month: {m}")


def _iso(day: str, month: str, year: str) -> str:
    return date(_year(year), _month(month), int(day)).isoformat()


def normalize_validity(raw: str) -> tuple[str | None, str | None]:
    s = raw.strip()
    # Numeric ranges: 03/09/2026 - 09/09/2026 or 03-09-2026 - 09-09-2026
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*[-–]\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if m:
        d1,m1,y1,d2,m2,y2 = m.groups()
        return date(_year(y1), int(m1), int(d1)).isoformat(), date(_year(y2), int(m2), int(d2)).isoformat()
    # Expiry-only evidence. Start deliberately remains unknown.
    m = re.search(r"(?:หมดอายุ\s*:?|valid\s+until\s*:?)\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s, re.I)
    if m:
        d,mn,y = m.groups()
        return None, date(_year(y), int(mn), int(d)).isoformat()
    # Single calendar date (common on daily flash-sale pages): treat as one-day validity.
    m = re.search(r"(?<!\d)(\d{1,2})[.](\d{1,2})[.](\d{2,4})(?!\d)", s)
    if m:
        d,mn,y = m.groups()
        iso = date(_year(y), int(mn), int(d)).isoformat()
        return iso, iso
    # 1 September 2026 – 30 September 2026 / 1 ก.ย. 2569 - 30 ก.ย. 2569
    m = re.search(rf"(\d{{1,2}})\s+({MONTH_TOKEN})\s+(\d{{2,4}})\s*[-–]\s*(\d{{1,2}})\s+({MONTH_TOKEN})\s+(\d{{2,4}})", s, re.I)
    if m:
        d1,m1,y1,d2,m2,y2 = m.groups()
        return _iso(d1,m1,y1), _iso(d2,m2,y2)
    # 1–30 September 2026 / 3 - 30 กันยายน 2569
    m = re.search(rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+({MONTH_TOKEN})\s+(\d{{2,4}})", s, re.I)
    if m:
        d1,d2,mon,y = m.groups()
        return _iso(d1,mon,y), _iso(d2,mon,y)
    # 3 September – 31 October 2026
    m = re.search(rf"(\d{{1,2}})\s+({MONTH_TOKEN})\s*[-–]\s*(\d{{1,2}})\s+({MONTH_TOKEN})\s+(\d{{2,4}})", s, re.I)
    if m:
        d1,m1,d2,m2,y = m.groups()
        return _iso(d1,m1,y), _iso(d2,m2,y)
    # From 1 September 2026 onwards
    m = re.search(rf"From\s+(\d{{1,2}})\s+({MONTH_TOKEN})\s+(\d{{2,4}})\s+onwards", s, re.I)
    if m:
        d,mn,y = m.groups()
        return _iso(d,mn,y), None
    return None, None


def normalize_candidate(c: dict) -> dict:
    integrity = evaluate_candidate_price_integrity(c)
    start, end = normalize_validity(c.get("validity_raw", ""))
    return {
        **c,
        "regular_price": integrity["regular_price"],
        "promo_price": integrity["promo_price"],
        "currency": "THB",
        "start": start,
        "end": end,
        "discount_amount": integrity["discount_amount"],
        "discount_percent": integrity["discount_percent"],
        "price_integrity": integrity,
    }
