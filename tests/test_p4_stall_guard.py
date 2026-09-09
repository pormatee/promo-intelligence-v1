import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.fetch import FetchResult
from promo_intelligence import pipeline


class StallGuardTests(unittest.TestCase):
    def test_live_fetches_overlap_and_progress_is_reported(self):
        sources = [
            {
                "source_id": f"s{i}", "url": f"https://example.invalid/{i}",
                "family": f"f{i}", "merchant": f"M{i}", "extractor": "dummy",
            }
            for i in range(6)
        ]
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_fetch(url, timeout=12):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return FetchResult(url, 200, "text/html", b"x", "2026-09-08T00:00:00Z", "sha256:x")

        def fake_process(source, body, observed_at, content_hash, now=None):
            return [], {"candidates": 0, "normalized": 0, "exportable": 0, "dedupe_removed": 0, "location_known": 0, "location_unknown": 0}

        messages = []
        with tempfile.TemporaryDirectory() as td, \
             patch.object(pipeline, "load_sources", return_value=sources), \
             patch.object(pipeline, "fetch_url", side_effect=fake_fetch), \
             patch.object(pipeline, "_process", side_effect=fake_process):
            stats_offers, stats = pipeline.run_live(td, on_progress=messages.append, max_workers=3)

        self.assertEqual(stats_offers, [])
        self.assertEqual(stats["fetched"], 6)
        self.assertGreaterEqual(max_active, 2)
        self.assertTrue(any(m.startswith("FETCH_PROGRESS=") for m in messages))


if __name__ == "__main__":
    unittest.main()
