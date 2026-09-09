import importlib.util, json, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_promo_lab',ROOT/'build_promo_lab.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class PromoLabTests(unittest.TestCase):
    def docs(self):
        offer={'contract':'promo_offer_v1','offer_id':'o1','merchant':{'name':'Demo'},'item':{'name':'Item'},'pricing':{'promo_price':10,'regular_price':20,'discount_percent':50},'validity':{'start':'2026-09-01','end':'2026-09-30'},'applicability':{'scope':'nationwide','channel':'store'},'verification':{'verification_state':'verified','expiry_state':'active'},'source':{'url':'https://example.com'},'evidence':{},'merchant_place_ref':'m1','place_refs':[]}
        places=[{'contract':'promo_place_v1','place_id':'m1','record_kind':'merchant','merchant':{'name':'Demo'},'branch':{},'location':{},'precision':'merchant','search_terms':['demo'],'verification':{'verification_state':'verified'},'evidence':[],'updated_at':'2026-09-08T00:00:00Z'}, {'contract':'promo_place_v1','place_id':'b1','record_kind':'branch','parent_place_id':'m1','merchant':{'name':'Demo'},'branch':{'name':'Demo Branch'},'location':{'province':'Prachinburi','province_raw':'ปราจีนบุรี'},'precision':'province','search_terms':['demo branch'],'verification':{'verification_state':'verified'},'evidence':[],'updated_at':'2026-09-08T00:00:00Z'}]
        manifest={'contract':'promo_published_manifest_v1','publication_id':'pub_test','published_at':'2026-09-08T00:00:00Z','offer_contract':'promo_offer_v1','place_contract':'promo_place_v1','offer_count':1,'place_count':2,'branch_place_count':1,'merchant_branch_index_count':1,'policy':{'read_only':True,'branch_directory_not_offer_applicability':True}}
        index={'contract':'promo_place_index_v1','merchant_branches':{'m1':['b1']}}
        return manifest,[offer],places,index
    def test_html_has_separate_lab_semantics(self):
        m,o,p,i=self.docs(); html=mod.build_html(m,o,p,i)
        self.assertIn('Promo Intelligence Lab',html); self.assertIn('Read-only',html); self.assertIn('Place Directory',html); self.assertIn('branch_directory_not_offer_applicability',html)
    def test_main_consistency_gate_and_build(self):
        m,o,p,i=self.docs()
        with tempfile.TemporaryDirectory() as td:
            d=Path(td); pub=d/'pub'; pub.mkdir(); (pub/'manifest.json').write_text(json.dumps(m),encoding='utf-8'); (pub/'promo_offer_v1.jsonl').write_text(json.dumps(o[0])+'\n',encoding='utf-8'); (pub/'promo_place_v1.jsonl').write_text('\n'.join(json.dumps(x) for x in p)+'\n',encoding='utf-8'); (pub/'merchant_branch_index_v1.json').write_text(json.dumps(i),encoding='utf-8')
            out=d/'lab.html'; old=mod.ROOT; mod.ROOT=d
            try:
                import sys; argv=sys.argv; sys.argv=['x','--published-dir',str(pub),'--output',str(out)]
                try:self.assertEqual(mod.main(),0)
                finally:sys.argv=argv
            finally:mod.ROOT=old
            self.assertTrue(out.exists()); self.assertGreater(out.stat().st_size,1000)
if __name__=='__main__': unittest.main()
