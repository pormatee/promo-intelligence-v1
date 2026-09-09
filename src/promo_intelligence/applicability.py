from __future__ import annotations
import re

SCOPES = {"nationwide", "selected_branches", "branch_specific", "unknown"}
CHANNELS = {"online", "store", "omnichannel", "unknown"}

# Canonical English province names are kept compatible with coverage.THAIL_PROVINCES.
THAI_PROVINCE_MAP = {
    "อำนาจเจริญ":"Amnat Charoen", "อ่างทอง":"Ang Thong", "กรุงเทพมหานคร":"Bangkok", "กรุงเทพฯ":"Bangkok",
    "บึงกาฬ":"Bueng Kan", "บุรีรัมย์":"Buriram", "ฉะเชิงเทรา":"Chachoengsao", "ชัยนาท":"Chai Nat",
    "ชัยภูมิ":"Chaiyaphum", "จันทบุรี":"Chanthaburi", "เชียงใหม่":"Chiang Mai", "เชียงราย":"Chiang Rai",
    "ชลบุรี":"Chonburi", "ชุมพร":"Chumphon", "กาฬสินธุ์":"Kalasin", "กำแพงเพชร":"Kamphaeng Phet",
    "กาญจนบุรี":"Kanchanaburi", "ขอนแก่น":"Khon Kaen", "กระบี่":"Krabi", "ลำปาง":"Lampang",
    "ลำพูน":"Lamphun", "เลย":"Loei", "ลพบุรี":"Lopburi", "แม่ฮ่องสอน":"Mae Hong Son",
    "มหาสารคาม":"Maha Sarakham", "มุกดาหาร":"Mukdahan", "นครนายก":"Nakhon Nayok", "นครปฐม":"Nakhon Pathom",
    "นครพนม":"Nakhon Phanom", "นครราชสีมา":"Nakhon Ratchasima", "นครสวรรค์":"Nakhon Sawan",
    "นครศรีธรรมราช":"Nakhon Si Thammarat", "น่าน":"Nan", "นราธิวาส":"Narathiwat", "หนองบัวลำภู":"Nong Bua Lamphu",
    "หนองคาย":"Nong Khai", "นนทบุรี":"Nonthaburi", "ปทุมธานี":"Pathum Thani", "ปัตตานี":"Pattani",
    "พังงา":"Phang Nga", "พัทลุง":"Phatthalung", "พะเยา":"Phayao", "เพชรบูรณ์":"Phetchabun",
    "เพชรบุรี":"Phetchaburi", "พิจิตร":"Phichit", "พิษณุโลก":"Phitsanulok", "พระนครศรีอยุธยา":"Phra Nakhon Si Ayutthaya",
    "แพร่":"Phrae", "ภูเก็ต":"Phuket", "ปราจีนบุรี":"Prachinburi", "ประจวบคีรีขันธ์":"Prachuap Khiri Khan",
    "ระนอง":"Ranong", "ราชบุรี":"Ratchaburi", "ระยอง":"Rayong", "ร้อยเอ็ด":"Roi Et", "สระแก้ว":"Sa Kaeo",
    "สกลนคร":"Sakon Nakhon", "สมุทรปราการ":"Samut Prakan", "สมุทรสาคร":"Samut Sakhon", "สมุทรสงคราม":"Samut Songkhram",
    "สระบุรี":"Saraburi", "สตูล":"Satun", "สิงห์บุรี":"Sing Buri", "ศรีสะเกษ":"Sisaket", "สงขลา":"Songkhla",
    "สุโขทัย":"Sukhothai", "สุพรรณบุรี":"Suphan Buri", "สุราษฎร์ธานี":"Surat Thani", "สุรินทร์":"Surin",
    "ตาก":"Tak", "ตรัง":"Trang", "ตราด":"Trat", "อุบลราชธานี":"Ubon Ratchathani", "อุดรธานี":"Udon Thani",
    "อุทัยธานี":"Uthai Thani", "อุตรดิตถ์":"Uttaradit", "ยะลา":"Yala", "ยโสธร":"Yasothon",
}


