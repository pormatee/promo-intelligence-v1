import unittest
from promo_intelligence.normalize import normalize_candidate, normalize_validity

class NormalizeTest(unittest.TestCase):
    def test_same_month_range(self):
        self.assertEqual(normalize_validity("1–30 September 2026"), ("2026-09-01", "2026-09-30"))
    def test_open_ended(self):
        self.assertEqual(normalize_validity("From 1 September 2026 onwards"), ("2026-09-01", None))
    def test_prices(self):
        c = normalize_candidate({"regular_price_raw":87.0,"promo_price_raw":69.0,"validity_raw":"1–30 September 2026"})
        self.assertEqual(c["discount_amount"], 18.0)
        self.assertEqual(c["discount_percent"], 20.69)
