from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from .applicability_enrichment import html_to_lines, _discover_from_text, _context, _title_hits
from .geo import resolve_geography


_BLOCKED_SCHEMES = {"javascript", "mailto", "tel", "data"}
_BLOCKED_PATH_PARTS = (
    "/login", "/signin", "/sign-in", "/register", "/account", "/cart", "/checkout",
    "/privacy", "/cookie", "/terms-of-use", "/career", "/job", "/contact-us",
)
_ASSET_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".zip", ".css", ".js", ".json")
_DETAIL_HINTS = ("promotion", "promo", "campaign", "article", "detail", "terms", "condition", "offer", "privilege", "coupon")


def _norm(s: str | None) -> str:
    s = unescape(s or "").casefold()
    s = re.sub(r"[\s\u200b]+", " ", s).strip()
    return s


def _host_norm(host: str | None) -> str:
    h = (host or "").lower().strip(".")
    return h[4:] if h.startswith("www.") else h


def _same_official_host(base_url: str, candidate_url: str) -> bool:
    a = _host_norm(urlparse(base_url).hostname)
    b = _host_norm(urlparse(candidate_url).hostname)
    return bool(a and b and a == b)


def _canonical_url(url: str) -> str:
    p = urlparse(url)
    # fragments never affect terms content and would cause duplicate fetches
    return urlunparse((p.scheme, p.netloc, p.path or "/", p.params, p.query, ""))


@dataclass(frozen=True)
class LinkCandidate:
    url: str
    anchor_text: str
    score: int
    reason: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            d = {k.lower(): v for k, v in attrs}
            self._href = d.get("href")
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            text = re.sub(r"\s+", " ", unescape(" ".join(self._parts))).strip()
            self.links.append((self._href, text))
            self._href = None
            self._parts = []


def _title_tokens(title: str) -> set[str]:
    # Space-token overlap helps English/mixed titles. Thai titles often do not
    # tokenize usefully, so exact/contained matching remains the primary signal.
    return {x for x in re.findall(r"[a-z0-9ก-๙]+", _norm(title)) if len(x) >= 3}


def _link_score(title: str, anchor: str, url: str) -> tuple[int, str]:
    t = _norm(title)
    a = _norm(anchor)
    path = _norm(urlparse(url).path)
    if not t or len(t) < 4:
        return 0, "title_too_short"
    if a == t:
        return 100, "anchor_exact_title"
    if len(t) >= 12 and (t in a or (a in t and len(a) >= 12)):
        return 80, "anchor_contains_title"

    tt = _title_tokens(t)
    at = _title_tokens(a)
    overlap = len(tt & at)
    ratio = overlap / max(1, len(tt))
    score = 0
    reason = []
    if overlap >= 2 and ratio >= 0.5:
        score += 45
        reason.append("anchor_token_overlap")
    if any(h in path for h in _DETAIL_HINTS):
        score += 10
        reason.append("detail_path_hint")
    # Never accept a generic detail-path hint alone; there must be an offer-title
    # relation so unrelated campaign terms cannot become offer applicability.
    if score <= 10:
        return 0, "insufficient_title_relation"
    return score, "+".join(reason)


def discover_detail_links(raw_html: str, source_url: str, offer_title: str, limit: int = 3) -> list[LinkCandidate]:
    parser = _LinkParser()
    parser.feed(raw_html or "")
    out: list[LinkCandidate] = []
    seen: set[str] = set()
    source_canon = _canonical_url(source_url)
    for href, anchor in parser.links:
        if not href:
            continue
        parsed_href = urlparse(href)
        if parsed_href.scheme.lower() in _BLOCKED_SCHEMES:
            continue
        absolute = _canonical_url(urljoin(source_url, href))
        p = urlparse(absolute)
        if p.scheme not in {"http", "https"}:
            continue
        if not _same_official_host(source_url, absolute):
            continue
        low_path = p.path.lower()
        if any(x in low_path for x in _BLOCKED_PATH_PARTS) or low_path.endswith(_ASSET_EXTS):
            continue
        if absolute == source_canon or absolute in seen:
            continue
        score, reason = _link_score(offer_title, anchor, absolute)
        if score <= 0:
            continue
        seen.add(absolute)
        out.append(LinkCandidate(absolute, anchor, score, reason))
    out.sort(key=lambda x: (-x.score, len(x.url), x.url))
    return out[: max(0, limit)]