def _channel_from_text(text: str, source: dict) -> tuple[str, str]:
    low = text.lower()
    if re.search(r"(?:เฉพาะ(?:ช่องทาง)?ออนไลน์|ออนไลน์เท่านั้น|online\s+only)", low, re.I):
        return "online", "offer_text"
    if re.search(r"(?:เฉพาะหน้าร้าน|in[- ]store\s+only)", low, re.I):
        return "store", "offer_text"
    configured = source.get("channel", "unknown")
    if configured in CHANNELS:
        return configured, "source_config" if configured != "unknown" else "none"
    return "unknown", "none"


def _explicit_provinces(text: str) -> list[str]:
    found: list[str] = []
    for thai, canonical in THAI_PROVINCE_MAP.items():
        # Require a geographic marker so product/brand text cannot accidentally
        # turn a province name into geographic applicability.
        pat = rf"(?:จังหวัด|จ\.|ในจังหวัด|เฉพาะจังหวัด)\s*{re.escape(thai)}"
        if re.search(pat, text, re.I) and canonical not in found:
            found.append(canonical)
    return found


def _explicit_branches(text: str) -> list[str]:
    branches: list[str] = []
    # Stop before address/geography markers so "เฉพาะสาขา X ที่อยู่ ..."
    # does not turn the whole postal address into the branch name.
    pat = (r"เฉพาะสาขา\s*([^|;]{2,80}?)(?=\s*(?:ที่อยู่|address|ตำบล|ต\.|อำเภอ|อ\.|"
           r"จังหวัด|จ\.|แขวง|เขต|รหัสไปรษณีย์|postal\s*code|[|;]|$))")
    for m in re.finditer(pat, text, re.I):
        name = re.sub(r"\s+", " ", m.group(1)).strip(" .,-–")
        # Avoid turning nationwide wording into a branch name.
        if name and not re.search(r"^(?:ทุกสาขา|ทั่วประเทศ)$", name, re.I):
            branches.append(name)
    return branches[:10]


def resolve_applicability(candidate: dict, source: dict) -> dict:
    """Resolve geographic/channel applicability using explicit evidence only.

    Geographic priority:
      1) explicit nationwide / province / branch text
      2) explicit source config
      3) unknown

    Sales channel is orthogonal to geography. An online offer can legitimately
    retain geographic scope=unknown; this is not silently promoted to nationwide.
    """
    text = " | ".join([
        candidate.get("evidence_excerpt", ""),
        " | ".join(candidate.get("conditions", []) or []),
    ]).strip()
    low = text.lower()
    channel, channel_basis = _channel_from_text(text, source)

    if re.search(r"(?:\b(?:all branches|nationwide)\b|ทั่วประเทศ|ทุกสาขา)", low, re.I):
        return {
            "scope": "nationwide", "country": "TH", "provinces": [], "branches": [],
            "verification_state": "explicit", "basis": "offer_text",
            "channel": channel, "channel_basis": channel_basis,
        }

    provinces = _explicit_provinces(text)
    branches = _explicit_branches(text)
    if branches:
        return {
            "scope": "branch_specific" if len(branches) == 1 else "selected_branches",
            "country": "TH", "provinces": provinces, "branches": branches,
            "verification_state": "explicit", "basis": "offer_text",
            "channel": channel, "channel_basis": channel_basis,
        }
    if provinces:
        return {
            "scope": "selected_branches", "country": "TH", "provinces": provinces, "branches": [],
            "verification_state": "explicit", "basis": "offer_text",
            "channel": channel, "channel_basis": channel_basis,
        }

    cfg = source.get("applicability") or {}
    scope = cfg.get("scope", "unknown")
    if scope not in SCOPES:
        scope = "unknown"
    provinces = list(cfg.get("provinces") or [])
    branches = list(cfg.get("branches") or [])
    verification_state = cfg.get("verification_state")
    if scope != "unknown" and verification_state == "explicit":
        return {
            "scope": scope, "country": cfg.get("country", "TH"), "provinces": provinces,
            "branches": branches, "verification_state": "explicit", "basis": "source_config",
            "channel": channel, "channel_basis": channel_basis,
        }

    return {
        "scope": "unknown", "country": "TH", "provinces": [], "branches": [],
        "verification_state": "unknown", "basis": "none",
        "channel": channel, "channel_basis": channel_basis,
    }
