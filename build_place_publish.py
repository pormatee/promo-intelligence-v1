#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "promo_offer_v1.jsonl"
PLACE_OUTPUT = ROOT / "output" / "promo_place_v1.jsonl"
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.contract import validate_offer
from promo_intelligence.place_master import build_place_master, validate_place, write_place_master
from promo_intelligence.place_enrichment import load_place_cache
from promo_intelligence.published import publish_snapshot


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    offers = read_jsonl(OUTPUT)
    if not offers:
        print("PLACE_PUBLISH_RESULT=FAIL")
        print("REASON=NO_PROMO_OFFER_OUTPUT")
        return 2
    seed_places = load_place_cache(ROOT)
    enriched, places, stats = build_place_master(offers, ROOT / "config" / "place_aliases.json", seed_places=seed_places)
    offer_errors = sum(bool(validate_offer(x)) for x in enriched)
    place_errors = sum(bool(validate_place(x)) for x in places)
    if offer_errors or place_errors:
        print(f"CONTRACT_ERRORS={offer_errors}")
        print(f"PLACE_CONTRACT_ERRORS={place_errors}")
        print("PLACE_PUBLISH_RESULT=FAIL")
        return 3
    write_jsonl(OUTPUT, enriched)
    write_place_master(PLACE_OUTPUT, places)
    manifest, published = publish_snapshot(ROOT, enriched, places)
    print(f"OFFERS_INPUT={len(offers)}")
    print(f"PLACE_ENRICHMENT_CACHE_RECORDS={len(seed_places)}")
    print(f"PLACE_MASTER_RECORDS={stats['places']}")
    print(f"MERCHANT_PLACES={stats['merchant_places']}")
    print(f"BRANCH_PLACES={stats['branch_places']}")
    print(f"OFFERS_WITH_MERCHANT_REF={stats['offers_with_merchant_ref']}")
    print(f"OFFERS_WITH_PHYSICAL_PLACE_REF={stats['offers_with_physical_place_ref']}")
    print(f"OFFERS_WITH_EXPLICIT_BRANCH_NAMES={stats.get('offers_with_explicit_branch_names', 0)}")
    print(f"OFFERS_BRANCH_LINKED={stats.get('offers_branch_linked', 0)}")
    print(f"EXPLICIT_BRANCH_MATCHES={stats.get('explicit_branch_matches', 0)}")
    print(f"EXPLICIT_BRANCH_UNMATCHED={stats.get('explicit_branch_unmatched', 0)}")
    print(f"EXPLICIT_BRANCH_AMBIGUOUS={stats.get('explicit_branch_ambiguous', 0)}")
    print(f"OFFERS_WITH_LOCAL_PROVINCE={stats.get('offers_with_local_province', 0)}")
    print(f"PUBLISHED_OFFERS={len(published)}")
    print(f"PUBLISHED_PLACES={manifest['place_count']}")
    print(f"PUBLISHED_BRANCH_PLACES={manifest.get('branch_place_count', 0)}")
    print(f"MERCHANT_BRANCH_INDEX_ENTRIES={manifest.get('merchant_branch_index_count', 0)}")
    print(f"PUBLICATION_ID={manifest['publication_id']}")
    print("CONTRACT_ERRORS=0")
    print("PLACE_CONTRACT_ERRORS=0")
    print("PUBLISHED_READ_MODEL=PASS")
    print("PLACE_PUBLISH_RESULT=PASS")
    print(f"PLACE_OUTPUT={PLACE_OUTPUT}")
    print(f"PUBLISHED_MANIFEST={ROOT / 'output' / 'published' / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
