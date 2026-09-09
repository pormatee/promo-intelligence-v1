import unittest
from pathlib import Path
from promo_intelligence.pipeline import run_fixture

ROOT=Path(__file__).resolve().parents[1]
class PipelineTest(unittest.TestCase):
    def test_real_structure_fixture(self):
        offers,stats=run_fixture(ROOT)
        self.assertEqual(stats["sources"],1)
        self.assertGreaterEqual(stats["candidates"],1)
        o=offers[0]
        self.assertEqual(o["merchant"]["name"],"Mister Donut")
        self.assertEqual(o["pricing"]["promo_price"],69.0)
        self.assertEqual(o["pricing"]["regular_price"],87.0)
        self.assertEqual(o["validity"]["end"],"2026-09-30")
        self.assertEqual(o["verification"]["expiry_state"],"active")
        self.assertEqual(o["applicability"]["scope"],"unknown")
        self.assertEqual(stats["location_unknown"], len(offers))
