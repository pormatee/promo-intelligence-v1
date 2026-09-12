import unittest

from promo_intelligence.place_enrichment import extract_globalhouse_detail


class P8JGlobalHouseKabinburiTests(unittest.TestCase):
    def source(self):
        return {
            "branch_name": "กบินทร์บุรี",
            "province": "ปราจีนบุรี",
            "province_token": "จังหวัดปราจีนบุรี",
            "heading_token": "โกลบอลเฮ้าส์ สาขากบินทร์บุรี",
        }

    def test_explicit_heading_and_address_publish(self):
        html = "<h1>โกลบอลเฮ้าส์ สาขากบินทร์บุรี</h1><div>เลขที่ 346 หมู่ที่ 9 ตำบลเมืองเก่า อำเภอกบินทร์บุรี จังหวัดปราจีนบุรี 25240</div>"
        rows = extract_globalhouse_detail(self.source(), html.encode("utf-8"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch_name"], "กบินทร์บุรี")
        self.assertEqual(rows[0]["province"], "ปราจีนบุรี")
        self.assertEqual(rows[0]["postal_code"], "25240")
        self.assertIn("346", rows[0]["address"])

    def test_branch_heading_without_province_address_rejected(self):
        html = "<h1>โกลบอลเฮ้าส์ สาขากบินทร์บุรี</h1><div>เปิดทุกวัน</div>"
        self.assertEqual(extract_globalhouse_detail(self.source(), html.encode("utf-8")), [])

    def test_address_without_correct_heading_rejected(self):
        html = "<h1>โกลบอลเฮ้าส์ สาขานครนายก</h1><div>เลขที่ 346 หมู่ที่ 9 อำเภอกบินทร์บุรี จังหวัดปราจีนบุรี 25240</div>"
        self.assertEqual(extract_globalhouse_detail(self.source(), html.encode("utf-8")), [])

    def test_other_province_cannot_be_relabelled(self):
        html = "<h1>โกลบอลเฮ้าส์ สาขากบินทร์บุรี</h1><div>เลขที่ 1 อำเภอเมือง จังหวัดนครนายก 26000</div>"
        self.assertEqual(extract_globalhouse_detail(self.source(), html.encode("utf-8")), [])


if __name__ == "__main__":
    unittest.main()
