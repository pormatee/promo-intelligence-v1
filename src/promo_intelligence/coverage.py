from __future__ import annotations

THAI_PROVINCES = (
    "Amnat Charoen", "Ang Thong", "Bangkok", "Bueng Kan", "Buriram",
    "Chachoengsao", "Chai Nat", "Chaiyaphum", "Chanthaburi", "Chiang Mai",
    "Chiang Rai", "Chonburi", "Chumphon", "Kalasin", "Kamphaeng Phet",
    "Kanchanaburi", "Khon Kaen", "Krabi", "Lampang", "Lamphun", "Loei",
    "Lopburi", "Mae Hong Son", "Maha Sarakham", "Mukdahan", "Nakhon Nayok",
    "Nakhon Pathom", "Nakhon Phanom", "Nakhon Ratchasima", "Nakhon Sawan",
    "Nakhon Si Thammarat", "Nan", "Narathiwat", "Nong Bua Lamphu", "Nong Khai",
    "Nonthaburi", "Pathum Thani", "Pattani", "Phang Nga", "Phatthalung", "Phayao",
    "Phetchabun", "Phetchaburi", "Phichit", "Phitsanulok", "Phra Nakhon Si Ayutthaya",
    "Phrae", "Phuket", "Prachinburi", "Prachuap Khiri Khan", "Ranong", "Ratchaburi",
    "Rayong", "Roi Et", "Sa Kaeo", "Sakon Nakhon", "Samut Prakan", "Samut Sakhon",
    "Samut Songkhram", "Saraburi", "Satun", "Sing Buri", "Sisaket", "Songkhla",
    "Sukhothai", "Suphan Buri", "Surat Thani", "Surin", "Tak", "Trang", "Trat",
    "Ubon Ratchathani", "Udon Thani", "Uthai Thani", "Uttaradit", "Yala", "Yasothon",
)


def _eligible(offer: dict) -> bool:
    v = offer.get("verification") or {}
    return (
        v.get("verification_state") in {"verified", "partial"}
        and v.get("freshness_state") == "fresh"
        and v.get("expiry_state") == "active"
    )


def coverage_summary(offers: list[dict]) -> dict:
    reached: set[str] = set()
    nationwide = 0
    explicit_geo = 0
    unknown_geo = 0

    for offer in offers:
        a = offer.get("applicability") or {}
        scope = a.get("scope", "unknown")
        if scope == "unknown":
            unknown_geo += 1
            continue
        explicit_geo += 1
        if not _eligible(offer):
            continue
        if scope == "nationwide":
            nationwide += 1
            reached.update(THAI_PROVINCES)
        else:
            reached.update(p for p in (a.get("provinces") or []) if p in THAI_PROVINCES)

    target = len(THAI_PROVINCES)
    return {
        "target_provinces": target,
        "reached_provinces": len(reached),
        "provinces": sorted(reached),
        "nationwide_active_offers": nationwide,
        "explicit_geo_offers": explicit_geo,
        "unknown_geo_offers": unknown_geo,
        "national_geographic_reach": len(reached) == target,
        # Geographic reach is not the same as complete market/source coverage.
        "market_coverage_complete": False,
    }
