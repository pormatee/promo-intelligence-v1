from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Callable

from .fetch import FetchResult, SourceFetchError, fetch_source
from .place_master import make_locator_records, merge_place_records, validate_place


BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "button", "li", "p", "option", "a", "div"}
THAI_PROVINCES = {
    "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา",
    "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก",
    "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน",
    "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา",
    "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต",
    "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี",
    "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ",
    "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี",
    "สุรินทร์", "หนองคาย", "หนองบัวลำภู", "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


class _Blocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, list[str], dict[str, str]]] = []
        self.lines: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self.stack.append((tag, [], dict(attrs)))

    def handle_data(self, data):
        if self.stack:
            for i in range(len(self.stack)):
                self.stack[i][1].append(data)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                t, parts, attrs = self.stack.pop(i)
                text = _clean("".join(parts))
                if text:
                    self.lines.append(text)
                    if t == "a":
                        self.anchors.append((text, attrs.get("href", "")))
                return


def html_blocks(body: bytes) -> tuple[list[str], list[tuple[str, str]]]:
    text = body.decode("utf-8", errors="replace")
    p = _Blocks()
    p.feed(text)
    # Preserve order, drop exact duplicates caused by nested blocks.
    lines: list[str] = []
    for line in p.lines:
        if not lines or line != lines[-1]:
            lines.append(line)
    return lines, p.anchors


def _province_line(line: str) -> str | None:
    line = _clean(line).replace("จังหวัด", "").strip()
    return line if line in THAI_PROVINCES else None


def _candidate(branch_name: str, *, province: str | None = None, district: str | None = None,
               subdistrict: str | None = None, address: str | None = None, postal_code: str | None = None,
               latitude=None, longitude=None, evidence_excerpt: str = "") -> dict:
    return {
        "branch_name": _clean(branch_name),
        "province": _clean(province) or None,
        "district": _clean(district) or None,
        "subdistrict": _clean(subdistrict) or None,
        "address": _clean(address) or None,
        "postal_code": postal_code,
        "latitude": latitude,
        "longitude": longitude,
        "evidence_excerpt": _clean(evidence_excerpt)[:500],
    }


def extract_globalhouse(source: dict, body: bytes) -> list[dict]:
    lines, anchors = html_blocks(body)
    out: list[dict] = []
    seen: set[str] = set()
    for text, href in anchors:
        m = re.search(r"โกลบอลเฮ้าส์\s*สาขา\s*(.+)$", text, re.I)
        if not m:
            continue
        if href and "store-finder" not in href:
            continue
        name = _clean(m.group(1))
        if name and name not in seen:
            out.append(_candidate(name, evidence_excerpt=text))
            seen.add(name)
    if not out:
        for line in lines:
            m = re.search(r"โกลบอลเฮ้าส์\s*สาขา\s*(.+)$", line, re.I)
            if m:
                name = _clean(m.group(1))
                if name and name not in seen and len(name) < 120:
                    out.append(_candidate(name, evidence_excerpt=line))
                    seen.add(name)
    return out


