import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN=("prachinlife", "decision_published_places", "msb", "dqe", "central_db")
ALLOW_FILES={"README.md", "test_boundary.py"}

class BoundaryTest(unittest.TestCase):
    def test_forbidden_dependencies_absent(self):
        hits=[]
        for p in list((ROOT/"src").rglob("*.py"))+[ROOT/"pyproject.toml"]:
            text=p.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN:
                if token in text:
                    hits.append((str(p.relative_to(ROOT)),token))
        self.assertEqual(hits,[])
