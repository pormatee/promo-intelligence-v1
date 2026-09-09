import unittest

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from promo_intelligence.offer_identity import evaluate_offer_identity, annotate_offer_identity
from promo_intelligence.published import is_publishable
from promo_intelligence.contract import validate_offer


def offer(merchant="Lotus's", item="Weekday Specials at THB 199 per set", promo=None):
    return {
        'contract':'promo_offer_v1','offer_id':'o1','offer_type':'other',
        'merchant':{'name':merchant,'branch':None},'item':{'name':item,'brand':None,'category':None},
        'pricing':{'currency':'THB','regular_price':None,'promo_price':promo,'discount_amount':None,'discount_percent':None},
        'validity':{'start':None,'end':None},'conditions':[],
        'verification':{'verification_state':'partial','freshness_state':'fresh','expiry_state':'unknown'},
        'source':{'source_id':'s','source_type':'official','url':'https://example.com','observed_at':'2026-09-09T00:00:00Z'},
        'evidence':{'content_hash':'sha256:x','extracted_text':'evidence'},
        'applicability':{'scope':'unknown','verification_state':'unknown','provinces':[],'branches':[],'channel':'store'},
    }


class P6IdentityTests(unittest.TestCase):
    def test_normal_campaign_accepted(self):
        self.assertEqual(evaluate_offer_identity(offer())['state'],'accepted')

    def test_availability_condition_as_merchant_rejected(self):
        x=evaluate_offer_identity(offer('Available Monday–Friday, excluding public holidays.','The Pizza Company'))
        self.assertEqual(x['state'],'rejected'); self.assertIn('merchant_availability_condition',x['reason_codes'])

    def test_price_disclaimer_as_merchant_rejected(self):
        x=evaluate_offer_identity(offer('Prices are subject to 7% VAT.','Mc JEANS'))
        self.assertEqual(x['state'],'rejected'); self.assertIn('merchant_price_disclaimer',x['reason_codes'])

    def test_globalhouse_exclusion_rejected(self):
        x=evaluate_offer_identity(offer('Global House','4. สินค้ายกเว้นการใช้คูปองส่วนลด สินค้าโครงสร้าง, เครื่องใช้ไฟฟ้า'))
        self.assertEqual(x['state'],'rejected'); self.assertTrue(any('exclusion_fragment' in r for r in x['reason_codes']))

    def test_action_only_cta_rejected(self):
        x=evaluate_offer_identity(offer('7-Eleven Thailand','ดาวน์โหลดแอป 7-Eleven'))
        self.assertEqual(x['state'],'rejected'); self.assertIn('item_action_only_cta',x['reason_codes'])

    def test_cta_with_benefit_retained(self):
        x=evaluate_offer_identity(offer('Example','ดาวน์โหลดแอป รับฟรีคูปอง 50 บาท'))
        self.assertEqual(x['state'],'accepted')

    def test_description_without_price_review_only(self):
        x=evaluate_offer_identity(offer('Mr. Bao MALATANG','Includes Sour & Spicy Fish, steamed rice and plum juice.'))
        self.assertEqual(x['state'],'review')

    def test_description_with_price_retained(self):
        x=evaluate_offer_identity(offer('Mr. Bao MALATANG','Includes Sour & Spicy Fish, steamed rice and plum juice.',199))
        self.assertEqual(x['state'],'accepted')

    def test_technical_payload_rejected(self):
        x=evaluate_offer_identity(offer('Big C Online','{"props":{"pageProps":{"redis_uri":"x"}}}'))
        self.assertEqual(x['state'],'rejected')

    def test_published_gate_excludes_rejected_identity(self):
        x=annotate_offer_identity(offer('Prices are subject to 7% VAT.','Mc JEANS'))
        self.assertFalse(is_publishable(x))

    def test_published_gate_allows_review(self):
        x=annotate_offer_identity(offer('Mr. Bao MALATANG','Includes Sour & Spicy Fish, steamed rice and plum juice.'))
        self.assertTrue(is_publishable(x))

    def test_contract_accepts_identity_metadata(self):
        x=annotate_offer_identity(offer())
        self.assertEqual(validate_offer(x),[])


if __name__=='__main__': unittest.main()
