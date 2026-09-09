import importlib.util, pathlib, unittest, json, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('b', ROOT/'build_promo_consumer.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

class T(unittest.TestCase):
    def offer(self, oid, *, scope='unknown', channel='store', province=None, place_refs=None, merchant_ref='m1'):
        loc=[] if not province else [{'province':province}]
        return {
            'offer_id':oid,'offer_type':'price_discount','merchant':{'name':'M'},'item':{'name':oid},
            'pricing':{},'validity':{},'conditions':[],
            'verification':{'verification_state':'verified'},
            'source':{'source_id':'s'},'evidence':{'price_fields':{}},
            'applicability':{'scope':scope,'channel':channel},'geography':{'locations':loc},
            'place_refs':place_refs or [],'merchant_place_ref':merchant_ref,
        }
    def place(self, pid, province):
        return {'place_id':pid,'record_kind':'branch','merchant':{'name':'M'},'branch':{'name':pid},'location':{'province':province},'verification':{'state':'verified'},'evidence':[]}

    def test_explicit_province_is_local(self):
        rows,_=b.prepare_consumer_offers([self.offer('o1',province='ปราจีนบุรี')])
        rows=b.attach_consumer_area_semantics(rows,[])
        self.assertEqual(rows[0]['_consumer_area']['local_provinces'], ['ปราจีนบุรี'])
        self.assertIn('east', rows[0]['_consumer_area']['local_regions'])

    def test_direct_place_ref_can_supply_local_province(self):
        rows,_=b.prepare_consumer_offers([self.offer('o1',place_refs=['p1'])])
        places=b.prepare_consumer_places([self.place('p1','ชลบุรี')])
        rows=b.attach_consumer_area_semantics(rows,places)
        self.assertEqual(rows[0]['_consumer_area']['local_provinces'], ['ชลบุรี'])

    def test_merchant_directory_does_not_imply_offer_applicability(self):
        rows,_=b.prepare_consumer_offers([self.offer('o1',merchant_ref='m1')])
        places=b.prepare_consumer_places([self.place('p1','ปราจีนบุรี')])
        rows=b.attach_consumer_area_semantics(rows,places)
        self.assertEqual(rows[0]['_consumer_area']['local_provinces'], [])
        h=b.build_html({'publication_id':'x'},[self.offer('o1',merchant_ref='m1')],[self.place('p1','ปราจีนบุรี')],{'merchant_branches':{'m1':['p1']}})
        # Branch directory can remain in payload for browse, but must not be used as area inference in JS.
        self.assertNotIn("merchant_place_ref&&IDX.merchant_branches", h)

    def test_nationwide_is_explicit_flag_not_77_fake_local_provinces(self):
        rows,_=b.prepare_consumer_offers([self.offer('o1',scope='nationwide')])
        rows=b.attach_consumer_area_semantics(rows,[])
        self.assertEqual(rows[0]['_consumer_area']['local_provinces'], [])
        self.assertTrue(rows[0]['_consumer_area']['nationwide'])

    def test_area_breakdown_ui_present(self):
        h=b.build_html({'publication_id':'x'},[],[],{})
        self.assertIn('id="areaBreakdown"',h)
        self.assertIn('ยืนยันในพื้นที่',h)
        self.assertIn('ออนไลน์ไม่ถูกนับเป็นโปรของจังหวัดโดยอัตโนมัติ',h)
        self.assertIn("PROMO_CONSUMER_VERSION=1.8", (ROOT/'build_promo_consumer.py').read_text())

if __name__=='__main__': unittest.main()
