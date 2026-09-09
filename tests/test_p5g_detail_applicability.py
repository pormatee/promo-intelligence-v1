import unittest
from promo_intelligence.detail_applicability import discover_detail_links, evaluate_detail_page, apply_detail_results, LinkCandidate


def offer(title='โปรพิเศษ', channel='store'):
    return {
        'offer_id':'x',
        'item':{'name':title},
        'merchant':{'name':'Demo'},
        'applicability':{'scope':'unknown','country':'TH','provinces':[],'branches':[],'verification_state':'unknown','channel':channel},
        'evidence':{'content_hash':'sha256:x','extracted_text':''},
        'conditions':[],
    }

SOURCE={'source_id':'demo','url':'https://shop.example.com/promotion','channel':'store'}

class P5GTests(unittest.TestCase):
    def test_same_host_exact_anchor_discovered(self):
        html='''<a href="/promotion/detail/123">ภารกิจพิชิตรางวัล ช้อปครบรับเงินคืน</a>
                <a href="https://evil.example.net/promo">ภารกิจพิชิตรางวัล ช้อปครบรับเงินคืน</a>'''
        xs=discover_detail_links(html,SOURCE['url'],'ภารกิจพิชิตรางวัล ช้อปครบรับเงินคืน')
        self.assertEqual(len(xs),1)
        self.assertEqual(xs[0].url,'https://shop.example.com/promotion/detail/123')
        self.assertGreaterEqual(xs[0].score,80)

    def test_generic_detail_link_without_title_not_accepted(self):
        html='<a href="/promotion/detail/123">ดูรายละเอียด</a>'
        self.assertEqual(discover_detail_links(html,SOURCE['url'],'โปรพิเศษมากๆ'),[])

    def test_external_official_looking_link_not_followed(self):
        html='<a href="https://other.example.com/promotion/123">โปรพิเศษมากๆ</a>'
        self.assertEqual(discover_detail_links(html,SOURCE['url'],'โปรพิเศษมากๆ'),[])

    def test_detail_nationwide(self):
        c=LinkCandidate('https://shop.example.com/promotion/1','โปรพิเศษมากๆ',100,'anchor_exact_title')
        page='<h1>โปรพิเศษมากๆ</h1><p>โปรโมชั่นนี้ใช้ได้ที่ทุกสาขาทั่วประเทศ</p>'
        r,s=evaluate_detail_page(offer('โปรพิเศษมากๆ'),SOURCE,c,page,'2026-09-09T00:00:00Z','sha256:a')
        self.assertEqual(r['applicability']['scope'],'nationwide')
        self.assertEqual(r['kind'],'nationwide')
        self.assertEqual(s['discovered'],1)

    def test_detail_province(self):
        c=LinkCandidate('https://shop.example.com/promotion/2','โปรจังหวัด',100,'anchor_exact_title')
        page='<h1>โปรจังหวัด</h1><p>โปรโมชั่นนี้ใช้ได้เฉพาะในจังหวัดปราจีนบุรี</p>'
        r,s=evaluate_detail_page(offer('โปรจังหวัด'),SOURCE,c,page)
        self.assertIn('Prachinburi',r['applicability']['provinces'])
        self.assertEqual(r['kind'],'province')

    def test_detail_branch(self):
        c=LinkCandidate('https://shop.example.com/promotion/3','โปรสาขา',100,'anchor_exact_title')
        page='<h1>โปรสาขา</h1><p>ใช้ได้เฉพาะสาขา กบินทร์บุรี จังหวัดปราจีนบุรี</p>'
        r,s=evaluate_detail_page(offer('โปรสาขา'),SOURCE,c,page)
        self.assertEqual(r['applicability']['scope'],'branch_specific')
        self.assertTrue(r['applicability']['branches'])

    def test_online_offer_never_promoted_to_local(self):
        c=LinkCandidate('https://shop.example.com/promotion/4','โปรออนไลน์',100,'anchor_exact_title')
        page='<h1>โปรออนไลน์</h1><p>ใช้ได้ทุกสาขาทั่วประเทศ</p>'
        r,s=evaluate_detail_page(offer('โปรออนไลน์','online'),SOURCE,c,page)
        self.assertIsNone(r)

    def test_conflicting_pages_preserve_unknown(self):
        o=offer('โปร')
        a={'applicability':{'scope':'nationwide','provinces':[],'branches':[],'channel':'store'},'geography':{},'evidence':{'detail_url':'https://x/a'},'kind':'nationwide'}
        b={'applicability':{'scope':'selected_branches','provinces':['Prachinburi'],'branches':[],'channel':'store'},'geography':{},'evidence':{'detail_url':'https://x/b'},'kind':'province'}
        out,state=apply_detail_results(o,[a,b])
        self.assertEqual(state,'conflict')
        self.assertEqual(out['applicability']['scope'],'unknown')

    def test_same_result_multiple_pages_is_safe(self):
        o=offer('โปร')
        a={'applicability':{'scope':'nationwide','provinces':[],'branches':[],'channel':'store'},'geography':{'detail_state':'nationwide'},'evidence':{'detail_url':'https://x/a'},'kind':'nationwide'}
        b={'applicability':{'scope':'nationwide','provinces':[],'branches':[],'channel':'store'},'geography':{'detail_state':'nationwide'},'evidence':{'detail_url':'https://x/b'},'kind':'nationwide'}
        out,state=apply_detail_results(o,[a,b])
        self.assertEqual(state,'nationwide')
        self.assertEqual(out['applicability']['scope'],'nationwide')

    def test_title_not_found_weak_candidate_does_not_scan_pagewide(self):
        c=LinkCandidate('https://shop.example.com/promotion/5','คลิกดู',50,'anchor_token_overlap')
        page='<h1>โปรอื่น</h1><p>โปรโมชั่นนี้ใช้ได้ทุกสาขาทั่วประเทศ</p>'
        r,s=evaluate_detail_page(offer('โปรเป้าหมาย'),SOURCE,c,page)
        self.assertIsNone(r)
        self.assertEqual(s['title_not_found'],1)

if __name__=='__main__': unittest.main()
