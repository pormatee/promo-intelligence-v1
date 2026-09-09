import json
import unittest
from pathlib import Path
from promo_intelligence.extract import extract
from promo_intelligence.normalize import normalize_candidate, normalize_validity
from promo_intelligence.applicability import resolve_applicability

ROOT = Path(__file__).resolve().parents[1]

class P4ScaleTest(unittest.TestCase):
    def test_numeric_date_range(self):
        self.assertEqual(normalize_validity('03/09/2026 - 09/09/2026'), ('2026-09-03','2026-09-09'))

    def test_expiry_only(self):
        self.assertEqual(normalize_validity('หมดอายุ :30-09-2026'), (None,'2026-09-30'))

    def test_daily_dot_date(self):
        self.assertEqual(normalize_validity('08.09.26 | 00:01'), ('2026-09-08','2026-09-08'))

    def test_generic_dual_price_grid(self):
        raw=(ROOT/'tests/fixtures/p4_product_grid_sample.html').read_text(encoding='utf-8')
        rows=extract(raw,'generic_dual_price_grid_v1',{'merchant':'Power Buy'})
        self.assertEqual(len(rows),2)
        row=next(x for x in rows if x['item_name'].startswith('PHILIPS'))
        self.assertEqual(row['promo_price_raw'],2490.0)
        self.assertEqual(row['regular_price_raw'],3490.0)

    def test_brand_discount_cards(self):
        raw=(ROOT/'tests/fixtures/p4_brand_cards_sample.html').read_text(encoding='utf-8')
        rows=extract(raw,'brand_discount_cards_v1',{'merchant':'Watsons Thailand'})
        self.assertEqual(len(rows),2)
        self.assertTrue(all(x['offer_type_hint']=='coupon' for x in rows))
        n=normalize_candidate(rows[0])
        self.assertEqual(n['start'],'2026-08-27')
        self.assertEqual(n['end'],'2026-09-23')

    def test_campaign_list_and_nationwide_evidence(self):
        raw=(ROOT/'tests/fixtures/p4_campaign_sample.html').read_text(encoding='utf-8')
        rows=extract(raw,'campaign_list_v1',{'merchant':'Test Merchant'})
        self.assertGreaterEqual(len(rows),3)
        nationwide=next(x for x in rows if 'แคมเปญทั่วประเทศ' in x['item_name'])
        app=resolve_applicability(nationwide, {'applicability':{'scope':'unknown'}})
        self.assertEqual(app['scope'],'nationwide')

    def test_coupon_cards(self):
        raw=(ROOT/'tests/fixtures/p4_coupon_sample.html').read_text(encoding='utf-8')
        rows=extract(raw,'coupon_cards_v1',{'merchant':'ALL Online'})
        self.assertGreaterEqual(len(rows),2)
        norms=[normalize_candidate(x) for x in rows]
        self.assertTrue(any(x['end']=='2026-09-30' for x in norms))

    def test_shipping_tiers(self):
        raw=(ROOT/'tests/fixtures/p4_shipping_sample.html').read_text(encoding='utf-8')
        rows=extract(raw,'shipping_tiers_v1',{'merchant':'Dohome','validity_raw':'1 July 2026 - 30 September 2026'})
        self.assertEqual(len(rows),2)
        self.assertEqual(normalize_candidate(rows[0])['end'],'2026-09-30')

    def test_registry_has_13_families_and_23_sources(self):
        sources=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
        self.assertEqual(len(sources),23)
        self.assertGreaterEqual(len({x.get('family') for x in sources}),13)
        self.assertTrue(all(x.get('source_type')=='official_web' for x in sources))

if __name__=='__main__': unittest.main()
