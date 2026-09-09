import unittest
from datetime import datetime, timezone
from promo_intelligence.verify import verify_offer

SOURCE={"reliability":"high"}
NOW=datetime(2026,9,7,12,0,tzinfo=timezone.utc)
OBS="2026-09-07T12:00:00Z"

class VerifyTest(unittest.TestCase):
    def base(self, **kw):
        d={"start":"2026-09-01","end":"2026-09-30","regular_price":87.0,"promo_price":69.0,"evidence_excerpt":"evidence"}
        d.update(kw); return d
    def test_active_fresh(self):
        v=verify_offer(self.base(),SOURCE,OBS,NOW)
        self.assertEqual(v["expiry_state"],"active")
        self.assertEqual(v["freshness_state"],"fresh")
        self.assertEqual(v["verification_state"],"verified")
    def test_expired(self):
        v=verify_offer(self.base(end="2026-09-01"),SOURCE,OBS,NOW)
        self.assertEqual(v["expiry_state"],"expired")
    def test_missing_expiry(self):
        v=verify_offer(self.base(end=None),SOURCE,OBS,NOW)
        self.assertEqual(v["expiry_state"],"unknown")
        self.assertEqual(v["verification_state"],"partial")
    def test_invalid_discount_price(self):
        v=verify_offer(self.base(regular_price=50.0,promo_price=60.0),SOURCE,OBS,NOW)
        self.assertEqual(v["verification_state"],"rejected")
