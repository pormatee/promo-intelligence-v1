from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .price_integrity import has_currency_evidence, sanitize_offer_pricing

PUBLISHED_MANIFEST_CONTRACT = "promo_published_manifest_v1"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _encode_jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows).encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def is_publishable(offer: dict) -> bool:
    verification = offer.get("verification") or {}
    identity = offer.get("offer_identity") or {}
    return (
        verification.get("verification_state") in {"verified", "partial"}
        and verification.get("expiry_state") != "expired"
        and verification.get("freshness_state") != "stale"
        and identity.get("state") != "rejected"
    )


def publish_snapshot(project_root: str | Path, offers: list[dict], places: list[dict], now: str | None = None) -> tuple[dict, list[dict]]:
    root = Path(project_root)
    published_dir = root / "output" / "published"
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    # Defense in depth: Published Read Model never trusts historical pricing
    # blindly. Old JSONL rows are rechecked against their own evidence before
    # external consumers can see price/discount claims.
    sanitized = []
    for x in offers:
        # New pipeline rows and repaired historical rows declare pricing
        # integrity metadata. Legacy synthetic/compat rows are left unchanged
        # until explicitly migrated by repair_price_integrity.py.
        has_price_gate = (
            "verification_state" in (x.get("pricing") or {})
            or bool((x.get("evidence") or {}).get("price_fields"))
            or has_currency_evidence((x.get("evidence") or {}).get("extracted_text", ""))
        )
        sanitized.append(sanitize_offer_pricing(x) if has_price_gate else x)
    published_offers = [x for x in sanitized if is_publishable(x)]
    direct_place_ids = {pid for x in published_offers for pid in ([x.get("merchant_place_ref")] + list(x.get("place_refs") or [])) if pid}
    # Place directory is an independent read model. A verified/partial place may
    # be useful even when that merchant has no current promotion. This never
    # implies that any offer applies to that branch.
    published_places = [
        x for x in places
        if (x.get("verification") or {}).get("state") in {"verified", "partial"}
        or x.get("place_id") in direct_place_ids
    ]
    branch_index: dict[str, list[str]] = {}
    for place in published_places:
        if place.get("record_kind") == "branch" and place.get("parent_place_id"):
            branch_index.setdefault(place["parent_place_id"], []).append(place["place_id"])
    for key in branch_index:
        branch_index[key] = sorted(set(branch_index[key]))

    offers_data = _encode_jsonl(published_offers)
    places_data = _encode_jsonl(published_places)
    index_doc = {
        "contract": "promo_place_index_v1",
        "generated_at": now,
        "merchant_count": len(branch_index),
        "branch_count": sum(len(v) for v in branch_index.values()),
        "merchant_branches": branch_index,
        "semantics": "place directory only; offer applicability must be evaluated separately",
    }
    index_data = (json.dumps(index_doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    publication_material = (now + "|" + _sha256_bytes(offers_data) + "|" + _sha256_bytes(places_data)).encode("utf-8")
    publication_id = "pub_" + hashlib.sha256(publication_material).hexdigest()[:20]
    manifest = {
        "contract": PUBLISHED_MANIFEST_CONTRACT,
        "publication_id": publication_id,
        "published_at": now,
        "offer_contract": "promo_offer_v1",
        "place_contract": "promo_place_v1",
        "offer_count": len(published_offers),
        "place_count": len(published_places),
        "branch_place_count": sum(x.get("record_kind") == "branch" for x in published_places),
        "merchant_branch_index_count": len(branch_index),
        "offer_sha256": _sha256_bytes(offers_data),
        "place_sha256": _sha256_bytes(places_data),
        "place_index_sha256": _sha256_bytes(index_data),
        "files": {
            "offers": "promo_offer_v1.jsonl",
            "places": "promo_place_v1.jsonl",
            "merchant_branch_index": "merchant_branch_index_v1.json",
        },
        "policy": {
            "verification_states": ["verified", "partial"],
            "exclude_expired": True,
            "exclude_stale": True,
            "read_only": True,
            "branch_directory_not_offer_applicability": True,
            "place_directory_independent_of_offer_presence": True,
            "price_evidence_integrity_gate": True,
            "unsupported_price_claims_sanitized": True,
            "offer_identity_integrity_gate": True,
            "identity_rejected_excluded": True,
        },
    }

    _atomic_write(published_dir / "promo_offer_v1.jsonl", offers_data)
    _atomic_write(published_dir / "promo_place_v1.jsonl", places_data)
    _atomic_write(published_dir / "merchant_branch_index_v1.json", index_data)
    _atomic_write(published_dir / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return manifest, published_offers


def load_manifest(project_root: str | Path) -> dict | None:
    path = Path(project_root) / "output" / "published" / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_published_offers(project_root: str | Path) -> list[dict]:
    return read_jsonl(Path(project_root) / "output" / "published" / "promo_offer_v1.jsonl")


def load_published_places(project_root: str | Path) -> list[dict]:
    return read_jsonl(Path(project_root) / "output" / "published" / "promo_place_v1.jsonl")


def load_merchant_branch_index(project_root: str | Path) -> dict:
    path = Path(project_root) / "output" / "published" / "merchant_branch_index_v1.json"
    if not path.exists():
        return {"contract": "promo_place_index_v1", "merchant_branches": {}}
    return json.loads(path.read_text(encoding="utf-8"))