def extract_globalhouse_detail(source: dict, body: bytes) -> list[dict]:
    # Prefer structured PostalAddress from official JSON-LD.
    # Keep the address human-readable and deduplicate locality/province/postcode
    # already present inside streetAddress.
    # Branch name alone never becomes province evidence.
    raw = body.decode("utf-8", errors="replace")
    branch_name = _clean(source.get("branch_name"))
    province = _clean(source.get("province"))
    slug_hint = _clean(source.get("url")).rstrip("/").split("/")[-1].casefold()
    heading_token = _clean(source.get("heading_token"))
    province_token = _clean(source.get("province_token")) or province

    if not branch_name or not province:
        return []

    scripts = re.findall(
        r'<script\b[^>]*\btype\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw,
        flags=re.I | re.S,
    )

    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    def norm(value: str | None) -> str:
        return re.sub(r"[\s,]+", "", _clean(value)).casefold()

    def build_clean_address(address: dict) -> str:
        street = _clean(address.get("streetAddress"))
        locality = _clean(address.get("addressLocality"))
        region = _clean(address.get("addressRegion"))
        postal = _clean(address.get("postalCode"))

        parts = [street] if street else []
        whole = norm(street)

        for value in (locality, region, postal):
            if not value:
                continue
            nv = norm(value)
            if nv and nv not in whole:
                parts.append(value)
                whole += nv

        return ", ".join(parts)

    for blob in scripts:
        try:
            data = json.loads(blob.strip())
        except Exception:
            continue

        for obj in walk(data):
            address = obj.get("address")
            if not isinstance(address, dict):
                continue

            region = _clean(address.get("addressRegion"))
            postal = _clean(address.get("postalCode"))
            if region != province or not re.fullmatch(r"\d{5}", postal or ""):
                continue

            name = _clean(obj.get("name"))
            url = _clean(obj.get("url")).casefold()
            description = _clean(obj.get("description"))

            if not (
                branch_name.casefold() in name.casefold()
                or branch_name.casefold() in description.casefold()
                or (slug_hint and slug_hint in url)
            ):
                continue

            clean_address = build_clean_address(address)
            forbidden = ("acceptedAnswer", "@type", "FAQPage", "Question", "description", "schema.org")

            if (
                clean_address
                and len(clean_address) <= 350
                and not any(token.casefold() in clean_address.casefold() for token in forbidden)
            ):
                return [_candidate(
                    branch_name,
                    province=province,
                    address=clean_address,
                    postal_code=postal,
                    evidence_excerpt=f"{name or branch_name} | {clean_address}",
                )]

    # Backward-compatible explicit HTML fallback for older fixtures/pages.
    lines, _ = html_blocks(body)
    heading_cf = (heading_token or branch_name).casefold()
    heading_index = None

    for i, line in enumerate(lines):
        if heading_cf in _clean(line).casefold():
            heading_index = i
            break

    if heading_index is None:
        return []

    province_cf = province_token.casefold()
    forbidden = ("acceptedAnswer", "@type", "FAQPage", "Question", "description", "schema.org", "{", "}")

    for raw_line in lines[heading_index + 1:heading_index + 10]:
        line = _clean(raw_line)
        if not line or len(line) > 350:
            continue

        pc = re.search(r"\b(\d{5})\b", line)
        if not pc or province_cf not in line.casefold():
            continue
        if branch_name.casefold() not in line.casefold():
            continue
        if any(token.casefold() in line.casefold() for token in forbidden):
            continue

        return [_candidate(
            branch_name,
            province=province,
            address=line,
            postal_code=pc.group(1),
            evidence_excerpt=f"{heading_token or branch_name} | {line}",
        )]

    return []

def extract_makro(source: dict, body: bytes) -> list[dict]:
    lines, _ = html_blocks(body)
    out: list[dict] = []
    seen: set[tuple[str | None, str]] = set()
    province: str | None = None
    for line in lines:
        p = _province_line(line)
        if p:
            province = p
            continue
        # Thai and English pages use parenthesized chain names.
        m = re.match(r"(.+?)\s*\((?:แม็คโคร|Makro)(?:\s+Foodservice|\s+Club)?\)\s*$", line, re.I)
        if not m:
            continue
        name = _clean(m.group(1))
        if not name or len(name) > 160:
            continue
        key = (province, name.casefold())
        if key in seen:
            continue
        out.append(_candidate(name, province=province, evidence_excerpt=f"{province or ''} {line}".strip()))
        seen.add(key)
    return out


def extract_makro_detail(source: dict, body: bytes) -> list[dict]:
    """Extract one explicitly identified Makro branch detail page.

    Safety rule: configured canonical province is accepted only when the
    official page itself contains the configured explicit province token in
    both the branch heading and a nearby postal address. No branch-name-only
    inference is allowed.
    """
    lines, _ = html_blocks(body)
    branch_name = _clean(source.get("branch_name"))
    province = _clean(source.get("province"))
    token = _clean(source.get("province_token"))
    if not branch_name or not province or not token:
        return []

    token_cf = token.casefold()
    heading_index = None
    for i, line in enumerate(lines):
        if _clean(line).casefold() == token_cf:
            heading_index = i
            break
    if heading_index is None:
        return []

    for raw in lines[heading_index + 1:heading_index + 9]:
        line = _clean(raw)
        if not line:
            continue
        pc = re.search(r"\b(\d{5})\b", line)
        if not pc or token_cf not in line.casefold():
            continue
        return [_candidate(
            branch_name,
            province=province,
            address=line,
            postal_code=pc.group(1),
            evidence_excerpt=f"{token} | {line}",
        )]
    return []


