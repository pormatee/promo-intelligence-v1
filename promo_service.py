#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.published import load_manifest
from promo_intelligence.update_strategy import load_policy, load_state, request_refresh


def _print_result(result: dict) -> int:
    print("UPDATE_DECISION=" + str(result.get("decision", "unknown")).upper())
    print("UPDATE_REASON=" + str(result.get("reason", "")))
    if result.get("age_seconds") is not None:
        print(f"PUBLISHED_AGE_SECONDS={int(result['age_seconds'])}")
    if result.get("return_code") is not None:
        print(f"REFRESH_RETURN_CODE={result['return_code']}")
    manifest = load_manifest(ROOT)
    if manifest:
        print(f"PUBLICATION_ID={manifest.get('publication_id')}")
        print(f"PUBLISHED_AT={manifest.get('published_at')}")
        print(f"PUBLISHED_OFFERS={manifest.get('offer_count')}")
        print(f"PUBLISHED_PLACES={manifest.get('place_count')}")
    return 0 if result.get("decision") != "refresh_failed" else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Promo Intelligence update coordinator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scheduled", help="Run only when the daily refresh is due")
    p.add_argument("--requester", default="promo_scheduler")
    p = sub.add_parser("on-demand", help="Request a bounded refresh; single-flight protected")
    p.add_argument("--requester", default="external_consumer")
    p.add_argument("--reason", default="fresh_data_requested")
    p = sub.add_parser("manual", help="Operator refresh through the same single-flight gate")
    p.add_argument("--requester", default="operator")
    p.add_argument("--reason", default="manual_refresh")
    sub.add_parser("status", help="Show update state and current published manifest")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        policy = load_policy(ROOT / "config" / "update_policy.json")
        print(json.dumps({"state": load_state(ROOT, policy), "published": load_manifest(ROOT)}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    result = request_refresh(ROOT, args.cmd.replace("-", "_"), requester=args.requester, reason=args.reason)
    return _print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
