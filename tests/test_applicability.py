import unittest
from promo_intelligence.applicability import resolve_applicability


class ApplicabilityTest(unittest.TestCase):
    def test_unknown_stays_unknown(self):
        a=resolve_applicability({'evidence_excerpt':'Promo 69 THB','conditions':[]},{})
        self.assertEqual(a['scope'],'unknown')
        self.assertEqual(a['verification_state'],'unknown')
        self.assertEqual(a['basis'],'none')

    def test_explicit_nationwide_from_offer_text(self):
        a=resolve_applicability({'evidence_excerpt':'Available at all branches','conditions':[]},{})
        self.assertEqual(a['scope'],'nationwide')
        self.assertEqual(a['verification_state'],'explicit')
        self.assertEqual(a['basis'],'offer_text')

    def test_explicit_source_config(self):
        source={'applicability':{
            'scope':'branch_specific','country':'TH','provinces':['Prachinburi'],
            'branches':['Prachinburi Branch'],'verification_state':'explicit'
        }}
        a=resolve_applicability({'evidence_excerpt':'x','conditions':[]},source)
        self.assertEqual(a['scope'],'branch_specific')
        self.assertEqual(a['provinces'],['Prachinburi'])
        self.assertEqual(a['basis'],'source_config')
