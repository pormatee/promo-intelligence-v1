from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .contract import validate_offer
from .pipeline import run_fixture, run_live, write_jsonl


def _root() -> Path:
    # Installed editable from repo is the intended P0 mode.
    return Path(__file__).resolve().parents[2]


def _report(offers: list[dict], stats: dict, output: Path) -> int:
    errors = sum(bool(validate_offer(x)) for x in offers)
    trusted = sum(x["verification"]["verification_state"] in {"verified", "partial"} for x in offers)
    write_jsonl(output, offers)
    print(f"SOURCE_FOUND={stats['sources']}")
    print(f"FETCHED={stats['fetched']}")
    print(f"PROMO_CANDIDATES={stats['candidates']}")
    print(f"NORMALIZED={stats['normalized']}")
    print(f"TRUSTED_OR_PARTIAL={trusted}")
    print(f"EXPORTED={len(offers)}")
    print("CONTRACT=promo_offer_v1")
    print(f"CONTRACT_ERRORS={errors}")
    ok = stats['sources'] >= 1 and stats['fetched'] >= 1 and len(offers) >= 1 and errors == 0
    print("FINAL_RESULT=" + ("PASS" if ok else "FAIL"))
    print(f"OUTPUT={output}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="promo-intel")
    p.add_argument("command", choices=["run", "run-fixture"])
    args = p.parse_args(argv)
    root = _root()
    try:
        if args.command == "run":
            offers, stats = run_live(root)
            return _report(offers, stats, root / "output" / "promo_offer_v1.jsonl")
        offers, stats = run_fixture(root)
        return _report(offers, stats, root / "output" / "promo_offer_v1.fixture.jsonl")
    except Exception as exc:
        print(f"RUNTIME_ERROR={type(exc).__name__}: {exc}")
        print("FINAL_RESULT=FAIL")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
