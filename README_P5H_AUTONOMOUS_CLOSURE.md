# Promo Intelligence — P5H Applicability Autonomous Closure Loop

## Purpose
One command runs the conservative applicability enrichment/discovery chain until it reaches a stable state or a hard iteration bound. This removes the need to manually run P5F/P5G/build/coverage steps one by one.

## Command
```bash
python applicability_autoclose_loop.py
```

Default maximum is 3 iterations (hard-capped at 5). To choose a smaller/larger bounded value:
```bash
P5H_MAX_ITERATIONS=3 python applicability_autoclose_loop.py
```

## Per iteration
1. P5F direct/raw attached-evidence discovery.
2. P5G same-official-host detail/terms discovery.
3. Measure actionable unknown count and exact backlog signature.
4. Stop immediately when all are resolved or when no evidence-backed progress is possible.

After discovery stabilizes it rebuilds the Published Read Model and standalone Consumer once, then prints area coverage and remaining backlog.

## Safe stop semantics
- `ALL_RESOLVED`: no actionable local-area unknown remains.
- `STABLE_EVIDENCE_EXHAUSTED`: the same unknown backlog remains and neither P5F nor P5G discovered evidence. This is a successful fail-closed closure, not an error.
- `MAX_ITERATIONS_REACHED`: bounded stop; unknown remains and manual review/new source strategy may be needed.

The loop does **not** broaden evidence policy: no guessing from merchant branch existence, no online→local promotion, no external hosts, no login/cookie/CAPTCHA/proxy/anti-bot bypass.
