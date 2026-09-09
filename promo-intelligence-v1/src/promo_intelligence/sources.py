from __future__ import annotations
import json
from pathlib import Path


def load_sources(path: str | Path) -> list[dict]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [row for row in rows if row.get("enabled") is True]
