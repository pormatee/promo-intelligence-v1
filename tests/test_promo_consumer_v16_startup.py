import importlib.util, pathlib, unittest, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('b', ROOT/'build_promo_consumer.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
class T(unittest.TestCase):
    def test_geo_defined_from_payload(self):
        self.assertIn('GEO=D.geo_meta||', b.HTML)
    def test_geo_defined_before_geo_use(self):
        self.assertLess(b.HTML.index('GEO=D.geo_meta||'), b.HTML.index('function localProvinceSetForOffer'))
    def test_error_guard(self):
        self.assertIn("window.addEventListener('error'", b.HTML)
        self.assertIn('เปิดข้อมูลไม่สำเร็จ', b.HTML)
    def test_static_geo_options_still_present(self):
        self.assertIn('__REGION_OPTIONS__', b.HTML)
        self.assertIn('__PROVINCE_OPTIONS__', b.HTML)
    def test_geo_meta_embedded(self):
        h=b._render_html({'publication_id':'x','offer_count':0,'place_count':0},[],[],{})
        self.assertNotIn('__PAYLOAD_JSON__', h)
        self.assertIn('geo_meta', h)
        self.assertIn('ภาคตะวันออก', h)
        self.assertIn('ปราจีนบุรี', h)
if __name__=='__main__':unittest.main()
