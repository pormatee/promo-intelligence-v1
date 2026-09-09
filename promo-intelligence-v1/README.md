# Promo Intelligence P0

Standalone prototype for discovering, extracting, normalizing and verifying promotion evidence.

## Hard boundary
- No PrachinLife imports.
- No PrachinLife database writes.
- No MSB/DQE dependency.
- No recommendation or ranking authority.
- External integration is output-only through `promo_offer_v1`.

## Core rules
1. No evidence -> no trusted offer.
2. Unknown stays unknown.
3. Source facts are normalized, never guessed.
4. Contract is versioned.

## Termux quick start (zero external Python dependencies)
```bash
pkg install python -y
chmod +x run_tests.sh
./run_tests.sh
python promo_intel.py run
```

`run_tests.sh` runs deterministic offline regression and contract/boundary checks.
`python promo_intel.py run` performs the real live fetch from enabled source(s) in `config/sources.json` and writes JSONL output.
No `pip install` is required for P0.

## P0 real source
The initial registry uses an official Lotus's September 2026 promotion page. The extractor is deliberately small and text-pattern based; expansion to more source adapters belongs after P0 PASS.
