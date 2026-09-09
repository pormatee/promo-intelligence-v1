# Promo Intelligence — P4 Wave C Autonomous Recovery

Wave C turns the remaining P4 quality/recovery work into one bounded autonomous loop for Android + Termux.

## Verified baseline entering Wave C

- Sources: 23
- Fetched: 20
- Fetch failed: 3
- Exported: 430
- Location unknown actionable: 20
- Known live issues: Watsons 2x HTTP 403, ALL Online flash-sale timeout, Tops RTE source fetches but extracts 0.

## What Wave C changes

- Adds bounded official-source recovery: primary URL -> optional normal `curl` client -> configured alternate official URL.
- Never uses login, cookies, CAPTCHA solving, proxies, anti-bot bypass, or non-official mirrors.
- Classifies exhausted 401/403/451 official fallbacks as external hard blockers.
- Gives ALL Online Flash Sale a larger source-specific timeout plus hostname alternate.
- Adds Tops product-grid V2 for price/promo text split across multiple DOM lines.
- Adds official Tops zero-offer fallback pages, only used when the primary page yields 0 offers.
- Improves exact dedup so a core-identical offer with explicit location evidence can replace `unknown` while preserving corroborating evidence.
- Adds recovery/hard-block diagnostics.
- Adds `autonomous_wave_c.py` to run regression -> live -> diagnose -> bounded safe autofix -> rerun -> select best result.

## One command

After installing this overlay in `~/promo-intelligence-v1`:

```bash
python autonomous_wave_c.py
```

The runner performs up to 3 live iterations. It may increase timeout only for non-hard-block network failures, up to a bounded maximum. It stores every iteration under `output/wave_c_iter*.jsonl` and restores the best iteration as `output/promo_offer_v1.jsonl`.

Successful closure prints:

```text
WAVE_C_RESULT=PASS
PASS_MODE=CLEAN
```

or, when the system is healthy but an official site still blocks public automated HTTP access:

```text
WAVE_C_RESULT=PASS
PASS_MODE=DEGRADED_EXTERNAL_BLOCKERS
HARD_BLOCK_SOURCE=...
```

If a safe internal recovery path remains unresolved after the bounded loop, it stops instead of looping forever:

```text
WAVE_C_RESULT=HARD_BLOCK
HARD_BLOCK_REASON=SAFE_AUTONOMOUS_RECOVERY_EXHAUSTED
```

## Closure gates

- 23 configured sources retained
- >= 11 source families still yielding offers
- no contract errors
- nationwide geographic reach retained
- 0 zero-offer sources
- no unresolved internal fetch/extract errors
- fetch failures do not exceed verified Wave B baseline (3)
- actionable location unknown does not exceed Wave B baseline (20)
- exported unique offers do not collapse below 400 (allows legitimate stronger dedup from baseline 430)

## Development regression

Wave C clean development tree passes 53 unit/regression tests plus both fixture pipelines.
