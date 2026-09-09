import unittest
from pathlib import Path
from promo_intelligence.pipeline import run_nationwide_fixture
from promo_intelligence.coverage import coverage_summary
from promo_intelligence.contract import validate_offer

ROOT=Path(__file__).resolve().parents[1]


class NationwidePipelineTest(unittest.TestCase):
    def test_real_source_shape_nationwide_fixture(self):
        offers,stats=run_nationwide_fixture(ROOT)
        self.assertEqual(stats["sources"],1)
        self.assertEqual(len(offers),1)
        o=offers[0]
        self.assertEqual(validate_offer(o),[])
        self.assertEqual(o["offer_type"],"coupon")
        self.assertIsNone(o["pricing"]["promo_price"])
        self.assertEqual(o["applicability"]["scope"],"nationwide")
        self.assertEqual(o["applicability"]["basis"],"offer_text")
        self.assertEqual(o["verification"]["verification_state"],"verified")
        self.assertEqual(o["verification"]["expiry_state"],"active")
        c=coverage_summary(offers)
        self.assertEqual(c["reached_provinces"],77)
        self.assertTrue(c["national_geographic_reach"])
