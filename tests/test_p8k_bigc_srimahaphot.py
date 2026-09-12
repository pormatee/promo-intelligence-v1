import unittest

from promo_intelligence.place_enrichment import extract_bigc_branch


class P8KBigCSriMahaPhotTests(unittest.TestCase):
    def test_current_official_contact_proves_branch_and_province(self):
        source = {
            "branch_name": "ศรีมหาโพธิ",
            "province": "ปราจีนบุรี",
            "branch_tokens": ["BigC ศรีมหาโพธิ"],
        }
        html = """
        <table><tr><td>ปราจีนบุรี</td><td>BigC ศรีมหาโพธิ</td>
        <td>0954620953</td></tr></table>
        """.encode("utf-8")
        rows = extract_bigc_branch(source, html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["branch_name"], "ศรีมหาโพธิ")
        self.assertEqual(rows[0]["province"], "ปราจีนบุรี")
        self.assertIsNone(rows[0]["address"])

    def test_official_address_page_captures_explicit_address(self):
        source = {
            "branch_name": "ศรีมหาโพธิ",
            "province": "ปราจีนบุรี",
            "branch_tokens": ["บิ๊กซี-ศรีมหาโพธิ"],
            "postal_code": "25140",
        }
        html = """
        <table><tr><td>14</td><td>บิ๊กซี-ศรีมหาโพธิ</td>
        <td>เลขที่ 618 หมู่ 7 ตำบล ท่าตูม อำเภอ ศรีมหาโพธิ จังหวัด ปราจีนบุรี 25140</td>
        </tr></table>
        """.encode("utf-8")
        rows = extract_bigc_branch(source, html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["province"], "ปราจีนบุรี")
        self.assertEqual(rows[0]["postal_code"], "25140")
        self.assertIn("เลขที่ 618", rows[0]["address"])
        self.assertIn("ปราจีนบุรี", rows[0]["address"])

    def test_branch_name_without_explicit_province_rejected(self):
        source = {
            "branch_name": "ศรีมหาโพธิ",
            "province": "ปราจีนบุรี",
            "branch_tokens": ["BigC ศรีมหาโพธิ"],
        }
        html = "<p>BigC ศรีมหาโพธิ โทร 0954620953</p>".encode("utf-8")
        self.assertEqual(extract_bigc_branch(source, html), [])

    def test_wrong_province_rejected(self):
        source = {
            "branch_name": "ศรีมหาโพธิ",
            "province": "ปราจีนบุรี",
            "branch_tokens": ["BigC ศรีมหาโพธิ"],
        }
        html = "<p>นครนายก BigC ศรีมหาโพธิ</p>".encode("utf-8")
        self.assertEqual(extract_bigc_branch(source, html), [])


if __name__ == "__main__":
    unittest.main()

