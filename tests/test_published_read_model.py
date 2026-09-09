import copy
import json
import tempfile
import unittest
from pathlib import Path

from promo_intelligence.place_master import build_place_master
from promo_intelligence.published import load_manifest, load_published_offers, load_published_places, publish_snapshot
from test_place_foundation import offer


class PublishedReadModelTest(unittest.TestCase):
    def test_only_current_trusted_or_partial_offers_are_published(self):
        active = offer(source_id="active")
        expired = copy.deepcopy(active); expired["offer_id"]="expired"; expired["source"]["source_id"]="expired"; expired["verification"]["expiry_state"]="expired"
        stale = copy.deepcopy(active); stale["offer_id"]="stale"; stale["source"]["source_id"]="stale"; stale["verification"]["freshness_state"]="stale"
        rejected = copy.deepcopy(active); rejected["offer_id"]="rejected"; rejected["source"]["source_id"]="rejected"; rejected["verification"]["verification_state"]="rejected"
        enriched, places, _ = build_place_master([active, expired, stale, rejected], now="2026-09-08T00:00:00Z")
        with tempfile.TemporaryDirectory() as td:
            manifest, published = publish_snapshot(td, enriched, places, now="2026-09-08T01:00:00Z")
            self.assertEqual(len(published), 1)
            self.assertEqual(manifest["offer_count"], 1)
            self.assertTrue(manifest["policy"]["read_only"])
            self.assertEqual(len(load_published_offers(td)), 1)
            self.assertGreaterEqual(len(load_published_places(td)), 1)
            self.assertEqual(load_manifest(td)["publication_id"], manifest["publication_id"])

    def test_manifest_hashes_change_when_snapshot_changes(self):
        a, places_a, _ = build_place_master([offer(source_id="a")], now="2026-09-08T00:00:00Z")
        b_offer = offer(source_id="b"); b_offer["offer_id"] = "promo_b"; b_offer["item"]["name"] = "Other Item"
        b, places_b, _ = build_place_master([b_offer], now="2026-09-08T00:00:00Z")
        with tempfile.TemporaryDirectory() as td:
            ma, _ = publish_snapshot(td, a, places_a, now="2026-09-08T01:00:00Z")
            mb, _ = publish_snapshot(td, b, places_b, now="2026-09-08T02:00:00Z")
            self.assertNotEqual(ma["offer_sha256"], mb["offer_sha256"])
            self.assertNotEqual(ma["publication_id"], mb["publication_id"])


if __name__ == "__main__": unittest.main()
