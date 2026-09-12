import importlib.util
import pathlib
import tempfile
import unittest
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('b',ROOT/'build_promo_consumer.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

class P8DStoreFirstConsumerTests(unittest.TestCase):
    def test_consumer_place_keeps_parent_merchant_id(self):
        p={'place_id':'branch_1','parent_place_id':'merchant_1','record_kind':'branch','merchant':{'name':'Shop'},'branch':{'name':'Prachinburi'},'location':{'province':'ปราจีนบุรี'},'verification':{'state':'verified'}}
        row=b.prepare_place_for_consumer(p)
        self.assertEqual(row['parent_place_id'],'merchant_1')

    def test_store_first_ui_present(self):
        h=b.build_html({'publication_id':'x'},[],[],{'merchant_branches':{}})
        self.assertIn('id="areaStoresSection"',h)
        self.assertIn('function confirmedOffersForPlace(p)',h)
        self.assertIn('ยังไม่พบโปรที่ยืนยัน',h)
        self.assertIn("if(!['store','omnichannel'].includes(a.channel))continue",h)

    def test_selected_branches_not_inferred(self):
        h=b.build_html({'publication_id':'x'},[],[],{'merchant_branches':{}})
        self.assertIn("else if(mid&&om===mid&&a.scope==='nationwide')ok=true",h)
        self.assertNotIn("a.scope==='selected_branches')ok=true",h)

    def test_published_place_directory_independent_of_offers(self):
        sys.path.insert(0,str(ROOT/'src'))
        from promo_intelligence.published import publish_snapshot, load_published_places
        place={'contract':'promo_place_v1','place_id':'branch_no_offer','record_kind':'branch','parent_place_id':'merchant_no_offer','merchant':{'name':'No Offer Shop'},'branch':{'name':'Prachinburi'},'location':{'country':'TH','province':'ปราจีนบุรี','district':None,'subdistrict':None,'address':'Test address','postal_code':None,'latitude':None,'longitude':None},'precision':'address','search_terms':[],'verification':{'state':'verified','source_count':1,'evidence_count':1},'evidence':[{'source_id':'locator','url':'https://example.test','observed_at':'2026-09-11T00:00:00Z','content_hash':'sha256:x','basis':'official_store_locator','evidence_excerpt':'official'}],'updated_at':'2026-09-11T00:00:00Z'}
        with tempfile.TemporaryDirectory() as td:
            manifest,_=publish_snapshot(td,[],[place],now='2026-09-11T00:00:00Z')
            rows=load_published_places(td)
        self.assertEqual(manifest['place_count'],1)
        self.assertEqual(rows[0]['place_id'],'branch_no_offer')
        self.assertTrue(manifest['policy']['place_directory_independent_of_offer_presence'])

if __name__=='__main__': unittest.main()