def extract_homepro(source: dict, body: bytes) -> list[dict]:
    # Explicit locator evidence only. Branch names alone never become province evidence.
    lines, _ = html_blocks(body)
    by_name: dict[str, dict] = {}

    def explicit_address_after(index: int) -> tuple[str | None, str | None, str | None]:
        for raw in lines[index + 1:index + 9]:
            line = _clean(raw)
            if not line:
                continue
            if re.match(r"^(?:โฮมโปร|เมกาโฮม)\s*", line, re.I):
                break
            pc = re.search(r"\b(\d{5})\b", line)
            provinces = [p for p in THAI_PROVINCES if p in line]
            if not pc or not provinces:
                continue
            province = max(provinces, key=lambda p: line.rfind(p))
            address = re.sub(r"\s*Tel\s*:.*$", "", line, flags=re.I).strip(" ,")
            return address or None, province, pc.group(1)
        return None, None, None

    for i, line in enumerate(lines):
        if line in {"โฮมโปรออนไลน์", "HomePro Online"}:
            continue
        m = re.match(r"โฮมโปร\s*(?:S\s*)?(.+)$", line, re.I)
        if not m:
            continue
        name = _clean(m.group(1))
        if not name or name in {"ออนไลน์"} or len(name) > 140:
            continue
        address, province, postal_code = explicit_address_after(i)
        candidate = _candidate(
            name,
            province=province,
            address=address,
            postal_code=postal_code,
            evidence_excerpt=(f"{line} | {address}" if address else line),
        )
        key = name.casefold()
        prev = by_name.get(key)
        if prev is None or (not prev.get("province") and candidate.get("province")) or (not prev.get("address") and candidate.get("address")):
            by_name[key] = candidate
    return list(by_name.values())


