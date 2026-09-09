import json
import tempfile
import unittest
from pathlib import Path

from promo_intelligence.contract import build_offer, validate_offer
from promo_intelligence.extract import extract
from promo_intelligence.normalize import normalize_candidate
from promo_intelligence.price_integrity import evaluate_candidate_price_integrity, sanitize_offer_pricing
from promo_intelligence.published import publish_snapshot


class PriceIntegrityTests(unittest.TestCase):
    def test_unsupported_regular_price_is_removed(self):
        c={
            'item_name':'HISENSE TV', 'merchant_name':'Power Buy',
            'promo_price_raw':8900.0, 'regular_price_raw':101999.0,
            'evidence_excerpt':'HISENSE TV | ฿8,900.00 | ผ่อน 0%',
            'validity_raw':'', 'conditions':[],
        }
        n=normalize_candidate(c)
        self.assertEqual(n['promo_price'],8900.0)
        self.assertIsNone(n['regular_price'])
        self.assertIsNone(n['discount_percent'])
        self.assertIn('regular_price_without_numeric_evidence',n['price_integrity']['anomalies'])

    def test_unsupported_promo_price_is_rejected_at_price_gate(self):
        c={
            'item_name':'TV', 'merchant_name':'Power Buy',
            'promo_price_raw':8900.0, 'regular_price_raw':12990.0,
            'evidence_excerpt':'TV | ฿12,990', 'validity_raw':'', 'conditions':[],
        }
        n=normalize_candidate(c)
        self.assertIsNone(n['promo_price'])
        self.assertEqual(n['price_integrity']['state'],'rejected')

    def test_normal_evidence_backed_pair_is_kept(self):
        c={
            'item_name':'Air Fryer', 'merchant_name':'Power Buy',
            'promo_price_raw':2490.0, 'regular_price_raw':3490.0,
            'evidence_excerpt':'Air Fryer | ฿2,490 | ฿3,490', 'validity_raw':'', 'conditions':[],
        }
        n=normalize_candidate(c)
        self.assertEqual(n['regular_price'],3490.0)
        self.assertEqual(n['promo_price'],2490.0)
        self.assertAlmostEqual(n['discount_percent'],28.65)

    def test_extreme_discount_without_explicit_percent_is_suppressed(self):
        c={
            'item_name':'TV', 'merchant_name':'Power Buy',
            'promo_price_raw':8900.0, 'regular_price_raw':101999.0,
            'evidence_excerpt':'TV | ฿8,900 | ฿101,999', 'validity_raw':'', 'conditions':[],
        }
        n=normalize_candidate(c)
        self.assertEqual(n['promo_price'],8900.0)
        self.assertIsNone(n['regular_price'])
        self.assertIn('extreme_discount_without_explicit_percent_evidence',n['price_integrity']['anomalies'])

    def test_extreme_discount_with_matching_explicit_percent_can_survive(self):
        c={
            'item_name':'Clearance TV', 'merchant_name':'Power Buy',
            'promo_price_raw':8900.0, 'regular_price_raw':101999.0,
            'evidence_excerpt':'Clearance TV | ฿8,900 | ฿101,999 | ลด 91%', 'validity_raw':'', 'conditions':[],
            'price_evidence':{
                'block_text':'Clearance TV | ฿8,900 | ฿101,999 | ลด 91%',
                'promo_price_text':'฿8,900','regular_price_text':'฿101,999','same_product_block':True,
            }
        }
        n=normalize_candidate(c)
        self.assertEqual(n['regular_price'],101999.0)
        self.assertGreater(n['discount_percent'],90)

    def test_generic_grid_never_crosses_into_next_product(self):
        raw='''<html><body>
        <h2>HISENSE TV 43</h2><div>฿8,900</div><div>ผ่อน 0%</div>
        <h2>Premium TV 85</h2><div>฿101,999</div><div>฿129,999</div>
        </body></html>'''
        rows=extract(raw,'generic_dual_price_grid_v1',{'merchant':'Power Buy'})
        # First product has one price only, so it must not borrow the next product's price.
        self.assertFalse(any(x['item_name']=='HISENSE TV 43' for x in rows))
        premium=next(x for x in rows if x['item_name']=='Premium TV 85')
        self.assertEqual(premium['promo_price_raw'],101999.0)
        self.assertEqual(premium['regular_price_raw'],129999.0)
        self.assertTrue(premium['price_evidence']['same_product_block'])

    def test_existing_offer_sanitizer_fixes_observed_unsupported_regular(self):
        o={
            'contract':'promo_offer_v1','offer_id':'promo_x','offer_type':'price_discount',
            'merchant':{'name':'Power Buy','branch':None},'item':{'name':'HISENSE TV','brand':None,'category':None},
            'pricing':{'currency':'THB','regular_price':101999.0,'promo_price':8900.0,'discount_amount':93099.0,'discount_percent':91.27},
            'validity':{'start':None,'end':None},'conditions':[],
            'verification':{'verification_state':'partial','freshness_state':'fresh','expiry_state':'unknown','source_reliability':'high'},
            'source':{'source_id':'p','source_type':'official_web','url':'https://example.test','observed_at':'2026-09-08T00:00:00Z'},
            'evidence':{'content_hash':'sha256:x','source_offer_id':None,'extracted_text':'HISENSE TV | ฿8,900.00 | ผ่อน 0%'},
        }
        s=sanitize_offer_pricing(o)
        self.assertEqual(s['offer_type'],'special_price')
        self.assertEqual(s['pricing']['promo_price'],8900.0)
        self.assertIsNone(s['pricing']['regular_price'])
        self.assertIsNone(s['pricing']['discount_percent'])
        self.assertEqual(validate_offer(s),[])

    def test_published_read_model_sanitizes_old_rows_defense_in_depth(self):
        o={
            'contract':'promo_offer_v1','offer_id':'promo_x','offer_type':'price_discount',
            'merchant':{'name':'Power Buy','branch':None},'item':{'name':'HISENSE TV','brand':None,'category':None},
            'pricing':{'currency':'THB','regular_price':101999.0,'promo_price':8900.0,'discount_amount':93099.0,'discount_percent':91.27},
            'validity':{'start':'2026-09-01','end':'2099-09-30'},'conditions':[],
            'verification':{'verification_state':'partial','freshness_state':'fresh','expiry_state':'active','source_reliability':'high'},
            'source':{'source_id':'p','source_type':'official_web','url':'https://example.test','observed_at':'2026-09-08T00:00:00Z'},
            'evidence':{'content_hash':'sha256:x','source_offer_id':None,'extracted_text':'HISENSE TV | ฿8,900.00'},
            'merchant_place_ref':'place_m','place_refs':[],
        }
        place={'contract':'promo_place_v1','place_id':'place_m','record_kind':'merchant','merchant_name':'Power Buy','branch_name':None,'aliases':[],'parent_place_id':None,'geography':{'country':'TH','province':None,'district':None,'subdistrict':None,'address':None,'postal_code':None,'latitude':None,'longitude':None,'precision':'unknown'},'verification':{'verification_state':'verified'},'evidence':[]}
        with tempfile.TemporaryDirectory() as td:
            manifest,pub=publish_snapshot(td,[o],[place],now='2026-09-09T00:00:00Z')
        self.assertEqual(len(pub),1)
        self.assertIsNone(pub[0]['pricing']['regular_price'])
        self.assertIsNone(pub[0]['pricing']['discount_percent'])
        self.assertTrue(manifest['policy']['price_evidence_integrity_gate'])


if __name__=='__main__': unittest.main()
