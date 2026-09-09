import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_promo_consumer import build_html, geo_meta

class ConsumerV13CompactGeoTests(unittest.TestCase):
    def test_thailand_geo_has_77_provinces_and_regions(self):
        g = geo_meta()
        self.assertEqual(len(g['provinces']), 77)
        self.assertEqual(len(set(g['provinces'])), 77)
        self.assertEqual(len(g['regions']), 7)
        self.assertEqual(g['region_by_province']['ปราจีนบุรี'], 'east')
        self.assertEqual(g['region_by_province']['กรุงเทพมหานคร'], 'bangkok_metro')

    def test_consumer_has_compact_region_province_filters(self):
        h = build_html({'publication_id':'pub_x'}, [], [], {'merchant_branches':{}})
        self.assertIn('id="region"', h)
        self.assertIn('ทุกภูมิภาค', h)
        self.assertIn('id="province"', h)
        self.assertIn('ทุกจังหวัด', h)
        self.assertIn('advancedToggle', h)
        self.assertIn('advancedFilters', h)
        self.assertIn('refreshProvinceOptions()', h)
        self.assertIn('regionSetForOffer', h)
        self.assertIn('filterResultMini', h)
        self.assertIn('min-height:40px', h)
        self.assertIn('display:flex;overflow:auto', h)

if __name__ == '__main__':
    unittest.main()
