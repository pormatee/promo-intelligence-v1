from __future__ import annotations
import argparse
from pathlib import Path

from .contract import validate_offer
from .coverage import coverage_summary
from .pipeline import run_fixture, run_live, run_nationwide_fixture, write_diagnostics, write_jsonl
from .quality import quality_summary
from .geo import geography_summary


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _report(offers: list[dict], stats: dict, output: Path) -> int:
    errors = sum(bool(validate_offer(x)) for x in offers)
    trusted = sum(x["verification"]["verification_state"] in {"verified", "partial"} for x in offers)
    coverage = coverage_summary(offers)
    quality = quality_summary(offers)
    geo = geography_summary(offers)
    diagnostics = output.with_suffix(".diagnostics.json")
    write_jsonl(output, offers)
    write_diagnostics(diagnostics, stats, offers)

    print(f"SOURCE_FOUND={stats['sources']}")
    print(f"FETCHED={stats['fetched']}")
    print(f"FETCH_FAILED={stats.get('fetch_failed', 0)}")
    print(f"FETCH_RETRIED={stats.get('fetch_retried', 0)}")
    print(f"FETCH_RECOVERED={stats.get('fetch_recovered', 0)}")
    print(f"HARD_BLOCK_SOURCES={len(stats.get('hard_block_sources', []))}")
    print(f"SOURCE_FAMILIES_CONFIGURED={stats.get('families_configured', 1)}")
    print(f"SOURCE_FAMILIES_WITH_OFFERS={stats.get('families_with_offers', 1 if offers else 0)}")
    print(f"SOURCES_WITH_OFFERS={stats.get('sources_with_offers', 1 if offers else 0)}")
    print(f"ZERO_OFFER_SOURCES={stats.get('zero_offer_sources', 0)}")
    print(f"ZERO_OFFER_RECOVERED={stats.get('zero_offer_recovered', 0)}")
    print(f"PROMO_CANDIDATES={stats['candidates']}")
    print(f"NORMALIZED={stats['normalized']}")
    print(f"DEDUP_REMOVED={stats.get('dedupe_removed', 0)}")
    print(f"LOCATION_KNOWN={stats.get('location_known', 0)}")
    print(f"LOCATION_UNKNOWN={stats.get('location_unknown', 0)}")
    print(f"LOCATION_UNKNOWN_ACTIONABLE={quality['location_unknown_actionable']}")
    print(f"GEO_KNOWN_OFFERS={geo['geography_known']}")
    print(f"DISTRICT_KNOWN_OFFERS={geo['district_known']}")
    print(f"SUBDISTRICT_KNOWN_OFFERS={geo['subdistrict_known']}")
    print(f"ADDRESS_KNOWN_OFFERS={geo['address_known']}")
    print(f"POSTAL_CODE_KNOWN_OFFERS={geo['postal_code_known']}")
    print(f"COORDINATES_KNOWN_OFFERS={geo['coordinates_known']}")
    print(f"BRANCH_NAME_KNOWN_OFFERS={geo['branch_name_known']}")
    print(f"ONLINE_CHANNEL_OFFERS={quality['online']}")
    print(f"STORE_CHANNEL_OFFERS={quality['store']}")
    print(f"OMNICHANNEL_OFFERS={quality['omnichannel']}")
    print(f"CHANNEL_UNKNOWN_OFFERS={quality['channel_unknown']}")
    print(f"NATIONWIDE_ACTIVE_OFFERS={coverage['nationwide_active_offers']}")
    print(f"PROVINCES_REACHED={coverage['reached_provinces']}")
    print(f"PROVINCE_TARGET={coverage['target_provinces']}")
    print("NATIONAL_GEOGRAPHIC_REACH=" + ("TRUE" if coverage["national_geographic_reach"] else "FALSE"))
    print("MARKET_COVERAGE_COMPLETE=FALSE")
    print(f"VERIFIED_OFFERS={quality['verified']}")
    print(f"PARTIAL_OFFERS={quality['partial']}")
    print(f"ACTIVE_OFFERS={quality['active']}")
    print(f"EXPIRED_OFFERS={quality['expired']}")
    print(f"EXPIRY_UNKNOWN_OFFERS={quality['expiry_unknown']}")
    print(f"CORROBORATED_OFFERS={quality['corroborated']}")
    print(f"TRUSTED_OR_PARTIAL={trusted}")
    print(f"MERCHANTS_WITH_OFFERS={len({(x.get('merchant') or {}).get('name') for x in offers if (x.get('merchant') or {}).get('name')})}")
    print(f"EXPORTED={len(offers)}")
    print("CONTRACT=promo_offer_v1")
    print(f"CONTRACT_ERRORS={errors}")

    for row in stats.get("source_errors", []):
        if row.get("stage") == "fetch":
            print(f"FETCH_FAILED_SOURCE={row.get('source_id')} ERROR={row.get('error_type')}")
        elif row.get("stage") == "extract":
            print(f"EXTRACT_FAILED_SOURCE={row.get('source_id')} ERROR={row.get('error_type')}")
    for sid in stats.get("zero_offer_source_ids", []):
        print(f"ZERO_OFFER_SOURCE={sid}")
    for sid in stats.get("hard_block_sources", []):
        print(f"HARD_BLOCK_SOURCE={sid}")

    ok = stats['sources'] >= 1 and stats['fetched'] >= 1 and len(offers) >= 1 and errors == 0
    print("FINAL_RESULT=" + ("PASS" if ok else "FAIL"))
    print(f"OUTPUT={output}")
    print(f"DIAGNOSTICS={diagnostics}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="promo-intel")
    p.add_argument("command", choices=["run", "run-fixture", "run-national-fixture"])
    args = p.parse_args(argv)
    root = _root()
    try:
        if args.command == "run":
            offers, stats = run_live(root, on_progress=print)
            return _report(offers, stats, root / "output" / "promo_offer_v1.jsonl")
        if args.command == "run-national-fixture":
            offers, stats = run_nationwide_fixture(root)
            return _report(offers, stats, root / "output" / "promo_offer_v1.national.fixture.jsonl")
        offers, stats = run_fixture(root)
        return _report(offers, stats, root / "output" / "promo_offer_v1.fixture.jsonl")
    except Exception as exc:
        print(f"RUNTIME_ERROR={type(exc).__name__}: {exc}")
        print("FINAL_RESULT=FAIL")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
