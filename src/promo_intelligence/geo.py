from __future__ import annotations

from copy import deepcopy
import re

from .applicability import THAI_PROVINCE_MAP

GEO_STATES = {"explicit", "partial", "nationwide", "unknown"}
GEO_GRANULARITIES = {"coordinates", "address", "subdistrict", "district", "province", "branch", "nationwide", "unknown"}
GEO_BASES = {"offer_text", "source_config", "applicability", "none"}


def _offer_text(candidate: dict) -> str:
    return " | ".join([
        candidate.get("evidence_excerpt", "") or "",
        " | ".join(candidate.get("conditions", []) or []),
    ]).strip()


def _clean_piece(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" .,:;|/-–—")
    return value or None


def _explicit_province(text: str) -> tuple[str | None, str | None]:
    # Longest Thai name first so shorter aliases cannot steal the match.
    for thai in sorted(THAI_PROVINCE_MAP, key=len, reverse=True):
        pat = rf"(?:จังหวัด|จ\.|ในจังหวัด|เฉพาะจังหวัด)\s*{re.escape(thai)}"
        if re.search(pat, text, re.I):
            return THAI_PROVINCE_MAP[thai], thai
    return None, None


def _district(text: str) -> str | None:
    patterns = [
        r"(?:อำเภอ|อ\.)\s*([ก-๙A-Za-z][ก-๙A-Za-z0-9 ._'()-]{1,60}?)(?=\s*(?:จังหวัด|จ\.|ตำบล|ต\.|แขวง|เขต|รหัสไปรษณีย์|\b[1-9]\d{4}\b|[,;|]|$))",
        r"(?:เขต)\s*([ก-๙A-Za-z][ก-๙A-Za-z0-9 ._'()-]{1,60}?)(?=\s*(?:จังหวัด|จ\.|แขวง|รหัสไปรษณีย์|\b[1-9]\d{4}\b|[,;|]|$))",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return _clean_piece(m.group(1))
    return None


def _subdistrict(text: str) -> str | None:
    patterns = [
        r"(?:ตำบล|ต\.)\s*([ก-๙A-Za-z][ก-๙A-Za-z0-9 ._'()-]{1,60}?)(?=\s*(?:อำเภอ|อ\.|จังหวัด|จ\.|เขต|รหัสไปรษณีย์|\b[1-9]\d{4}\b|[,;|]|$))",
        r"(?:แขวง)\s*([ก-๙A-Za-z][ก-๙A-Za-z0-9 ._'()-]{1,60}?)(?=\s*(?:เขต|จังหวัด|จ\.|รหัสไปรษณีย์|\b[1-9]\d{4}\b|[,;|]|$))",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return _clean_piece(m.group(1))
    return None


def _address(text: str) -> str | None:
    # Address is captured only when the source explicitly labels it. This avoids
    # treating arbitrary evidence text as a postal address.
    m = re.search(r"(?:ที่อยู่|address)\s*[:：]?\s*([^|;]{5,220})", text, re.I)
    if not m:
        return None
    value = _clean_piece(m.group(1))
    return value


def _postal_code(text: str, has_geo_marker: bool) -> str | None:
    if not has_geo_marker:
        return None
    m = re.search(r"(?:รหัสไปรษณีย์|postal\s*code)\s*[:：]?\s*([1-9]\d{4})\b", text, re.I)
    if m:
        return m.group(1)
    # A bare 5-digit Thai postcode is accepted only when geographic markers are
    # already present in the same evidence string.
    m = re.search(r"(?<!\d)([1-9]\d{4})(?!\d)", text)
    return m.group(1) if m else None


def _coordinates(text: str) -> tuple[float | None, float | None]:
    lat_m = re.search(r"(?:lat(?:itude)?|ละติจูด)\s*[:=]?\s*(-?\d{1,2}(?:\.\d+)?)", text, re.I)
    lon_m = re.search(r"(?:lon(?:gitude)?|lng|ลองจิจูด)\s*[:=]?\s*(-?\d{1,3}(?:\.\d+)?)", text, re.I)
    if not lat_m or not lon_m:
        return None, None
    lat, lon = float(lat_m.group(1)), float(lon_m.group(1))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


def _granularity(location: dict) -> str:
    if location.get("latitude") is not None and location.get("longitude") is not None:
        return "coordinates"
    if location.get("address"):
        return "address"
    if location.get("subdistrict"):
        return "subdistrict"
    if location.get("district"):
        return "district"
    if location.get("province"):
        return "province"
    if location.get("branch_name"):
        return "branch"
    return "unknown"


def _rank(granularity: str) -> int:
    return {
        "unknown": 0, "nationwide": 1, "branch": 2, "province": 3,
        "district": 4, "subdistrict": 5, "address": 6, "coordinates": 7,
    }.get(granularity, 0)


def _location_row(*, province=None, province_raw=None, district=None, subdistrict=None,
                  branch_name=None, address=None, postal_code=None, latitude=None,
                  longitude=None, basis="offer_text", evidence_excerpt="") -> dict:
    row = {
        "province": province,
        "province_raw": province_raw,
        "district": district,
        "subdistrict": subdistrict,
        "branch_name": branch_name,
        "address": address,
        "postal_code": postal_code,
        "latitude": latitude,
        "longitude": longitude,
        "verification_state": "explicit",
        "basis": basis,
        "evidence_excerpt": evidence_excerpt[:500],
    }
    row["granularity"] = _granularity(row)
    return row


def _source_config_locations(source: dict) -> list[dict]:
    geo = source.get("geography") or {}
    if geo.get("verification_state") != "explicit":
        return []
    out = []
    for raw in geo.get("locations") or []:
        if not isinstance(raw, dict):
            continue
        row = _location_row(
            province=raw.get("province"), province_raw=raw.get("province_raw"),
            district=raw.get("district"), subdistrict=raw.get("subdistrict"),
            branch_name=raw.get("branch_name"), address=raw.get("address"),
            postal_code=raw.get("postal_code"), latitude=raw.get("latitude"),
            longitude=raw.get("longitude"), basis="source_config",
            evidence_excerpt=raw.get("evidence_excerpt", "source_config"),
        )
        out.append(row)
    return out


def resolve_geography(candidate: dict, source: dict, applicability: dict) -> dict:
    """Create structured geography without geocoding or inference.

    Only explicit offer text, explicit source config, or already-explicit
    applicability may populate fields. Missing district/address/coordinates stay
    null instead of being guessed from a merchant/branch name.
    """
    if applicability.get("scope") == "nationwide":
        return {
            "country": applicability.get("country") or "TH",
            "detail_state": "nationwide",
            "best_granularity": "nationwide",
            "locations": [],
        }

    text = _offer_text(candidate)
    province, province_raw = _explicit_province(text)
    district = _district(text)
    subdistrict = _subdistrict(text)
    address = _address(text)
    lat, lon = _coordinates(text)
    has_geo_marker = bool(province or district or subdistrict or address or lat is not None)
    postal = _postal_code(text, has_geo_marker)
    branches = list(applicability.get("branches") or [])
    provinces = list(applicability.get("provinces") or [])

    locations: list[dict] = []
    if has_geo_marker or len(branches) == 1:
        # Applicability may already carry a canonical province found by its own
        # explicit parser. Use it only when unambiguous.
        if province is None and len(provinces) == 1:
            province = provinces[0]
        locations.append(_location_row(
            province=province, province_raw=province_raw, district=district,
            subdistrict=subdistrict, branch_name=branches[0] if len(branches) == 1 else None,
            address=address, postal_code=postal, latitude=lat, longitude=lon,
            basis="offer_text" if has_geo_marker else "applicability",
            evidence_excerpt=text,
        ))
    elif provinces:
        # Never pair multiple provinces with multiple branches unless the source
        # explicitly supplies that relationship.
        for p in provinces:
            locations.append(_location_row(
                province=p, basis="applicability", evidence_excerpt=text,
            ))
    elif branches:
        for b in branches:
            locations.append(_location_row(
                branch_name=b, basis="applicability", evidence_excerpt=text,
            ))

    if not locations:
        locations = _source_config_locations(source)

    # Drop completely empty rows while preserving explicit partial records.
    locations = [x for x in locations if x.get("granularity") != "unknown"]
    if not locations:
        return {
            "country": applicability.get("country") or "TH",
            "detail_state": "unknown",
            "best_granularity": "unknown",
            "locations": [],
        }

    best = max((x.get("granularity", "unknown") for x in locations), key=_rank)
    state = "explicit" if _rank(best) >= _rank("district") else "partial"
    return {
        "country": applicability.get("country") or "TH",
        "detail_state": state,
        "best_granularity": best,
        "locations": locations,
    }


def geography_summary(offers: list[dict]) -> dict:
    out = {
        "geography_known": 0,
        "district_known": 0,
        "subdistrict_known": 0,
        "address_known": 0,
        "postal_code_known": 0,
        "coordinates_known": 0,
        "branch_name_known": 0,
    }
    for offer in offers:
        geo = offer.get("geography") or {}
        locations = geo.get("locations") or []
        if locations or geo.get("detail_state") == "nationwide":
            out["geography_known"] += 1
        if any(x.get("district") for x in locations): out["district_known"] += 1
        if any(x.get("subdistrict") for x in locations): out["subdistrict_known"] += 1
        if any(x.get("address") for x in locations): out["address_known"] += 1
        if any(x.get("postal_code") for x in locations): out["postal_code_known"] += 1
        if any(x.get("latitude") is not None and x.get("longitude") is not None for x in locations): out["coordinates_known"] += 1
        if any(x.get("branch_name") for x in locations): out["branch_name_known"] += 1
    return out


def geography_rank(geo: dict | None) -> int:
    if not geo:
        return 0
    return _rank(geo.get("best_granularity", "unknown"))


def merge_geography(a: dict | None, b: dict | None) -> dict:
    """Union explicit location evidence while preserving the best granularity."""
    a = deepcopy(a or {"country": "TH", "detail_state": "unknown", "best_granularity": "unknown", "locations": []})
    b = deepcopy(b or {"country": "TH", "detail_state": "unknown", "best_granularity": "unknown", "locations": []})
    if a.get("detail_state") == "nationwide" or b.get("detail_state") == "nationwide":
        return a if a.get("detail_state") == "nationwide" else b
    rows = []
    seen = set()
    for row in (a.get("locations") or []) + (b.get("locations") or []):
        key = tuple(row.get(k) for k in ["province","district","subdistrict","branch_name","address","postal_code","latitude","longitude"])
        if key not in seen:
            rows.append(row); seen.add(key)
    if not rows:
        return a if geography_rank(a) >= geography_rank(b) else b
    best = max((x.get("granularity", "unknown") for x in rows), key=_rank)
    return {
        "country": a.get("country") or b.get("country") or "TH",
        "detail_state": "explicit" if _rank(best) >= _rank("district") else "partial",
        "best_granularity": best,
        "locations": rows,
    }
