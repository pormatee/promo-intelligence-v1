from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .applicability import resolve_applicability
from .contract import build_offer, validate_offer
from .dedupe import dedupe
from .extract import extract
from .fetch import SourceFetchError, fetch_source, fetch_url
from .geo import geography_summary, resolve_geography
from .normalize import normalize_candidate
from .offer_identity import annotate_offer_identity
from .quality import quality_summary
from .sources import load_sources
from .verify import verify_offer


def _safe_name(source_id: str) -> str:
    return "".join(c for c in source_id if c.isalnum() or c in "-_")


def _process(source: dict, body: bytes, observed_at: str, content_hash: str, now: datetime | None = None) -> tuple[list[dict], dict]:
    raw_html = body.decode("utf-8", errors="replace")
    candidates = extract(raw_html, source["extractor"], source)
    normalized = [normalize_candidate(c) for c in candidates]
    built: list[dict] = []
    for c in normalized:
        verification = verify_offer(c, source, observed_at, now=now)
        applicability = resolve_applicability(c, source)
        geography = resolve_geography(c, source, applicability)
        offer = build_offer(c, source, observed_at, content_hash, verification, applicability, geography)
        offer = annotate_offer_identity(offer)
        if not validate_offer(offer):
            built.append(offer)
    before = len(built)
    offers = dedupe(built)
    geo = geography_summary(offers)
    stats = {
        "candidates": len(candidates),
        "normalized": len(normalized),
        "exportable": len(offers),
        "dedupe_removed": before - len(offers),
        "location_known": sum((o.get("applicability") or {}).get("scope") != "unknown" for o in offers),
        "location_unknown": sum((o.get("applicability") or {}).get("scope") == "unknown" for o in offers),
        **geo,
    }
    return offers, stats


def _needs_recovery_fetch(source: dict) -> bool:
    return bool(
        source.get("alternate_urls") or source.get("curl_fallback") or
        source.get("recovery_budget_seconds") or source.get("timeout_seconds")
    )


def _fetch_one(source: dict, default_timeout: int):
    # Preserve the simple fetch path for ordinary sources/tests while enabling
    # source-specific Wave C recovery only where configured.
    if _needs_recovery_fetch(source):
        return fetch_source(source, default_timeout=default_timeout)
    return fetch_url(source["url"], int(source.get("timeout_seconds", default_timeout)))


