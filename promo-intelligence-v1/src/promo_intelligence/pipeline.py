from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .contract import build_offer, validate_offer
from .dedupe import dedupe
from .extract import extract
from .fetch import fetch_url
from .normalize import normalize_candidate
from .sources import load_sources
from .verify import verify_offer


def _safe_name(source_id: str) -> str:
    return "".join(c for c in source_id if c.isalnum() or c in "-_")


def _process(source: dict, body: bytes, observed_at: str, content_hash: str, now: datetime | None = None) -> tuple[list[dict], dict]:
    raw_html = body.decode("utf-8", errors="replace")
    candidates = extract(raw_html, source["extractor"])
    normalized = [normalize_candidate(c) for c in candidates]
    offers = []
    for c in normalized:
        verification = verify_offer(c, source, observed_at, now=now)
        offer = build_offer(c, source, observed_at, content_hash, verification)
        if not validate_offer(offer):
            offers.append(offer)
    offers = dedupe(offers)
    stats = {"candidates": len(candidates), "normalized": len(normalized), "exportable": len(offers)}
    return offers, stats


def run_live(project_root: str | Path) -> tuple[list[dict], dict]:
    root = Path(project_root)
    sources = load_sources(root / "config" / "sources.json")
    all_offers: list[dict] = []
    totals = {"sources": len(sources), "fetched": 0, "candidates": 0, "normalized": 0, "exportable": 0}
    for source in sources:
        fetched = fetch_url(source["url"])
        totals["fetched"] += 1
        sid = _safe_name(source["source_id"])
        (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
        (root / "data" / "evidence").mkdir(parents=True, exist_ok=True)
        (root / "data" / "raw" / f"{sid}.html").write_bytes(fetched.body)
        meta = {"source_id": sid, "url": fetched.url, "status": fetched.status, "content_type": fetched.content_type, "observed_at": fetched.observed_at, "content_hash": fetched.content_hash}
        (root / "data" / "evidence" / f"{sid}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        offers, stats = _process(source, fetched.body, fetched.observed_at, fetched.content_hash)
        all_offers.extend(offers)
        for k in ["candidates","normalized","exportable"]: totals[k] += stats[k]
    all_offers = dedupe(all_offers)
    totals["exportable"] = len(all_offers)
    return all_offers, totals


def run_fixture(project_root: str | Path) -> tuple[list[dict], dict]:
    root = Path(project_root)
    source = load_sources(root / "config" / "sources.json")[0]
    body = (root / "tests" / "fixtures" / "lotus_offer_sample.html").read_bytes()
    observed_at = "2026-09-07T12:00:00Z"
    content_hash = "sha256:" + hashlib.sha256(body).hexdigest()
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    offers, stats = _process(source, body, observed_at, content_hash, now=now)
    totals = {"sources": 1, "fetched": 1, **stats}
    return offers, totals


def write_jsonl(path: str | Path, offers: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for offer in offers:
            f.write(json.dumps(offer, ensure_ascii=False, sort_keys=True) + "\n")
