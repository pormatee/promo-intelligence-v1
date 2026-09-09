import unittest
from promo_intelligence.pipeline import run_fixture
from promo_intelligence.contract import validate_offer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class ContractTest(unittest.TestCase):
    def test_fixture_contract(self):
        offers,_=run_fixture(ROOT)
        self.assertGreaterEqual(len(offers),1)
        self.assertEqual(validate_offer(offers[0]),[])
        self.assertEqual(offers[0]["contract"],"promo_offer_v1")
