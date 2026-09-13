import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("consumer", ROOT / "build_promo_consumer.py")
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


class WebPilotUXV19Tests(unittest.TestCase):
    def test_rc_runtime_token_is_hidden(self):
        self.assertTrue(consumer.looks_technical_payload('$RC("B:2","S:2")'))
        self.assertIsNone(consumer.clean_display_text('$RC("B:2","S:2")'))

    def test_pwa_and_fixed_nav_contract_present(self):
        src = (ROOT / "build_promo_consumer.py").read_text(encoding="utf-8")
        self.assertIn('href="./manifest.webmanifest"', src)
        self.assertIn("navigator.serviceWorker.register('./sw.js')", src)
        self.assertIn("promo_consumer_ui_state_v1", src)
        self.assertIn(".bottomnav{position:fixed!important", src)
        self.assertNotIn(".places,.bottomnav{position:relative}", src)

    def test_store_cards_are_tappable(self):
        src = (ROOT / "build_promo_consumer.py").read_text(encoding="utf-8")
        self.assertIn('data-place-detail=', src)
        self.assertIn("function openPlaceDetail(id)", src)
        self.assertIn("โปรที่ยืนยันกับสาขานี้", src)

    def test_save_action_has_clear_label(self):
        src = (ROOT / "build_promo_consumer.py").read_text(encoding="utf-8")
        self.assertIn("★ บันทึกแล้ว", src)
        self.assertIn("☆ บันทึก", src)


if __name__ == "__main__":
    unittest.main()
