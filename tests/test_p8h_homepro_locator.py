import unittest
from promo_intelligence.place_enrichment import extract_homepro

class P8HHomeProLocatorTests(unittest.TestCase):
    def test_explicit_address_sets_province(self):
        h="<div>โฮมโปร ปราจีนบุรี</div><div>44/1 หมู่ที่ 4, บางบริบูรณ์, เมืองปราจีนบุรี, ปราจีนบุรี, 25000 Tel: 037-482-222</div>"
        rows=extract_homepro({},h.encode())
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["province"],"ปราจีนบุรี")
        self.assertEqual(rows[0]["postal_code"],"25000")
        self.assertIn("44/1",rows[0]["address"])

    def test_branch_name_alone_is_not_province(self):
        rows=extract_homepro({},"<div>โฮมโปร ปราจีนบุรี</div>".encode())
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]["province"])
        self.assertIsNone(rows[0]["address"])

    def test_does_not_borrow_next_branch_address(self):
        h="<div>โฮมโปร ปราจีนบุรี</div><div>โฮมโปร ระยอง</div><div>560 ถ.สุขุมวิท, เนินพระ, เมืองระยอง, ระยอง, 21000 Tel: 033-060-100</div>"
        rows=extract_homepro({},h.encode())
        by={x["branch_name"]:x for x in rows}
        self.assertIsNone(by["ปราจีนบุรี"]["province"])
        self.assertEqual(by["ระยอง"]["province"],"ระยอง")

    def test_mega_home_not_mislabeled(self):
        h="<div>เมกาโฮม กบินทร์บุรี</div><div>61 หมู่ที่ 8, เมืองเก่า, กบินทร์บุรี, ปราจีนบุรี, 25240 Tel: 063-906-795</div>"
        self.assertEqual(extract_homepro({},h.encode()),[])

if __name__=="__main__":
    unittest.main()