def extract_bigc_branch(source: dict, body: bytes) -> list[dict]:
    class _Rows(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.in_row = False
            self.in_cell = False
            self.parts = []
            self.cells = []
            self.rows = []

        def handle_starttag(self, tag, attrs):
            tag = tag.casefold()
            if tag == "tr":
                self.in_row = True
                self.in_cell = False
                self.parts = []
                self.cells = []
            elif self.in_row and tag in {"td", "th"}:
                self.in_cell = True
                self.parts = []

        def handle_data(self, data):
            if self.in_row and self.in_cell:
                self.parts.append(data)

        def handle_endtag(self, tag):
            tag = tag.casefold()
            if self.in_row and tag in {"td", "th"} and self.in_cell:
                self.cells.append(_clean("".join(self.parts)))
                self.parts = []
                self.in_cell = False
            elif tag == "tr" and self.in_row:
                if any(self.cells):
                    self.rows.append(self.cells[:])
                self.in_row = False
                self.in_cell = False
                self.parts = []
                self.cells = []

    branch_name = _clean(source.get("branch_name"))
    province = _clean(source.get("province"))
    tokens = source.get("branch_tokens") or [source.get("branch_token")]
    tokens = [_clean(x) for x in tokens if _clean(x)]
    expected_postal = _clean(source.get("postal_code"))

    if not branch_name or not province or not tokens:
        return []

    p = _Rows()
    p.feed(body.decode("utf-8", errors="replace"))

    for cells in p.rows:
        row_text = " | ".join(x for x in cells if x)
        token = next((t for t in tokens if t.casefold() in row_text.casefold()), None)
        if not token or province.casefold() not in row_text.casefold():
            continue

        address = None
        postal = None
        if expected_postal:
            if expected_postal not in row_text:
                continue
            postal = expected_postal
            for cell in cells:
                c = _clean(cell).strip(" |,")
                if (
                    "เลขที่" in c
                    and province.casefold() in c.casefold()
                    and expected_postal in c
                    and len(c) <= 350
                ):
                    address = c
                    break
            if address is None:
                continue

        return [_candidate(
            branch_name,
            province=province,
            address=address,
            postal_code=postal,
            evidence_excerpt=(f"{token} | {address}" if address else row_text[:500]),
        )]

    return []

def extract_powerbuy(source: dict, body: bytes) -> list[dict]:
    lines, _ = html_blocks(body)
    out: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        if not re.match(r"^(?:Open Today|เปิดวันนี้|เปิดให้บริการ)", line, re.I):
            continue
        if i < 2:
            continue
        address = _clean(lines[i - 1])
        name = _clean(lines[i - 2])
        pc = re.search(r"\b(\d{5})\b\s*$", address)
        if not pc or not name or len(name) > 120:
            continue
        noise = {"Power Buy", "เพาเวอร์บาย", "Find nearest Power Buy Store", "ค้นหาสาขา"}
        if name in noise:
            continue
        key = name.casefold()
        if key not in seen:
            out.append(_candidate(name, address=address, postal_code=pc.group(1), evidence_excerpt=f"{name} {address}"))
            seen.add(key)
    return out


EXTRACTORS = {
    "globalhouse_directory": extract_globalhouse,
    "globalhouse_branch_detail": extract_globalhouse_detail,
    "makro_directory": extract_makro,
    "makro_branch_detail": extract_makro_detail,
    "homepro_directory": extract_homepro,
    "bigc_branch_evidence": extract_bigc_branch,
    "powerbuy_directory": extract_powerbuy,
}


def extract_place_candidates(source: dict, body: bytes) -> list[dict]:
    name = source.get("extractor")
    if name not in EXTRACTORS:
        raise ValueError(f"unknown place extractor: {name}")
    return EXTRACTORS[name](source, body)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def load_place_sources(path: str | Path) -> list[dict]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [x for x in rows if x.get("enabled") is True]


def _source_ids(place: dict) -> set[str]:
    return {e.get("source_id") for e in place.get("evidence", []) if e.get("source_id")}


def refresh_place_cache(project_root: str | Path, *, fetcher: Callable[[dict], FetchResult] = fetch_source,
                        max_workers: int = 4, progress: Callable[[str], None] | None = print) -> tuple[list[dict], dict]:
    root = Path(project_root)
    sources = load_place_sources(root / "config" / "place_sources.json")
    cache_path = root / "data" / "place_enrichment" / "official_places.jsonl"
    diagnostics_path = root / "output" / "place_enrichment.diagnostics.json"
    previous = _load_jsonl(cache_path)
    fresh_records: list[dict] = []
    succeeded: set[str] = set()
    failed: list[dict] = []
    zero: list[str] = []
    observed_candidates = 0

    def work(source: dict):
        result = fetcher(source)
        candidates = extract_place_candidates(source, result.body)
        records = make_locator_records(
            merchant=source["merchant"],
            candidates=candidates,
            source_id=source["source_id"],
            url=result.url,
            observed_at=result.observed_at,
            content_hash=result.content_hash,
            reliability=source.get("reliability", "high"),
        )
        return source, result, candidates, records

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        futures = {pool.submit(work, s): s for s in sources}
        done = 0
        for fut in as_completed(futures):
            source = futures[fut]
            done += 1
            try:
                s, result, candidates, records = fut.result()
                succeeded.add(s["source_id"])
                observed_candidates += len(candidates)
                fresh_records.extend(records)
                if not candidates:
                    zero.append(s["source_id"])
                if progress:
                    progress(f"PLACE_FETCH_PROGRESS={done}/{len(sources)} SOURCE={s['source_id']} RESULT=OK BRANCHES={len(candidates)}")
            except Exception as exc:
                failed.append({"source_id": source["source_id"], "error_type": type(exc).__name__, "error": str(exc)[:500]})
                if progress:
                    progress(f"PLACE_FETCH_PROGRESS={done}/{len(sources)} SOURCE={source['source_id']} RESULT=FAILED ERROR={type(exc).__name__}")

    # Replace records from successfully refreshed sources. Preserve last-known
    # records for failed sources so one outage does not erase the branch master.
    kept_previous = [p for p in previous if not (_source_ids(p) & succeeded)]
    combined = merge_place_records([*kept_previous, *fresh_records])
    errors = [p for p in combined if validate_place(p)]
    if errors:
        raise ValueError(f"place enrichment produced {len(errors)} invalid records")
    if combined:
        _write_jsonl_atomic(cache_path, combined)

    merchant_count = sum(p.get("record_kind") == "merchant" for p in combined)
    branch_count = sum(p.get("record_kind") == "branch" for p in combined)
    branch_with_province = sum(bool(p.get("record_kind") == "branch" and (p.get("location") or {}).get("province")) for p in combined)
    branch_with_address = sum(bool(p.get("record_kind") == "branch" and (p.get("location") or {}).get("address")) for p in combined)
    stats = {
        "sources_found": len(sources),
        "fetched": len(succeeded),
        "fetch_failed": len(failed),
        "zero_branch_sources": len(zero),
        "branch_candidates": observed_candidates,
        "cache_records": len(combined),
        "merchant_places": merchant_count,
        "branch_places": branch_count,
        "branch_with_province": branch_with_province,
        "branch_with_address": branch_with_address,
        "failed_sources": failed,
        "zero_sources": zero,
        "cache_path": str(cache_path),
        "result": "PASS" if branch_count > 0 else ("DEGRADED_CACHE" if previous else "DEGRADED_NO_BRANCHES"),
        "generated_at": _utcnow(),
    }
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return combined, stats


def load_place_cache(project_root: str | Path) -> list[dict]:
    return _load_jsonl(Path(project_root) / "data" / "place_enrichment" / "official_places.jsonl")
