import unittest
import applicability_autoclose_loop as m

class P5HTests(unittest.TestCase):
    def test_metric_last_value(self):
        self.assertEqual(m.metric('X=1\nX=3\n','X'),3)
    def test_actionable_excludes_online(self):
        self.assertTrue(m.actionable({'applicability':{'scope':'unknown','channel':'physical'}}))
        self.assertFalse(m.actionable({'applicability':{'scope':'unknown','channel':'online'}}))
    def test_signature_stable_order_independent(self):
        a={'offer_id':'a','applicability':{'scope':'unknown','channel':'physical'}}
        b={'offer_id':'b','applicability':{'scope':'unknown','channel':'physical'}}
        self.assertEqual(m.actionable_signature([a,b]),m.actionable_signature([b,a]))
    def test_stop_all_resolved(self):
        self.assertEqual(m.stop_reason(2,0,'a','b',1,1),'ALL_RESOLVED')
    def test_stop_stable_no_discovery(self):
        self.assertEqual(m.stop_reason(18,18,'x','x',0,0),'STABLE_EVIDENCE_EXHAUSTED')
    def test_continue_on_progress(self):
        self.assertIsNone(m.stop_reason(18,17,'x','y',0,1))

if __name__=='__main__': unittest.main()
