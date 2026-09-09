# Promo Intelligence P4 Wave B

Quality & Coverage Optimization overlay for the verified P4 Wave A baseline.

## Install on Termux

```bash
cd ~/promo-intelligence-v1
unzip -o ~/storage/downloads/promo-intelligence-p4-wave-b-overlay.zip
bash run_tests.sh
python promo_intel.py run
python show_diagnostics.py
```

Expected regression baseline: `Ran 48 tests ... OK` and fixture `FINAL_RESULT=PASS`.

Wave B does **not** claim that market coverage is complete. Geographic unknown remains unknown. Online-only offers are reported separately so an absent branch/province does not masquerade as a store-location quality defect.
