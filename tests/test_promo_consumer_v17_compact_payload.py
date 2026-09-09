import importlib.util, pathlib, unittest, re, json
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('b', ROOT/'build_promo_consumer.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
class T(unittest.TestCase):
    def offer(self, raw='X'*200000):
        return {
            'offer_id':'o1','offer_type':'price_discount','merchant':{'name':'Power Buy'},
            'item':{'name':'TV'},'pricing':{'promo_price':8900,'regular_price':9990,'discount_percent':10,'verification_state':'verified'},
            'validity':{'start':'2026-09-01','end':'2026-09-30'},'conditions':[],
            'verification':{'verification_state':'verified','expiry_state':'active','price_verification_state':'verified'},
            'source':{'source_id':'pb','url':'https://example.com','observed_at':'2026-09-09T00:00:00Z'},
            'evidence':{'extracted_text':raw,'price_fields':{'promo_price':{'supported':True,'evidence_excerpt':'8,900'},'regular_price':{'supported':True,'evidence_excerpt':'9,990'}}},
            'applicability':{'scope':'unknown','channel':'online'},'geography':{'locations':[]},'place_refs':[],'merchant_place_ref':'m1'
        }
    def test_raw_large_evidence_not_embedded(self):
        h=b.build_html({'publication_id':'x'},[self.offer()],[],{'merchant_branches':{}})
        self.assertNotIn('X'*10000,h)
        self.assertIn('8,900',h)
    def test_compact_payload_is_small(self):
        h=b.build_html({'publication_id':'x'},[self.offer() for _ in range(10)],[],{'merchant_branches':{}})
        self.assertLess(len(h), 300000)
    def test_version_marker_present(self):
        h=b.build_html({'publication_id':'x'},[],[],{})
        self.assertIn("promoConsumerVersion='1.8'",h)
    def test_place_evidence_compacted_to_count(self):
        p={'place_id':'p1','record_kind':'branch','merchant':{'name':'M'},'branch':{'name':'B'},'location':{'province':'ปราจีนบุรี'},'verification':{'state':'verified'},'evidence':[{'x':'Y'*100000} for _ in range(3)]}
        h=b.build_html({'publication_id':'x'},[],[p],{})
        self.assertNotIn('Y'*1000,h)
        self.assertIn('evidence_count',h)
if __name__=='__main__':unittest.main()
