import unittest
from build_promo_consumer import build_html

class P8ConsumerAreaClarityTests(unittest.TestCase):
    def test_area_copy_explains_confirmed_vs_nationwide(self):
        h = build_html({'publication_id':'pub_test'}, [], [], {'merchant_branches':{}})
        self.assertIn('ใช้ได้ตามหลักฐาน', h)
        self.assertIn('ยืนยันเฉพาะพื้นที่', h)
        self.assertIn('ถ้าเป็น 0 ไม่ได้แปลว่าไม่มีโปรโมชั่น', h)
        self.assertIn('หน้าร้านที่ร่วมรายการ (ยังไม่ยืนยันจังหวัด)', h)

    def test_selected_branches_stays_unconfirmed_for_area_filter(self):
        h = build_html({'publication_id':'pub_test'}, [], [], {'merchant_branches':{}})
        self.assertIn("return c==='all'||c==='local'||c==='nationwide'", h)
        self.assertIn('หน้าร้านที่ร่วมรายการ · ต้องตรวจสาขา', h)

if __name__ == '__main__':
    unittest.main()
