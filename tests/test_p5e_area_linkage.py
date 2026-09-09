import unittest
from promo_intelligence.area_linkage import link_offer_explicit_branches, link_offers_explicit_branches


def place(pid='p1', merchant='Makro PRO', branch='กบินทร์บุรี', province='Prachinburi'):
    return {
      'place_id':pid,'record_kind':'branch','merchant':{'name':merchant,'aliases':[]},
      'branch':{'name':branch,'aliases':['สาขา '+branch]},
      'location':{'province':province,'district':'Kabin Buri','subdistrict':None,'address':'x','postal_code':'25110','latitude':None,'longitude':None},
      'precision':'address','verification':{'state':'verified'}
    }

def offer(branch='กบินทร์บุรี', merchant='Makro PRO'):
    return {
      'offer_id':'o1','merchant':{'name':merchant},'place_refs':[],
      'applicability':{'scope':'branch_specific','verification_state':'explicit','branches':[branch]},
      'geography':{'detail_state':'partial','best_granularity':'branch','locations':[{'branch_name':branch,'basis':'applicability','granularity':'branch','evidence_excerpt':'เฉพาะสาขา '+branch}]}
    }

class TestAreaLinkage(unittest.TestCase):
    def test_exact_explicit_branch_links_and_fills_province(self):
        out,s=link_offer_explicit_branches(offer(),[place()])
        self.assertEqual(out['place_refs'],['p1'])
        self.assertEqual(out['geography']['locations'][0]['province'],'Prachinburi')
        self.assertEqual(out['area_linkage']['state'],'linked')
        self.assertEqual(s['matched_branches'],1)
    def test_branch_existence_does_not_link_unknown_offer(self):
        o=offer();o['applicability']={'scope':'unknown','verification_state':'unknown','branches':[]};o['geography']={'locations':[]}
        out,s=link_offer_explicit_branches(o,[place()])
        self.assertEqual(out['place_refs'],[]);self.assertEqual(s['matched_branches'],0)
    def test_wrong_merchant_does_not_link(self):
        out,s=link_offer_explicit_branches(offer(),[place(merchant='HomePro')])
        self.assertEqual(out['place_refs'],[]);self.assertEqual(out['area_linkage']['state'],'unmatched')
    def test_ambiguous_exact_match_does_not_link(self):
        out,s=link_offer_explicit_branches(offer(),[place('p1'),place('p2')])
        self.assertEqual(out['place_refs'],[]);self.assertEqual(out['area_linkage']['state'],'ambiguous')
    def test_batch_stats(self):
        rows,stats=link_offers_explicit_branches([offer()],[place()])
        self.assertEqual(stats['offers_branch_linked'],1)
        self.assertEqual(stats['offers_with_local_province'],1)

if __name__=='__main__':unittest.main()
