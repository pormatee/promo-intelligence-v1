import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from promo_intelligence.dedupe import dedupe
from promo_intelligence.extract import extract
from promo_intelligence.fetch import FetchResult, SourceFetchError, fetch_source

ROOT = Path(__file__).resolve().parents[1]


def offer(scope='unknown', source_id='a'):
    app={'scope':scope,'country':'TH','provinces':[],'branches':[],'verification_state':'unknown' if scope=='unknown' else 'explicit','basis':'none','channel':'store','channel_basis':'source_config'}
    if scope=='nationwide': app['basis']='explicit_nationwide'
    return {
        'contract':'promo_offer_v1','offer_id':'x','offer_type':'price_discount',
        'merchant':{'name':'Shop','branch':None},'item':{'name':'Milk 500 ml.','brand':None,'category':None},
        'pricing':{'currency':'THB','regular_price':60.0,'promo_price':49.0,'discount_amount':11.0,'discount_percent':18.33},
        'validity':{'start':'2026-09-01','end':'2026-09-30'},'conditions':[],
        'applicability':app,
        'verification':{'verification_state':'verified','freshness_state':'fresh','expiry_state':'active','source_reliability':'high'},
        'source':{'source_id':source_id,'source_type':'official_web','url':f'https://example.test/{source_id}','observed_at':'2026-09-08T00:00:00Z'},
        'evidence':{'content_hash':f'sha256:{source_id}','source_offer_id':None,'extracted_text':'Milk promo'},
    }


class WaveCTests(unittest.TestCase):
    def test_tops_v2_handles_split_price_lines_and_bundle(self):
        raw=(ROOT/'tests/fixtures/tops_split_price_sample.html').read_text(encoding='utf-8')
        src={'merchant':'Tops Online','validity_raw':'2 September 2026 - 15 September 2026'}
        rows=extract(raw,'tops_product_grid_v2',src)
        self.assertGreaterEqual(len(rows),2)
        price=next(x for x in rows if x['item_name'].startswith('เอ็มมิลค์'))
        self.assertEqual(price['promo_price_raw'],98.0)
        self.assertEqual(price['regular_price_raw'],101.5)
        bundle=next(x for x in rows if x['item_name'].startswith('เบทาโกร'))
        self.assertEqual(bundle['offer_type_hint'],'bundle')

    def test_config_has_wave_c_recovery_for_known_sources(self):
        rows={x['source_id']:x for x in json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))}
        self.assertEqual(len(rows),23)
        self.assertEqual(rows['tops_rte_fresh_food_sep_2026']['extractor'],'tops_product_grid_v2')
        self.assertTrue(rows['tops_rte_fresh_food_sep_2026']['zero_offer_alternate_urls'])
        self.assertTrue(rows['allonline_flashsale_live']['curl_fallback'])
        self.assertGreaterEqual(rows['allonline_flashsale_live']['timeout_seconds'],24)
        self.assertTrue(rows['watsons_brandcodes_sep_2026']['alternate_urls'])
        self.assertTrue(rows['watsons_99_campaign_2026']['curl_fallback'])

    def test_fetch_source_uses_alternate_official_url(self):
        source={'url':'https://a.test','alternate_urls':['https://b.test'],'timeout_seconds':5}
        good=FetchResult('https://b.test',200,'text/html',b'ok','2026-09-08T00:00:00Z','sha256:x')
        def ff(url, **kwargs):
            if url=='https://a.test':
                raise HTTPError(url,403,'Forbidden',{},None)
            return good
        with patch('promo_intelligence.fetch.fetch_url', side_effect=ff):
            r=fetch_source(source,default_timeout=5)
        self.assertEqual(r.url,'https://b.test')
        self.assertEqual(r.recovery_method,'alternate_urllib')

    def test_fetch_source_classifies_persistent_403_as_hard_block(self):
        source={'url':'https://a.test','alternate_urls':['https://b.test'],'timeout_seconds':5}
        def ff(url, **kwargs):
            raise HTTPError(url,403,'Forbidden',{},None)
        with patch('promo_intelligence.fetch.fetch_url', side_effect=ff):
            with self.assertRaises(SourceFetchError) as cm:
                fetch_source(source,default_timeout=5)
        self.assertTrue(cm.exception.hard_block)

    def test_dedupe_promotes_explicit_location_without_losing_corroboration(self):
        a=offer('unknown','a')
        b=offer('nationwide','b')
        b['applicability']['provinces']=[]
        rows=dedupe([a,b])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['applicability']['scope'],'nationwide')
        self.assertEqual(rows[0]['evidence']['corroborating_sources'][0]['source_id'],'b')


if __name__=='__main__': unittest.main()
