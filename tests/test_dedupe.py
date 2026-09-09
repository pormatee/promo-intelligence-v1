import unittest
from copy import deepcopy
from promo_intelligence.dedupe import dedupe


def offer(scope='unknown', branches=None):
    return {
      'merchant':{'name':'Shop','branch':None}, 'item':{'name':'Milk'},
      'pricing':{'promo_price':49.0}, 'validity':{'start':'2026-09-01','end':'2026-09-30'},
      'applicability':{'scope':scope,'provinces':[],'branches':branches or []}
    }


class DedupeTest(unittest.TestCase):
    def test_identical_offer_collapses(self):
        a=offer(); b=deepcopy(a)
        self.assertEqual(len(dedupe([a,b])),1)

    def test_different_branch_does_not_collapse(self):
        a=offer('branch_specific',['A'])
        b=offer('branch_specific',['B'])
        self.assertEqual(len(dedupe([a,b])),2)
