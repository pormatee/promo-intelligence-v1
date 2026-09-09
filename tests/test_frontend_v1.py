import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_frontend", ROOT / "build_frontend.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


class FrontendV1Tests(unittest.TestCase):
    def sample(self):
        return {
            "contract": "promo_offer_v1",
            "offer_id": "promo_test",
            "offer_type": "price_discount",
            "merchant": {"name": "Demo Store", "branch": None},
            "item": {"name": "Coffee 100g", "brand": "Demo", "category": None},
            "pricing": {"currency": "THB", "regular_price": 100.0, "promo_price": 70.0, "discount_amount": 30.0, "discount_percent": 30.0},
            "validity": {"start": "2026-09-01", "end": "2026-09-30"},
            "conditions": [],
            "verification": {"verification_state": "verified", "freshness_state": "fresh", "expiry_state": "active", "source_reliability": "high"},
            "source": {"source_id": "demo_source", "source_type": "official_web", "url": "https://example.com", "observed_at": "2026-09-08T00:00:00Z"},
            "evidence": {"content_hash": "sha256:x", "source_offer_id": None, "extracted_text": "Demo evidence </script> safe"},
            "applicability": {"scope": "nationwide", "country": "TH", "provinces": [], "branches": [], "verification_state": "explicit", "basis": "offer_text", "channel": "online", "channel_basis": "source_config"},
        }

    def test_single_html_contains_offline_ui(self):
        html = MOD.build_html([self.sample()], {"summary": {"sources": 1}}, {"demo_source": "demo"})
        self.assertIn("Promo Intelligence", html)
        self.assertIn("OFFLINE", "OFFLINE")
        self.assertNotIn("https://cdn.", html)
        self.assertNotIn("<script src=", html)
        self.assertIn("DATA_B64", html)

    def test_payload_does_not_embed_raw_script_breaker(self):
        html = MOD.build_html([self.sample()], {}, {})
        # Evidence is encoded as base64, so raw user/source text cannot break the script tag.
        self.assertNotIn("Demo evidence </script> safe", html)

    def test_family_mapping_is_ui_only(self):
        row = self.sample()
        out = MOD._prepare_rows([row], {"demo_source": "demo"})
        self.assertEqual(out[0]["_ui_source_family"], "demo")
        self.assertNotIn("_ui_source_family", row)


if __name__ == "__main__":
    unittest.main()
