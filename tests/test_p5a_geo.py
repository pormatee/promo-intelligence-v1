import unittest

from promo_intelligence.applicability import resolve_applicability
from promo_intelligence.contract import build_offer, validate_offer
from promo_intelligence.dedupe import dedupe
from promo_intelligence.geo import geography_summary, resolve_geography


class P5AGeoTests(unittest.TestCase):
    def source(self, **extra):
        x = {
            "source_id": "geo_test",
            "source_type": "official_web",
            "url": "https://example.com/promo",
            "merchant": "Demo",
            "channel": "store",
            "reliability": "high",
        }
        x.update(extra)
        return x

    def candidate(self, text):
        return {
            "merchant_name": "Demo",
            "item_name": "สินค้า A",
            "promo_price": 99.0,
            "regular_price": 129.0,
            "discount_amount": 30.0,
            "discount_percent": 23.26,
            "currency": "THB",
            "start": "2026-09-01",
            "end": "2026-09-30",
            "conditions": [],
            "evidence_excerpt": text,
        }

    def test_full_thai_address_is_structured_without_geocoding(self):
        c = self.candidate(
            "เฉพาะสาขาปราจีนบุรี ที่อยู่ 123 หมู่ 5 ตำบลหน้าเมือง "
            "อำเภอเมืองปราจีนบุรี จังหวัดปราจีนบุรี 25000"
        )
        s = self.source()
        app = resolve_applicability(c, s)
        self.assertEqual(app["scope"], "branch_specific")
        self.assertEqual(app["branches"], ["ปราจีนบุรี"])
        geo = resolve_geography(c, s, app)
        self.assertEqual(geo["detail_state"], "explicit")
        row = geo["locations"][0]
        self.assertEqual(row["province"], "Prachinburi")
        self.assertEqual(row["province_raw"], "ปราจีนบุรี")
        self.assertEqual(row["district"], "เมืองปราจีนบุรี")
        self.assertEqual(row["subdistrict"], "หน้าเมือง")
        self.assertEqual(row["branch_name"], "ปราจีนบุรี")
        self.assertEqual(row["postal_code"], "25000")
        self.assertIsNone(row["latitude"])
        self.assertIsNone(row["longitude"])
        self.assertEqual(row["granularity"], "address")

    def test_unknown_stays_unknown(self):
        c = self.candidate("ลดพิเศษวันนี้")
        s = self.source(channel="unknown")
        app = resolve_applicability(c, s)
        geo = resolve_geography(c, s, app)
        self.assertEqual(geo["detail_state"], "unknown")
        self.assertEqual(geo["locations"], [])

    def test_nationwide_has_no_fake_branch_address(self):
        c = self.candidate("ใช้ได้ทุกสาขาทั่วประเทศ")
        s = self.source()
        app = resolve_applicability(c, s)
        geo = resolve_geography(c, s, app)
        self.assertEqual(geo["detail_state"], "nationwide")
        self.assertEqual(geo["best_granularity"], "nationwide")
        self.assertEqual(geo["locations"], [])

    def test_explicit_labeled_coordinates_are_kept(self):
        c = self.candidate(
            "เฉพาะสาขา A จังหวัดปราจีนบุรี latitude 14.0500 longitude 101.3700"
        )
        s = self.source()
        app = resolve_applicability(c, s)
        geo = resolve_geography(c, s, app)
        row = geo["locations"][0]
        self.assertEqual(row["granularity"], "coordinates")
        self.assertEqual(row["latitude"], 14.05)
        self.assertEqual(row["longitude"], 101.37)

    def test_source_config_requires_explicit_verification(self):
        c = self.candidate("โปรหน้าร้าน")
        app = resolve_applicability(c, self.source())
        s = self.source(geography={
            "verification_state": "explicit",
            "locations": [{
                "province": "Prachinburi", "district": "เมืองปราจีนบุรี",
                "branch_name": "Demo Branch", "address": "123 Example Rd",
                "postal_code": "25000", "evidence_excerpt": "official store locator",
            }],
        })
        geo = resolve_geography(c, s, app)
        self.assertEqual(geo["locations"][0]["basis"], "source_config")
        self.assertEqual(geo["locations"][0]["district"], "เมืองปราจีนบุรี")

    def test_contract_accepts_structured_geography_and_rejects_bad_postcode(self):
        c = self.candidate("จังหวัดปราจีนบุรี อำเภอเมืองปราจีนบุรี")
        s = self.source()
        app = resolve_applicability(c, s)
        geo = resolve_geography(c, s, app)
        verification = {
            "verification_state": "verified", "freshness_state": "fresh",
            "expiry_state": "active", "source_reliability": "high",
        }
        offer = build_offer(c, s, "2026-09-08T10:00:00Z", "sha256:abc", verification, app, geo)
        self.assertEqual(validate_offer(offer), [])
        offer["geography"]["locations"][0]["postal_code"] = "1234"
        self.assertIn("geography.locations.postal_code", validate_offer(offer))

    def test_dedupe_does_not_merge_conflicting_explicit_addresses(self):
        verification = {
            "verification_state": "verified", "freshness_state": "fresh",
            "expiry_state": "active", "source_reliability": "high",
        }
        rows=[]
        for sid, text in [
            ("s1", "เฉพาะสาขา A ที่อยู่ 1 ถนน X ตำบลหน้าเมือง อำเภอเมืองปราจีนบุรี จังหวัดปราจีนบุรี 25000"),
            ("s2", "เฉพาะสาขา B ที่อยู่ 2 ถนน Y ตำบลหน้าเมือง อำเภอเมืองปราจีนบุรี จังหวัดปราจีนบุรี 25000"),
        ]:
            c=self.candidate(text)
            s=self.source(source_id=sid, url=f"https://example.com/{sid}")
            app=resolve_applicability(c,s)
            geo=resolve_geography(c,s,app)
            rows.append(build_offer(c,s,"2026-09-08T10:00:00Z",f"sha256:{sid}",verification,app,geo))
        self.assertEqual(len(dedupe(rows)), 2)

    def test_geography_summary_counts_detail_levels(self):
        c = self.candidate("เฉพาะสาขาปราจีนบุรี ที่อยู่ 123 ตำบลหน้าเมือง อำเภอเมืองปราจีนบุรี จังหวัดปราจีนบุรี 25000")
        s = self.source()
        app=resolve_applicability(c,s)
        geo=resolve_geography(c,s,app)
        verification={"verification_state":"verified","freshness_state":"fresh","expiry_state":"active","source_reliability":"high"}
        offer=build_offer(c,s,"2026-09-08T10:00:00Z","sha256:a",verification,app,geo)
        q=geography_summary([offer])
        self.assertEqual(q["district_known"],1)
        self.assertEqual(q["subdistrict_known"],1)
        self.assertEqual(q["address_known"],1)
        self.assertEqual(q["postal_code_known"],1)
        self.assertEqual(q["coordinates_known"],0)


if __name__ == "__main__":
    unittest.main()
