import unittest
from promo_intelligence.applicability_enrichment import enrich_offer_applicability


def offer(title='สินค้า A',channel='store',direct='รายละเอียดโปรโมชั่น'):
    return {
        'applicability':{'scope':'unknown','country':'TH','provinces':[],'branches':[],'verification_state':'unknown','basis':'none','channel':channel,'channel_basis':'source_config'},
        'item':{'name':title}, 'conditions':[],
        'evidence':{'extracted_text':direct,'content_hash':'sha256:x'},
    }

def source(channel='store'):
    return {'source_id':'s1','url':'https://example.test/p','channel':channel}

class P5F(unittest.TestCase):
    def test_exact_context_nationwide(self):
        html='<div>สินค้า A</div><div>โปรโมชั่นนี้ใช้ได้ทุกสาขาทั่วประเทศ</div>'
        o,s=enrich_offer_applicability(offer(),source(),html)
        self.assertEqual(o['applicability']['scope'],'nationwide'); self.assertEqual(s['discovered'],1)

    def test_exact_context_province(self):
        html='<div>สินค้า A</div><div>โปรโมชั่นนี้ใช้ได้เฉพาะจังหวัดปราจีนบุรี</div>'
        o,s=enrich_offer_applicability(offer(),source(),html)
        self.assertEqual(o['applicability']['provinces'],['Prachinburi'])
        self.assertTrue((o.get('geography') or {}).get('locations'))

    def test_exact_context_branch(self):
        html='<div>สินค้า A</div><div>โปรโมชั่นนี้ใช้ได้ที่สาขา กบินทร์บุรี จังหวัดปราจีนบุรี</div>'
        o,s=enrich_offer_applicability(offer(),source(),html)
        self.assertEqual(o['applicability']['scope'],'branch_specific')
        self.assertIn('กบินทร์บุรี',o['applicability']['branches'])

    def test_unrelated_nationwide_not_applied_without_title_context(self):
        html='<div>โปรโมชั่นอื่นใช้ได้ทุกสาขาทั่วประเทศ</div><div>สินค้า B</div>'
        o,s=enrich_offer_applicability(offer('สินค้า A'),source(),html)
        self.assertEqual(o['applicability']['scope'],'unknown')

    def test_ambiguous_title_does_not_apply(self):
        html='<div>สินค้า A</div><div>ทุกสาขาทั่วประเทศ</div><div>สินค้า A</div>'
        o,s=enrich_offer_applicability(offer(),source(),html)
        self.assertEqual(o['applicability']['scope'],'unknown'); self.assertEqual(s['context_ambiguous'],1)

    def test_online_not_promoted_to_local(self):
        html='<div>สินค้า A</div><div>โปรโมชั่นนี้ใช้ได้เฉพาะจังหวัดปราจีนบุรี</div>'
        o,s=enrich_offer_applicability(offer(channel='online'),source('online'),html)
        self.assertEqual(o['applicability']['scope'],'unknown')

    def test_existing_explicit_unchanged(self):
        x=offer(); x['applicability'].update({'scope':'nationwide','verification_state':'explicit','basis':'offer_text'})
        o,s=enrich_offer_applicability(x,source(),'<div>สินค้า A</div>')
        self.assertEqual(o['applicability']['scope'],'nationwide'); self.assertEqual(s['attempted'],0)

    def test_direct_offer_evidence_first(self):
        o,s=enrich_offer_applicability(offer(direct='โปรโมชั่นนี้ใช้ได้ทุกสาขาทั่วประเทศ'),source(),None)
        self.assertEqual(o['applicability']['scope'],'nationwide')
        self.assertEqual(o['applicability_evidence']['method'],'direct_offer_evidence')

if __name__=='__main__': unittest.main()
