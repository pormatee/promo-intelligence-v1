import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class P4RegistryTests(unittest.TestCase):
    def test_p4_registry_has_exactly_23_enabled_sources(self):
        rows = json.loads((ROOT / 'config' / 'sources.json').read_text(encoding='utf-8'))
        enabled = [r for r in rows if r.get('enabled') is True]
        self.assertEqual(len(enabled), 23)

    def test_p4_registry_has_13_families(self):
        rows = json.loads((ROOT / 'config' / 'sources.json').read_text(encoding='utf-8'))
        enabled = [r for r in rows if r.get('enabled') is True]
        families = {r.get('family') for r in enabled}
        self.assertEqual(len(families), 13)
        self.assertTrue({'lotus','tops','bigc','cjmore','7eleven','allonline','watsons','makro','homepro','central','powerbuy','dohome','globalhouse'} <= families)

if __name__ == '__main__':
    unittest.main()
