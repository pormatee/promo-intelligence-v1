import unittest
from promo_intelligence.place_enrichment import extract_bigc_branch

class P8K1BigCAddressSanitizationTests(unittest.TestCase):
    def test_matching_row_only(self):
        source = {
            "branch_name": "ศรีมหาโพธิ",
            "province": "ปราจีนบุรี",
            "branch_tokens": ["บิ๊กซี-ศรีมหาโพธิ"],
            "postal_code": "25140",
        }
        html = """
        <table>
        <tr><td>12</td><td>บิ๊กซี-บ้านบึง</td><td>เลขที่ 181 ถนน บ้านบึง-แกลง ตำบล บ้านบึง อำเภอ บ้านบึง จังหวัด ชลบุรี 20170</td></tr>
        <tr><td>13</td><td>บิ๊กซี-จันทบุรี</td><td>เลขที่ 1012 ถนนท่าแฉลบ ตำบล ตลาด อำเภอ เมืองจันทบุรี จังหวัด จันทบุรี 22000</td></tr>
        <tr><td>14</td><td>บิ๊กซี-ศรีมหาโพธิ</td><td>เลขที่ 618 หมู่ 7 ตำบล ท่าตูม อำเภอ ศรีมหาโพธิ จังหวัด ปราจีนบุรี 25140</td></tr>
        </table>
        """.encode()
        rows = extract_bigc_branch(source, html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["address"], "เลขที่ 618 หมู่ 7 ตำบล ท่าตูม อำเภอ ศรีมหาโพธิ จังหวัด ปราจีนบุรี 25140")
        self.assertNotIn("ชลบุรี", rows[0]["address"])
        self.assertNotIn("จันทบุรี", rows[0]["address"])

    def test_contact_row_no_address(self):
        source = {
            "branch_name": "ศรีมหาโพธิ",
            "province": "ปราจีนบุรี",
            "branch_tokens": ["BigC ศรีมหาโพธิ"],
        }
        html = "<table><tr><td>ปราจีนบุรี</td><td>BigC ศรีมหาโพธิ</td><td>0954620953</td></tr></table>".encode()
        rows = extract_bigc_branch(source, html)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["address"])

if __name__ == "__main__":
    unittest.main()

