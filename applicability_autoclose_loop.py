#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OFFERS = ROOT / "output" / "promo_offer_v1.jsonl"


def read_offers(path: Path = OFFERS) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def actionable(o: dict) -> bool:
    app = o.get("applicability") or {}
    identity = o.get("offer_identity") or {}
    return (app.get("scope") == "unknown" and app.get("channel") != "online"
            and identity.get("state") != "rejected")


def actionable_signature(rows: list[dict]) -> str:
    keys = []
    for o in rows:
        if not actionable(o):
            continue
        source = o.get("source") or {}
        merchant = o.get("merchant") or {}
        item = o.get("item") or {}
        key = o.get("offer_id") or o.get("id") or "|".join([
            str(source.get("source_id") or ""),
            str(merchant.get("name") or ""),
            str(item.get("name") or ""),
        ])
        keys.append(str(key))
    body = "\n".join(sorted(keys)).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def metric(text: str, name: str, default: int = 0) -> int:
    m = re.findall(rf"^{re.escape(name)}=(-?\d+)\s*$", text, flags=re.M)
    return int(m[-1]) if m else default


def run_capture(script: str) -> str:
    cmd = [sys.executable, script]
    print("STEP=" + " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout or ""
    print(out, end="" if out.endswith("\n") else "\n", flush=True)
    if p.returncode:
        print("P5H_RESULT=FAIL")
        print("FAILED_STEP=" + " ".join(cmd))
        raise SystemExit(p.returncode)
    return out


def run_stream(script: str) -> None:
    cmd = [sys.executable, script]
    print("STEP=" + " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT)
    if p.returncode:
        print("P5H_RESULT=FAIL")
        print("FAILED_STEP=" + " ".join(cmd))
        raise SystemExit(p.returncode)


def stop_reason(before_count: int, after_count: int, before_sig: str, after_sig: str,
                p5f_discovered: int, p5g_discovered: int) -> str | None:
    if after_count == 0:
        return "ALL_RESOLVED"
    if after_sig == before_sig and p5f_discovered == 0 and p5g_discovered == 0:
        return "STABLE_EVIDENCE_EXHAUSTED"
    if after_count >= before_count and p5f_discovered == 0 and p5g_discovered == 0:
        return "NO_PROGRESS"
    return None


def main() -> int:
    try:
        max_iterations = int(os.environ.get("P5H_MAX_ITERATIONS", "3"))
    except ValueError:
        max_iterations = 3
    max_iterations = min(max(max_iterations, 1), 5)

    rows = read_offers()
    if not rows:
        print("P5H_RESULT=FAIL")
        print("REASON=NO_OFFERS")
        return 2

    initial_count = sum(actionable(x) for x in rows)
    initial_sig = actionable_signature(rows)
    print("=== P5H Applicability Autonomous Closure ===")
    print(f"MAX_ITERATIONS={max_iterations}")
    print(f"ACTIONABLE_UNKNOWN_INITIAL={initial_count}")

    total_f = total_g = 0
    reason = "MAX_ITERATIONS_REACHED"
    completed = 0

    for iteration in range(1, max_iterations + 1):
        before_rows = read_offers()
        before_count = sum(actionable(x) for x in before_rows)
        before_sig = actionable_signature(before_rows)
        print(f"\n=== P5H ITERATION {iteration} ===")
        print(f"ITERATION_UNKNOWN_BEFORE={before_count}")

        if before_count == 0:
            reason = "ALL_RESOLVED"
            break

        p5f = run_capture("discover_applicability.py")
        p5g = run_capture("discover_applicability_details.py")
        f_disc = metric(p5f, "APPLICABILITY_DISCOVERED")
        g_disc = metric(p5g, "DETAIL_APPLICABILITY_DISCOVERED")
        total_f += f_disc
        total_g += g_disc

        after_rows = read_offers()
        after_count = sum(actionable(x) for x in after_rows)
        after_sig = actionable_signature(after_rows)
        completed = iteration

        print(f"ITERATION_P5F_DISCOVERED={f_disc}")
        print(f"ITERATION_P5G_DISCOVERED={g_disc}")
        print(f"ITERATION_UNKNOWN_AFTER={after_count}")
        print(f"ITERATION_UNKNOWN_DELTA={after_count-before_count}")

        sr = stop_reason(before_count, after_count, before_sig, after_sig, f_disc, g_disc)
        if sr:
            reason = sr
            break

    # Rebuild once after the bounded discovery loop, then show the user-facing truth.
    run_stream("build_place_publish.py")
    run_stream("build_promo_consumer.py")
    run_stream("show_area_coverage.py")
    run_stream("show_detail_discovery_backlog.py")

    final_rows = read_offers()
    final_count = sum(actionable(x) for x in final_rows)
    final_sig = actionable_signature(final_rows)

    print("\n=== P5H FINAL ===")
    print(f"ITERATIONS_COMPLETED={completed}")
    print(f"ACTIONABLE_UNKNOWN_INITIAL={initial_count}")
    print(f"TOTAL_P5F_DISCOVERED={total_f}")
    print(f"TOTAL_P5G_DISCOVERED={total_g}")
    print(f"ACTIONABLE_UNKNOWN_FINAL={final_count}")
    print(f"ACTIONABLE_UNKNOWN_DELTA={final_count-initial_count}")
    print(f"BACKLOG_CHANGED={'TRUE' if final_sig != initial_sig else 'FALSE'}")
    print(f"STOP_REASON={reason}")
    if reason in {"STABLE_EVIDENCE_EXHAUSTED", "NO_PROGRESS"}:
        print("CLOSURE_STATE=SAFE_UNKNOWN_REMAINS")
    elif reason == "ALL_RESOLVED":
        print("CLOSURE_STATE=ALL_RESOLVED")
    else:
        print("CLOSURE_STATE=BOUNDED_STOP")
    print("P5H_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
