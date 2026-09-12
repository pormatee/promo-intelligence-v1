import unittest

from promo_intelligence.place_enrichment import extract_makro_detail


class P8IMakroPrachinburiTests(unittest.TestCase):
    def source(self):
        return {
            "branch_name": "ปราจีนบุรี",
            "province": "ปราจีนบุรี",
            "province_token": "Prachinburi",
        }

    def test_explicit_heading_and_address_are_required(self):
        html = b"<h2>Prachinburi</h2><p>243/6 Prachintakham Road, Tambon Na Mueang, Amphoe Mueang Prachinburi, Prachinburi 25000</p>"
        rows = extract_makro_detail(self.source(), html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch_name"], "ปราจีนบุรี")
        self.assertEqual(rows[0]["province"], "ปราจีนบุรี")
        self.assertEqual(rows[0]["postal_code"], "25000")
        self.assertIn("243/6", rows[0]["address"])

    def test_heading_without_explicit_address_does_not_publish(self):
        html = b"<h2>Prachinburi</h2><p>037-623-920</p>"
        self.assertEqual(extract_makro_detail(self.source(), html), [])

    def test_address_without_heading_does_not_publish(self):
        html = b"<p>243/6 Road, Prachinburi 25000</p>"
        self.assertEqual(extract_makro_detail(self.source(), html), [])

    def test_other_province_cannot_be_relabelled(self):
        html = b"<h2>Rayong</h2><p>Some Road, Rayong 21000</p>"
        self.assertEqual(extract_makro_detail(self.source(), html), [])


if __name__ == "__main__":
    unittest.main()
