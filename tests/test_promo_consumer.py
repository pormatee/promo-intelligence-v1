import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_promo_consumer import build_html, main

class ConsumerTests(unittest.TestCase):
    def test_html_has_consumer_safety_semantics(self):
        h=build_html({'publication_id':'pub_x','published_at':'2026-09-09T00:00:00Z','offer_count':0,'place_count':0},{}, {}, {}) if False else build_html({'publication_id':'pub_x'},[],[],{'merchant_branches':{}})
        self.assertIn('Promo Finder',h)
        self.assertIn('Price Evidence Integrity',h)
        self.assertNotIn('LocalLife',h)
        self.assertNotIn('Promo Intelligence Lab',h)
    def test_builder_embeds_published_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); pub=root/'output'/'published'; pub.mkdir(parents=True)
            offer={'contract':'promo_offer_v1','offer_id':'o1','offer_type':'special_price','merchant':{'name':'Demo'},'item':{'name':'Demo Item'},'pricing':{'currency':'THB','regular_price':None,'promo_price':99,'discount_amount':None,'discount_percent':None,'verification_state':'verified','anomalies':[]},'validity':{'start':'2026-09-01','end':'2026-09-30'},'conditions':[],'verification':{'verification_state':'verified','expiry_state':'active','freshness_state':'fresh','price_verification_state':'verified'},'source':{'source_id':'demo','url':'https://example.com','observed_at':'2026-09-09T00:00:00Z'},'evidence':{'extracted_text':'฿99','price_fields':{'promo_price':{'supported':True,'evidence_excerpt':'฿99'},'regular_price':{'supported':False,'evidence_excerpt':None}}},'applicability':{'scope':'unknown','channel':'online'},'geography':{'locations':[]},'merchant_place_ref':'p1','place_refs':[]}
            place={'contract':'promo_place_v1','place_id':'p1','record_kind':'merchant','parent_place_id':None,'merchant':{'name':'Demo','aliases':['Demo']},'branch':{'name':None,'aliases':[]},'location':{'country':'TH','province':None,'district':None,'subdistrict':None,'address':None,'postal_code':None,'latitude':None,'longitude':None},'precision':'merchant','search_terms':['demo'],'verification':{'state':'partial'},'evidence':[]}
            (pub/'promo_offer_v1.jsonl').write_text(json.dumps(offer,ensure_ascii=False)+'\n',encoding='utf-8')
            (pub/'promo_place_v1.jsonl').write_text(json.dumps(place,ensure_ascii=False)+'\n',encoding='utf-8')
            (pub/'merchant_branch_index_v1.json').write_text(json.dumps({'contract':'promo_place_index_v1','merchant_branches':{}}),encoding='utf-8')
            (pub/'manifest.json').write_text(json.dumps({'contract':'promo_published_manifest_v1','publication_id':'pub_demo','published_at':'2026-09-09T00:00:00Z','offer_contract':'promo_offer_v1','place_contract':'promo_place_v1','offer_count':1,'place_count':1,'branch_place_count':0,'policy':{'read_only':True}}),encoding='utf-8')
            # Direct module functions are enough for isolated test; main ROOT remains module directory.
            from build_promo_consumer import load_json,load_jsonl,build_html
            h=build_html(load_json(pub/'manifest.json'),load_jsonl(pub/'promo_offer_v1.jsonl'),load_jsonl(pub/'promo_place_v1.jsonl'),load_json(pub/'merchant_branch_index_v1.json'))
            self.assertNotIn('__PAYLOAD__',h)
            self.assertIn('Promo Finder',h)
            self.assertGreater(len(h),10000)
    def test_technical_payload_is_hidden_from_display_fields(self):
        import re
        offer={'contract':'promo_offer_v1','offer_id':'raw1','offer_type':'coupon','merchant':{'name':'Big C Online'},'item':{'name':'{\"props\":{\"pageProps\":{\"envConfig\":{\"REDIS_URI\":\"unicorn.cache.amazonaws.com\"}}}}'},'pricing':{'currency':'THB','regular_price':None,'promo_price':None,'discount_amount':None,'discount_percent':None,'verification_state':'not_applicable','anomalies':[]},'validity':{'start':'2026-09-03','end':'2026-09-30'},'conditions':[],'verification':{'verification_state':'verified','expiry_state':'active','freshness_state':'fresh'},'source':{'source_id':'bigc','url':'https://example.com','observed_at':'2026-09-09T00:00:00Z'},'evidence':{'extracted_text':'{\"props\":{\"pageProps\":{\"REDIS_URI\":\"cache.amazonaws.com\"}}}'},'applicability':{'scope':'nationwide','channel':'online'},'geography':{'locations':[]},'merchant_place_ref':'p1','place_refs':[]}
        h=build_html({'publication_id':'pub_x'},[offer],[],{'merchant_branches':{}})
        m=re.search(r'<script id="payloadData" type="application/json">(.*?)</script>',h,re.S)
        self.assertIsNotNone(m)
        payload=json.loads(m.group(1))
        d=payload['offers'][0]['_consumer_display']
        self.assertEqual(d['title'],'คูปองจาก Big C Online')
        self.assertTrue(d['title_fallback'])
        self.assertTrue(d['technical_payload_hidden'])
        self.assertNotIn('REDIS_URI',d['title'])
        self.assertIsNone(d['evidence_text'])
        self.assertEqual(payload['display_stats']['title_fallback_offers'],1)
if __name__=='__main__':unittest.main()
