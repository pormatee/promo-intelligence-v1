from __future__ import annotations

from copy import deepcopy
from html import unescape
from html.parser import HTMLParser
import re

from .applicability import THAI_PROVINCE_MAP
from .geo import resolve_geography


class _TextParser(HTMLParser):
    BLOCK = {"p","div","li","br","h1","h2","h3","h4","section","article","span","a","button"}
    def __init__(self) -> None:
        super().__init__(); self.parts: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.BLOCK: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in self.BLOCK: self.parts.append("\n")
    def handle_data(self, data): self.parts.append(data)


def html_to_lines(raw_html: str) -> list[str]:
    p=_TextParser(); p.feed(raw_html)
    text=unescape("".join(p.parts)).replace("\xa0"," ")
    out=[]
    for line in text.splitlines():
        line=re.sub(r"\s+"," ",line).strip()
        if line: out.append(line)
    return out


def _norm(value: str | None) -> str:
    s=unescape(value or "").casefold()
    s=re.sub(r"\s+"," ",s).strip()
    return s


def _title_hits(lines: list[str], title: str) -> list[int]:
    target=_norm(title)
    if len(target) < 4: return []
    exact=[i for i,x in enumerate(lines) if _norm(x)==target]
    if exact: return exact
    # Conservative contained match. Require a substantial title so generic
    # campaign words cannot anchor unrelated page text.
    if len(target) < 12: return []
    return [i for i,x in enumerate(lines) if target in _norm(x) or _norm(x) in target and len(_norm(x)) >= 12]


def _context(lines: list[str], idx: int, radius: int = 10) -> str:
    return " | ".join(lines[max(0,idx-radius):min(len(lines),idx+radius+1)])


