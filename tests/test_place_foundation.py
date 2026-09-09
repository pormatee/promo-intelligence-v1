import copy
import json
import tempfile
import unittest
from pathlib import Path

from promo_intelligence.contract import validate_offer
from promo_intelligence.place_master import build_place_master, validate_place


def offer(merchant="Demo Mart", branch="North Branch", province="Prachinburi", district="Mueang Prachinburi", address="99 Demo Road", source_id="demo"):
    loc = {
        "province": province, "province_raw": province, "district": district,
        "subdistrict": None, "branch_name": branch, "address": address,
        "postal_code": "25000", "latitude": None, "longitude": None,
        "verification_state": "explicit", "basis": "offer_text",
        "evidence_excerpt": f"{branch} {address} {district} {province} 25000",
        "granularity": "address",
    }
    return {
        "contract": "promo_offer_v1", "offer_id": "promo_demo", "offer_type": "price_discount",
        "merchant": {"name": merchant, "branch": None},
        "item": {"name": "Item", "brand": None, "category": None},
        "pricing": {"currency": "THB", "regular_price": 100.0, "promo_price": 80.0, "discount_amount": 20.0, "discount_percent": 20.0},
        "validity": {"start": "2026-09-01", "end": "2026-09-30"},
        "conditions": [],
        "applicability": {"scope": "branch_specific", "country": "TH", "provinces": [province], "branches": [branch], "verification_state": "explicit", "basis": "offer_text", "channel": "store", "channel_basis": "offer_text"},
        "geography": {"country": "TH", "detail_state": "explicit", "best_granularity": "address", "locations": [loc]},
        "verification": {"verification_state": "verified", "freshness_state": "fresh", "expiry_state": "active", "source_reliability": "high"},
        "source": {"source_id": source_id, "source_type": "official_web", "url": f"https://example.test/{source_id}", "observed_at": "2026-09-08T00:00:00Z"},
        "evidence": {"content_hash": "sha256:abc", "source_offer_id": None, "extracted_text": loc["evidence_excerpt"]},
    }


class PlaceFoundationTest(unittest.TestCase):
    def test_generic_merchant_and_branch_records_and_offer_refs(self):
        enriched, places, stats = build_place_master([offer()], now="2026-09-08T00:00:00Z")
        self.assertEqual(stats["merchant_places"], 1)
        self.assertEqual(stats["branch_places"], 1)
        self.assertTrue(enriched[0]["merchant_place_ref"].startswith("place_"))
        self.assertEqual(len(enriched[0]["place_refs"]), 1)
        self.assertFalse(validate_offer(enriched[0]))
        self.assertTrue(all(not validate_place(p) for p in places))
        branch = next(p for p in places if p["record_kind"] == "branch")
        self.assertEqual(branch["location"]["district"], "Mueang Prachinburi")
        self.assertEqual(branch["location"]["address"], "99 Demo Road")

    def test_same_branch_merges_evidence_but_id_stays_stable(self):
        a = offer(source_id="s1")
        b = offer(source_id="s2")
        enriched, places, stats = build_place_master([a, b], now="2026-09-08T00:00:00Z")
        self.assertEqual(stats["branch_places"], 1)
        self.assertEqual(enriched[0]["place_refs"], enriched[1]["place_refs"])
        branch = next(p for p in places if p["record_kind"] == "branch")
        self.assertEqual(branch["verification"]["source_count"], 2)

    def test_distinct_branches_do_not_merge(self):
        a = offer(branch="North Branch", address="99 Demo Road")
        b = offer(branch="South Branch", address="88 Other Road", source_id="s2")
        enriched, places, stats = build_place_master([a, b], now="2026-09-08T00:00:00Z")
        self.assertEqual(stats["branch_places"], 2)
        self.assertNotEqual(enriched[0]["place_refs"], enriched[1]["place_refs"])

    def test_nationwide_offer_does_not_create_fake_branch(self):
        x = offer()
        x["applicability"].update({"scope": "nationwide", "provinces": [], "branches": []})
        x["geography"] = {"country": "TH", "detail_state": "nationwide", "best_granularity": "nationwide", "locations": []}
        enriched, places, stats = build_place_master([x], now="2026-09-08T00:00:00Z")
        self.assertEqual(stats["merchant_places"], 1)
        self.assertEqual(stats["branch_places"], 0)
        self.assertEqual(enriched[0]["place_refs"], [])

    def test_operator_aliases_are_additive_not_brand_hardcoded(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "aliases.json"
            p.write_text(json.dumps({"merchants": {"Demo Mart": ["DM", "เดโมมาร์ท"]}, "branches": {"Demo Mart|North Branch": ["สาขาเหนือ"]}}), encoding="utf-8")
            _, places, _ = build_place_master([offer()], alias_config_path=p, now="2026-09-08T00:00:00Z")
            merchant = next(x for x in places if x["record_kind"] == "merchant")
            branch = next(x for x in places if x["record_kind"] == "branch")
            self.assertIn("DM", merchant["merchant"]["aliases"])
            self.assertIn("สาขาเหนือ", branch["branch"]["aliases"])


if __name__ == "__main__": unittest.main()
