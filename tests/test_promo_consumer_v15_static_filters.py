import unittest, re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_promo_consumer import build_html

class ConsumerV15StaticFilterTests(unittest.TestCase):
    def html(self):
        offers=[
            {'offer_id':'o1','offer_type':'price_discount','merchant':{'name':'Power Buy'},'item':{'name':'TV'},'pricing':{},'validity':{},'conditions':[], 'verification':{}, 'source':{}, 'evidence':{}, 'applicability':{}, 'geography':{'locations':[]}, 'place_refs':[]},
            {'offer_id':'o2','offer_type':'coupon','merchant':{'name':'Big C Online'},'item':{'name':'Coupon'},'pricing':{},'validity':{},'conditions':[], 'verification':{}, 'source':{}, 'evidence':{}, 'applicability':{}, 'geography':{'locations':[]}, 'place_refs':[]},
        ]
        places=[{'record_kind':'merchant','merchant':{'name':'Power Buy'}},{'record_kind':'merchant','merchant':{'name':'Big C Online'}}]
        return build_html({'publication_id':'pub_v15','published_at':'2026-09-09T00:00:00Z'},offers,places,{'merchant_branches':{}})

    def test_region_options_are_baked_into_html(self):
        h=self.html()
        block=re.search(r'<select id="region">(.*?)</select>',h,re.S).group(1)
        self.assertIn('ภาคตะวันออก', block)
        self.assertIn('ภาคเหนือ', block)
        self.assertGreaterEqual(block.count('<option'), 8)

    def test_all_77_provinces_are_baked_into_html(self):
        h=self.html()
        block=re.search(r'<select id="province">(.*?)</select>',h,re.S).group(1)
        self.assertIn('ปราจีนบุรี', block)
        self.assertIn('เชียงใหม่', block)
        self.assertIn('ภูเก็ต', block)
        self.assertEqual(block.count('<option'), 78)  # all + 77 provinces
        self.assertIn('<optgroup', block)

    def test_merchant_and_type_options_are_baked(self):
        h=self.html()
        merchant=re.search(r'<select id="merchant">(.*?)</select>',h,re.S).group(1)
        typ=re.search(r'<select id="type">(.*?)</select>',h,re.S).group(1)
        self.assertIn('Power Buy', merchant)
        self.assertIn('Big C Online', merchant)
        self.assertIn('price_discount', typ)
        self.assertIn('coupon', typ)

    def test_no_unresolved_option_placeholders(self):
        h=self.html()
        for token in ['__REGION_OPTIONS__','__PROVINCE_OPTIONS__','__MERCHANT_OPTIONS__','__TYPE_OPTIONS__','__PLACE_MERCHANT_OPTIONS__','__PLACE_PROVINCE_OPTIONS__']:
            self.assertNotIn(token,h)

    def test_js_dynamic_fill_is_dedupe_safe(self):
        h=self.html()
        self.assertIn("existing=new Set([...el.options].map(o=>o.value))",h)
        self.assertIn("if(existing.has(v))continue",h)

if __name__=='__main__':
    unittest.main()
