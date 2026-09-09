import unittest
from pathlib import Path
from promo_intelligence.extract import extract
from promo_intelligence.normalize import normalize_candidate, normalize_validity
from promo_intelligence.verify import verify_offer

ROOT=Path(__file__).resolve().parents[1]

class P3ExtractTest(unittest.TestCase):
    def test_thai_buddhist_date_full_month(self):
        self.assertEqual(normalize_validity('3 - 30 กันยายน 2569'), ('2026-09-03','2026-09-30'))

    def test_thai_buddhist_date_abbrev(self):
        self.assertEqual(normalize_validity('1 ก.ค. 2569 - 30 ก.ย. 2569'), ('2026-07-01','2026-09-30'))

    def test_thai_cross_month_without_first_year(self):
        self.assertEqual(normalize_validity('16 สิงหาคม - 30 กันยายน 2569'), ('2026-08-16','2026-09-30'))

    def test_tops_price_and_bundle(self):
        raw=(ROOT/'tests/fixtures/tops_product_grid_sample.html').read_text(encoding='utf-8')
        source={'validity_raw':'2 September 2026 - 15 September 2026'}
        rows=extract(raw,'tops_product_grid_v1',source)
        self.assertEqual(len(rows),2)
        price=next(x for x in rows if x['item_name'].startswith('สินค้า A'))
        self.assertEqual(price['promo_price_raw'],75.0)
        self.assertEqual(price['regular_price_raw'],100.0)
        bundle=next(x for x in rows if x['item_name'].startswith('สินค้า B'))
        self.assertEqual(bundle['offer_type_hint'],'bundle')
        self.assertIsNone(bundle['promo_price_raw'])

    def test_bundle_without_numeric_promo_can_verify(self):
        c={'item_name':'สินค้า B','offer_type_hint':'bundle','regular_price':None,'promo_price':None,
           'start':'2026-09-02','end':'2026-09-15','evidence_excerpt':'ซื้อ 2 จ่าย 1'}
        v=verify_offer(c,{'reliability':'high'},'2026-09-08T00:00:00Z')
        self.assertEqual(v['verification_state'],'verified')

    def test_bigc_multiple_coupon_tiers(self):
        raw=(ROOT/'tests/fixtures/bigc_coupon_sample.html').read_text(encoding='utf-8')
        rows=extract(raw,'bigc_coupon_terms_v1',{})
        self.assertEqual(len(rows),2)
        norm=[normalize_candidate(x) for x in rows]
        self.assertTrue(all(x['start']=='2026-09-03' and x['end']=='2026-09-30' for x in norm))

if __name__=='__main__': unittest.main()