def _detail_evidence(detail_html: str, offer_title: str, candidate: LinkCandidate) -> tuple[str | None, str]:
    lines = html_to_lines(detail_html or "")
    if not lines:
        return None, "empty_page"
    hits = _title_hits(lines, offer_title)
    if len(hits) == 1:
        return _context(lines, hits[0], radius=24), "detail_exact_title_context"
    if len(hits) > 1:
        return None, "detail_title_ambiguous"

    # If the listing anchor itself exactly matched the offer title, the link is a
    # strong direct association. We still limit evidence to the page beginning,
    # where a dedicated campaign title/terms normally live, rather than scanning
    # arbitrary site-wide text.
    if candidate.score >= 80:
        return " | ".join(lines[:120]), "detail_direct_link_context"
    return None, "detail_title_not_found"


def evaluate_detail_page(offer: dict, source: dict, candidate: LinkCandidate, detail_html: str,
                         observed_at: str | None = None, content_hash: str | None = None) -> tuple[dict | None, dict]:
    app = offer.get("applicability") or {}
    channel = app.get("channel") or source.get("channel") or "unknown"
    stats = {"page_evaluated": 1, "discovered": 0, "nationwide": 0, "province": 0, "branch": 0,
             "title_not_found": 0, "title_ambiguous": 0}
    if app.get("scope") != "unknown" or channel == "online":
        return None, stats
    evidence, method = _detail_evidence(detail_html, ((offer.get("item") or {}).get("name") or ""), candidate)
    if evidence is None:
        if method == "detail_title_ambiguous": stats["title_ambiguous"] = 1
        else: stats["title_not_found"] = 1
        return None, stats
    discovered, kind = _discover_from_text(evidence, channel)
    if discovered is None:
        return None, stats
    result = {
        "applicability": discovered,
        "geography": resolve_geography({"evidence_excerpt": evidence, "conditions": []}, source, discovered),
        "evidence": {
            "state": "explicit",
            "method": method,
            "source_id": source.get("source_id"),
            "source_url": source.get("url"),
            "detail_url": candidate.url,
            "link_anchor": candidate.anchor_text[:240],
            "link_reason": candidate.reason,
            "detail_observed_at": observed_at,
            "detail_content_hash": content_hash,
            "evidence_excerpt": evidence[:800],
        },
        "kind": kind,
    }
    stats["discovered"] = 1
    stats[kind] += 1
    return result, stats


def apply_detail_results(offer: dict, results: list[dict]) -> tuple[dict, str]:
    """Apply only one unambiguous explicit applicability result.

    If multiple official detail pages disagree, preserve unknown and surface a
    conflict instead of choosing one.
    """
    out = deepcopy(offer)
    if not results:
        return out, "none"

    def signature(r: dict) -> str:
        a = r["applicability"]
        return json.dumps({
            "scope": a.get("scope"),
            "provinces": sorted(a.get("provinces") or []),
            "branches": sorted(a.get("branches") or []),
            "channel": a.get("channel"),
        }, sort_keys=True, ensure_ascii=False)

    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(signature(r), []).append(r)
    if len(groups) != 1:
        out["applicability_detail_evidence"] = {
            "state": "conflict",
            "method": "official_detail_page",
            "detail_urls": [r["evidence"]["detail_url"] for r in results],
        }
        return out, "conflict"
    chosen = next(iter(groups.values()))[0]
    out["applicability"] = chosen["applicability"]
    out["geography"] = chosen["geography"]
    out["applicability_evidence"] = chosen["evidence"]
    out["applicability_detail_evidence"] = chosen["evidence"]
    return out, chosen["kind"]


def cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def cache_paths(cache_dir: Path, url: str) -> tuple[Path, Path]:
    key = cache_key(url)
    return cache_dir / f"{key}.html", cache_dir / f"{key}.json"
