import unittest

from promo_intelligence.place_enrichment import extract_powerbuy


class P8NPowerBuyFailClosedTests(unittest.TestCase):
    def source(self):
        return {
            "source_id": "powerbuy_storelocator",
            "merchant": "Power Buy",
        }

    def test_branch_name_never_becomes_province(self):
        html = (
            "<div>Robinson Prachinburi</div>"
            "<div>72 Moo.3 Robinson Prachinburi 1st FL "
            "T.Bangbriboon A.Muang Prachinburi Prachinburi 25000</div>"
            "<div>Open Today: 11:00 - 20:00</div>"
        ).encode()

        rows = extract_powerbuy(self.source(), html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["branch_name"], "Robinson Prachinburi")
        self.assertEqual(row["postal_code"], "25000")
        self.assertIsNone(row["province"])

    def test_empty_default_payload_does_not_create_place(self):
        self.assertEqual(extract_powerbuy(self.source(), b"<html></html>"), [])

    def test_name_without_address_and_postcode_is_rejected(self):
        html = (
            "<div>Robinson Prachinburi</div>"
            "<div>Open Today: 11:00 - 20:00</div>"
        ).encode()
        self.assertEqual(extract_powerbuy(self.source(), html), [])

    def test_wrong_layout_does_not_borrow_address(self):
        html = (
            "<div>Robinson Prachinburi</div>"
            "<div>Open Today: 11:00 - 20:00</div>"
            "<div>72 Moo.3 Prachinburi 25000</div>"
        ).encode()
        self.assertEqual(extract_powerbuy(self.source(), html), [])


if __name__ == "__main__":
    unittest.main()
