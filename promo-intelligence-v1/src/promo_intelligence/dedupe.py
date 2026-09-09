from __future__ import annotations
import hashlib
import json


def fingerprint(offer: dict) -> str:
    basis = {
        "merchant": offer["merchant"],
        "item": offer["item"]["name"],
        "promo_price": offer["pricing"]["promo_price"],
        "start": offer["validity"]["start"],
        "end": offer["validity"]["end"],
    }
    payload = json.dumps(basis, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def dedupe(offers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for offer in offers:
        fp = fingerprint(offer)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(offer)
    return out
