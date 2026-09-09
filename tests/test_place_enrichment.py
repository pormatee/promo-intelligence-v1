import copy
import json
import tempfile
import unittest
from pathlib import Path

from promo_intelligence.fetch import FetchResult
from promo_intelligence.place_enrichment import (
    extract_globalhouse, extract_homepro, extract_makro, extract_powerbuy,
    refresh_place_cache,
)
from promo_intelligence.place_master import build_place_master, make_locator_records, validate_place
from promo_intelligence.published import load_merchant_branch_index, load_published_places, publish_snapshot
from test_place_foundation import offer


def src(extractor, merchant="Demo"):
    return {"source_id":"s", "merchant":merchant, "extractor":extractor, "url":"https://example.test", "enabled":True, "reliability":"high"}


class PlaceEnrichmentTest(unittest.TestCase):
    def test_globalhouse_directory_extracts_explicit_branch_names(self):
        html='''<a href="/store-finder/roi-et">โกลบอลเฮ้าส์ สาขาร้อยเอ็ด</a>
        <a href="/store-finder/kabin-buri">โกลบอลเฮ้าส์ สาขากบินทร์บุรี</a>'''.encode()
        rows=extract_globalhouse(src("globalhouse_directory"), html)
        self.assertEqual([x["branch_name"] for x in rows], ["ร้อยเอ็ด", "กบินทร์บุรี"])
        self.assertTrue(all(x["province"] is None for x in rows))  # no inference from branch name

    def test_makro_directory_keeps_explicit_province_context(self):
        html='''<h2>ปราจีนบุรี</h2><li>กบินทร์บุรี(แม็คโคร)</li><li>ปราจีนบุรี(แม็คโคร)</li>
        <h2>ระยอง</h2><li>ระยอง(แม็คโคร)</li>'''.encode()
        rows=extract_makro(src("makro_directory"), html)
        self.assertEqual(rows[0]["province"], "ปราจีนบุรี")
        self.assertEqual(rows[0]["branch_name"], "กบินทร์บุรี")
        self.assertEqual(rows[-1]["province"], "ระยอง")

    def test_homepro_directory_keeps_branch_only_without_guessing_province(self):
        html='''<option>โฮมโปรออนไลน์</option><option>โฮมโปร ลาดพร้าว</option><option>โฮมโปร S เกตเวย์ เอกมัย</option>'''.encode()
        rows=extract_homepro(src("homepro_directory"), html)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["branch_name"],"ลาดพร้าว")
        self.assertIsNone(rows[0]["province"])

    def test_powerbuy_locator_extracts_explicit_address_and_postcode(self):
        html='''<div>MEGA BANGNA</div><div>39 Moo 6 Bangna-Trad Rd. T.Bangkaew A.Bangplee Samutprakarn 10540</div><div>Open Today: 11:00 - 20:00</div>'''.encode()
        rows=extract_powerbuy(src("powerbuy_directory"), html)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["postal_code"],"10540")
        self.assertIn("Bangna-Trad", rows[0]["address"])

    def test_locator_records_are_verified_places(self):
        rows=make_locator_records("Demo Mart", [{"branch_name":"North", "province":"ปราจีนบุรี", "evidence_excerpt":"North ปราจีนบุรี"}],
            source_id="official", url="https://example.test/branches", observed_at="2026-09-08T00:00:00Z", content_hash="sha256:abc")
        self.assertEqual(sum(x["record_kind"]=="merchant" for x in rows),1)
        self.assertEqual(sum(x["record_kind"]=="branch" for x in rows),1)
        self.assertTrue(all(not validate_place(x) for x in rows))
        branch=next(x for x in rows if x["record_kind"]=="branch")
        self.assertEqual(branch["verification"]["state"],"verified")

    def test_seed_branches_do_not_fake_offer_applicability(self):
        x=offer(merchant="Demo Mart")
        x["applicability"].update({"scope":"nationwide", "branches":[], "provinces":[]})
        x["geography"]={"country":"TH","detail_state":"nationwide","best_granularity":"nationwide","locations":[]}
        seed=make_locator_records("Demo Mart", [{"branch_name":"North", "province":"ปราจีนบุรี"}], source_id="official", url="https://example.test", observed_at="2026-09-08T00:00:00Z", content_hash="sha256:abc")
        enriched, places, stats=build_place_master([x], seed_places=seed, now="2026-09-08T00:00:00Z")
        self.assertEqual(stats["branch_places"],1)
        self.assertEqual(enriched[0]["place_refs"],[])
        self.assertEqual(stats["offers_with_physical_place_ref"],0)

    def test_published_directory_includes_child_branches_and_index(self):
        x=offer(merchant="Demo Mart")
        x["applicability"].update({"scope":"nationwide", "branches":[], "provinces":[]})
        x["geography"]={"country":"TH","detail_state":"nationwide","best_granularity":"nationwide","locations":[]}
        seed=make_locator_records("Demo Mart", [{"branch_name":"North", "province":"ปราจีนบุรี"}], source_id="official", url="https://example.test", observed_at="2026-09-08T00:00:00Z", content_hash="sha256:abc")
        enriched, places, _=build_place_master([x], seed_places=seed, now="2026-09-08T00:00:00Z")
        with tempfile.TemporaryDirectory() as td:
            manifest,_=publish_snapshot(td,enriched,places,now="2026-09-08T01:00:00Z")
            self.assertEqual(manifest["branch_place_count"],1)
            self.assertEqual(len(load_published_places(td)),2)
            idx=load_merchant_branch_index(td)
            self.assertEqual(idx["branch_count"],1)
            self.assertIn("offer applicability", idx["semantics"])
            self.assertEqual(enriched[0]["place_refs"],[])

    def test_failed_refresh_preserves_previous_cache_for_failed_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"config").mkdir(parents=True)
            (root/"config"/"place_sources.json").write_text(json.dumps([
                {"source_id":"gh", "merchant":"Global House", "extractor":"globalhouse_directory", "url":"https://example.test", "reliability":"high", "enabled":True}
            ]),encoding="utf-8")
            cache=root/"data"/"place_enrichment"/"official_places.jsonl"
            cache.parent.mkdir(parents=True)
            old=make_locator_records("Global House", [{"branch_name":"เดิม"}], source_id="gh", url="https://example.test", observed_at="2026-09-01T00:00:00Z", content_hash="sha256:old")
            cache.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in old),encoding="utf-8")
            def fail(_): raise TimeoutError("offline")
            rows,stats=refresh_place_cache(root, fetcher=fail, progress=None)
            self.assertEqual(stats["fetch_failed"],1)
            self.assertEqual(sum(x["record_kind"]=="branch" for x in rows),1)
            self.assertEqual(stats["result"],"PASS")


if __name__=="__main__": unittest.main()
