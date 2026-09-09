import unittest
from promo_intelligence.coverage import THAI_PROVINCES, coverage_summary


class CoverageTest(unittest.TestCase):
    def offer(self, scope="unknown", provinces=None, expiry="active"):
        return {
            "applicability": {"scope": scope, "provinces": provinces or []},
            "verification": {
                "verification_state": "verified", "freshness_state": "fresh", "expiry_state": expiry
            },
        }

    def test_thailand_has_77_targets(self):
        self.assertEqual(len(THAI_PROVINCES), 77)
        self.assertIn("Prachinburi", THAI_PROVINCES)

    def test_explicit_nationwide_reaches_77(self):
        c = coverage_summary([self.offer("nationwide")])
        self.assertEqual(c["reached_provinces"], 77)
        self.assertTrue(c["national_geographic_reach"])
        self.assertFalse(c["market_coverage_complete"])

    def test_unknown_location_reaches_zero(self):
        c = coverage_summary([self.offer("unknown")])
        self.assertEqual(c["reached_provinces"], 0)

    def test_expired_nationwide_does_not_count_current_reach(self):
        c = coverage_summary([self.offer("nationwide", expiry="expired")])
        self.assertEqual(c["reached_provinces"], 0)
