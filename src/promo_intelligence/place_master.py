from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

from .area_linkage import link_offers_explicit_branches

PLACE_CONTRACT = "promo_place_v1"
VALID_RECORD_KINDS = {"merchant", "branch"}
VALID_PRECISIONS = {"merchant", "branch", "province", "district", "subdistrict", "address", "coordinates", "unknown"}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    value = value.casefold().strip()
    value = re.sub(r"[’'`\"]", "", value)
    value = re.sub(r"[^0-9a-zก-๙]+", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def _id(prefix: str, *parts: str | None) -> str:
    material = "|".join(_norm(x) for x in parts).encode("utf-8")
    return prefix + hashlib.sha256(material).hexdigest()[:20]


def _load_alias_config(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _aliases(canonical: str | None, configured: Iterable[str] = ()) -> list[str]:
    out: list[str] = []
    for value in [canonical, *configured]:
        if not value:
            continue
        value = re.sub(r"\s+", " ", str(value)).strip()
        if value and value not in out:
            out.append(value)
    return out


def _search_terms(*values: str | None) -> list[str]:
    out: list[str] = []
    for value in values:
        n = _norm(value)
        if n and n not in out:
            out.append(n)
    return out


def _precision(location: dict) -> str:
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


def _evidence_from_offer(offer: dict, basis: str, excerpt: str = "") -> dict:
    src = offer.get("source") or {}
    ev = offer.get("evidence") or {}
    return {
        "source_id": src.get("source_id"),
        "url": src.get("url"),
        "observed_at": src.get("observed_at"),
        "content_hash": ev.get("content_hash"),
        "basis": basis,
        "evidence_excerpt": (excerpt or ev.get("extracted_text") or "")[:500],
    }


def _evidence_key(row: dict) -> tuple:
    return (row.get("source_id"), row.get("url"), row.get("content_hash"), row.get("basis"), row.get("evidence_excerpt"))


def _merge_evidence(existing: list[dict], incoming: list[dict]) -> list[dict]:
    out = list(existing)
    seen = {_evidence_key(x) for x in out}
    for row in incoming:
        key = _evidence_key(row)
        if key not in seen:
            out.append(row)
            seen.add(key)
    return out


def _verification(evidence: list[dict], precision: str) -> dict:
    source_ids = {x.get("source_id") for x in evidence if x.get("source_id")}
    if precision in {"coordinates", "address", "subdistrict", "district"} and evidence:
        state = "verified" if len(source_ids) >= 1 else "partial"
    elif evidence:
        state = "partial"
    else:
        state = "unverified"
    return {
        "state": state,
        "source_count": len(source_ids),
        "evidence_count": len(evidence),
    }


def _merchant_record(name: str, aliases: list[str], offer: dict, now: str) -> dict:
    place_id = _id("place_", "merchant", name)
    evidence = [_evidence_from_offer(offer, "merchant_name")]
    return {
        "contract": PLACE_CONTRACT,
        "place_id": place_id,
        "record_kind": "merchant",
        "parent_place_id": None,
        "merchant": {"name": name, "aliases": aliases},
        "branch": {"name": None, "aliases": []},
        "location": {
            "country": "TH", "province": None, "district": None, "subdistrict": None,
            "address": None, "postal_code": None, "latitude": None, "longitude": None,
        },
        "precision": "merchant",
        "search_terms": _search_terms(name, *aliases),
        "verification": _verification(evidence, "merchant"),
        "evidence": evidence,
        "updated_at": now,
    }


def _branch_key(merchant_id: str, location: dict) -> tuple[str, str]:
    branch = location.get("branch_name")
    if branch:
        # Stable branch identity prefers merchant + explicit branch name. Better
        # geography may enrich this record later without changing its id.
        return merchant_id, _norm(branch)
    if location.get("address"):
        return merchant_id, "addr:" + _norm(location.get("address"))
    if location.get("latitude") is not None and location.get("longitude") is not None:
        return merchant_id, f"coord:{float(location['latitude']):.6f},{float(location['longitude']):.6f}"
    return merchant_id, ""


def _branch_record(merchant: str, merchant_id: str, merchant_aliases: list[str], location: dict,
                   branch_aliases: list[str], offer: dict, now: str) -> dict | None:
    key_merchant, key_location = _branch_key(merchant_id, location)
    # Province-only applicability is not a physical place. A physical branch
    # needs explicit branch name, postal address, or coordinates.
    if not key_location:
        return None
    branch_name = location.get("branch_name")
    place_id = _id("place_", "branch", key_merchant, key_location)
    precision = _precision(location)
    evidence = [_evidence_from_offer(offer, location.get("basis") or "geography", location.get("evidence_excerpt") or "")]
    return {
        "contract": PLACE_CONTRACT,
        "place_id": place_id,
        "record_kind": "branch",
        "parent_place_id": merchant_id,
        "merchant": {"name": merchant, "aliases": merchant_aliases},
        "branch": {"name": branch_name, "aliases": branch_aliases},
        "location": {
            "country": "TH",
            "province": location.get("province"),
            "district": location.get("district"),
            "subdistrict": location.get("subdistrict"),
            "address": location.get("address"),
            "postal_code": location.get("postal_code"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        },
        "precision": precision,
        "search_terms": _search_terms(merchant, *merchant_aliases, branch_name, *branch_aliases,
                                      location.get("province"), location.get("district"),
                                      location.get("subdistrict"), location.get("address"), location.get("postal_code")),
        "verification": _verification(evidence, precision),
        "evidence": evidence,
        "updated_at": now,
    }


def _merge_place(a: dict, b: dict) -> dict:
    out = deepcopy(a)
    out["merchant"]["aliases"] = _aliases(out["merchant"].get("name"), [*out["merchant"].get("aliases", []), *b["merchant"].get("aliases", [])])
    out["branch"]["aliases"] = _aliases(out["branch"].get("name"), [*out["branch"].get("aliases", []), *b["branch"].get("aliases", [])]) if out.get("record_kind") == "branch" else []
    # Fill missing location fields only; never overwrite conflicting explicit
    # facts. Conflicts remain visible in evidence for a later reconciliation step.
    for key, value in (b.get("location") or {}).items():
        if out["location"].get(key) is None and value is not None:
            out["location"][key] = value
    if out.get("record_kind") == "branch":
        out["precision"] = _precision({**out["location"], "branch_name": out["branch"].get("name")})
    out["search_terms"] = sorted(set(out.get("search_terms", [])) | set(b.get("search_terms", [])))
    out["evidence"] = _merge_evidence(out.get("evidence", []), b.get("evidence", []))
    out["verification"] = _verification(out["evidence"], out.get("precision", "unknown"))
    out["updated_at"] = max(out.get("updated_at") or "", b.get("updated_at") or "")
    return out



def make_locator_records(merchant: str, candidates: list[dict], *, source_id: str, url: str, observed_at: str,
                         content_hash: str, reliability: str = "high") -> list[dict]:
    """Create merchant/branch place records from an explicit official locator.

    Locator evidence establishes place existence only. It never implies that a
    promotion applies to the branch. No geocoding or name-to-province inference
    is performed here.
    """
    merchant = (merchant or "").strip()
    if not merchant:
        return []
    merchant_id = _id("place_", "merchant", merchant)
    evidence_base = {
        "source_id": source_id, "url": url, "observed_at": observed_at,
        "content_hash": content_hash, "basis": "official_store_locator",
        "evidence_excerpt": f"Official store locator for {merchant}",
    }
    m = {
        "contract": PLACE_CONTRACT, "place_id": merchant_id, "record_kind": "merchant",
        "parent_place_id": None,
        "merchant": {"name": merchant, "aliases": _aliases(merchant)},
        "branch": {"name": None, "aliases": []},
        "location": {"country": "TH", "province": None, "district": None, "subdistrict": None,
                     "address": None, "postal_code": None, "latitude": None, "longitude": None},
        "precision": "merchant",
        "search_terms": _search_terms(merchant),
        "verification": {"state": "verified" if reliability == "high" else "partial", "source_count": 1, "evidence_count": 1},
        "evidence": [evidence_base],
        "updated_at": observed_at,
    }
    records = [m]
    for row in candidates:
        branch_name = (row.get("branch_name") or "").strip()
        if not branch_name:
            continue
        location = {
            "branch_name": branch_name,
            "province": row.get("province"), "district": row.get("district"), "subdistrict": row.get("subdistrict"),
            "address": row.get("address"), "postal_code": row.get("postal_code"),
            "latitude": row.get("latitude"), "longitude": row.get("longitude"),
        }
        _, key_location = _branch_key(merchant_id, location)
        if not key_location:
            continue
        pid = _id("place_", "branch", merchant_id, key_location)
        precision = _precision(location)
        ev = dict(evidence_base)
        ev["evidence_excerpt"] = (row.get("evidence_excerpt") or f"{merchant} {branch_name}")[:500]
        records.append({
            "contract": PLACE_CONTRACT, "place_id": pid, "record_kind": "branch",
            "parent_place_id": merchant_id,
            "merchant": {"name": merchant, "aliases": _aliases(merchant)},
            "branch": {"name": branch_name, "aliases": _aliases(branch_name)},
            "location": {
                "country": "TH", "province": row.get("province"), "district": row.get("district"),
                "subdistrict": row.get("subdistrict"), "address": row.get("address"),
                "postal_code": row.get("postal_code"), "latitude": row.get("latitude"), "longitude": row.get("longitude"),
            },
            "precision": precision,
            "search_terms": _search_terms(merchant, branch_name, row.get("province"), row.get("district"),
                                          row.get("subdistrict"), row.get("address"), row.get("postal_code")),
            "verification": {"state": "verified" if reliability == "high" else "partial", "source_count": 1, "evidence_count": 1},
            "evidence": [ev],
            "updated_at": observed_at,
        })
    return merge_place_records(records)


def merge_place_records(records: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in records:
        pid = row.get("place_id")
        if not pid:
            continue
        merged[pid] = _merge_place(merged[pid], row) if pid in merged else deepcopy(row)
    return sorted(merged.values(), key=lambda x: (x.get("record_kind") != "merchant",
        _norm((x.get("merchant") or {}).get("name")), _norm((x.get("branch") or {}).get("name"))))

def build_place_master(offers: list[dict], alias_config_path: str | Path | None = None,
                       now: str | None = None, seed_places: list[dict] | None = None) -> tuple[list[dict], list[dict], dict]:
    """Build a generic merchant/branch master and link offers to stable ids.

    This is deliberately brand-neutral. It uses explicit offer geography and
    optional operator-maintained aliases only; it does not geocode or invent
    missing branch/address facts.
    """
    aliases_cfg = _load_alias_config(alias_config_path)
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    places: dict[str, dict] = {x["place_id"]: deepcopy(x) for x in (seed_places or []) if x.get("place_id")}
    enriched: list[dict] = []
    linked_offers = 0
    physical_linked = 0

    for raw_offer in offers:
        offer = deepcopy(raw_offer)
        merchant = ((offer.get("merchant") or {}).get("name") or "").strip()
        merchant_ref = None
        place_refs: list[str] = []
        if merchant:
            configured = aliases_cfg.get("merchants", {}).get(merchant, []) if isinstance(aliases_cfg.get("merchants", {}), dict) else []
            m_aliases = _aliases(merchant, configured)
            m = _merchant_record(merchant, m_aliases, offer, now)
            merchant_ref = m["place_id"]
            places[merchant_ref] = _merge_place(places[merchant_ref], m) if merchant_ref in places else m

            geo = offer.get("geography") or {}
            for location in geo.get("locations") or []:
                bname = location.get("branch_name")
                branch_config = []
                if bname and isinstance(aliases_cfg.get("branches", {}), dict):
                    branch_config = aliases_cfg.get("branches", {}).get(f"{merchant}|{bname}", [])
                b_aliases = _aliases(bname, branch_config) if bname else []
                branch = _branch_record(merchant, merchant_ref, m_aliases, location, b_aliases, offer, now)
                if branch is None:
                    continue
                pid = branch["place_id"]
                places[pid] = _merge_place(places[pid], branch) if pid in places else branch
                if pid not in place_refs:
                    place_refs.append(pid)

        offer["merchant_place_ref"] = merchant_ref
        offer["place_refs"] = place_refs
        if merchant_ref:
            linked_offers += 1
        if place_refs:
            physical_linked += 1
        enriched.append(offer)

    # P5E: link only explicitly named offer branches to verified official
    # branch-directory records. Merchant branch existence by itself never
    # creates offer applicability.
    records_pre = sorted(places.values(), key=lambda x: (x.get("record_kind") != "merchant", _norm((x.get("merchant") or {}).get("name")), _norm((x.get("branch") or {}).get("name"))))
    enriched, linkage_stats = link_offers_explicit_branches(enriched, records_pre)
    physical_linked = sum(bool(x.get("place_refs")) for x in enriched)
    records = records_pre
    stats = {
        "places": len(records),
        "merchant_places": sum(x.get("record_kind") == "merchant" for x in records),
        "branch_places": sum(x.get("record_kind") == "branch" for x in records),
        "offers_with_merchant_ref": linked_offers,
        "offers_with_physical_place_ref": physical_linked,
        **linkage_stats,
    }
    return enriched, records, stats


def validate_place(place: dict) -> list[str]:
    errors: list[str] = []
    if place.get("contract") != PLACE_CONTRACT: errors.append("contract")
    if not place.get("place_id"): errors.append("place_id")
    if place.get("record_kind") not in VALID_RECORD_KINDS: errors.append("record_kind")
    if place.get("precision") not in VALID_PRECISIONS: errors.append("precision")
    if not isinstance((place.get("merchant") or {}).get("aliases"), list): errors.append("merchant.aliases")
    if not isinstance((place.get("branch") or {}).get("aliases"), list): errors.append("branch.aliases")
    if not isinstance(place.get("search_terms"), list): errors.append("search_terms")
    if not isinstance(place.get("evidence"), list): errors.append("evidence")
    loc = place.get("location") or {}
    pc = loc.get("postal_code")
    if pc is not None and (not isinstance(pc, str) or len(pc) != 5 or not pc.isdigit()): errors.append("location.postal_code")
    lat, lon = loc.get("latitude"), loc.get("longitude")
    if lat is not None and (not isinstance(lat, (int, float)) or not -90 <= lat <= 90): errors.append("location.latitude")
    if lon is not None and (not isinstance(lon, (int, float)) or not -180 <= lon <= 180): errors.append("location.longitude")
    if place.get("record_kind") == "branch" and not place.get("parent_place_id"): errors.append("parent_place_id")
    return errors


def write_place_master(path: str | Path, places: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for place in places:
            f.write(json.dumps(place, ensure_ascii=False, sort_keys=True) + "\n")
