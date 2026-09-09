#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.place_enrichment import refresh_place_cache


def main() -> int:
    places, stats = refresh_place_cache(ROOT)
    print(f"PLACE_SOURCE_FOUND={stats['sources_found']}")
    print(f"PLACE_FETCHED={stats['fetched']}")
    print(f"PLACE_FETCH_FAILED={stats['fetch_failed']}")
    print(f"ZERO_BRANCH_SOURCES={stats['zero_branch_sources']}")
    print(f"BRANCH_CANDIDATES={stats['branch_candidates']}")
    print(f"PLACE_CACHE_RECORDS={stats['cache_records']}")
    print(f"PLACE_CACHE_MERCHANTS={stats['merchant_places']}")
    print(f"PLACE_CACHE_BRANCHES={stats['branch_places']}")
    print(f"BRANCH_WITH_PROVINCE={stats['branch_with_province']}")
    print(f"BRANCH_WITH_ADDRESS={stats['branch_with_address']}")
    for row in stats['failed_sources']:
        print(f"PLACE_FETCH_FAILED_SOURCE={row['source_id']} ERROR={row['error_type']}:{row['error'][:120]}")
    for source_id in stats['zero_sources']:
        print(f"ZERO_BRANCH_SOURCE={source_id}")
    print(f"PLACE_ENRICHMENT_RESULT={stats['result']}")
    print(f"PLACE_CACHE={stats['cache_path']}")
    return 0 if stats['branch_places'] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
