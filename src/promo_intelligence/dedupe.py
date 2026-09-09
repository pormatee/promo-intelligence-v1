from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import re
import unicodedata

from .geo import merge_geography


def _canon(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = " ".join(str(value.get(k) or "") for k in sorted(value))
    s = unicodedata.normalize("NFKC", str(value)).casefold()
    # Mild unit normalization only; do not translate names or infer identities.
    s = re.sub(r"\b(?:millilit(?:er|re)s?|มล\.?|ml\.?)\b", "ml", s, flags=re.I)
    s = re.sub(r"\b(?:grams?|กรัม|g\.?)\b", "g", s, flags=re.I)
    s = re.sub(r"[^0-9a-zก-๙]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _basis(offer: dict, *, include_applicability: bool = True) -> dict:
    applicability = offer.get("applicability") or {}
    merchant = offer.get("merchant") or {}
    item = offer.get("item") or {}
    pricing = offer.get("pricing") or {}
    validity = offer.get("validity") or {}
    basis = {
        "merchant": _canon(merchant.get("name")),
        "branch": _canon(merchant.get("branch")),
        "item": _canon(item.get("name")),
        "offer_type": offer.get("offer_type"),
        "promo_price": pricing.get("promo_price"),
        "regular_price": pricing.get("regular_price"),
        "start": validity.get("start"),
        "end": validity.get("end"),
    }
    if include_applicability:
        geography = offer.get("geography") or {}
        geo_locations = []
        for row in geography.get("locations") or []:
            geo_locations.append(tuple(_canon(row.get(k)) for k in [
                "province", "district", "subdistrict", "branch_name", "address", "postal_code",
                "latitude", "longitude",
            ]))
        basis.update({
            "scope": applicability.get("scope", "unknown"),
            "provinces": sorted(_canon(x) for x in (applicability.get("provinces") or [])),
            "branches": sorted(_canon(x) for x in (applicability.get("branches") or [])),
            "geography": sorted(geo_locations),
        })
    return basis


def _hash_basis(basis: dict) -> str:
    payload = json.dumps(basis, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fingerprint(offer: dict) -> str:
    return _hash_basis(_basis(offer, include_applicability=True))


def _core_fingerprint(offer: dict) -> str:
    return _hash_basis(_basis(offer, include_applicability=False))


def _corroboration(offer: dict) -> dict:
    src = offer.get("source") or {}
    evidence = offer.get("evidence") or {}
    return {
        "source_id": src.get("source_id"),
        "source_type": src.get("source_type"),
        "url": src.get("url"),
        "observed_at": src.get("observed_at"),
        "content_hash": evidence.get("content_hash"),
    }


def _merge_evidence(keeper: dict, duplicate: dict) -> None:
    ksrc = (keeper.get("source") or {}).get("source_id")
    dsrc = (duplicate.get("source") or {}).get("source_id")
    if not dsrc or dsrc == ksrc:
        return
    evidence = keeper.setdefault("evidence", {})
    rows = evidence.setdefault("corroborating_sources", [])
    existing = {x.get("source_id") for x in rows}
    if dsrc not in existing:
        rows.append(_corroboration(duplicate))


def _scope(o: dict) -> str:
    return (o.get("applicability") or {}).get("scope", "unknown")


def _geo_keys(o: dict) -> set[tuple]:
    keys = set()
    for row in ((o.get("geography") or {}).get("locations") or []):
        key = tuple(_canon(row.get(k)) for k in [
            "province", "district", "subdistrict", "branch_name", "address", "postal_code",
            "latitude", "longitude",
        ])
        if any(key):
            keys.add(key)
    return keys


def _can_merge_core(a: dict, b: dict) -> bool:
    # Never collapse conflicting explicit geographic claims. Core-identical
    # offers may merge when applicability agrees or one side is unknown, and
    # detailed locations do not explicitly disagree.
    sa, sb = _scope(a), _scope(b)
    if sa != "unknown" and sb != "unknown" and (a.get("applicability") or {}) != (b.get("applicability") or {}):
        return False
    ga, gb = _geo_keys(a), _geo_keys(b)
    if ga and gb and ga.isdisjoint(gb):
        return False
    return True


def _promote_applicability(keeper: dict, duplicate: dict) -> None:
    if _scope(keeper) == "unknown" and _scope(duplicate) != "unknown":
        keeper["applicability"] = deepcopy(duplicate.get("applicability") or {})


def _merge_geography(keeper: dict, duplicate: dict) -> None:
    keeper["geography"] = merge_geography(keeper.get("geography"), duplicate.get("geography"))


def dedupe(offers: list[dict]) -> list[dict]:
    exact: dict[str, dict] = {}
    core_to_exact: dict[str, str] = {}
    order: list[str] = []
    for offer in offers:
        fp = fingerprint(offer)
        if fp in exact:
            _merge_evidence(exact[fp], offer)
            _merge_geography(exact[fp], offer)
            continue

        core = _core_fingerprint(offer)
        existing_fp = core_to_exact.get(core)
        if existing_fp is not None and _can_merge_core(exact[existing_fp], offer):
            keeper = exact[existing_fp]
            _merge_evidence(keeper, offer)
            _promote_applicability(keeper, offer)
            _merge_geography(keeper, offer)
            continue

        exact[fp] = deepcopy(offer)
        core_to_exact[core] = fp
        order.append(fp)
    return [exact[x] for x in order]
