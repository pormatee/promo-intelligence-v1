import unittest
from promo_intelligence.place_enrichment import extract_lotus_current_branch, extract_lotus_tenant_location

class P8K2LotusPrachinburiTests(unittest.TestCase):
    def current_source(self):
        return {"branch_name": "ปราจีนบุรี", "branch_token": "โลตัส ปราจีนบุรี"}

    def location_source(self):
        return {
            "branch_name": "ปราจีนบุรี",
            "page_token": "dtac center สาขาโลตัสปราจีนบุรี",
            "address_label": "ที่อยู่:",
            "next_store_prefix": "dtac center",
            "province": "ปราจีนบุรี",
            "province_evidence_token": "ปราจีนบุรี",
            "postal_code": "25000",
        }

    def test_current_first_party_page_confirms_branch_only(self):
        rows = extract_lotus_current_branch(self.current_source(), '<h1>โลตัส ปราจีนบุรี</h1>'.encode())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch_name"], "ปราจีนบุรี")
        self.assertIsNone(rows[0]["province"])
        self.assertIsNone(rows[0]["address"])
        self.assertIsNone(rows[0]["postal_code"])

    def test_current_nextjs_json_title_is_accepted_without_geography(self):
        html = '<script>{"contentId":"branch-5100","title":"โลตัส ปราจีนบุรี"}</script>'.encode()
        rows = extract_lotus_current_branch(self.current_source(), html)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["province"])

    def test_branch_name_without_lotus_token_is_not_enough(self):
        self.assertEqual(extract_lotus_current_branch(self.current_source(), '<p>ปราจีนบุรี</p>'.encode()), [])

    def test_tenant_page_requires_exact_marker_address_province_and_postcode(self):
        html = ("<h2>dtac center สาขาโลตัสปราจีนบุรี</h2>"
                "<div>ที่อยู่:</div>"
                "<p>เลขที่ 15/1 บางบริบูรณ์ เมืองปราจีนบุรี ปราจีนบุรี 25000</p>"
                "<h2>dtac center สาขาโรบินสันปราจีนบุรี</h2>").encode()
        rows = extract_lotus_tenant_location(self.location_source(), html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["province"], "ปราจีนบุรี")
        self.assertEqual(rows[0]["postal_code"], "25000")

    def test_tenant_page_missing_exact_store_marker_is_rejected(self):
        html = ("<div>ที่อยู่:</div>"
                "<p>เลขที่ 15/1 บางบริบูรณ์ เมืองปราจีนบุรี ปราจีนบุรี 25000</p>").encode()
        self.assertEqual(extract_lotus_tenant_location(self.location_source(), html), [])

    def test_tenant_page_wrong_postcode_is_rejected(self):
        html = ("<h2>dtac center สาขาโลตัสปราจีนบุรี</h2>"
                "<div>ที่อยู่:</div>"
                "<p>เลขที่ 15/1 บางบริบูรณ์ เมืองปราจีนบุรี ปราจีนบุรี 25130</p>").encode()
        self.assertEqual(extract_lotus_tenant_location(self.location_source(), html), [])

    def test_tenant_page_missing_explicit_province_token_is_rejected(self):
        html = ("<h2>dtac center สาขาโลตัสปราจีนบุรี</h2>"
                "<div>ที่อยู่:</div><p>เลขที่ 15/1 บางบริบูรณ์ 25000</p>").encode()
        self.assertEqual(extract_lotus_tenant_location(self.location_source(), html), [])

    def test_tenant_page_does_not_borrow_address_from_next_store(self):
        html = ("<h2>dtac center สาขาโลตัสปราจีนบุรี</h2>"
                "<div>ที่อยู่:</div><p>ข้อมูลไม่ครบ</p>"
                "<h2>dtac center สาขาโรบินสันปราจีนบุรี</h2>"
                "<div>ที่อยู่:</div><p>เลขที่ 72 ปราจีนบุรี 25000</p>").encode()
        self.assertEqual(extract_lotus_tenant_location(self.location_source(), html), [])

if __name__ == "__main__":
    unittest.main()
