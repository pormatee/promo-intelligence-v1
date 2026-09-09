#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.contract import validate_offer
from promo_intelligence.detail_applicability import (
    discover_detail_links, evaluate_detail_page, apply_detail_results, cache_paths,
)
from promo_intelligence.fetch import fetch_source

OFFERS = ROOT / "output" / "promo_offer_v1.jsonl"
SOURCES = ROOT / "config" / "sources.json"
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "applicability_details"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def actionable(o: dict) -> bool:
    app = o.get("applicability") or {}
    identity = o.get("offer_identity") or {}
    return (app.get("scope") == "unknown" and app.get("channel") != "online"
            and identity.get("state") != "rejected")


def _fetch_one(url: str, source: dict) -> dict:
    detail_source = {
        "url": url,
        "curl_fallback": bool(source.get("curl_fallback", True)),
        "timeout_seconds": int(source.get("detail_timeout_seconds", 8)),
        "recovery_budget_seconds": int(source.get("detail_recovery_budget_seconds", 10)),
    }
    html_path, meta_path = cache_paths(CACHE, url)
    try:
        r = fetch_source(detail_source, default_timeout=8, max_bytes=4_000_000)
        text = r.body.decode("utf-8", errors="replace")
        html_path.write_text(text, encoding="utf-8")
        meta_path.write_text(json.dumps({
            "url": url, "observed_at": r.observed_at, "content_hash": r.content_hash,
            "recovery_method": r.recovery_method,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"url": url, "ok": True, "html": text, "observed_at": r.observed_at,
                "content_hash": r.content_hash, "cache_fallback": False}
    except Exception as exc:
        if html_path.exists():
            text = html_path.read_text(encoding="utf-8", errors="replace")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            return {"url": url, "ok": True, "html": text, "observed_at": meta.get("observed_at"),
                    "content_hash": meta.get("content_hash"), "cache_fallback": True,
                    "fetch_error": f"{type(exc).__name__}: {exc}"}
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    offers = read_jsonl(OFFERS)
    if not offers:
        print("P5G_DISCOVERY_RESULT=FAIL"); print("REASON=NO_OFFERS"); return 2
    rows = json.loads(SOURCES.read_text(encoding="utf-8"))
    sources = {x["source_id"]: x for x in rows if x.get("enabled", True)}
    raw_by_source = {}
    for sid in sources:
        p = RAW / f"{sid}.html"
        if p.exists(): raw_by_source[sid] = p.read_text(encoding="utf-8", errors="replace")

    before = sum(actionable(x) for x in offers)
    offer_candidates: dict[int, list] = {}
    url_sources: dict[str, dict] = {}
    candidate_count = 0
    missing_raw = 0
    for idx, offer in enumerate(offers):
        if not actionable(offer): continue
        sid = (offer.get("source") or {}).get("source_id") or ""
        src = sources.get(sid)
        raw = raw_by_source.get(sid)
        if not src or not raw:
            missing_raw += 1
            continue
        title = ((offer.get("item") or {}).get("name") or "").strip()
        cands = discover_detail_links(raw, src.get("url") or "", title, limit=3)
        if cands:
            offer_candidates[idx] = cands
            candidate_count += len(cands)
            for c in cands: url_sources.setdefault(c.url, src)

    # Bound total network work. The current backlog is tiny, but this protects
    # future runs if actionable unknown grows unexpectedly.
    max_urls = 36
    unique_urls = list(url_sources)[:max_urls]
    fetched: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_fetch_one, u, url_sources[u]): u for u in unique_urls}
        done = 0
        for fut in as_completed(futs):
            u = futs[fut]
            try: fetched[u] = fut.result()
            except Exception as exc: fetched[u] = {"url": u, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            done += 1
            status = "OK" if fetched[u].get("ok") else "FAILED"
            cache = " CACHE" if fetched[u].get("cache_fallback") else ""
            print(f"DETAIL_FETCH_PROGRESS={done}/{len(unique_urls)} RESULT={status}{cache} URL={u}", flush=True)

    totals = {
        "discovered": 0, "nationwide": 0, "province": 0, "branch": 0, "conflicts": 0,
        "page_title_not_found": 0, "page_title_ambiguous": 0,
    }
    new_offers = list(offers)
    for idx, cands in offer_candidates.items():
        offer = offers[idx]
        sid = (offer.get("source") or {}).get("source_id") or ""
        src = sources.get(sid) or {}
        results = []
        for c in cands:
            page = fetched.get(c.url)
            if not page or not page.get("ok"): continue
            result, stats = evaluate_detail_page(offer, src, c, page.get("html", ""),
                                                 page.get("observed_at"), page.get("content_hash"))
            totals["page_title_not_found"] += stats.get("title_not_found", 0)
            totals["page_title_ambiguous"] += stats.get("title_ambiguous", 0)
            if result: results.append(result)
        enriched, kind = apply_detail_results(offer, results)
        if kind == "conflict":
            totals["conflicts"] += 1
        elif kind in {"nationwide", "province", "branch"}:
            totals["discovered"] += 1
            totals[kind] += 1
        new_offers[idx] = enriched

    errors = sum(bool(validate_offer(x)) for x in new_offers)
    after = sum(actionable(x) for x in new_offers)
    if errors:
        print(f"CONTRACT_ERRORS={errors}"); print("P5G_DISCOVERY_RESULT=FAIL"); return 3

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "output" / f"promo_offer_v1.pre_detail_discovery_{stamp}.jsonl"
    shutil.copy2(OFFERS, backup)
    write_jsonl(OFFERS, new_offers)

    fetch_ok = sum(1 for x in fetched.values() if x.get("ok"))
    fetch_fail = sum(1 for x in fetched.values() if not x.get("ok"))
    cache_fallback = sum(1 for x in fetched.values() if x.get("cache_fallback"))
    print(f"OFFERS_SCANNED={len(offers)}")
    print(f"ACTIONABLE_UNKNOWN_BEFORE={before}")
    print(f"DETAIL_OFFERS_WITH_CANDIDATE_LINKS={len(offer_candidates)}")
    print(f"DETAIL_CANDIDATE_LINKS={candidate_count}")
    print(f"DETAIL_URLS_UNIQUE={len(unique_urls)}")
    print(f"DETAIL_FETCHED={fetch_ok}")
    print(f"DETAIL_FETCH_FAILED={fetch_fail}")
    print(f"DETAIL_CACHE_FALLBACKS={cache_fallback}")
    print(f"DETAIL_RAW_SOURCE_MISSING={missing_raw}")
    print(f"DETAIL_APPLICABILITY_DISCOVERED={totals['discovered']}")
    print(f"DETAIL_DISCOVERED_NATIONWIDE={totals['nationwide']}")
    print(f"DETAIL_DISCOVERED_PROVINCE={totals['province']}")
    print(f"DETAIL_DISCOVERED_BRANCH={totals['branch']}")
    print(f"DETAIL_CONFLICTS={totals['conflicts']}")
    print(f"DETAIL_TITLE_NOT_FOUND={totals['page_title_not_found']}")
    print(f"DETAIL_TITLE_AMBIGUOUS={totals['page_title_ambiguous']}")
    print(f"ACTIONABLE_UNKNOWN_AFTER={after}")
    print("CONTRACT_ERRORS=0")
    print(f"BACKUP={backup}")
    print("P5G_DISCOVERY_RESULT=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
