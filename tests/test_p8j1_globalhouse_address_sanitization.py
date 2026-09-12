import json
import unittest

from promo_intelligence.place_enrichment import extract_globalhouse_detail


class P8J1GlobalHouseAddressSanitizationTests(unittest.TestCase):
    def source(self):
        return {
            'branch_name': 'กบินทร์บุรี',
            'province': 'ปราจีนบุรี',
            'url': 'https://globalhouse.co.th/store-finder/kabin-buri',
        }

    def html(self, obj):
        blob = json.dumps(obj, ensure_ascii=False)
        return f'<html><script type="application/ld+json">{blob}</script></html>'.encode('utf-8')

    def test_clean_postal_address_only(self):
        obj = {
            '@context': 'https://schema.org',
            '@type': 'Store',
            'name': 'โกลบอลเฮ้าส์ สาขากบินทร์บุรี',
            'url': 'https://globalhouse.co.th/store-finder/kabin-buri',
            'description': 'ข้อความยาวที่ไม่ควรเข้า address',
            'address': {
                '@type': 'PostalAddress',
                'streetAddress': '346 หมู่ที่ 9 ตำบลเมืองเก่า อำเภอกบินทร์บุรี',
                'addressLocality': 'กบินทร์บุรี',
                'addressRegion': 'ปราจีนบุรี',
                'postalCode': '25240',
            },
        }
        rows = extract_globalhouse_detail(self.source(), self.html(obj))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['province'], 'ปราจีนบุรี')
        self.assertEqual(rows[0]['postal_code'], '25240')
        self.assertIn('346 หมู่ที่ 9', rows[0]['address'])
        self.assertNotIn('description', rows[0]['address'])
        self.assertNotIn('@type', rows[0]['address'])

    def test_faq_blob_does_not_contaminate_address(self):
        obj = {
            '@graph': [
                {
                    '@type': 'FAQPage',
                    'mainEntity': [{'@type': 'Question', 'name': 'เปิดกี่โมง?', 'acceptedAnswer': {'text': '08:00'}}],
                },
                {
                    '@type': 'Store',
                    'name': 'โกลบอลเฮ้าส์ สาขากบินทร์บุรี',
                    'url': 'https://globalhouse.co.th/store-finder/kabin-buri',
                    'address': {
                        '@type': 'PostalAddress',
                        'streetAddress': '346 หมู่ที่ 9 ตำบลเมืองเก่า อำเภอกบินทร์บุรี',
                        'addressLocality': 'กบินทร์บุรี',
                        'addressRegion': 'ปราจีนบุรี',
                        'postalCode': '25240',
                    },
                },
            ]
        }
        rows = extract_globalhouse_detail(self.source(), self.html(obj))
        self.assertEqual(len(rows), 1)
        self.assertNotIn('เปิดกี่โมง', rows[0]['address'])
        self.assertNotIn('acceptedAnswer', rows[0]['address'])

    def test_wrong_province_rejected(self):
        obj = {
            '@type': 'Store',
            'name': 'โกลบอลเฮ้าส์ สาขากบินทร์บุรี',
            'url': 'https://globalhouse.co.th/store-finder/kabin-buri',
            'address': {'streetAddress': '1 Road', 'addressRegion': 'นครนายก', 'postalCode': '26000'},
        }
        self.assertEqual(extract_globalhouse_detail(self.source(), self.html(obj)), [])

    def test_branch_name_without_postal_address_rejected(self):
        obj = {'@type': 'Store', 'name': 'โกลบอลเฮ้าส์ สาขากบินทร์บุรี'}
        self.assertEqual(extract_globalhouse_detail(self.source(), self.html(obj)), [])


if __name__ == '__main__':
    unittest.main()

