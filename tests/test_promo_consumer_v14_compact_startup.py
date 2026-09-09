import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_promo_consumer import build_html

class ConsumerV14Tests(unittest.TestCase):
    def html(self):
        return build_html({'publication_id':'pub_v14','published_at':'2026-09-09T00:00:00Z'},[],[],{'merchant_branches':{}})
    def test_clear_button_stays_inside_search_and_hidden_when_empty(self):
        h=self.html()
        self.assertIn('.heroSearch button{position:absolute!important', h)
        self.assertIn('.heroSearch button.show{display:flex}', h)
        self.assertIn('function syncClearButton()', h)
    def test_payload_uses_direct_json_not_base64_runtime_decode(self):
        h=self.html()
        self.assertIn('type="application/json"', h)
        self.assertIn("JSON.parse(payloadNode.textContent)", h)
        self.assertNotIn('Uint8Array.from(atob', h)
    def test_mobile_header_is_compact_and_stats_hidden(self):
        h=self.html()
        self.assertIn('V1.4 compact mobile header + fast-first-view', h)
        self.assertIn('.stats{display:none!important}', h)
        self.assertIn('ค้นหาโปร สินค้า ร้าน หรือจังหวัด', h)
    def test_loading_placeholder_is_human_readable(self):
        h=self.html()
        self.assertIn('กำลังเตรียมรายการโปรโมชั่น', h)

if __name__ == '__main__':
    unittest.main()
