import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / 'build_promo_consumer.py').read_text(encoding='utf-8')

class AndroidInteractionTests(unittest.TestCase):
    def test_native_controls_are_touch_hardened(self):
        self.assertIn('touch-action:manipulation', TEXT)
        self.assertIn('pointer-events:auto!important', TEXT)
        self.assertIn('.drawerBackdrop:not(.show)', TEXT)
        self.assertIn('bindInteractions()', TEXT)

    def test_filter_status_exists(self):
        self.assertIn('interactionStatus', TEXT)
        self.assertIn("addEventListener('change'", TEXT)

if __name__ == '__main__':
    unittest.main()