def _save_fetch(root: Path, sid: str, fetched, suffix: str = "") -> None:
    (root / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (root / "data" / "evidence").mkdir(parents=True, exist_ok=True)
    stem = sid + suffix
    (root / "data" / "raw" / f"{stem}.html").write_bytes(fetched.body)
    meta = {
        "source_id": sid,
        "url": fetched.url,
        "status": fetched.status,
        "content_type": fetched.content_type,
        "observed_at": fetched.observed_at,
        "content_hash": fetched.content_hash,
        "attempts": getattr(fetched, "attempts", 1),
        "recovery_method": getattr(fetched, "recovery_method", "urllib"),
        "original_url": getattr(fetched, "original_url", None),
    }
    (root / "data" / "evidence" / f"{stem}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _process_fetched(source: dict, fetched) -> tuple[list[dict], dict]:
    effective = dict(source)
    # Evidence must point to the exact official URL actually fetched when a
    # configured alternate URL was used.
    effective["url"] = fetched.url
    return _process(effective, fetched.body, fetched.observed_at, fetched.content_hash)


def _recover_zero_offer(root: Path, source: dict, sid: str, default_timeout: int, progress) -> tuple[list[dict], dict | None, list[dict]]:
    urls = [u for u in source.get("zero_offer_alternate_urls", []) if u]
    attempts: list[dict] = []
    merged_offers: list[dict] = []
    merged_stats = None
    for n, url in enumerate(urls, 1):
        alt = dict(source)
        alt["url"] = url
        alt["alternate_urls"] = []
        alt["curl_fallback"] = bool(source.get("zero_offer_curl_fallback", source.get("curl_fallback", False)))
        alt["timeout_seconds"] = int(source.get("zero_offer_timeout_seconds", source.get("timeout_seconds", default_timeout)))
        try:
            fetched = fetch_source(alt, default_timeout=default_timeout) if _needs_recovery_fetch(alt) else fetch_url(url, alt["timeout_seconds"])
            _save_fetch(root, sid, fetched, suffix=f"__zero_alt{n}")
            offers, stats = _process_fetched(alt, fetched)
            attempts.append({"url": url, "result": "ok", "offers": len(offers), "method": getattr(fetched, "recovery_method", "urllib")})
            progress(f"ZERO_RECOVERY SOURCE={sid} ALT={n}/{len(urls)} RESULT=OK OFFERS={len(offers)}")
            if offers:
                merged_offers.extend(offers)
                if merged_stats is None:
                    merged_stats = dict(stats)
                else:
                    for k in ["candidates", "normalized", "dedupe_removed", "location_known", "location_unknown"]:
                        merged_stats[k] += stats.get(k, 0)
                # Stop on first productive official fallback to keep load low.
                break
        except Exception as exc:
            attempts.append({"url": url, "result": "failed", "error_type": type(exc).__name__, "error": str(exc)})
            progress(f"ZERO_RECOVERY SOURCE={sid} ALT={n}/{len(urls)} RESULT=FAILED ERROR={type(exc).__name__}")
    if merged_offers:
        before = len(merged_offers)
        merged_offers = dedupe(merged_offers)
        if merged_stats is None:
            merged_stats = {"candidates": 0, "normalized": 0, "dedupe_removed": 0, "location_known": 0, "location_unknown": 0}
        merged_stats["dedupe_removed"] += before - len(merged_offers)
        merged_stats["exportable"] = len(merged_offers)
        merged_stats["location_known"] = sum((o.get("applicability") or {}).get("scope") != "unknown" for o in merged_offers)
        merged_stats["location_unknown"] = sum((o.get("applicability") or {}).get("scope") == "unknown" for o in merged_offers)
    return merged_offers, merged_stats, attempts


def run_live(project_root: str | Path, on_progress=None, max_workers: int = 4, fetch_timeout: int = 12) -> tuple[list[dict], dict]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    root = Path(project_root)
    sources = load_sources(root / "config" / "sources.json")
    all_offers: list[dict] = []
    totals = {
        "sources": len(sources), "fetched": 0, "fetch_failed": 0, "fetch_retried": 0, "fetch_recovered": 0,
        "candidates": 0, "normalized": 0, "exportable": 0, "dedupe_removed": 0,
        "location_known": 0, "location_unknown": 0,
        "geography_known": 0, "district_known": 0, "subdistrict_known": 0,
        "address_known": 0, "postal_code_known": 0, "coordinates_known": 0, "branch_name_known": 0,
        "source_errors": [], "fetch_success_ids": [], "sources_with_offers": 0,
        "zero_offer_sources": 0, "zero_offer_source_ids": [], "zero_offer_recovered": 0,
        "source_offer_counts": {}, "family_offer_counts": {},
        "location_unknown_by_source": {}, "location_known_by_source": {},
        "families_configured": len({s.get("family") or s.get("merchant") or s.get("source_id") for s in sources}),
        "families_with_offers_set": set(), "hard_block_sources": [], "fetch_recovery_methods": {},
        "zero_recovery_attempts": {},
    }

    def progress(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    fetched_by_sid: dict[str, object] = {}
    workers = max(1, min(int(max_workers), len(sources) or 1))
    completed = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="promo-fetch") as pool:
        future_map = {pool.submit(_fetch_one, source, fetch_timeout): source for source in sources}
        for future in as_completed(future_map):
            source = future_map[future]
            sid = _safe_name(source["source_id"])
            completed += 1
            try:
                fetched = future.result()
                fetched_by_sid[sid] = fetched
                totals["fetched"] += 1
                totals["fetch_success_ids"].append(sid)
                if getattr(fetched, "attempts", 1) > 1:
                    totals["fetch_retried"] += 1
                method = getattr(fetched, "recovery_method", "urllib")
                totals["fetch_recovery_methods"][sid] = method
                if method != "urllib" or fetched.url != source.get("url"):
                    totals["fetch_recovered"] += 1
                progress(
                    f"FETCH_PROGRESS={completed}/{len(sources)} SOURCE={sid} RESULT=OK "
                    f"METHOD={method} ATTEMPTS={getattr(fetched, 'attempts', 1)}"
                )
            except Exception as exc:
                totals["fetch_failed"] += 1
                hard = bool(getattr(exc, "hard_block", False))
                if hard:
                    totals["hard_block_sources"].append(sid)
                totals["source_errors"].append({
                    "source_id": sid, "stage": "fetch", "error_type": type(exc).__name__, "error": str(exc),
                    "hard_block": hard, "attempt_log": getattr(exc, "attempt_log", []),
                })
                progress(
                    f"FETCH_PROGRESS={completed}/{len(sources)} SOURCE={sid} RESULT=FAILED "
                    f"ERROR={type(exc).__name__} HARD_BLOCK={'TRUE' if hard else 'FALSE'}"
                )

    for index, source in enumerate(sources, 1):
        sid = _safe_name(source["source_id"])
        family = source.get("family") or source.get("merchant") or sid
        fetched = fetched_by_sid.get(sid)
        if fetched is None:
            totals["source_offer_counts"][sid] = 0
            continue
        _save_fetch(root, sid, fetched)
        try:
            offers, stats = _process_fetched(source, fetched)
        except Exception as exc:
            totals["source_errors"].append({
                "source_id": sid, "stage": "extract", "error_type": type(exc).__name__, "error": str(exc)
            })
            totals["source_offer_counts"][sid] = 0
            progress(f"EXTRACT_PROGRESS={index}/{len(sources)} SOURCE={sid} RESULT=FAILED ERROR={type(exc).__name__}")
            continue

        if not offers and source.get("zero_offer_alternate_urls"):
            rec_offers, rec_stats, attempts = _recover_zero_offer(root, source, sid, fetch_timeout, progress)
            totals["zero_recovery_attempts"][sid] = attempts
            if rec_offers:
                offers, stats = rec_offers, rec_stats or stats
                totals["zero_offer_recovered"] += 1

        all_offers.extend(offers)
        totals["source_offer_counts"][sid] = len(offers)
        totals["family_offer_counts"][family] = totals["family_offer_counts"].get(family, 0) + len(offers)
        totals["location_unknown_by_source"][sid] = stats["location_unknown"]
        totals["location_known_by_source"][sid] = stats["location_known"]
        if offers:
            totals["sources_with_offers"] += 1
            totals["families_with_offers_set"].add(family)
        else:
            totals["zero_offer_sources"] += 1
            totals["zero_offer_source_ids"].append(sid)
        for k in ["candidates", "normalized", "dedupe_removed"]:
            totals[k] += stats[k]
        progress(f"EXTRACT_PROGRESS={index}/{len(sources)} SOURCE={sid} OFFERS={len(offers)}")

    before_global = len(all_offers)
    all_offers = dedupe(all_offers)
    totals["dedupe_removed"] += before_global - len(all_offers)
    totals["exportable"] = len(all_offers)
    totals["location_known"] = sum((o.get("applicability") or {}).get("scope") != "unknown" for o in all_offers)
    totals["location_unknown"] = sum((o.get("applicability") or {}).get("scope") == "unknown" for o in all_offers)
    totals.update(geography_summary(all_offers))
    totals["families_with_offers"] = len(totals.pop("families_with_offers_set"))
    totals["primary_source_export_counts"] = dict(Counter(
        (o.get("source") or {}).get("source_id", "unknown") for o in all_offers
    ))
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


def run_nationwide_fixture(project_root: str | Path) -> tuple[list[dict], dict]:
    root = Path(project_root)
    sources = load_sources(root / "config" / "sources.json")
    source = next(s for s in sources if s["source_id"] == "lotus_tctplus_g2_en")
    body = (root / "tests" / "fixtures" / "lotus_nationwide_coupon_sample.html").read_bytes()
    observed_at = "2026-09-08T00:30:00Z"
    content_hash = "sha256:" + hashlib.sha256(body).hexdigest()
    now = datetime(2026, 9, 8, 0, 30, tzinfo=timezone.utc)
    offers, stats = _process(source, body, observed_at, content_hash, now=now)
    totals = {"sources": 1, "fetched": 1, **stats}
    return offers, totals


def write_jsonl(path: str | Path, offers: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for offer in offers:
            f.write(json.dumps(offer, ensure_ascii=False, sort_keys=True) + "\n")


def write_diagnostics(path: str | Path, stats: dict, offers: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "contract": "promo_offer_v1",
        "summary": {
            "sources": stats.get("sources", 0), "fetched": stats.get("fetched", 0),
            "fetch_failed": stats.get("fetch_failed", 0), "fetch_retried": stats.get("fetch_retried", 0),
            "fetch_recovered": stats.get("fetch_recovered", 0),
            "hard_block_sources": len(stats.get("hard_block_sources", [])),
            "families_configured": stats.get("families_configured", 1),
            "families_with_offers": stats.get("families_with_offers", 1 if offers else 0),
            "sources_with_offers": stats.get("sources_with_offers", 1 if offers else 0),
            "zero_offer_sources": stats.get("zero_offer_sources", 0),
            "zero_offer_recovered": stats.get("zero_offer_recovered", 0),
            "candidates": stats.get("candidates", 0), "normalized": stats.get("normalized", 0),
            "dedupe_removed": stats.get("dedupe_removed", 0), "exported": len(offers),
            "location_known": stats.get("location_known", 0), "location_unknown": stats.get("location_unknown", 0),
            "geography_known": stats.get("geography_known", 0),
            "district_known": stats.get("district_known", 0),
            "subdistrict_known": stats.get("subdistrict_known", 0),
            "address_known": stats.get("address_known", 0),
            "postal_code_known": stats.get("postal_code_known", 0),
            "coordinates_known": stats.get("coordinates_known", 0),
            "branch_name_known": stats.get("branch_name_known", 0),
        },
        "quality": quality_summary(offers),
        "fetch_success_ids": stats.get("fetch_success_ids", []),
        "hard_block_sources": stats.get("hard_block_sources", []),
        "fetch_recovery_methods": stats.get("fetch_recovery_methods", {}),
        "source_errors": stats.get("source_errors", []),
        "zero_offer_source_ids": stats.get("zero_offer_source_ids", []),
        "zero_recovery_attempts": stats.get("zero_recovery_attempts", {}),
        "source_offer_counts": stats.get("source_offer_counts", {}),
        "family_offer_counts": stats.get("family_offer_counts", {}),
        "primary_source_export_counts": stats.get("primary_source_export_counts", {}),
        "location_unknown_by_source": stats.get("location_unknown_by_source", {}),
        "location_known_by_source": stats.get("location_known_by_source", {}),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
