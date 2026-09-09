#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "promo_offer_v1.jsonl"
PLACE_OUTPUT = ROOT / "output" / "promo_place_v1.jsonl"


def _stream(cmd: list[str]) -> int:
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert p.stdout is not None
    for line in p.stdout:
        print(line, end="", flush=True)
    return p.wait()


def _offers() -> list[dict]:
    rows=[]
    if not OUTPUT.exists():
        return rows
    for line in OUTPUT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--core-refresh", action="store_true", help="refresh backend/place/published snapshot without rebuilding the large frontend")
    args, _ = ap.parse_known_args(argv)

    print("=== Promo Intelligence Autonomous Runner ===", flush=True)
    print("STEP=BACKEND_AUTONOMOUS_LOOP", flush=True)
    rc = _stream([sys.executable, "autonomous_wave_c.py"])
    if rc != 0:
        print("PROMO_AUTONOMOUS_RESULT=HARD_BLOCK")
        print("HARD_BLOCK_REASON=BACKEND_LOOP_FAILED")
        return rc

    offers = _offers()
    if not offers:
        print("PROMO_AUTONOMOUS_RESULT=HARD_BLOCK")
        print("HARD_BLOCK_REASON=NO_OUTPUT_OFFERS")
        return 3

    sys.path.insert(0, str(ROOT / "src"))
    from promo_intelligence.contract import validate_offer
    from promo_intelligence.geo import geography_summary
    from promo_intelligence.place_master import build_place_master, validate_place, write_place_master
    from promo_intelligence.place_enrichment import refresh_place_cache
    from promo_intelligence.published import publish_snapshot

    print("STEP=PLACE_ENRICHMENT", flush=True)
    try:
        seed_places, enrichment_stats = refresh_place_cache(ROOT, progress=print)
    except Exception as exc:
        print(f"PLACE_ENRICHMENT_ERROR={type(exc).__name__}:{str(exc)[:200]}", flush=True)
        seed_places, enrichment_stats = [], {"result": "DEGRADED_ERROR", "sources_found": 0, "fetched": 0, "fetch_failed": 0, "branch_places": 0}

    print("STEP=PLACE_MASTER", flush=True)
    offers, places, place_stats = build_place_master(
        offers,
        alias_config_path=ROOT / "config" / "place_aliases.json",
        seed_places=seed_places,
    )
    _write_jsonl(OUTPUT, offers)
    write_place_master(PLACE_OUTPUT, places)

    contract_errors = sum(bool(validate_offer(x)) for x in offers)
    place_errors = sum(bool(validate_place(x)) for x in places)
    missing_geo = sum("geography" not in x for x in offers)
    geo = geography_summary(offers)

    print("STEP=PUBLISH_READ_MODEL", flush=True)
    manifest, published_offers = publish_snapshot(ROOT, offers, places)

    frontend_rc = 0
    if not args.core_refresh:
        print("STEP=FRONTEND_BUILD", flush=True)
        frontend_rc = _stream([sys.executable, "build_frontend.py"])
    else:
        print("STEP=FRONTEND_BUILD SKIPPED=CORE_REFRESH", flush=True)

    print("\n=== PROMO AUTONOMOUS FINAL ===")
    print(f"EXPORTED={len(offers)}")
    print(f"GEO_SCHEMA_MISSING={missing_geo}")
    print(f"GEO_KNOWN_OFFERS={geo['geography_known']}")
    print(f"DISTRICT_KNOWN_OFFERS={geo['district_known']}")
    print(f"SUBDISTRICT_KNOWN_OFFERS={geo['subdistrict_known']}")
    print(f"ADDRESS_KNOWN_OFFERS={geo['address_known']}")
    print(f"POSTAL_CODE_KNOWN_OFFERS={geo['postal_code_known']}")
    print(f"COORDINATES_KNOWN_OFFERS={geo['coordinates_known']}")
    print(f"BRANCH_NAME_KNOWN_OFFERS={geo['branch_name_known']}")
    print(f"PLACE_ENRICHMENT_RESULT={enrichment_stats.get('result')}")
    print(f"PLACE_SOURCE_FOUND={enrichment_stats.get('sources_found', 0)}")
    print(f"PLACE_FETCHED={enrichment_stats.get('fetched', 0)}")
    print(f"PLACE_FETCH_FAILED={enrichment_stats.get('fetch_failed', 0)}")
    print(f"PLACE_CACHE_BRANCHES={enrichment_stats.get('branch_places', 0)}")
    print(f"PLACE_MASTER_RECORDS={place_stats['places']}")
    print(f"MERCHANT_PLACES={place_stats['merchant_places']}")
    print(f"BRANCH_PLACES={place_stats['branch_places']}")
    print(f"OFFERS_WITH_MERCHANT_REF={place_stats['offers_with_merchant_ref']}")
    print(f"OFFERS_WITH_PHYSICAL_PLACE_REF={place_stats['offers_with_physical_place_ref']}")
    print(f"PLACE_CONTRACT_ERRORS={place_errors}")
    print(f"PUBLICATION_ID={manifest['publication_id']}")
    print(f"PUBLISHED_OFFERS={manifest['offer_count']}")
    print(f"PUBLISHED_PLACES={manifest['place_count']}")
    print(f"PUBLISHED_BRANCH_PLACES={manifest.get('branch_place_count', 0)}")
    print(f"MERCHANT_BRANCH_INDEX_ENTRIES={manifest.get('merchant_branch_index_count', 0)}")
    print("PUBLISHED_READ_MODEL=PASS")
    print(f"CONTRACT_ERRORS={contract_errors}")
    print(f"FRONTEND_BUILD={'SKIPPED' if args.core_refresh else ('PASS' if frontend_rc == 0 else 'FAIL')}")
    ok = missing_geo == 0 and contract_errors == 0 and place_errors == 0 and frontend_rc == 0
    print("PROMO_AUTONOMOUS_RESULT=" + ("PASS" if ok else "HARD_BLOCK"))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
