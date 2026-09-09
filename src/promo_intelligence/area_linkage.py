from __future__ import annotations

from copy import deepcopy
import re


def _norm(value: str | None) -> str:
    s = (value or '').strip().casefold()
    s = re.sub(r'^(?:สาขา|branch)\s*[:：-]?\s*', '', s, flags=re.I)
    s = re.sub(r'\b(?:สาขา|branch)\b', ' ', s, flags=re.I)
    s = re.sub(r'[^0-9a-zก-๙]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _merchant_keys(place: dict) -> set[str]:
    m = place.get('merchant') or {}
    vals = [m.get('name'), *(m.get('aliases') or [])]
    return {_norm(x) for x in vals if _norm(x)}


def _branch_keys(place: dict) -> set[str]:
    b = place.get('branch') or {}
    vals = [b.get('name'), *(b.get('aliases') or [])]
    return {_norm(x) for x in vals if _norm(x)}


def branch_index(places: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Index verified physical branches by exact normalized merchant + branch aliases.

    Multiple records may share a key; callers must require an unambiguous result.
    No fuzzy matching is used because a wrong branch link would create false local
    applicability.
    """
    out: dict[tuple[str, str], list[dict]] = {}
    for p in places:
        if p.get('record_kind') != 'branch':
            continue
        if (p.get('verification') or {}).get('state') not in {'verified', 'partial'}:
            continue
        mkeys = _merchant_keys(p)
        bkeys = _branch_keys(p)
        for mk in mkeys:
            for bk in bkeys:
                out.setdefault((mk, bk), []).append(p)
    return out


def _location_from_place(place: dict, branch_name: str, evidence_excerpt: str = '') -> dict:
    loc = place.get('location') or {}
    gran = place.get('precision') or 'branch'
    return {
        'province': loc.get('province'),
        'province_raw': loc.get('province'),
        'district': loc.get('district'),
        'subdistrict': loc.get('subdistrict'),
        'branch_name': (place.get('branch') or {}).get('name') or branch_name,
        'address': loc.get('address'),
        'postal_code': loc.get('postal_code'),
        'latitude': loc.get('latitude'),
        'longitude': loc.get('longitude'),
        'verification_state': 'explicit',
        'basis': 'applicability',
        'directory_match_basis': 'official_branch_directory_exact_match',
        'evidence_excerpt': (evidence_excerpt or f"explicit branch {branch_name} matched official branch directory")[:500],
        'granularity': gran if gran in {'branch','province','district','subdistrict','address','coordinates'} else 'branch',
    }


def link_offer_explicit_branches(offer: dict, places: list[dict], index: dict | None = None) -> tuple[dict, dict]:
    """Link only explicitly named offer branches to official Place records.

    Safety rules:
      * offer applicability must explicitly carry branch names, or geography must
        contain branch_name from explicit/applicability evidence;
      * merchant + branch match must be exact after conservative normalization;
      * ambiguous matches are not linked;
      * merchant branch existence alone never creates applicability.
    """
    out = deepcopy(offer)
    idx = index or branch_index(places)
    merchant = ((out.get('merchant') or {}).get('name') or '').strip()
    mk = _norm(merchant)
    app = out.get('applicability') or {}
    geo = out.get('geography') or {}

    names: list[str] = []
    if app.get('scope') in {'branch_specific', 'selected_branches'} and app.get('verification_state') == 'explicit':
        names.extend([x for x in (app.get('branches') or []) if x])
    for loc in geo.get('locations') or []:
        if loc.get('branch_name') and loc.get('basis') in {'offer_text','applicability','source_config'}:
            names.append(loc.get('branch_name'))
    # stable unique order
    seen = set(); names = [x for x in names if not (_norm(x) in seen or seen.add(_norm(x)))]

    matched: list[dict] = []
    unmatched: list[str] = []
    ambiguous: list[str] = []
    for name in names:
        rows = idx.get((mk, _norm(name)), []) if mk and _norm(name) else []
        unique = {r.get('place_id'): r for r in rows if r.get('place_id')}
        if len(unique) == 1:
            matched.append(next(iter(unique.values())))
        elif len(unique) > 1:
            ambiguous.append(name)
        else:
            unmatched.append(name)

    if matched:
        refs = list(out.get('place_refs') or [])
        locs = list(geo.get('locations') or [])
        for p in matched:
            pid = p.get('place_id')
            if pid and pid not in refs:
                refs.append(pid)
            bname = (p.get('branch') or {}).get('name') or ''
            existing = next((x for x in locs if _norm(x.get('branch_name')) == _norm(bname)), None)
            newloc = _location_from_place(p, bname, (existing or {}).get('evidence_excerpt',''))
            if existing is not None:
                # Preserve original explicit offer evidence while filling only
                # missing structured detail from the verified branch directory.
                for k, v in newloc.items():
                    if existing.get(k) in (None, '', []):
                        existing[k] = v
                existing['directory_match_basis'] = 'official_branch_directory_exact_match'
            else:
                locs.append(newloc)
        out['place_refs'] = refs
        best_order = {'unknown':0,'branch':1,'province':2,'district':3,'subdistrict':4,'address':5,'coordinates':6}
        best = max((x.get('granularity','unknown') for x in locs), key=lambda x: best_order.get(x,0), default='unknown')
        out['geography'] = {
            **geo,
            'detail_state': 'explicit' if best_order.get(best,0) >= best_order['district'] else 'partial',
            'best_granularity': best,
            'locations': locs,
        }

    out['area_linkage'] = {
        'state': 'linked' if matched else ('ambiguous' if ambiguous else ('unmatched' if names else 'not_applicable')),
        'basis': 'explicit_branch_name_exact_official_directory_match',
        'requested_branch_count': len(names),
        'matched_place_refs': [p.get('place_id') for p in matched if p.get('place_id')],
        'unmatched_branches': unmatched,
        'ambiguous_branches': ambiguous,
    }
    stats = {
        'explicit_branch_names': len(names),
        'matched_branches': len(matched),
        'unmatched_branches': len(unmatched),
        'ambiguous_branches': len(ambiguous),
        'offer_linked': int(bool(matched)),
    }
    return out, stats


def link_offers_explicit_branches(offers: list[dict], places: list[dict]) -> tuple[list[dict], dict]:
    idx = branch_index(places)
    out: list[dict] = []
    totals = {
        'offers_with_explicit_branch_names': 0,
        'offers_branch_linked': 0,
        'explicit_branch_names': 0,
        'explicit_branch_matches': 0,
        'explicit_branch_unmatched': 0,
        'explicit_branch_ambiguous': 0,
        'offers_with_local_province': 0,
    }
    for offer in offers:
        linked, s = link_offer_explicit_branches(offer, places, idx)
        out.append(linked)
        if s['explicit_branch_names']:
            totals['offers_with_explicit_branch_names'] += 1
        totals['offers_branch_linked'] += s['offer_linked']
        totals['explicit_branch_names'] += s['explicit_branch_names']
        totals['explicit_branch_matches'] += s['matched_branches']
        totals['explicit_branch_unmatched'] += s['unmatched_branches']
        totals['explicit_branch_ambiguous'] += s['ambiguous_branches']
        geo = linked.get('geography') or {}
        if any((x or {}).get('province') for x in geo.get('locations') or []):
            totals['offers_with_local_province'] += 1
    return out, totals
