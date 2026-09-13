import unittest

from promo_intelligence.place_enrichment import extract_homepro


class P8MHomeProPrachinburiTests(unittest.TestCase):
    def source(self):
        return {
            "source_id": "homepro_branch_contact",
            "merchant": "HomePro",
        }

    def test_explicit_branch_address_sets_province_and_postcode(self):
        html = (
            "<div>โฮมโปร ปราจีนบุรี</div>"
            "<div>44/1 หมู่ที่ 4, บางบริบูรณ์, เมืองปราจีนบุรี, ปราจีนบุรี 25000</div>"
            "<div>037-482-222</div>"
        ).encode()
        rows = extract_homepro(self.source(), html)
        matches = [x for x in rows if x["branch_name"] == "ปราจีนบุรี"]
        self.assertEqual(len(matches), 1)
        row = matches[0]
        self.assertEqual(row["province"], "ปราจีนบุรี")
        self.assertEqual(row["postal_code"], "25000")
        self.assertIn("บางบริบูรณ์", row["address"])

    def test_branch_name_alone_never_implies_province(self):
        html = "<div>โฮมโปร ปราจีนบุรี</div>".encode()
        rows = extract_homepro(self.source(), html)
        matches = [x for x in rows if x["branch_name"] == "ปราจีนบุรี"]
        self.assertEqual(len(matches), 1)
        self.assertIsNone(matches[0]["province"])
        self.assertIsNone(matches[0]["address"])
        self.assertIsNone(matches[0]["postal_code"])

    def test_address_without_postcode_is_not_geography_evidence(self):
        html = (
            "<div>โฮมโปร ปราจีนบุรี</div>"
            "<div>44/1 หมู่ที่ 4, บางบริบูรณ์, เมืองปราจีนบุรี, ปราจีนบุรี</div>"
        ).encode()
        rows = extract_homepro(self.source(), html)
        matches = [x for x in rows if x["branch_name"] == "ปราจีนบุรี"]
        self.assertEqual(len(matches), 1)
        self.assertIsNone(matches[0]["province"])
        self.assertIsNone(matches[0]["address"])
        self.assertIsNone(matches[0]["postal_code"])

    def test_does_not_borrow_next_branch_address(self):
        html = (
            "<div>โฮมโปร ปราจีนบุรี</div>"
            "<div>โฮมโปร ฉะเชิงเทรา</div>"
            "<div>187/9 ถนนฉะเชิงเทรา-บางประกง, หน้าเมือง, เมืองฉะเชิงเทรา, ฉะเชิงเทรา 24000</div>"
        ).encode()
        rows = extract_homepro(self.source(), html)
        p = [x for x in rows if x["branch_name"] == "ปราจีนบุรี"]
        c = [x for x in rows if x["branch_name"] == "ฉะเชิงเทรา"]
        self.assertEqual(len(p), 1)
        self.assertIsNone(p[0]["province"])
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["province"], "ฉะเชิงเทรา")

    def test_explicit_wrong_province_stays_wrong_and_is_not_rewritten(self):
        html = (
            "<div>โฮมโปร ปราจีนบุรี</div>"
            "<div>99 หมู่ 1, หน้าเมือง, เมืองฉะเชิงเทรา, ฉะเชิงเทรา 24000</div>"
        ).encode()
        rows = extract_homepro(self.source(), html)
        matches = [x for x in rows if x["branch_name"] == "ปราจีนบุรี"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["province"], "ฉะเชิงเทรา")
        self.assertNotEqual(matches[0]["province"], "ปราจีนบุรี")


if __name__ == "__main__":
    unittest.main()
