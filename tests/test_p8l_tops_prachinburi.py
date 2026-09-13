import unittest

from promo_intelligence.place_enrichment import extract_tops_branch_detail


class P8LTopsPrachinburiTests(unittest.TestCase):
    def source(self):
        return {
            "branch_name": "โรบินสัน ปราจีนบุรี",
            "heading_token": "Tops Robinson Prachin Buri",
            "province": "ปราจีนบุรี",
            "province_token": "Prachin Buri",
            "postal_code": "25000",
        }

    def good_html(self):
        return (
            "<h1>Tops Robinson Prachin Buri</h1>"
            "<p>Prachin Buri</p>"
            "<div>Address 72 Moo 3 Bang Boribun Mueang Prachin Buri Prachin Buri 25000</div>"
            "<div>Coordinates 14.0597115, 101.3768242</div>"
        ).encode()

    def test_explicit_official_branch_detail_is_accepted(self):
        rows=extract_tops_branch_detail(self.source(),self.good_html())
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row["province"],"ปราจีนบุรี")
        self.assertEqual(row["postal_code"],"25000")
        self.assertEqual(row["latitude"],14.0597115)
        self.assertEqual(row["longitude"],101.3768242)

    def test_heading_alone_never_implies_province(self):
        self.assertEqual(extract_tops_branch_detail(self.source(),b"<h1>Tops Robinson Prachin Buri</h1>"),[])

    def test_missing_explicit_province_token_is_rejected(self):
        html=("<h1>Tops Robinson Prachin Buri</h1><div>Address 72 Moo 3 25000</div>"
              "<div>Coordinates 14.0597115, 101.3768242</div>").encode()
        self.assertEqual(extract_tops_branch_detail(self.source(),html),[])

    def test_wrong_postcode_is_rejected(self):
        html=("<h1>Tops Robinson Prachin Buri</h1>"
              "<div>Address 72 Moo 3 Mueang Prachin Buri 25140</div>"
              "<div>Coordinates 14.0597115, 101.3768242</div>").encode()
        self.assertEqual(extract_tops_branch_detail(self.source(),html),[])

    def test_missing_coordinates_is_rejected(self):
        html=("<h1>Tops Robinson Prachin Buri</h1>"
              "<div>Address 72 Moo 3 Mueang Prachin Buri 25000</div>").encode()
        self.assertEqual(extract_tops_branch_detail(self.source(),html),[])

    def test_invalid_coordinates_are_rejected(self):
        html=("<h1>Tops Robinson Prachin Buri</h1>"
              "<div>Address 72 Moo 3 Mueang Prachin Buri 25000</div>"
              "<div>Coordinates 114.0, 201.0</div>").encode()
        self.assertEqual(extract_tops_branch_detail(self.source(),html),[])

    def test_does_not_borrow_from_next_tops_branch(self):
        html=("<h1>Tops Robinson Prachin Buri</h1><p>ข้อมูลไม่ครบ</p>"
              "<h2>Tops Robinson Chachoengsao</h2>"
              "<div>Address 910 Mueang Chachoengsao 24000</div>"
              "<div>Coordinates 13.6681425, 101.028724</div>").encode()
        self.assertEqual(extract_tops_branch_detail(self.source(),html),[])

    def test_missing_heading_is_rejected(self):
        html=("<div>Address 72 Moo 3 Mueang Prachin Buri 25000</div>"
              "<div>Coordinates 14.0597115, 101.3768242</div>").encode()
        self.assertEqual(extract_tops_branch_detail(self.source(),html),[])


if __name__ == "__main__":
    unittest.main()
