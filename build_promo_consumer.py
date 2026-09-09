#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, copy, html, json, re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_PUBLISHED = ROOT / "output" / "published"
DEFAULT_OUTPUT = ROOT / "promo_consumer.html"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ไม่พบ {path}\nกรุณาสร้าง Published Read Model ก่อน")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ไฟล์ {path} ต้องเป็น JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"ไม่พบ {path}\nกรุณาสร้าง Published Read Model ก่อน")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"JSONL ผิดรูปแบบ {path}:{n}: {e}")
            if isinstance(value, dict):
                rows.append(value)
    return rows


def payload_b64(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def payload_json_text(value: Any) -> str:
    """Embed JSON safely inside <script type=application/json> without Base64 decode cost."""
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (raw.replace("&", "\\u0026")
               .replace("<", "\\u003c")
               .replace(">", "\\u003e"))


_TECH_TOKENS = (
    '"props"', '"pageprops"', '__next_data__', 'redis_uri', 'redis_url',
    'amazonaws.com', 'webpack', 'runtimeconfig', 'buildmanifest',
    '<!doctype', '<html', '<script', 'window.__', 'self.__next',
    'application/json', 'cache.amazonaws', 'cloudfront.net',
)


def looks_technical_payload(value: Any) -> bool:
    """True when a value looks like site/runtime payload, not human-facing offer copy."""
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    low = text.lower()
    if any(tok in low for tok in _TECH_TOKENS):
        return True
    if text[:1] in '{[' and any(k in low for k in ('":', 'props', 'config', 'data', 'query')):
        return True
    if re.search(r'https?://[^\s]+(?:amazonaws|cloudfront|redis|cache)[^\s]*', low):
        return True
    # Long machine-looking blobs are not suitable as card titles/descriptions.
    if len(text) > 220:
        punct = sum(ch in '{}[]<>"=:;,\\' for ch in text)
        if punct / max(len(text), 1) > 0.08:
            return True
    return False


def clean_display_text(value: Any, *, max_len: int = 180) -> str | None:
    if value is None:
        return None
    text = re.sub(r'\s+', ' ', str(value)).strip()
    if not text or looks_technical_payload(text):
        return None
    if text.lower().startswith(('http://', 'https://', 'data:', 'content://')):
        return None
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + '…'
    return text


def _fallback_title(offer: dict[str, Any]) -> str:
    merchant = clean_display_text((offer.get('merchant') or {}).get('name'), max_len=80) or 'ร้านค้า'
    label = {
        'coupon': 'คูปอง',
        'price_discount': 'โปรโมชั่นลดราคา',
        'special_price': 'ราคาพิเศษ',
        'bundle': 'โปรซื้อเป็นชุด',
        'buy_x_get_y': 'โปรซื้อ X แถม Y',
    }.get(offer.get('offer_type'), 'โปรโมชั่น')
    return f'{label}จาก {merchant}'


def _compact_geo_locations(offer: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in ((offer.get("geography") or {}).get("locations") or []):
        if not isinstance(g, dict):
            continue
        row = {k: g.get(k) for k in (
            "province", "province_raw", "district", "subdistrict", "branch_name",
            "address", "postal_code", "latitude", "longitude", "detail_state",
            "best_granularity", "verification_state", "basis", "evidence_excerpt",
        ) if g.get(k) not in (None, "", [])}
        if row:
            rows.append(row)
    return rows


def _compact_price_field(field: Any) -> dict[str, Any]:
    field = field if isinstance(field, dict) else {}
    out = {"supported": field.get("supported") is True}
    excerpt = clean_display_text(field.get("evidence_excerpt"), max_len=420)
    if excerpt:
        out["evidence_excerpt"] = excerpt
    return out


def prepare_offer_for_consumer(offer: dict[str, Any]) -> dict[str, Any]:
    """Build a compact frontend-only row.

    The published contract remains untouched on disk. Large raw source/evidence payloads are
    intentionally excluded from the initial browser payload so Android does not have to parse
    tens of megabytes before rendering the first cards.
    """
    item = offer.get('item') or {}
    raw_title = item.get('name')
    title = clean_display_text(raw_title, max_len=180)
    title_fallback = title is None
    if title is None:
        brand = clean_display_text(item.get('brand'), max_len=100)
        category = clean_display_text(item.get('category'), max_len=100)
        title = brand or category or _fallback_title(offer)

    brand = clean_display_text(item.get('brand'), max_len=100)
    category = clean_display_text(item.get('category'), max_len=100)
    description = brand if brand and brand != title else category if category and category != title else None

    clean_conditions: list[str] = []
    hidden_conditions = 0
    for value in offer.get('conditions') or []:
        cleaned = clean_display_text(value, max_len=220)
        if cleaned:
            clean_conditions.append(cleaned)
        elif value:
            hidden_conditions += 1

    ev = offer.get('evidence') or {}
    raw_evidence = ev.get('extracted_text')
    evidence_is_technical = looks_technical_payload(raw_evidence)
    evidence_display = None if evidence_is_technical else clean_display_text(raw_evidence, max_len=900)

    merchant = offer.get('merchant') or {}
    pricing = offer.get('pricing') or {}
    verification = offer.get('verification') or {}
    applicability = offer.get('applicability') or {}
    validity = offer.get('validity') or {}
    source = offer.get('source') or {}
    pf = ev.get('price_fields') or {}

    out: dict[str, Any] = {
        'offer_id': offer.get('offer_id'),
        'offer_type': offer.get('offer_type'),
        'merchant': {'name': merchant.get('name')},
        'pricing': {k: pricing.get(k) for k in (
            'currency', 'promo_price', 'regular_price', 'discount_amount', 'discount_percent',
            'verification_state', 'anomalies',
        ) if pricing.get(k) not in (None, '', [])},
        'validity': {k: validity.get(k) for k in ('start', 'end') if validity.get(k) not in (None, '')},
        'verification': {k: verification.get(k) for k in (
            'verification_state', 'freshness_state', 'expiry_state', 'source_reliability',
            'price_verification_state',
        ) if verification.get(k) not in (None, '')},
        'applicability': {k: applicability.get(k) for k in ('scope', 'channel') if applicability.get(k) not in (None, '')},
        'geography': {'locations': _compact_geo_locations(offer)},
        'source': {k: source.get(k) for k in ('source_id', 'source_type', 'url', 'observed_at') if source.get(k) not in (None, '')},
        'evidence': {'price_fields': {
            'promo_price': _compact_price_field(pf.get('promo_price')),
            'regular_price': _compact_price_field(pf.get('regular_price')),
        }},
        'place_refs': list(offer.get('place_refs') or []),
        'merchant_place_ref': offer.get('merchant_place_ref'),
        '_consumer_display': {
            'title': title,
            'description': description,
            'conditions': clean_conditions,
            'title_fallback': title_fallback,
            'technical_payload_hidden': bool(title_fallback and looks_technical_payload(raw_title)) or evidence_is_technical or hidden_conditions > 0,
            'hidden_condition_count': hidden_conditions,
            'evidence_text': evidence_display,
        },
    }
    return out

def prepare_consumer_offers(offers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = [prepare_offer_for_consumer(o) for o in offers]
    fallback = sum(bool((o.get('_consumer_display') or {}).get('title_fallback')) for o in rows)
    hidden = sum(bool((o.get('_consumer_display') or {}).get('technical_payload_hidden')) for o in rows)
    return rows, {
        'title_fallback_offers': fallback,
        'technical_payload_hidden_offers': hidden,
    }


def prepare_place_for_consumer(place: dict[str, Any]) -> dict[str, Any]:
    merchant = place.get('merchant') or {}
    branch = place.get('branch') or {}
    loc = place.get('location') or {}
    ver = place.get('verification') or {}
    return {
        'place_id': place.get('place_id'),
        'record_kind': place.get('record_kind'),
        'merchant': {'name': merchant.get('name')},
        'branch': {'name': branch.get('name')} if branch.get('name') else {},
        'location': {k: loc.get(k) for k in (
            'province', 'district', 'subdistrict', 'address', 'postal_code', 'latitude', 'longitude'
        ) if loc.get(k) not in (None, '')},
        'precision': place.get('precision'),
        'verification': {'state': ver.get('state')},
        'search_terms': [str(x) for x in (place.get('search_terms') or [])[:24] if x],
        'evidence_count': len(place.get('evidence') or []),
    }


def prepare_consumer_places(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [prepare_place_for_consumer(p) for p in places]


# Canonical Thailand geography used only by the standalone consumer UI.
# This does not mutate Published Read Model data.
REGION_PROVINCES = {
    "bangkok_metro": ("กรุงเทพฯ / ปริมณฑล", ["กรุงเทพมหานคร","นครปฐม","นนทบุรี","ปทุมธานี","สมุทรปราการ","สมุทรสาคร"]),
    "central": ("ภาคกลาง", ["ชัยนาท","นครนายก","พระนครศรีอยุธยา","ลพบุรี","สระบุรี","สิงห์บุรี","อ่างทอง","สุพรรณบุรี","สมุทรสงคราม"]),
    "east": ("ภาคตะวันออก", ["ฉะเชิงเทรา","ชลบุรี","ระยอง","จันทบุรี","ตราด","ปราจีนบุรี","สระแก้ว"]),
    "west": ("ภาคตะวันตก", ["กาญจนบุรี","ราชบุรี","เพชรบุรี","ประจวบคีรีขันธ์"]),
    "north": ("ภาคเหนือ", ["เชียงใหม่","เชียงราย","ลำพูน","ลำปาง","แม่ฮ่องสอน","พะเยา","แพร่","น่าน","อุตรดิตถ์","ตาก","สุโขทัย","พิษณุโลก","พิจิตร","เพชรบูรณ์","กำแพงเพชร","นครสวรรค์","อุทัยธานี"]),
    "northeast": ("ภาคตะวันออกเฉียงเหนือ", ["กาฬสินธุ์","ขอนแก่น","ชัยภูมิ","นครพนม","นครราชสีมา","บึงกาฬ","บุรีรัมย์","มหาสารคาม","มุกดาหาร","ยโสธร","ร้อยเอ็ด","เลย","ศรีสะเกษ","สกลนคร","สุรินทร์","หนองคาย","หนองบัวลำภู","อำนาจเจริญ","อุดรธานี","อุบลราชธานี"]),
    "south": ("ภาคใต้", ["กระบี่","ชุมพร","ตรัง","นครศรีธรรมราช","นราธิวาส","ปัตตานี","พังงา","พัทลุง","ภูเก็ต","ยะลา","ระนอง","สงขลา","สตูล","สุราษฎร์ธานี"]),
}

PROVINCE_EN_ALIASES = {
    "bangkok":"กรุงเทพมหานคร","krung thep maha nakhon":"กรุงเทพมหานคร","nakhon pathom":"นครปฐม","nonthaburi":"นนทบุรี","pathum thani":"ปทุมธานี","samut prakan":"สมุทรปราการ","samut sakhon":"สมุทรสาคร",
    "chai nat":"ชัยนาท","nakhon nayok":"นครนายก","samut songkhram":"สมุทรสงคราม","phra nakhon si ayutthaya":"พระนครศรีอยุธยา","ayutthaya":"พระนครศรีอยุธยา","lop buri":"ลพบุรี","lopburi":"ลพบุรี","saraburi":"สระบุรี","sing buri":"สิงห์บุรี","ang thong":"อ่างทอง","suphan buri":"สุพรรณบุรี",
    "chachoengsao":"ฉะเชิงเทรา","chon buri":"ชลบุรี","chonburi":"ชลบุรี","rayong":"ระยอง","chanthaburi":"จันทบุรี","trat":"ตราด","prachin buri":"ปราจีนบุรี","prachinburi":"ปราจีนบุรี","sa kaeo":"สระแก้ว","sakaeo":"สระแก้ว",
    "kanchanaburi":"กาญจนบุรี","ratchaburi":"ราชบุรี","phetchaburi":"เพชรบุรี","prachuap khiri khan":"ประจวบคีรีขันธ์",
    "chiang mai":"เชียงใหม่","chiang rai":"เชียงราย","lamphun":"ลำพูน","lampang":"ลำปาง","mae hong son":"แม่ฮ่องสอน","phayao":"พะเยา","phrae":"แพร่","nan":"น่าน","uttaradit":"อุตรดิตถ์","tak":"ตาก","sukhothai":"สุโขทัย","phitsanulok":"พิษณุโลก","phichit":"พิจิตร","phetchabun":"เพชรบูรณ์","kamphaeng phet":"กำแพงเพชร","nakhon sawan":"นครสวรรค์","uthai thani":"อุทัยธานี",
    "kalasin":"กาฬสินธุ์","khon kaen":"ขอนแก่น","chaiyaphum":"ชัยภูมิ","nakhon phanom":"นครพนม","nakhon ratchasima":"นครราชสีมา","korat":"นครราชสีมา","bueng kan":"บึงกาฬ","buriram":"บุรีรัมย์","buri ram":"บุรีรัมย์","maha sarakham":"มหาสารคาม","mukdahan":"มุกดาหาร","yasothon":"ยโสธร","roi et":"ร้อยเอ็ด","loei":"เลย","si sa ket":"ศรีสะเกษ","sisaket":"ศรีสะเกษ","sakon nakhon":"สกลนคร","surin":"สุรินทร์","nong khai":"หนองคาย","nong bua lam phu":"หนองบัวลำภู","amnat charoen":"อำนาจเจริญ","udon thani":"อุดรธานี","ubon ratchathani":"อุบลราชธานี",
    "krabi":"กระบี่","chumphon":"ชุมพร","trang":"ตรัง","nakhon si thammarat":"นครศรีธรรมราช","narathiwat":"นราธิวาส","pattani":"ปัตตานี","phang nga":"พังงา","phatthalung":"พัทลุง","phuket":"ภูเก็ต","yala":"ยะลา","ranong":"ระนอง","songkhla":"สงขลา","satun":"สตูล","surat thani":"สุราษฎร์ธานี",
}

def geo_meta() -> dict[str, Any]:
    provinces = []
    region_by_province = {}
    regions = []
    for rid, (label, rows) in REGION_PROVINCES.items():
        regions.append({"id": rid, "label": label, "provinces": rows})
        for province in rows:
            provinces.append(province)
            region_by_province[province] = rid
    aliases = {}
    for province in provinces:
        aliases[province.strip().lower()] = province
    aliases.update(PROVINCE_EN_ALIASES)
    return {"regions": regions, "provinces": provinces, "region_by_province": region_by_province, "aliases": aliases}


def canonical_province_for_consumer(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+province$", "", str(value).strip().lower())
    text = re.sub(r"\s+", " ", text)
    meta = geo_meta()
    return meta["aliases"].get(text) or (str(value).strip() if str(value).strip() in meta["provinces"] else None)


def attach_consumer_area_semantics(offers: list[dict[str, Any]], places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach safe area metadata for consumer filtering.

    IMPORTANT: branch-directory existence alone must never imply that an offer applies to that
    province. Only explicit offer geography, direct physical place_refs, or explicit nationwide
    applicability may affect province/region results.
    """
    place_by_id = {p.get("place_id"): p for p in places if p.get("place_id")}
    region_by_province = geo_meta()["region_by_province"]
    for offer in offers:
        local: set[str] = set()
        for g in ((offer.get("geography") or {}).get("locations") or []):
            if not isinstance(g, dict):
                continue
            for key in ("province", "province_raw"):
                pv = canonical_province_for_consumer(g.get(key))
                if pv:
                    local.add(pv)
        # Direct offer place_refs are explicit offer-to-place evidence. merchant_place_ref /
        # merchant_branch_index is deliberately NOT used here.
        for pid in offer.get("place_refs") or []:
            place = place_by_id.get(pid)
            loc = (place or {}).get("location") or {}
            pv = canonical_province_for_consumer(loc.get("province"))
            if pv:
                local.add(pv)
        app = offer.get("applicability") or {}
        offer["_consumer_area"] = {
            "local_provinces": sorted(local),
            "local_regions": sorted({region_by_province[pv] for pv in local if pv in region_by_province}),
            "nationwide": app.get("scope") == "nationwide",
            "online": app.get("channel") == "online",
        }
    return offers


HTML = r'''<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0967b2">
<meta name="color-scheme" content="light">
<title>Promo Finder</title>
<style>
:root{--bg:#f4f8fb;--card:#fff;--ink:#132b3f;--muted:#6a7c8d;--line:#dbe7ef;--blue:#0c67b5;--blue2:#125296;--cyan:#0e9eb8;--teal:#087d72;--green:#0a7a55;--orange:#a86800;--red:#b23f43;--soft:#eaf5fb;--shadow:0 8px 24px rgba(19,43,63,.08);--radius:18px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:system-ui,-apple-system,"Noto Sans Thai","Segoe UI",sans-serif;background:linear-gradient(180deg,#eaf6fb 0,#f7fafc 260px,var(--bg) 100%);color:var(--ink)}button,input,select{font:inherit}button{cursor:pointer}a{color:var(--blue)}.hide{display:none!important}
.app{max-width:1180px;margin:auto;padding:0 12px 88px}.hero{margin:0 -12px;padding:18px 16px 20px;background:linear-gradient(125deg,#0e4f94,#087bb5 58%,#07887d);color:#fff;box-shadow:var(--shadow)}.brand{display:flex;gap:11px;align-items:center}.logo{width:46px;height:46px;border-radius:15px;background:rgba(255,255,255,.17);display:grid;place-items:center;font-size:25px}.brand h1{font-size:23px;margin:0;line-height:1.1}.brand p{font-size:12px;margin:4px 0 0;opacity:.9}.fresh{margin-left:auto;text-align:right;font-size:11px;opacity:.92}.heroSearch{margin-top:16px;position:relative}.heroSearch input{width:100%;border:0;border-radius:15px;padding:14px 46px 14px 14px;background:#fff;color:var(--ink);box-shadow:0 8px 24px rgba(0,0,0,.12);outline:none}.heroSearch button{position:absolute;right:6px;top:6px;border:0;border-radius:11px;width:36px;height:36px;background:#eaf5fb;color:var(--blue);font-size:18px}.quick{display:flex;gap:7px;overflow:auto;padding:11px 0 1px}.quick button{white-space:nowrap;border:1px solid rgba(255,255,255,.32);background:rgba(255,255,255,.11);color:#fff;border-radius:999px;padding:7px 10px;font-size:11px}.quick button.active{background:#fff;color:#075f9d;border-color:#fff;font-weight:800}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}.stat{background:#fff;border:1px solid var(--line);border-radius:15px;padding:10px 11px;box-shadow:var(--shadow)}.stat b{font-size:20px;display:block}.stat span{font-size:10px;color:var(--muted)}
.toolbar{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:8px;box-shadow:var(--shadow);margin:8px 0}.filterGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.filterGrid select,.filterGrid input,.filterGrid button{width:100%;border:1px solid var(--line);border-radius:10px;padding:7px 9px;background:#fff;color:var(--ink);font-size:12px}.filterGrid .wide{grid-column:span 2}.advancedFilters{display:none;margin-top:6px}.advancedFilters.show{display:grid}.advancedToggle{font-weight:800;color:#0b648f!important;background:#eef8fc!important}.subfilters{display:flex;gap:5px;overflow:auto;margin-top:6px}.subfilters button{white-space:nowrap;border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 8px;font-size:10px;color:#4c6275;min-height:32px!important}.subfilters button.active{background:var(--soft);border-color:#a2cfdf;color:#08607a;font-weight:800}.filterLabel{font-size:9px;color:var(--muted);margin:1px 2px 4px}.filterResultMini{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:6px 2px 0;font-size:10px;color:#49697e}.filterResultMini b{font-size:12px;color:#0b648f}.areaBreakdown{display:none;margin:5px 2px 0;padding:6px 8px;border-radius:10px;background:#f4f9fc;color:#365a70;font-size:9.5px;line-height:1.35}.areaBreakdown.show{display:block}.areaBreakdown b{color:#0b648f}.resultsAnchor{scroll-margin-top:8px}
.sectionHead{display:flex;justify-content:space-between;align-items:end;margin:12px 2px 8px}.sectionHead h2{font-size:16px;margin:0}.sectionHead small{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:13px;box-shadow:var(--shadow);position:relative}.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.merchant{font-weight:900;color:#0a5e9d}.pill{font-size:10px;border:1px solid var(--line);border-radius:999px;padding:3px 7px;color:#617487}.title{font-size:16px;font-weight:850;line-height:1.4;margin:8px 0 5px}.desc{font-size:11px;color:#667b8d;line-height:1.45;min-height:16px}.pricebox{margin:10px 0 8px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}.promo{font-size:25px;font-weight:950;color:var(--teal)}.regular{color:#788895;text-decoration:line-through}.discount{font-weight:900;color:var(--red)}.priceNote{font-size:10px;color:var(--orange);margin-top:-3px}.meta{font-size:11px;line-height:1.7;color:#506678}.badges{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}.badge{font-size:9.5px;padding:4px 7px;border-radius:999px;background:#eef3f6;color:#526576}.badge.good{background:#e3f6ed;color:var(--green)}.badge.warn{background:#fff1d4;color:var(--orange)}.badge.info{background:#e7f4fb;color:#086b8d}.actions{display:flex;gap:7px;margin-top:10px}.actions button,.actions a{flex:1;text-align:center;border:1px solid var(--line);border-radius:10px;background:#fff;padding:8px 7px;text-decoration:none;color:var(--blue);font-weight:750;font-size:11px}.actions .primary{background:var(--blue);border-color:var(--blue);color:#fff}.fav{position:absolute;right:12px;top:11px;border:0;background:transparent;font-size:20px;color:#a1afba}.fav.on{color:#e6a100}.more{display:none;width:100%;margin:12px 0;border:1px solid var(--line);border-radius:12px;background:#fff;padding:11px;color:var(--blue);font-weight:800}
.drawerBackdrop{position:fixed;inset:0;background:rgba(9,24,38,.44);display:none;z-index:20}.drawerBackdrop.show{display:block}.drawer{position:absolute;left:0;right:0;bottom:0;background:#fff;border-radius:24px 24px 0 0;max-height:86vh;overflow:auto;padding:16px;box-shadow:0 -14px 34px rgba(0,0,0,.18)}.drawer h3{margin:0 36px 6px 0}.close{position:absolute;right:14px;top:12px;border:0;background:#eef4f7;border-radius:50%;width:32px;height:32px}.detailGrid{display:grid;grid-template-columns:130px 1fr;gap:7px 10px;font-size:11px;margin:12px 0}.detailGrid div:nth-child(odd){color:var(--muted)}.evidence{white-space:pre-wrap;background:#f6f9fb;border-radius:12px;padding:10px;font-size:10px;line-height:1.55;max-height:220px;overflow:auto}.warning{border-left:4px solid #e4a22d;background:#fff8e8;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.5;margin:10px 0}.safe{border-left:4px solid #1a9b6a;background:#ebf8f2;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.5;margin:10px 0}
.tabPanel{display:none}.tabPanel.active{display:block}.places{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.placeCard{background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px;box-shadow:var(--shadow)}.placeCard h3{font-size:15px;margin:5px 0}.placeCard p{font-size:11px;line-height:1.6;color:#566d80;margin:0}.systemCard{background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px;box-shadow:var(--shadow)}.kv{display:grid;grid-template-columns:180px 1fr;gap:8px 12px;font-size:11px}.kv div:nth-child(odd){color:var(--muted)}
.bottomnav{position:fixed;bottom:0;left:0;right:0;background:rgba(255,255,255,.97);border-top:1px solid var(--line);display:flex;justify-content:center;z-index:10;padding-bottom:max(4px,env(safe-area-inset-bottom))}.bottomnav .inner{width:min(680px,100%);display:grid;grid-template-columns:repeat(4,1fr)}.navbtn{border:0;background:transparent;padding:9px 4px 7px;color:#607487;font-size:10px}.navbtn b{display:block;font-size:18px;line-height:1.1}.navbtn.active{color:var(--blue);font-weight:850}.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:36px 10px}.countBadge{display:inline-block;background:#edf5fa;border-radius:999px;padding:3px 8px;font-size:10px;color:#547083}
/* Android interaction hardening */
button,input,select,a{touch-action:manipulation;-webkit-tap-highlight-color:rgba(12,103,181,.16)}
.hero,.heroSearch,.quick,.stats,.toolbar,.filterGrid,.subfilters,.sectionHead,.cards,.places,.bottomnav{position:relative}
.hero{z-index:2}.toolbar{z-index:3}.filterGrid{z-index:4}.subfilters{z-index:4}.bottomnav{z-index:30}
.filterGrid select,.filterGrid input,.filterGrid button{position:relative;z-index:5;pointer-events:auto!important;min-height:40px;-webkit-appearance:auto;appearance:auto}
.quick button,.subfilters button,.navbtn,.actions button,.actions a,.fav,.heroSearch button,.more{position:relative;pointer-events:auto!important;z-index:6;min-height:42px}
.quick,.subfilters{touch-action:pan-x;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}
.drawerBackdrop:not(.show){display:none!important;pointer-events:none!important}.drawerBackdrop.show{display:block!important;pointer-events:auto!important;z-index:60}.drawer{pointer-events:auto}
.interactionStatus{margin:8px 2px 0;font-size:10px;color:var(--muted)}
@media(max-width:780px){.stats{display:flex;overflow:auto;gap:6px;margin:8px 0;padding-bottom:2px}.stat{min-width:118px;padding:7px 9px}.stat b{font-size:18px}.stat span{font-size:9px}.filterGrid{grid-template-columns:1fr 1fr;gap:6px}.filterGrid .wide{grid-column:1/-1}.toolbar{padding:8px;border-radius:15px}.interactionStatus{margin-top:5px}.cards,.places{grid-template-columns:1fr}.fresh{font-size:9px}.detailGrid,.kv{grid-template-columns:1fr}.app{padding-bottom:84px}.sectionHead{margin-top:8px}.hero{padding-bottom:14px}}

/* V1.4 compact mobile header + fast-first-view; V1.5 server-baked filter options */
.hero{padding:10px 12px 9px}.logo{width:34px;height:34px;border-radius:11px;font-size:19px}.brand{gap:8px}.brand h1{font-size:19px}.brand p{font-size:10px;margin-top:2px}.fresh{font-size:9px;line-height:1.25;max-width:132px}.heroSearch{margin-top:8px}.heroSearch input{border-radius:12px;padding:10px 42px 10px 12px;min-height:42px;font-size:15px}.heroSearch button{position:absolute!important;right:5px!important;top:5px!important;width:32px!important;height:32px!important;min-height:32px!important;border-radius:10px;display:none;align-items:center;justify-content:center}.heroSearch button.show{display:flex}.quick{padding:7px 0 0;gap:5px}.quick button{padding:5px 9px;font-size:10px;min-height:32px!important}.toolbar{margin:6px 0;padding:7px}.filterGrid{gap:5px}.filterGrid select,.filterGrid input,.filterGrid button{padding:5px 8px;min-height:36px;font-size:11px}.advancedFilters{margin-top:5px}.subfilters{margin-top:5px}.subfilters button{min-height:29px!important;padding:4px 7px;font-size:9.5px}.filterResultMini{margin-top:5px}.sectionHead{margin-top:7px}.loadingCard{grid-column:1/-1;background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;text-align:center;color:var(--muted);font-size:12px}.startupHint{font-size:9px;opacity:.9}.compactSummary{display:none}
@media(max-width:780px){.brand p{display:none}.fresh #pubText{display:none}.fresh{font-size:9px;max-width:110px}.hero{padding:9px 10px 8px}.stats{display:none!important}.app{padding-left:9px;padding-right:9px}.hero{margin-left:-9px;margin-right:-9px}.toolbar{border-radius:13px}.filterLabel{margin-bottom:3px}.filterResultMini{font-size:9px}.filterResultMini b{font-size:11px}.compactSummary{display:block;color:rgba(255,255,255,.9);font-size:9px;margin-top:2px}}
</style>
</head>
<body>
<div class="app">
<header class="hero">
  <div class="brand"><div class="logo">🏷️</div><div><h1>Promo Finder</h1><p>โปรจากแหล่งข้อมูลที่ตรวจสอบย้อนกลับได้</p><div class="compactSummary">__SUMMARY_LABEL__</div></div><div class="fresh"><div id="freshText">ข้อมูลพร้อมใช้</div><div id="pubText">__PUB_LABEL__</div></div></div>
  <div class="heroSearch"><input id="mainSearch" placeholder="ค้นหาโปร สินค้า ร้าน หรือจังหวัด"><button id="clearSearch" title="ล้างคำค้น" aria-label="ล้างคำค้น">×</button></div>
  <div class="quick" id="quickTop"><button class="active" data-q="all">ทั้งหมด</button><button data-q="active">โปรที่ยังใช้ได้</button><button data-q="discount30">ลด 30%+</button><button data-q="online">ออนไลน์</button><button data-q="nationwide">ทั่วประเทศ</button><button data-q="verifiedprice">ราคายืนยัน</button><button data-q="expiring">ใกล้หมดโปร</button></div>
</header>
<div class="stats" id="stats"></div>

<section id="offersPanel" class="tabPanel active">
  <div class="toolbar">
    <div class="filterLabel">พื้นที่และร้าน</div>
    <div class="filterGrid">
      <select id="region"><option value="">ทุกภูมิภาค</option>__REGION_OPTIONS__</select>
      <select id="province"><option value="">ทุกจังหวัด</option>__PROVINCE_OPTIONS__</select>
      <select id="merchant"><option value="">ทุกร้าน</option>__MERCHANT_OPTIONS__</select>
      <button type="button" class="advancedToggle" id="advancedToggle">ตัวกรองเพิ่ม ▾</button>
    </div>
    <div class="filterGrid advancedFilters" id="advancedFilters">
      <select id="type"><option value="">ทุกประเภทโปร</option>__TYPE_OPTIONS__</select>
      <select id="channel"><option value="">ทุกช่องทาง</option><option value="online">ออนไลน์</option><option value="store">หน้าร้าน</option><option value="omnichannel">ออนไลน์ + หน้าร้าน</option><option value="unknown">ไม่ระบุ</option></select>
      <select id="sort"><option value="updated">อัปเดตล่าสุด</option><option value="discount">ส่วนลดมาก</option><option value="price">ราคาโปรต่ำ</option><option value="expiry">ใกล้หมดโปร</option><option value="merchant">ร้าน A-Z</option></select>
    </div>
    <div class="subfilters" id="subfilters"><button class="active" data-f="all">ทั้งหมด</button><button data-f="priceok">มีราคาที่ยืนยัน</button><button data-f="noregular">ไม่บังคับราคาปกติ</button><button data-f="directplace">มีสถานที่อ้างอิงตรง</button><button data-f="saved">ที่บันทึกไว้</button></div>
    <div class="filterResultMini"><b id="filterResultMini">กำลังคำนวณผล…</b><span id="interactionStatus">แตะตัวกรองเพื่อเลือก</span></div>
    <div class="areaBreakdown" id="areaBreakdown"></div>
  </div>
  <div class="sectionHead resultsAnchor" id="resultsAnchor"><h2 id="offerCount">โปรโมชั่น</h2><small id="offerHint"></small></div>
  <div class="cards" id="offerCards"><div class="loadingCard">กำลังเตรียมรายการโปรโมชั่น…<br><span class="startupHint">ข้อมูลอยู่ในเครื่องและกำลังเปิด snapshot ล่าสุด</span></div></div><button class="more" id="offerMore">แสดงเพิ่ม</button>
</section>

<section id="placesPanel" class="tabPanel">
  <div class="toolbar"><div class="filterGrid"><input class="wide" id="placeSearch" placeholder="ค้นหาร้าน สาขา จังหวัด อำเภอ…"><select id="placeMerchant"><option value="">ทุกร้าน</option>__PLACE_MERCHANT_OPTIONS__</select><select id="placeProvince"><option value="">ทุกจังหวัด</option>__PLACE_PROVINCE_OPTIONS__</select><select id="placeKind"><option value="branch">เฉพาะสาขา</option><option value="merchant">เฉพาะร้านหลัก</option><option value="">ทั้งหมด</option></select></div></div>
  <div class="warning">ข้อมูลสาขาหมายถึง “สาขานี้มีอยู่จริงตามหลักฐาน” เท่านั้น ไม่ได้แปลว่าโปรโมชั่นทุกตัวใช้ได้ที่สาขานั้น การ์ดโปรโมชั่นจะระบุพื้นที่ใช้สิทธิ์แยกต่างหาก</div>
  <div class="sectionHead"><h2 id="placeCount">ร้านและสาขา</h2><small id="placeHint"></small></div><div class="places" id="placeCards"></div><button class="more" id="placeMore">แสดงเพิ่ม</button>
</section>

<section id="savedPanel" class="tabPanel"><div class="sectionHead"><h2>โปรที่บันทึกไว้</h2><small>เก็บเฉพาะในเบราว์เซอร์เครื่องนี้</small></div><div class="cards" id="savedCards"></div></section>
<section id="aboutPanel" class="tabPanel"><div class="systemCard"><h2 style="margin-top:0">เกี่ยวกับข้อมูล</h2><div class="safe">หน้านี้อ่านเฉพาะข้อมูลที่ผ่าน Published Read Model แบบ read-only และไม่แก้ข้อมูลหลังบ้าน</div><div class="kv" id="systemKv"></div><div class="warning">ถ้าราคาปกติหรือเปอร์เซ็นต์ส่วนลดไม่มีหลักฐานที่ยืนยัน ระบบจะไม่แสดงตัวเลขเปรียบเทียบนั้น แม้ต้นฉบับเก่าจะเคยมีค่าอยู่</div></div></section>
</div>

<div class="bottomnav"><div class="inner"><button class="navbtn active" data-panel="offers"><b>🏷️</b>โปร</button><button class="navbtn" data-panel="places"><b>🏬</b>ร้าน/สาขา</button><button class="navbtn" data-panel="saved"><b>⭐</b>บันทึก</button><button class="navbtn" data-panel="about"><b>ⓘ</b>ข้อมูล</button></div></div>
<div class="drawerBackdrop" id="drawerBackdrop"><div class="drawer" id="drawer"><button class="close" id="drawerClose">×</button><div id="drawerBody"></div></div></div>
<script id="payloadData" type="application/json">__PAYLOAD_JSON__</script>
<script>
window.addEventListener('error',function(e){
  try{
    const cards=document.getElementById('offerCards');
    const mini=document.getElementById('filterResultMini');
    const fresh=document.getElementById('freshText');
    if(cards) cards.innerHTML='<div class=\"loadingCard\">เปิดข้อมูลไม่สำเร็จ<br><span class=\"startupHint\">กรุณา rebuild หน้าเว็บหรือตรวจ JavaScript error</span></div>';
    if(mini) mini.textContent='เกิดข้อผิดพลาดขณะเปิดข้อมูล';
    if(fresh) fresh.textContent='ข้อมูลเปิดไม่สำเร็จ';
  }catch(_err){}
});
document.documentElement.dataset.promoConsumerVersion='1.8';
const payloadNode=document.getElementById('payloadData');
const D=JSON.parse(payloadNode.textContent);
payloadNode.remove();
const M=D.manifest||{}, O=D.offers||[], P=D.places||[], IDX=D.index||{}, DS=D.display_stats||{}, GEO=D.geo_meta||{regions:[],provinces:[],region_by_province:{},aliases:{}};
const $=id=>document.getElementById(id); const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); const val=(o,k)=>o&&o[k]!=null?o[k]:null;
const fmt=n=>Number(n||0).toLocaleString('th-TH'); const money=n=>n==null?'':Number(n).toLocaleString('th-TH',{style:'currency',currency:'THB',minimumFractionDigits:Number(n)%1?2:0,maximumFractionDigits:2});
const pricing=o=>o.pricing||{}, verify=o=>o.verification||{}, app=o=>o.applicability||{}, geo=o=>o.geography||{}, source=o=>o.source||{}, evidence=o=>o.evidence||{}, disp=o=>o._consumer_display||{};
const displayTitle=o=>disp(o).title||'รายละเอียดโปรโมชั่น'; const displayDesc=o=>disp(o).description||''; const displayConditions=o=>disp(o).conditions||[];
const savedKey='promo_consumer_saved_v1'; let saved=new Set(); try{saved=new Set(JSON.parse(localStorage.getItem(savedKey)||'[]'))}catch(_e){saved=new Set()} const savePersist=()=>{try{localStorage.setItem(savedKey,JSON.stringify([...saved]))}catch(_e){}};
const state={quick:'all',sub:'all',limit:60,placeLimit:80};
function dateText(s){if(!s)return '-'; try{return new Intl.DateTimeFormat('th-TH',{year:'numeric',month:'short',day:'numeric'}).format(new Date(s+'T00:00:00'))}catch{return s}}
function observed(o){return source(o).observed_at||''}
function priceDisplay(o){const p=pricing(o), pf=(evidence(o).price_fields||{}), pv=p.verification_state||verify(o).price_verification_state||'unknown'; const promoSupported=p.promo_price!=null && pv!=='rejected' && ((pf.promo_price||{}).supported===true); const regularSupported=p.regular_price!=null && promoSupported && ((pf.regular_price||{}).supported===true); return {promo:promoSupported?p.promo_price:null,regular:regularSupported?p.regular_price:null,discount:regularSupported&&p.discount_percent!=null?p.discount_percent:null,state:pv,anomalies:p.anomalies||[]}}
function offerText(o){const fields=[val(o.merchant,'name'),displayTitle(o),displayDesc(o),o.offer_type,displayConditions(o).join(' '),app(o).scope,app(o).channel,source(o).source_id]; for(const g of geo(o).locations||[])fields.push(g.province,g.province_raw,g.district,g.subdistrict,g.branch_name,g.address,g.postal_code); return fields.filter(Boolean).join(' ').toLowerCase()}
function placeText(p){const l=p.location||{},b=p.branch||{};return [val(p.merchant,'name'),b.name,l.province,l.district,l.subdistrict,l.address,l.postal_code,(p.search_terms||[]).join(' ')].filter(Boolean).join(' ').toLowerCase()}
const placeById=new Map(P.map(p=>[p.place_id,p]));
const areaMeta=o=>o._consumer_area||{};
function localProvinceSetForOffer(o){return new Set(areaMeta(o).local_provinces||[])}
function localRegionSetForOffer(o){return new Set(areaMeta(o).local_regions||[])}
function selectedAreaClass(o){
  const pv=$('province').value,rid=$('region').value,a=areaMeta(o);
  if(!pv&&!rid)return 'all';
  if(pv&&localProvinceSetForOffer(o).has(pv))return 'local';
  if(!pv&&rid&&localRegionSetForOffer(o).has(rid))return 'local';
  if(a.nationwide===true)return 'nationwide';
  if(a.online===true)return 'online';
  return 'other';
}
function areaOk(o){const c=selectedAreaClass(o);return c==='all'||c==='local'||c==='nationwide'}
function statusLocation(o){const a=app(o), gs=geo(o).locations||[]; if(a.channel==='online')return 'ออนไลน์'; if(a.scope==='nationwide')return 'ทั่วประเทศ'; if(gs.length){const g=gs[0];return [g.branch_name,g.district,g.province_raw||g.province].filter(Boolean).join(' · ')||'มีข้อมูลพื้นที่'} return 'ยังไม่ระบุพื้นที่'}
function merchantOptions(){return [...new Set(O.map(o=>val(o.merchant,'name')).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'th'))} function placeMerchantOptions(){return [...new Set(P.map(p=>val(p.merchant,'name')).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'th'))}
function normProvince(x){return String(x||'').trim().toLowerCase().replace(/\s+province$/,'').replace(/\s+/g,' ')}
function canonicalProvince(x){const n=normProvince(x);return GEO.aliases?.[n]||String(x||'').trim()}
function provinces(){return (GEO.provinces||[]).slice()}
function regionIdForProvince(x){return GEO.region_by_province?.[canonicalProvince(x)]||''}
function fill(id,arr){const el=$(id),existing=new Set([...el.options].map(o=>o.value));for(const x of arr){const v=String(x);if(existing.has(v))continue;el.insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(v)}</option>`);existing.add(v)}}
function fillRegions(){const el=$('region'),existing=new Set([...el.options].map(o=>o.value));for(const r of GEO.regions||[]){if(existing.has(r.id))continue;el.insertAdjacentHTML('beforeend',`<option value="${esc(r.id)}">${esc(r.label)}</option>`);existing.add(r.id)}}
function refreshProvinceOptions(){const el=$('province'),rid=$('region').value,old=el.value;const reg=(GEO.regions||[]).find(r=>r.id===rid);const rows=reg?reg.provinces:(GEO.provinces||[]);el.innerHTML='<option value="">ทุกจังหวัด</option>'+rows.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');if(rows.includes(old))el.value=old;else el.value=''}
fill('merchant',merchantOptions());fill('placeMerchant',placeMerchantOptions());fill('type',[...new Set(O.map(o=>o.offer_type).filter(Boolean))].sort());fillRegions();refreshProvinceOptions();fill('placeProvince',provinces());
function quickOk(o){const v=verify(o),a=app(o),p=priceDisplay(o); if(state.quick==='active')return v.expiry_state==='active'; if(state.quick==='discount30')return p.discount!=null&&p.discount>=30; if(state.quick==='online')return a.channel==='online'; if(state.quick==='nationwide')return a.scope==='nationwide'; if(state.quick==='verifiedprice')return p.state==='verified'&&p.promo!=null; if(state.quick==='expiring'){const end=val(o.validity,'end');if(!end)return false;const d=(new Date(end+'T00:00:00')-new Date())/86400000;return d>=0&&d<=7} return true}
function subOk(o){const p=priceDisplay(o);if(state.sub==='priceok')return p.promo!=null;if(state.sub==='noregular')return p.promo!=null&&p.regular==null;if(state.sub==='directplace')return (o.place_refs||[]).length>0;if(state.sub==='saved')return saved.has(o.offer_id);return true}
function offerOkNonArea(o){const q=$('mainSearch').value.trim().toLowerCase();if(q&&!offerText(o).includes(q))return false;if($('merchant').value&&val(o.merchant,'name')!==$('merchant').value)return false;if($('type').value&&o.offer_type!==$('type').value)return false;if($('channel').value&&app(o).channel!==$('channel').value)return false;return quickOk(o)&&subOk(o)}
function offerOk(o){return offerOkNonArea(o)&&areaOk(o)}
function areaBreakdown(){
  const pv=$('province').value,rid=$('region').value,box=$('areaBreakdown');
  if(!pv&&!rid){box.classList.remove('show');box.textContent='';return}
  const base=O.filter(offerOkNonArea);let local=0,nationwide=0,online=0;
  for(const o of base){const c=selectedAreaClass(o);if(c==='local')local++;else if(c==='nationwide')nationwide++;else if(c==='online')online++}
  const label=pv||((GEO.regions||[]).find(r=>r.id===rid)?.label||'พื้นที่ที่เลือก');
  box.innerHTML=`<b>${esc(label)}</b> · ยืนยันในพื้นที่ ${fmt(local)} · ทั่วประเทศ ${fmt(nationwide)} · ออนไลน์ ${fmt(online)} <span style="opacity:.75">(ออนไลน์ไม่ถูกนับเป็นโปรของจังหวัดโดยอัตโนมัติ)</span>`;
  box.classList.add('show');
}
function offerSort(a,b){const s=$('sort').value;if(s==='discount')return (priceDisplay(b).discount??-1)-(priceDisplay(a).discount??-1);if(s==='price')return (priceDisplay(a).promo??1e99)-(priceDisplay(b).promo??1e99);if(s==='expiry')return String(val(a.validity,'end')||'9999').localeCompare(String(val(b.validity,'end')||'9999'));if(s==='merchant')return String(val(a.merchant,'name')||'').localeCompare(String(val(b.merchant,'name')||''),'th');return String(observed(b)).localeCompare(String(observed(a)))}
function typeLabel(t){return ({price_discount:'ลดราคา',special_price:'ราคาพิเศษ',coupon:'คูปอง',bundle:'ซื้อเป็นชุด',buy_x_get_y:'ซื้อ X แถม Y'}[t]||t||'โปรโมชั่น')}
function priceHtml(o){const p=priceDisplay(o);if(p.promo==null)return `<div class="pricebox"><span class="pill">${esc(typeLabel(o.offer_type))}</span></div><div class="priceNote">ไม่มีราคาโปรที่ยืนยันสำหรับรายการนี้</div>`;return `<div class="pricebox"><span class="promo">${money(p.promo)}</span>${p.regular!=null?`<span class="regular">${money(p.regular)}</span>`:''}${p.discount!=null?`<span class="discount">-${Number(p.discount).toFixed(0)}%</span>`:''}</div>${p.regular==null&&o.offer_type==='special_price'?'<div class="priceNote">แสดงเฉพาะราคาโปรที่มีหลักฐาน · ไม่คำนวณส่วนลดเมื่อราคาปกติยังไม่ยืนยัน</div>':''}`}
function card(o){const p=priceDisplay(o),v=verify(o),a=app(o),d=disp(o), fav=saved.has(o.offer_id);return `<article class="card"><button class="fav ${fav?'on':''}" data-save="${esc(o.offer_id)}" title="บันทึก">★</button><div class="topline"><span class="merchant">${esc(val(o.merchant,'name')||'-')}</span><span class="pill">${esc(typeLabel(o.offer_type))}</span></div><div class="title">${esc(displayTitle(o))}</div><div class="desc">${esc(displayDesc(o))}</div>${priceHtml(o)}<div class="meta">📅 ${dateText(val(o.validity,'start'))} – ${dateText(val(o.validity,'end'))}<br>📍 ${esc(statusLocation(o))} · ${esc(a.channel||'unknown')}</div><div class="badges"><span class="badge ${v.verification_state==='verified'?'good':'warn'}">${esc(v.verification_state||'unknown')}</span><span class="badge ${p.state==='verified'?'good':p.state==='partial'?'warn':''}">ราคา: ${esc(p.state)}</span>${d.title_fallback?'<span class="badge info">ชื่อแสดงผลปรับให้อ่านง่าย</span>':''}${d.technical_payload_hidden?'<span class="badge info">ซ่อนข้อมูลเทคนิค</span>':''}${(p.anomalies||[]).length?`<span class="badge warn">ตรวจราคา ${p.anomalies.length} จุด</span>`:''}${a.scope==='nationwide'?'<span class="badge info">ทั่วประเทศ</span>':''}</div><div class="actions"><button class="primary" data-detail="${esc(o.offer_id)}">ดูรายละเอียด</button>${source(o).url?`<a href="${esc(source(o).url)}" target="_blank" rel="noopener">เปิดแหล่งข้อมูล</a>`:''}</div></article>`}
function renderOffers(){let a=O.filter(offerOk).sort(offerSort), s=a.slice(0,state.limit);areaBreakdown();$('filterResultMini').textContent=`พบ ${fmt(a.length)} โปร`;$('offerCount').textContent=`พบ ${fmt(a.length)} โปรโมชั่นตามตัวกรอง`;$('offerHint').textContent=a.length?`กำลังแสดง ${fmt(s.length)} จาก ${fmt(a.length)} รายการ`:'';$('offerCards').innerHTML=s.length?s.map(card).join(''):'<div class="empty">ไม่พบโปรโมชั่นที่ยืนยันว่าใช้ได้ในพื้นที่นี้ หรือเป็นโปรทั่วประเทศตามเงื่อนไขปัจจุบัน</div>';$('offerMore').style.display=a.length>s.length?'block':'none'}
function placeOk(p){const q=$('placeSearch').value.trim().toLowerCase();if(q&&!placeText(p).includes(q))return false;if($('placeMerchant').value&&val(p.merchant,'name')!==$('placeMerchant').value)return false;if($('placeKind').value&&p.record_kind!==$('placeKind').value)return false;const l=p.location||{};if($('placeProvince').value&&l.province!==$('placeProvince').value)return false;return true}
function placeCard(p){const l=p.location||{},b=p.branch||{},v=p.verification||{};return `<article class="placeCard"><div class="topline"><span class="merchant">${esc(val(p.merchant,'name')||'-')}</span><span class="pill">${esc(p.record_kind||'-')}</span></div><h3>${esc(b.name||val(p.merchant,'name')||'สถานที่')}</h3><p>📍 ${esc([l.subdistrict,l.district,l.province].filter(Boolean).join(' · ')||'ยังไม่มีรายละเอียดพื้นที่')}<br>${l.address?`🏠 ${esc(l.address)}<br>`:''}ความละเอียด: ${esc(p.precision||'unknown')} · หลักฐาน: ${fmt(p.evidence_count??(p.evidence||[]).length)}</p><div class="badges"><span class="badge ${v.state==='verified'?'good':'warn'}">${esc(v.state||'unknown')}</span>${l.postal_code?'<span class="badge info">รหัสไปรษณีย์</span>':''}${l.latitude!=null&&l.longitude!=null?'<span class="badge good">พิกัด</span>':''}</div></article>`}
function renderPlaces(){let a=P.filter(placeOk),s=a.slice(0,state.placeLimit);$('placeCount').textContent=`พบ ${fmt(a.length)} สถานที่`;$('placeHint').textContent=a.length>s.length?`แสดง ${fmt(s.length)} รายการแรก`:'';$('placeCards').innerHTML=s.length?s.map(placeCard).join(''):'<div class="empty">ไม่พบสถานที่</div>';$('placeMore').style.display=a.length>s.length?'block':'none'}
function renderSaved(){const a=O.filter(o=>saved.has(o.offer_id));$('savedCards').innerHTML=a.length?a.map(card).join(''):'<div class="empty">ยังไม่มีโปรที่บันทึกไว้</div>'}
function renderStats(){const priceVerified=O.filter(o=>priceDisplay(o).state==='verified'&&priceDisplay(o).promo!=null).length, branches=P.filter(p=>p.record_kind==='branch').length;$('stats').innerHTML=[[O.length,'โปรโมชั่นที่เผยแพร่'],[priceVerified,'โปรที่ราคายืนยัน'],[P.length,'สถานที่ทั้งหมด'],[branches,'สาขาที่พบ']].map(([n,l])=>`<div class="stat"><b>${fmt(n)}</b><span>${l}</span></div>`).join('')}
function renderSystem(){const kv=[['Publication ID',M.publication_id],['อัปเดตล่าสุด',M.published_at],['Published offers',M.offer_count],['Published places',M.place_count],['Physical branches',M.branch_place_count],['ปรับชื่อให้อ่านง่าย',DS.title_fallback_offers||0],['ซ่อน payload เทคนิค',DS.technical_payload_hidden_offers||0],['Offer contract',M.offer_contract],['Place contract',M.place_contract],['Read-only',val(M.policy,'read_only')]];$('systemKv').innerHTML=kv.map(([k,v])=>`<div>${esc(k)}</div><div><b>${esc(v??'-')}</b></div>`).join('');$('freshText').textContent=M.published_at?`ข้อมูลล่าสุด ${new Date(M.published_at).toLocaleString('th-TH')}`:'ข้อมูล Published';$('pubText').textContent=M.publication_id||''}
function detail(o){const p=priceDisplay(o),pf=evidence(o).price_fields||{},a=app(o),v=verify(o),g=geo(o).locations||[],d=disp(o);const regularEvidence=(pf.regular_price||{}).evidence_excerpt,promoEvidence=(pf.promo_price||{}).evidence_excerpt;return `<h3>${esc(displayTitle(o))}</h3><div class="topline"><span class="merchant">${esc(val(o.merchant,'name')||'-')}</span><span class="pill">${esc(typeLabel(o.offer_type))}</span></div>${priceHtml(o)}<div class="detailGrid"><div>Offer ID</div><div>${esc(o.offer_id||'-')}</div><div>ช่วงเวลา</div><div>${dateText(val(o.validity,'start'))} – ${dateText(val(o.validity,'end'))}</div><div>พื้นที่ใช้สิทธิ์</div><div>${esc(a.scope||'unknown')} / ${esc(a.channel||'unknown')}</div><div>สถานที่อ้างอิงตรง</div><div>${esc((o.place_refs||[]).join(', ')||'-')}</div><div>สถานะข้อมูล</div><div>${esc(v.verification_state||'-')}</div><div>สถานะราคา</div><div>${esc(p.state)}</div><div>เงื่อนไข</div><div>${esc(displayConditions(o).join(' · ')||'-')}</div></div>${p.anomalies.length?`<div class="warning">Price integrity flag: ${esc(p.anomalies.join(' · '))}</div>`:'<div class="safe">ข้อมูลราคาที่แสดงผ่าน Price Evidence Integrity Gate ของ snapshot นี้</div>'}<h4>หลักฐานราคาโปร</h4><div class="evidence">${esc(promoEvidence||'ไม่มีหลักฐานราคาโปรแบบ field-level')}</div><h4>หลักฐานราคาปกติ</h4><div class="evidence">${esc(regularEvidence||'ไม่แสดงราคาปกติเมื่อไม่มีหลักฐานที่ยืนยัน')}</div><h4>หลักฐานต้นทาง</h4>${d.technical_payload_hidden?'<div class="warning">ซ่อน raw technical payload จากหน้าผู้ใช้เพื่อให้อ่านง่าย โดยข้อมูลต้นฉบับยังคงอยู่ใน Published/Source evidence</div>':''}<div class="evidence">${esc(d.evidence_text||'ดูแหล่งข้อมูลต้นทางเพื่อยืนยันรายละเอียดเพิ่มเติม')}</div>${source(o).url?`<div class="actions"><a class="primary" href="${esc(source(o).url)}" target="_blank" rel="noopener">เปิดต้นทาง</a><button data-share="${esc(o.offer_id)}">แชร์รายการนี้</button></div>`:''}`}
function openDetail(id){const o=O.find(x=>x.offer_id===id);if(!o)return;$('drawerBody').innerHTML=detail(o);$('drawerBackdrop').classList.add('show')}
function shareOffer(id){const o=O.find(x=>x.offer_id===id);if(!o)return;const p=priceDisplay(o);const text=`${displayTitle(o)} · ${val(o.merchant,'name')||''}${p.promo!=null?' · '+money(p.promo):''} · ${statusLocation(o)}`;if(navigator.share)navigator.share({title:'Promo Finder',text,url:source(o).url||location.href}).catch(()=>{});else navigator.clipboard?.writeText(text+' '+(source(o).url||''))}
function toggleSave(id){if(saved.has(id))saved.delete(id);else saved.add(id);savePersist();renderOffers();renderSaved()}
function switchPanel(name){document.querySelectorAll('.tabPanel').forEach(x=>x.classList.toggle('active',x.id===name+'Panel'));document.querySelectorAll('.navbtn').forEach(x=>x.classList.toggle('active',x.dataset.panel===name));if(name==='saved')renderSaved();if(name==='places')renderPlaces()}
function interactionNote(text){const n=$('interactionStatus');if(n)n.textContent=text}
function syncClearButton(){const b=$('clearSearch');if(b)b.classList.toggle('show',Boolean($('mainSearch').value.trim()))}
function bindInteractions(){
  $('clearSearch').addEventListener('click',()=>{$('mainSearch').value='';syncClearButton();state.limit=60;renderOffers();interactionNote('ล้างคำค้นแล้ว')});
  $('mainSearch').addEventListener('input',()=>{syncClearButton();state.limit=60;renderOffers()});
  ['merchant','type','channel','province','sort'].forEach(id=>{const el=$(id);el.addEventListener('change',()=>{state.limit=60;renderOffers();interactionNote('เลือก '+(el.options?.[el.selectedIndex]?.text||'ตัวกรอง')+' แล้ว')});});
  $('region').addEventListener('change',()=>{refreshProvinceOptions();state.limit=60;renderOffers();interactionNote('เลือก '+($('region').options[$('region').selectedIndex]?.text||'ภูมิภาค')+' แล้ว')});
  $('advancedToggle').addEventListener('click',()=>{const box=$('advancedFilters'),show=!box.classList.contains('show');box.classList.toggle('show',show);$('advancedToggle').textContent=show?'ซ่อนตัวกรอง ▴':'ตัวกรองเพิ่ม ▾';});
  $('quickTop').addEventListener('click',e=>{const b=e.target.closest('[data-q]');if(!b)return;state.quick=b.dataset.q;state.limit=60;document.querySelectorAll('#quickTop button').forEach(x=>x.classList.toggle('active',x===b));renderOffers();interactionNote('เลือก '+b.textContent.trim()+' แล้ว')});
  $('subfilters').addEventListener('click',e=>{const b=e.target.closest('[data-f]');if(!b)return;state.sub=b.dataset.f;state.limit=60;document.querySelectorAll('#subfilters button').forEach(x=>x.classList.toggle('active',x===b));renderOffers();interactionNote('เลือก '+b.textContent.trim()+' แล้ว')});
  $('offerMore').addEventListener('click',()=>{state.limit+=60;renderOffers()});
  $('offerCards').addEventListener('click',e=>{const d=e.target.closest('[data-detail]'),sv=e.target.closest('[data-save]');if(d)openDetail(d.dataset.detail);if(sv)toggleSave(sv.dataset.save)});
  $('savedCards').addEventListener('click',e=>{const d=e.target.closest('[data-detail]'),sv=e.target.closest('[data-save]');if(d)openDetail(d.dataset.detail);if(sv)toggleSave(sv.dataset.save)});
  $('drawerBackdrop').addEventListener('click',e=>{if(e.target===$('drawerBackdrop'))$('drawerBackdrop').classList.remove('show')});
  $('drawerClose').addEventListener('click',()=>$('drawerBackdrop').classList.remove('show'));
  $('drawerBody').addEventListener('click',e=>{const b=e.target.closest('[data-share]');if(b)shareOffer(b.dataset.share)});
  ['placeSearch','placeMerchant','placeProvince','placeKind'].forEach(id=>$(id).addEventListener(id==='placeSearch'?'input':'change',()=>{state.placeLimit=80;renderPlaces()}));
  $('placeMore').addEventListener('click',()=>{state.placeLimit+=80;renderPlaces()});
  document.querySelectorAll('.navbtn').forEach(b=>b.addEventListener('click',()=>switchPanel(b.dataset.panel)));
  // A capture listener documents taps and also helps diagnose Android WebView/Chrome hit-target issues.
  document.addEventListener('pointerup',e=>{const t=e.target.closest('button,select,a');if(t&&t.tagName!=='SELECT')t.blur?.()},{passive:true});
}
bindInteractions();
syncClearButton();renderStats();renderSystem();renderOffers();renderPlaces();renderSaved();
</script>
</body></html>'''


def _option(value: str, label: str | None = None) -> str:
    value = str(value)
    label = value if label is None else str(label)
    return f'<option value="{html.escape(value, quote=True)}">{html.escape(label)}</option>'


def _region_options_html() -> str:
    return ''.join(_option(rid, label) for rid, (label, _rows) in REGION_PROVINCES.items())


def _province_options_html(grouped: bool = True) -> str:
    if not grouped:
        return ''.join(_option(p) for _rid, (_label, rows) in REGION_PROVINCES.items() for p in rows)
    chunks = []
    for _rid, (label, rows) in REGION_PROVINCES.items():
        chunks.append(f'<optgroup label="{html.escape(label, quote=True)}">')
        chunks.extend(_option(p) for p in rows)
        chunks.append('</optgroup>')
    return ''.join(chunks)


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({str(v).strip() for v in values if str(v or '').strip()}, key=lambda x: x.casefold())


def _render_html(manifest: dict, offers: list[dict], places: list[dict], index: dict) -> str:
    consumer_offers, display_stats = prepare_consumer_offers(offers)
    consumer_places = prepare_consumer_places(places)
    consumer_offers = attach_consumer_area_semantics(consumer_offers, consumer_places)
    branches = sum(p.get("record_kind") == "branch" for p in places)
    payload = payload_json_text({"manifest": manifest, "offers": consumer_offers, "places": consumer_places, "index": index, "display_stats": display_stats, "geo_meta": geo_meta()})
    merchants = _unique_sorted([(o.get('merchant') or {}).get('name') for o in offers])
    offer_types = _unique_sorted([o.get('offer_type') for o in offers])
    place_merchants = _unique_sorted([(p.get('merchant') or {}).get('name') for p in places])
    return (HTML.replace("__PAYLOAD_JSON__", payload)
                .replace("__SUMMARY_LABEL__", html.escape(f"{len(offers):,} โปร · {branches:,} สาขา"))
                .replace("__PUB_LABEL__", html.escape(str(manifest.get("publication_id") or "")))
                .replace("__REGION_OPTIONS__", _region_options_html())
                .replace("__PROVINCE_OPTIONS__", _province_options_html(grouped=True))
                .replace("__MERCHANT_OPTIONS__", ''.join(_option(x) for x in merchants))
                .replace("__TYPE_OPTIONS__", ''.join(_option(x) for x in offer_types))
                .replace("__PLACE_MERCHANT_OPTIONS__", ''.join(_option(x) for x in place_merchants))
                .replace("__PLACE_PROVINCE_OPTIONS__", _province_options_html(grouped=True)))


def build_html(manifest: dict, offers: list[dict], places: list[dict], index: dict) -> str:
    return _render_html(manifest, offers, places, index)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build standalone consumer-facing Promo Finder from Promo Intelligence Published Read Model")
    ap.add_argument("--published-dir", type=Path, default=DEFAULT_PUBLISHED)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    pd = args.published_dir if args.published_dir.is_absolute() else ROOT / args.published_dir
    out = args.output if args.output.is_absolute() else ROOT / args.output
    manifest = load_json(pd / "manifest.json")
    offers = load_jsonl(pd / "promo_offer_v1.jsonl")
    places = load_jsonl(pd / "promo_place_v1.jsonl")
    index = load_json(pd / "merchant_branch_index_v1.json")
    if int(manifest.get("offer_count", -1)) != len(offers):
        raise SystemExit(f"MANIFEST_OFFER_COUNT_MISMATCH manifest={manifest.get('offer_count')} actual={len(offers)}")
    if int(manifest.get("place_count", -1)) != len(places):
        raise SystemExit(f"MANIFEST_PLACE_COUNT_MISMATCH manifest={manifest.get('place_count')} actual={len(places)}")
    # Consumer safety gate: never embed rejected price-only offers.
    bad = [o.get("offer_id") for o in offers if (o.get("verification") or {}).get("verification_state") == "rejected"]
    if bad:
        raise SystemExit(f"PUBLISHED_REJECTED_OFFERS_PRESENT count={len(bad)}")
    consumer_offers, display_stats = prepare_consumer_offers(offers)
    # Reuse the fast JSON-in-script renderer; avoids large Base64 decode on Android.
    out.write_text(_render_html(manifest, offers, places, index), encoding="utf-8")
    verified_price = sum((o.get("pricing") or {}).get("verification_state") == "verified" and (o.get("pricing") or {}).get("promo_price") is not None for o in offers)
    print("PROMO_CONSUMER_BUILD=PASS")
    print("PROMO_CONSUMER_VERSION=1.8")
    print(f"PUBLICATION_ID={manifest.get('publication_id','-')}")
    print(f"OFFERS_EMBEDDED={len(offers)}")
    print(f"PLACES_EMBEDDED={len(places)}")
    print(f"BRANCHES_EMBEDDED={sum(p.get('record_kind') == 'branch' for p in places)}")
    print(f"VERIFIED_PRICE_OFFERS={verified_price}")
    print(f"DISPLAY_TITLE_FALLBACKS={display_stats['title_fallback_offers']}")
    print(f"TECHNICAL_PAYLOADS_HIDDEN={display_stats['technical_payload_hidden_offers']}")
    print(f"CONSUMER_HTML_BYTES={out.stat().st_size}")
    print("CONSUMER_MODE=STANDALONE_READ_ONLY_PUBLISHED_SNAPSHOT")
    print(f"OUTPUT={out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
