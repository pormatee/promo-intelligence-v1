import json
import unittest

from promo_intelligence.place_enrichment import extract_globalhouse_detail


class P8J2GlobalHouseAddressDedupTests(unittest.TestCase):
    def source(self):
        return {
            "branch_name": "กบินทร์บุรี",
            "province": "ปราจีนบุรี",
            "url": "https://globalhouse.co.th/store-finder/kabin-buri",
        }

    def html(self, obj):
        blob = json.dumps(obj, ensure_ascii=False)
        return f'<script type="application/ld+json">{blob}</script>'.encode("utf-8")

    def test_does_not_repeat_locality_region_postcode_when_already_in_street(self):
        obj = {
            "@type": "Store",
            "name": "โกลบอลเฮ้าส์ สาขากบินทร์บุรี",
            "url": "https://globalhouse.co.th/store-finder/kabin-buri",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "346 หมู่ที่ 16 ต.เมืองเก่า อ.กบินทร์บุรี จ.ปราจีนบุรี 25240",
                "addressLocality": "กบินทร์บุรี",
                "addressRegion": "ปราจีนบุรี",
                "postalCode": "25240",
            },
        }
        rows = extract_globalhouse_detail(self.source(), self.html(obj))
        self.assertEqual(len(rows), 1)
        address = rows[0]["address"]
        self.assertEqual(address.count("25240"), 1)
        self.assertEqual(address.count("ปราจีนบุรี"), 1)
        self.assertEqual(address.count("กบินทร์บุรี"), 1)

    def test_appends_missing_components_once(self):
        obj = {
            "@type": "Store",
            "name": "โกลบอลเฮ้าส์ สาขากบินทร์บุรี",
            "url": "https://globalhouse.co.th/store-finder/kabin-buri",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "346 หมู่ที่ 16",
                "addressLocality": "กบินทร์บุรี",
                "addressRegion": "ปราจีนบุรี",
                "postalCode": "25240",
            },
        }
        rows = extract_globalhouse_detail(self.source(), self.html(obj))
        self.assertEqual(len(rows), 1)
        address = rows[0]["address"]
        self.assertEqual(address.count("25240"), 1)
        self.assertEqual(address.count("ปราจีนบุรี"), 1)
        self.assertEqual(address.count("กบินทร์บุรี"), 1)

    def test_wrong_province_still_rejected(self):
        obj = {
            "@type": "Store",
            "name": "โกลบอลเฮ้าส์ สาขากบินทร์บุรี",
            "url": "https://globalhouse.co.th/store-finder/kabin-buri",
            "address": {
                "streetAddress": "1 Road",
                "addressRegion": "นครนายก",
                "postalCode": "26000",
            },
        }
        self.assertEqual(extract_globalhouse_detail(self.source(), self.html(obj)), [])


if __name__ == "__main__":
    unittest.main()

