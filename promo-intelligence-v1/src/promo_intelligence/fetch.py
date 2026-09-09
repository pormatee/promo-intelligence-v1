from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes
    observed_at: str
    content_hash: str


def fetch_url(url: str, timeout: int = 20) -> FetchResult:
    req = Request(url, headers={"User-Agent": "PromoIntelligence-P0/0.1 (+evidence-only)"})
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return FetchResult(
            url=url,
            status=getattr(resp, "status", 200),
            content_type=resp.headers.get("Content-Type", "unknown"),
            body=body,
            observed_at=observed_at,
            content_hash="sha256:" + hashlib.sha256(body).hexdigest(),
        )
