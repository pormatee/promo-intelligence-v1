import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from promo_intelligence.applicability import resolve_applicability
from promo_intelligence.contract import validate_offer
from promo_intelligence.dedupe import dedupe
from promo_intelligence.fetch import FetchResult, fetch_url
from promo_intelligence.pipeline import run_live, write_diagnostics
from promo_intelligence.quality import quality_summary

ROOT = Path(__file__).resolve().parents[1]


def full_offer(source_id='a', item='Milk 1L'):
    return {
        'contract':'promo_offer_v1', 'offer_id':'promo_x', 'offer_type':'price_discount',
        'merchant':{'name':'Shop','branch':None}, 'item':{'name':item,'brand':None,'category':None},
        'pricing':{'currency':'THB','regular_price':60.0,'promo_price':49.0,'discount_amount':11.0,'discount_percent':18.33},
        'validity':{'start':'2026-09-01','end':'2026-09-30'}, 'conditions':[],
        'applicability':{'scope':'unknown','country':'TH','provinces':[],'branches':[], 'verification_state':'unknown','basis':'none','channel':'online','channel_basis':'source_config'},
        'verification':{'verification_state':'verified','freshness_state':'fresh','expiry_state':'active','source_reliability':'high'},
        'source':{'source_id':source_id,'source_type':'official_web','url':f'https://example.test/{source_id}','observed_at':'2026-09-08T00:00:00Z'},
        'evidence':{'content_hash':f'sha256:{source_id}','source_offer_id':None,'extracted_text':'Milk promo'},
    }


class _Resp:
    status=200
    headers={'Content-Type':'text/html'}
    def __init__(self, body=b'ok'):
        self.body=body; self.done=False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n):
        if self.done: return b''
        self.done=True
        return self.body


class WaveBTests(unittest.TestCase):
    def test_explicit_prachinburi_from_text(self):
        a=resolve_applicability({'evidence_excerpt':'ใช้ได้เฉพาะจังหวัดปราจีนบุรี','conditions':[]},{'channel':'store'})
        self.assertEqual(a['scope'],'selected_branches')
        self.assertEqual(a['provinces'],['Prachinburi'])
        self.assertEqual(a['channel'],'store')

    def test_explicit_branch_from_text(self):
        a=resolve_applicability({'evidence_excerpt':'โปรโมชั่นเฉพาะสาขา ปราจีนบุรี | วันนี้เท่านั้น','conditions':[]},{'channel':'store'})
        self.assertEqual(a['scope'],'branch_specific')
        self.assertEqual(a['branches'],['ปราจีนบุรี'])

    def test_online_unknown_is_not_actionable_location_gap(self):
        o=full_offer()
        q=quality_summary([o])
        self.assertEqual(q['online'],1)
        self.assertEqual(q['location_unknown_actionable'],0)

    def test_canonical_dedupe_and_corroboration(self):
        a=full_offer('source_a','Milk 1L')
        b=full_offer('source_b','milk-1l')
        rows=dedupe([a,b])
        self.assertEqual(len(rows),1)
        corr=rows[0]['evidence']['corroborating_sources']
        self.assertEqual(corr[0]['source_id'],'source_b')
        self.assertEqual(validate_offer(rows[0]),[])

    def test_fetch_retries_transient_error_within_budget(self):
        with patch('promo_intelligence.fetch.urlopen', side_effect=[URLError('temporary'), _Resp(b'hello')]), \
             patch('promo_intelligence.fetch.time.sleep', return_value=None):
            r=fetch_url('https://example.test', timeout=3, attempts=2)
        self.assertEqual(r.body,b'hello')
        self.assertEqual(r.attempts,2)

    def test_live_stats_name_failed_and_zero_offer_sources(self):
        sources=[
            {'source_id':'bad','url':'https://bad.test','family':'badfam','merchant':'Bad','extractor':'x','channel':'store'},
            {'source_id':'zero','url':'https://zero.test','family':'zerofam','merchant':'Zero','extractor':'x','channel':'online'},
        ]
        def ff(url, timeout=12):
            if 'bad' in url: raise URLError('blocked')
            return FetchResult(url,200,'text/html',b'x','2026-09-08T00:00:00Z','sha256:x')
        empty=([],{'candidates':0,'normalized':0,'exportable':0,'dedupe_removed':0,'location_known':0,'location_unknown':0})
        with tempfile.TemporaryDirectory() as td, \
             patch('promo_intelligence.pipeline.load_sources', return_value=sources), \
             patch('promo_intelligence.pipeline.fetch_url', side_effect=ff), \
             patch('promo_intelligence.pipeline._process', return_value=empty):
            offers,stats=run_live(td,max_workers=2)
        self.assertEqual(offers,[])
        self.assertEqual(stats['fetch_failed'],1)
        self.assertEqual(stats['source_errors'][0]['source_id'],'bad')
        self.assertEqual(stats['zero_offer_source_ids'],['zero'])

    def test_registry_channels_are_explicit(self):
        rows=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows),23)
        self.assertTrue(all(r.get('channel') in {'online','store','omnichannel','unknown'} for r in rows))

    def test_diagnostics_file_is_json_safe(self):
        stats={'sources':2,'fetched':1,'fetch_failed':1,'source_errors':[{'source_id':'x','stage':'fetch','error_type':'URLError','error':'x'}]}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'d.json'
            write_diagnostics(p,stats,[full_offer()])
            x=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(x['summary']['sources'],2)
        self.assertEqual(x['quality']['online'],1)


if __name__=='__main__': unittest.main()