def _explicit_provinces(text: str) -> list[str]:
    out=[]
    for thai, canonical in sorted(THAI_PROVINCE_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
        pat=rf"(?:เฉพาะ(?:ใน)?|ใช้ได้(?:เฉพาะ)?(?:ใน|ที่)?|ร่วมรายการ(?:เฉพาะ)?(?:ใน|ที่)?|จังหวัด|จ\.)\s*(?:จังหวัด|จ\.)?\s*{re.escape(thai)}"
        if re.search(pat,text,re.I) and canonical not in out:
            out.append(canonical)
    return out


def _clean_branch(s: str) -> str:
    return re.sub(r"\s+"," ",s).strip(" .,:;|/-–—")


def _explicit_branches(text: str) -> list[str]:
    out=[]
    pats=[
        r"(?:เฉพาะ|ใช้ได้(?:เฉพาะ)?ที่|ร่วมรายการ(?:เฉพาะ)?ที่)\s*สาขา\s*([^|;]{2,80}?)(?=\s*(?:ที่อยู่|ตำบล|ต\.|อำเภอ|อ\.|จังหวัด|จ\.|แขวง|เขต|รหัสไปรษณีย์|postal\s*code|[|;]|$))",
        r"(?:valid|available)\s+(?:only\s+)?at\s+branch\s+([^|;]{2,80}?)(?=\s*(?:address|province|district|[|;]|$))",
    ]
    for pat in pats:
        for m in re.finditer(pat,text,re.I):
            name=_clean_branch(m.group(1))
            if name and not re.search(r"^(?:ทุกสาขา|all branches|nationwide)$",name,re.I) and name not in out:
                out.append(name)
    return out[:10]


def _is_nationwide(text: str) -> bool:
    strong=[
        r"(?:โปรโมชั่น(?:นี้)?|โปรโมชัน(?:นี้)?|รายการ(?:นี้)?|สิทธิ์(?:นี้)?|คูปอง(?:นี้)?).{0,140}(?:ใช้ได้|ร่วมรายการ|ใช้สิทธิ์ได้).{0,100}(?:ทุกสาขา|ทั่วประเทศ)",
        r"(?:ใช้ได้|ร่วมรายการ|ใช้สิทธิ์ได้).{0,100}(?:ทุกสาขาทั่วประเทศ|ทุกสาขา|ทั่วประเทศ)",
        r"(?:promotion|offer|coupon).{0,140}(?:valid|available|redeemable).{0,100}(?:all branches|nationwide)",
        r"(?:valid|available|redeemable).{0,100}(?:at all branches|nationwide)",
        r"(?:ทุกสาขาทั่วประเทศ|all branches nationwide)",
    ]
    return any(re.search(p,text,re.I|re.S) for p in strong)


def _discover_from_text(text: str, channel: str) -> tuple[dict | None, str | None]:
    # Online offers are not converted into local physical applicability. Their
    # delivery geography is a separate future concern.
    if channel == "online": return None, None
    branches=_explicit_branches(text)
    provinces=_explicit_provinces(text)
    if branches:
        return ({
            "scope":"branch_specific" if len(branches)==1 else "selected_branches",
            "country":"TH", "provinces":provinces, "branches":branches,
            "verification_state":"explicit", "basis":"offer_text",
            "channel":channel, "channel_basis":"source_config" if channel!="unknown" else "none",
        }, "branch")
    if provinces:
        return ({
            "scope":"selected_branches", "country":"TH", "provinces":provinces, "branches":[],
            "verification_state":"explicit", "basis":"offer_text",
            "channel":channel, "channel_basis":"source_config" if channel!="unknown" else "none",
        }, "province")
    if _is_nationwide(text):
        return ({
            "scope":"nationwide", "country":"TH", "provinces":[], "branches":[],
            "verification_state":"explicit", "basis":"offer_text",
            "channel":channel, "channel_basis":"source_config" if channel!="unknown" else "none",
        }, "nationwide")
    return None, None


def enrich_offer_applicability(offer: dict, source: dict, raw_html: str | None) -> tuple[dict, dict]:
    out=deepcopy(offer)
    app=out.get("applicability") or {}
    channel=app.get("channel") or source.get("channel") or "unknown"
    stats={"attempted":0,"discovered":0,"nationwide":0,"province":0,"branch":0,"context_ambiguous":0,"title_not_found":0,"raw_missing":0}
    if app.get("scope") != "unknown" or channel == "online":
        return out,stats
    stats["attempted"]=1

    # First inspect the evidence already attached directly to this offer.
    direct=" | ".join([
        (out.get("evidence") or {}).get("extracted_text","") or "",
        " | ".join(out.get("conditions") or []),
    ]).strip()
    discovered,kind=_discover_from_text(direct,channel)
    method="direct_offer_evidence"
    evidence=direct

    # If direct evidence is insufficient, anchor raw-page context to the offer
    # title. Exactly one match is required; ambiguous/missing titles never apply
    # page-level geography.
    if discovered is None:
        if not raw_html:
            stats["raw_missing"]=1; return out,stats
        lines=html_to_lines(raw_html)
        title=((out.get("item") or {}).get("name") or "").strip()
        hits=_title_hits(lines,title)
        if len(hits)==0:
            stats["title_not_found"]=1; return out,stats
        if len(hits)!=1:
            stats["context_ambiguous"]=1; return out,stats
        evidence=_context(lines,hits[0],radius=10)
        discovered,kind=_discover_from_text(evidence,channel)
        method="raw_exact_title_context"

    if discovered is None:
        return out,stats

    out["applicability"]=discovered
    candidate={"evidence_excerpt":evidence,"conditions":[]}
    out["geography"]=resolve_geography(candidate,source,discovered)
    out["applicability_evidence"]={
        "state":"explicit",
        "method":method,
        "source_id":source.get("source_id"),
        "url":source.get("url"),
        "content_hash":(out.get("evidence") or {}).get("content_hash"),
        "evidence_excerpt":evidence[:500],
    }
    stats["discovered"]=1
    stats[kind]+=1
    return out,stats


def enrich_offers_applicability(offers: list[dict], sources: dict[str,dict], raw_by_source: dict[str,str]) -> tuple[list[dict],dict]:
    totals={"offers_scanned":len(offers),"attempted":0,"discovered":0,"nationwide":0,"province":0,"branch":0,"context_ambiguous":0,"title_not_found":0,"raw_missing":0}
    out=[]
    for offer in offers:
        sid=(offer.get("source") or {}).get("source_id") or ""
        source=sources.get(sid) or {"source_id":sid,"url":(offer.get("source") or {}).get("url"),"channel":(offer.get("applicability") or {}).get("channel","unknown")}
        enriched,s=enrich_offer_applicability(offer,source,raw_by_source.get(sid))
        out.append(enriched)
        for k in totals:
            if k!="offers_scanned": totals[k]+=s.get(k,0)
    return out,totals
