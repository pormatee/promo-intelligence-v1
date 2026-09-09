#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "output" / "promo_offer_v1.jsonl"
DEFAULT_DIAG = ROOT / "output" / "promo_offer_v1.diagnostics.json"
DEFAULT_CONFIG = ROOT / "config" / "sources.json"
DEFAULT_OUTPUT = ROOT / "promo_frontend.html"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"ไม่พบข้อมูล {path}\nกรุณารัน: python autonomous_wave_c.py")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"JSONL ผิดรูปแบบที่บรรทัด {lineno}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    if not rows:
        raise SystemExit(f"ไม่พบ offer ใน {path}")
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _source_family_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, str] = {}
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and row.get("source_id"):
                out[str(row["source_id"])] = str(row.get("family") or "unknown")
    return out


def _prepare_rows(rows: list[dict[str, Any]], family_by_source: dict[str, str]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for raw in rows:
        # Copy only. Do not mutate the trusted promo_offer_v1 output.
        x = json.loads(json.dumps(raw, ensure_ascii=False))
        source = x.get("source") or {}
        x["_ui_source_family"] = family_by_source.get(str(source.get("source_id") or ""), "unknown")
        cleaned.append(x)
    return cleaned


def _payload_b64(data: Any) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def build_html(rows: list[dict[str, Any]], diagnostics: dict[str, Any], family_by_source: dict[str, str]) -> str:
    prepared = _prepare_rows(rows, family_by_source)
    payload = _payload_b64(prepared)
    diag_payload = _payload_b64(diagnostics)
    built_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # No external JS/CSS/fonts: this remains a portable, offline single HTML file.
    return f'''<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light">
<title>Promo Intelligence</title>
<style>
:root{{--bg:#f4f8fb;--card:#fff;--ink:#10243b;--muted:#65758b;--line:#dbe6ee;--blue:#1368ce;--cyan:#00a9c7;--teal:#0b8f84;--good:#0b7a52;--warn:#ad6c00;--bad:#b83b3b;--soft:#eaf6fb;--shadow:0 8px 26px rgba(16,36,59,.08)}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:linear-gradient(180deg,#eef8fc 0,#f7fafc 260px,#f4f8fb 100%);font-family:system-ui,-apple-system,"Noto Sans Thai","Segoe UI",sans-serif;color:var(--ink)}}
a{{color:var(--blue)}}button,input,select{{font:inherit}}button{{cursor:pointer}}
.shell{{max-width:1180px;margin:auto;padding:0 14px 48px}}
.hero{{margin:0 -14px;padding:24px 18px 22px;background:linear-gradient(125deg,#0b4f9c,#087fbb 52%,#0b978b);color:#fff;box-shadow:var(--shadow)}}
.brandline{{display:flex;align-items:center;gap:10px}}.logo{{width:43px;height:43px;border-radius:14px;background:rgba(255,255,255,.16);display:grid;place-items:center;font-size:23px;border:1px solid rgba(255,255,255,.25)}}
h1{{font-size:24px;line-height:1.18;margin:0}}.subtitle{{margin:7px 0 0;opacity:.9;font-size:14px}}.built{{font-size:11px;opacity:.68;margin-top:7px}}
.stats{{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:9px;margin-top:-12px;position:relative}}.stat{{background:var(--card);border:1px solid rgba(219,230,238,.92);border-radius:16px;padding:12px;box-shadow:var(--shadow)}}.stat b{{display:block;font-size:22px;letter-spacing:-.4px}}.stat span{{font-size:11px;color:var(--muted)}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:12px;margin-top:12px;box-shadow:0 3px 14px rgba(16,36,59,.04)}}
.searchrow{{display:grid;grid-template-columns:1fr auto;gap:8px}}.search{{width:100%;border:1px solid var(--line);background:#f9fcfe;border-radius:14px;padding:13px 14px;outline:none}}.search:focus{{border-color:#79bde6;box-shadow:0 0 0 3px rgba(19,104,206,.08)}}.reset{{border:0;border-radius:13px;background:#eaf2f8;color:#355269;padding:0 14px;font-weight:700}}
.chips{{display:flex;gap:7px;overflow:auto;padding:10px 1px 3px;scrollbar-width:none}}.chip{{white-space:nowrap;border:1px solid var(--line);background:#fff;color:#355269;border-radius:999px;padding:8px 11px;font-weight:650;font-size:12px}}.chip.active{{background:#e4f5fa;border-color:#83d2df;color:#08697a}}
.filters{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:8px}}select{{width:100%;border:1px solid var(--line);background:#fff;border-radius:12px;padding:10px 9px;color:var(--ink)}}
.summary{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:16px 2px 9px}}.summary strong{{font-size:16px}}.summary small{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.offer{{background:var(--card);border:1px solid var(--line);border-radius:17px;padding:14px;box-shadow:0 4px 16px rgba(16,36,59,.045)}}.topline{{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}}.merchant{{font-size:12px;font-weight:800;color:#17699e;background:#eaf6fd;border-radius:999px;padding:5px 9px;max-width:70%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.type{{font-size:10px;font-weight:800;color:#43616f;border:1px solid var(--line);border-radius:999px;padding:4px 7px}}.item{{font-size:16px;font-weight:800;line-height:1.38;margin:10px 0 8px;min-height:44px}}.brand{{color:var(--muted);font-size:11px;margin-top:-4px}}
.pricebox{{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin:8px 0}}.promo{{font-weight:900;font-size:25px;color:#087b6d}}.regular{{font-size:12px;color:#8190a0;text-decoration:line-through}}.discount{{font-size:11px;font-weight:850;color:#fff;background:#e56b3f;border-radius:8px;padding:4px 7px}}.nprice{{font-size:13px;color:#476072;font-weight:700}}
.meta{{display:grid;gap:5px;font-size:12px;color:#496171;margin-top:8px}}.meta div{{display:flex;gap:7px;align-items:flex-start}}.icon{{width:18px;text-align:center;flex:0 0 18px}}.badges{{display:flex;gap:5px;flex-wrap:wrap;margin-top:10px}}.badge{{font-size:10px;border-radius:999px;padding:4px 7px;background:#eef4f7;color:#4c6574;font-weight:750}}.badge.good{{background:#e7f7f0;color:var(--good)}}.badge.warn{{background:#fff3d9;color:var(--warn)}}.badge.online{{background:#e9efff;color:#3f5ba4}}.badge.nation{{background:#e6f7fb;color:#08758a}}
.details{{margin-top:10px;border-top:1px dashed var(--line);padding-top:8px}}details summary{{cursor:pointer;color:#3b5b70;font-size:12px;font-weight:750}}.detailbody{{font-size:11px;line-height:1.6;color:#526b7a;margin-top:8px;word-break:break-word}}.sourcebtn{{display:inline-block;margin-top:7px;text-decoration:none;background:#edf6fb;border:1px solid #cbe3ef;border-radius:10px;padding:7px 9px;font-weight:750}}
.morewrap{{display:flex;justify-content:center;padding:18px}}.more{{border:0;background:linear-gradient(120deg,#1267c7,#07999a);color:#fff;border-radius:13px;padding:11px 19px;font-weight:800;box-shadow:var(--shadow)}}.empty{{text-align:center;padding:38px 12px;color:var(--muted);background:#fff;border:1px dashed var(--line);border-radius:16px}}.diag{{font-size:12px;color:#526b7a}}.diag summary{{font-size:12px}}.diaggrid{{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:9px}}.diagitem{{background:#f7fafc;border-radius:10px;padding:8px}}.blockers{{color:#8d4141;margin-top:7px}}
.footer{{text-align:center;color:#8293a3;font-size:11px;margin-top:28px}}
@media(max-width:800px){{.stats{{grid-template-columns:repeat(5,132px);overflow:auto;padding-bottom:2px}}.filters{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}.hero{{padding-top:20px}}.diaggrid{{grid-template-columns:1fr 1fr}}}}
@media(max-width:430px){{.shell{{padding-left:10px;padding-right:10px}}.hero{{margin-left:-10px;margin-right:-10px}}h1{{font-size:21px}}.filters{{grid-template-columns:1fr 1fr}}.item{{min-height:0}}}}
</style>
</head>
<body>
<div class="shell">
<section class="hero">
  <div class="brandline"><div class="logo">%</div><div><h1>Promo Intelligence</h1><div class="subtitle">ค้นหาโปรโมชั่นจากหลักฐานที่ระบบตรวจพบและ Normalize แล้ว</div></div></div>
  <div class="built">สร้างหน้าเว็บ: {built_at} · Contract: promo_offer_v1 · Standalone</div>
</section>
<section class="stats" id="stats"></section>
<section class="panel">
  <div class="searchrow"><input id="q" class="search" type="search" placeholder="ค้นหา เช่น กาแฟ, ทีวี, Lotus's, คูปอง…" autocomplete="off"><button id="reset" class="reset">ล้าง</button></div>
  <div class="chips" id="chips">
    <button class="chip active" data-quick="all">ทั้งหมด</button>
    <button class="chip" data-quick="active">ยังไม่หมดโปร</button>
    <button class="chip" data-quick="nationwide">ทั่วประเทศ</button>
    <button class="chip" data-quick="prachinburi">ปราจีนบุรีที่ยืนยัน</button>
    <button class="chip" data-quick="online">ออนไลน์</button>
    <button class="chip" data-quick="discount30">ลด ≥ 30%</button>
  </div>
  <div class="filters">
    <select id="merchant"><option value="">ทุกร้าน</option></select>
    <select id="type"><option value="">ทุกประเภทโปร</option></select>
    <select id="channel"><option value="">ทุกช่องทาง</option></select>
    <select id="verification"><option value="">ทุกสถานะตรวจสอบ</option></select>
    <select id="sort">
      <option value="discount">เรียง: ส่วนลดสูง</option>
      <option value="price">เรียง: ราคาโปรต่ำ</option>
      <option value="expiry">เรียง: ใกล้หมดโปร</option>
      <option value="merchant">เรียง: ร้าน A-Z</option>
    </select>
  </div>
</section>
<section class="panel diag" id="diagPanel" style="display:none"><details><summary>สุขภาพแหล่งข้อมูล / Diagnostics</summary><div id="diagBody"></div></details></section>
<div class="summary"><strong id="resultText">กำลังเตรียมข้อมูล…</strong><small id="resultHint"></small></div>
<section class="grid" id="grid"></section>
<div class="morewrap"><button id="more" class="more" style="display:none">แสดงเพิ่ม</button></div>
<div class="footer">ข้อมูลนี้เป็น promotion evidence ไม่ใช่การจัดอันดับร้าน · Unknown stays unknown · เปิด Source เพื่อตรวจสอบต้นทางได้</div>
</div>
<script>
const DATA_B64="{payload}";
const DIAG_B64="{diag_payload}";
const decodeB64=b64=>JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64),c=>c.charCodeAt(0))));
const offers=decodeB64(DATA_B64), diagnostics=decodeB64(DIAG_B64);
const $=id=>document.getElementById(id);
const state={{quick:'all',limit:80}};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));
const money=n=>n==null?'':new Intl.NumberFormat('th-TH',{{maximumFractionDigits:2}}).format(Number(n))+' บาท';
const dateTH=s=>{{if(!s)return '-'; const m=/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/.exec(s); if(!m)return esc(s); return `${{Number(m[3])}}/${{Number(m[2])}}/${{Number(m[1])+543}}`;}};
const geo=o=>o.geography||{{detail_state:'unknown',best_granularity:'unknown',locations:[]}};
const geoText=o=>(geo(o).locations||[]).flatMap(x=>[x.province,x.province_raw,x.district,x.subdistrict,x.branch_name,x.address,x.postal_code]).filter(Boolean).join(' ');
const txt=o=>{{const m=o.merchant||{{}},i=o.item||{{}},c=o.conditions||[],s=o.source||{{}};return [m.name,m.branch,i.name,i.brand,i.category,o.offer_type,c.join(' '),s.source_id,o._ui_source_family,geoText(o)].filter(Boolean).join(' ').toLowerCase();}};
const app=o=>o.applicability||{{scope:'unknown',provinces:[],branches:[],channel:'unknown'}};
const ver=o=>o.verification||{{}}; const price=o=>o.pricing||{{}};
function populate(id,values,label){{const el=$(id); [...new Set(values.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'th')).forEach(v=>{{const op=document.createElement('option');op.value=v;op.textContent=`${{label?label+': ':''}}${{v}}`;el.appendChild(op)}})}}
populate('merchant',offers.map(o=>(o.merchant||{{}}).name));
populate('type',offers.map(o=>o.offer_type));
populate('channel',offers.map(o=>app(o).channel));
populate('verification',offers.map(o=>ver(o).verification_state));
function quickMatch(o){{const a=app(o),v=ver(o),p=price(o),g=geo(o);switch(state.quick){{case'active':return v.expiry_state==='active';case'nationwide':return a.scope==='nationwide';case'prachinburi':return a.scope==='nationwide'||(a.provinces||[]).some(x=>String(x).includes('ปราจีนบุรี')||String(x).toLowerCase().includes('prachin'))||(g.locations||[]).some(x=>String(x.province||'').toLowerCase().includes('prachin')||String(x.province_raw||'').includes('ปราจีนบุรี'));case'online':return a.channel==='online';case'discount30':return Number(p.discount_percent||0)>=30;default:return true}}}}
function filtered(){{const q=$('q').value.trim().toLowerCase(),mer=$('merchant').value,typ=$('type').value,ch=$('channel').value,vf=$('verification').value;let arr=offers.filter(o=>{{if(q&&!txt(o).includes(q))return false;if(mer&&(o.merchant||{{}}).name!==mer)return false;if(typ&&o.offer_type!==typ)return false;if(ch&&app(o).channel!==ch)return false;if(vf&&ver(o).verification_state!==vf)return false;return quickMatch(o)}});const sort=$('sort').value;arr.sort((a,b)=>{{if(sort==='price')return (price(a).promo_price??1e99)-(price(b).promo_price??1e99);if(sort==='expiry')return String((a.validity||{{}}).end||'9999').localeCompare(String((b.validity||{{}}).end||'9999'));if(sort==='merchant')return String((a.merchant||{{}}).name||'').localeCompare(String((b.merchant||{{}}).name||''),'th');return (Number(price(b).discount_percent)||-1)-(Number(price(a).discount_percent)||-1)}});return arr;}}
function scopeLabel(a){{if(a.scope==='nationwide')return'ทั่วประเทศ';if(a.scope==='selected_branches')return'บางสาขา';if(a.scope==='branch_specific')return'เฉพาะสาขา';return'ยังไม่ทราบพื้นที่';}}
function channelLabel(c){{return {{online:'ออนไลน์',store:'หน้าร้าน',omnichannel:'ออนไลน์ + หน้าร้าน',unknown:'ไม่ระบุช่องทาง'}}[c]||c}}
function typeLabel(t){{return {{price_discount:'ลดราคา',special_price:'ราคาพิเศษ',coupon:'คูปอง',bundle:'แพ็ก/ซื้อแถม',other:'โปรโมชั่น'}}[t]||t||'โปรโมชั่น'}}
function geoLabel(o){{const g=geo(o),x=(g.locations||[])[0];if(!x)return'';return [x.branch_name,x.subdistrict,x.district,x.province_raw||x.province].filter(Boolean).join(' · ');}}
function geoDetails(o){{const g=geo(o),rows=g.locations||[];if(!rows.length)return `Geo detail: ${{esc(g.detail_state||'unknown')}} / ${{esc(g.best_granularity||'unknown')}}`;return rows.map((x,idx)=>{{const parts=[x.province_raw||x.province?`จังหวัด: ${{esc(x.province_raw||x.province)}}`:'',x.district?`อำเภอ/เขต: ${{esc(x.district)}}`:'',x.subdistrict?`ตำบล/แขวง: ${{esc(x.subdistrict)}}`:'',x.branch_name?`สาขา: ${{esc(x.branch_name)}}`:'',x.postal_code?`รหัสไปรษณีย์: ${{esc(x.postal_code)}}`:'',x.address?`ที่อยู่: ${{esc(x.address)}}`:'',(x.latitude!=null&&x.longitude!=null)?`พิกัด: ${{esc(x.latitude)}}, ${{esc(x.longitude)}}`:''].filter(Boolean);return `${{rows.length>1?'ตำแหน่ง '+(idx+1)+': ':''}}${{parts.join(' · ')}}`;}}).join('<br>');}}
function card(o){{const m=o.merchant||{{}},i=o.item||{{}},p=price(o),v=ver(o),a=app(o),valid=o.validity||{{}},e=o.evidence||{{}},s=o.source||{{}};const disc=p.discount_percent!=null?`<span class="discount">-${{Number(p.discount_percent).toFixed(0)}}%</span>`:'';let prices='';if(p.promo_price!=null) prices=`<span class="promo">${{money(p.promo_price)}}</span>${{p.regular_price!=null?`<span class="regular">${{money(p.regular_price)}}</span>`:''}}${{disc}}`; else prices=`<span class="nprice">${{esc(typeLabel(o.offer_type))}}${{(o.conditions||[])[0]?': '+esc((o.conditions||[])[0]):''}}</span>`;const provinces=(a.provinces||[]).join(', '),branches=(a.branches||[]).join(', '),glabel=geoLabel(o);const locExtra=glabel?` · ${{esc(glabel)}}`:(provinces||branches?` · ${{esc([provinces,branches].filter(Boolean).join(' / '))}}`:'');const verifyClass=v.verification_state==='verified'?'good':(v.verification_state==='partial'?'warn':'');const rel=v.source_reliability==='high'?'good':'';const corr=(e.corroborating_sources||[]).length;return `<article class="offer"><div class="topline"><span class="merchant">${{esc(m.name||'-')}}</span><span class="type">${{esc(typeLabel(o.offer_type))}}</span></div><div class="item">${{esc(i.name||'โปรโมชั่น')}}</div>${{i.brand?`<div class="brand">${{esc(i.brand)}}</div>`:''}}<div class="pricebox">${{prices}}</div><div class="meta"><div><span class="icon">📅</span><span>${{dateTH(valid.start)}} – ${{dateTH(valid.end)}}</span></div><div><span class="icon">📍</span><span>${{esc(scopeLabel(a))}}${{locExtra}}</span></div><div><span class="icon">🛒</span><span>${{esc(channelLabel(a.channel||'unknown'))}}</span></div></div><div class="badges"><span class="badge ${{verifyClass}}">${{esc(v.verification_state||'unknown')}}</span><span class="badge ${{p.verification_state==='verified'?'good':'warn'}}">price ${{esc(p.verification_state||'unknown')}}</span><span class="badge ${{rel}}">source ${{esc(v.source_reliability||'unknown')}}</span>${{a.channel==='online'?'<span class="badge online">online</span>':''}}${{a.scope==='nationwide'?'<span class="badge nation">nationwide</span>':''}}${{geo(o).best_granularity&&geo(o).best_granularity!=='unknown'&&geo(o).best_granularity!=='nationwide'?`<span class="badge good">geo ${{esc(geo(o).best_granularity)}}</span>`:''}}${{corr?`<span class="badge good">ยืนยันเพิ่ม ${{corr}} source</span>`:''}}</div><div class="details"><details><summary>ดูรายละเอียดและหลักฐาน</summary><div class="detailbody">Offer ID: ${{esc(o.offer_id||'-')}}<br>Source family: ${{esc(o._ui_source_family||'unknown')}}<br>Source ID: ${{esc(s.source_id||'-')}}<br>ตรวจพบ: ${{esc(s.observed_at||'-')}}<br>Freshness: ${{esc(v.freshness_state||'-')}} · Expiry: ${{esc(v.expiry_state||'-')}}<br>Price integrity: ${{esc(p.verification_state||'-')}} · anomalies=${{esc((p.anomalies||[]).join(', ')||'-')}}<br>${{geoDetails(o)}}<br>เงื่อนไข: ${{esc((o.conditions||[]).join(' · ')||'-')}}<br>Evidence: ${{esc(e.extracted_text||'-')}}${{s.url?`<br><a class="sourcebtn" href="${{esc(s.url)}}" target="_blank" rel="noopener">เปิดแหล่งข้อมูลทางการ ↗</a>`:''}}</div></details></div></article>`}}
function renderStats(){{const active=offers.filter(o=>ver(o).expiry_state==='active').length,verified=offers.filter(o=>ver(o).verification_state==='verified').length,nation=offers.filter(o=>app(o).scope==='nationwide').length,online=offers.filter(o=>app(o).channel==='online').length;const vals=[[offers.length,'Offers ทั้งหมด'],[active,'ยัง Active'],[verified,'Verified'],[nation,'Nationwide'],[online,'Online']];$('stats').innerHTML=vals.map(([n,l])=>`<div class="stat"><b>${{new Intl.NumberFormat('th-TH').format(n)}}</b><span>${{l}}</span></div>`).join('')}}
function renderDiag(){{if(!diagnostics||!Object.keys(diagnostics).length)return;const s=diagnostics.summary||{{}},q=diagnostics.quality||{{}},hard=diagnostics.hard_block_sources||[];$('diagPanel').style.display='block';$('diagBody').innerHTML=`<div class="diaggrid"><div class="diagitem">Sources<br><b>${{s.sources??'-'}}</b></div><div class="diagitem">Fetched<br><b>${{s.fetched??'-'}}</b></div><div class="diagitem">Fetch failed<br><b>${{s.fetch_failed??'-'}}</b></div><div class="diagitem">Actionable location gap<br><b>${{q.location_unknown_actionable??'-'}}</b></div><div class="diagitem">District known<br><b>${{s.district_known??0}}</b></div><div class="diagitem">Address known<br><b>${{s.address_known??0}}</b></div></div>${{hard.length?`<div class="blockers">External blockers: ${{hard.map(esc).join(', ')}}</div>`:''}}`}}
function render(){{const arr=filtered(),slice=arr.slice(0,state.limit);$('resultText').textContent=`พบ ${{new Intl.NumberFormat('th-TH').format(arr.length)}} โปรโมชั่น`;$('resultHint').textContent=arr.length>slice.length?`แสดง ${{slice.length}} รายการแรก`:'';$('grid').innerHTML=slice.length?slice.map(card).join(''):'<div class="empty">ไม่พบโปรโมชั่นตามตัวกรองนี้</div>';$('more').style.display=arr.length>slice.length?'block':'none'}}
['q','merchant','type','channel','verification','sort'].forEach(id=>$(id).addEventListener(id==='q'?'input':'change',()=>{{state.limit=80;render()}}));
$('chips').addEventListener('click',e=>{{const b=e.target.closest('[data-quick]');if(!b)return;state.quick=b.dataset.quick;state.limit=80;document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('active',x===b));render()}});
$('reset').onclick=()=>{{$('q').value='';['merchant','type','channel','verification'].forEach(id=>$(id).value='');$('sort').value='discount';state.quick='all';state.limit=80;document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('active',x.dataset.quick==='all'));render()}};
$('more').onclick=()=>{{state.limit+=80;render()}};
renderStats();renderDiag();render();
</script>
</body></html>'''


def main() -> int:
    ap = argparse.ArgumentParser(description="Build offline single-file Promo Intelligence frontend")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--diagnostics", type=Path, default=DEFAULT_DIAG)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    def abs_in_root(p: Path) -> Path:
        return p if p.is_absolute() else ROOT / p

    input_path = abs_in_root(args.input)
    diag_path = abs_in_root(args.diagnostics)
    config_path = abs_in_root(args.config)
    output_path = abs_in_root(args.output)

    rows = _load_jsonl(input_path)
    diagnostics = _load_json(diag_path)
    families = _source_family_map(config_path)
    html = build_html(rows, diagnostics, families)
    output_path.write_text(html, encoding="utf-8")

    print("FRONTEND_BUILD=PASS")
    print(f"OFFERS_EMBEDDED={len(rows)}")
    print("FRONTEND_MODE=OFFLINE_SINGLE_HTML")
    print(f"OUTPUT={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
