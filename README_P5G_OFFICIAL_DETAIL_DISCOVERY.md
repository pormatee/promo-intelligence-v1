# Promo Intelligence — P5G Official Terms / Detail Page Discovery

## Purpose
P5F proved that the evidence/raw HTML already attached to the actionable local-area unknown offers is insufficient. P5G follows **only strongly-associated links on the same official host** to dedicated promotion/detail/terms pages and looks for explicit applicability evidence there.

## Safety / semantics
- Promo Intelligence remains standalone; no LocalLife/PrachinLife/MSB/DQE dependency.
- Same official host only. No search-engine scraping, login, cookies, CAPTCHA solving, proxies, or anti-bot bypass.
- A detail link must be strongly related to the offer title (exact/contained or strong token overlap); generic “ดูรายละเอียด” links alone are not trusted.
- Online offers are never converted into physical province/branch applicability.
- Explicit nationwide / province / branch terms only.
- If multiple official detail pages conflict, the offer stays unknown and the conflict is recorded.
- Merchant branch existence remains separate from offer applicability.
- Missing/ambiguous evidence stays unknown.

## Files added
- `src/promo_intelligence/detail_applicability.py`
- `discover_applicability_details.py`
- `applicability_detail_loop.py`
- `show_detail_discovery_backlog.py`
- `tests/test_p5g_detail_applicability.py`
- cache directory `data/applicability_details/`

## Run
```bash
python applicability_detail_loop.py
```

Key output:
```text
ACTIONABLE_UNKNOWN_BEFORE=...
DETAIL_OFFERS_WITH_CANDIDATE_LINKS=...
DETAIL_CANDIDATE_LINKS=...
DETAIL_URLS_UNIQUE=...
DETAIL_FETCHED=...
DETAIL_FETCH_FAILED=...
DETAIL_APPLICABILITY_DISCOVERED=...
DETAIL_DISCOVERED_NATIONWIDE=...
DETAIL_DISCOVERED_PROVINCE=...
DETAIL_DISCOVERED_BRANCH=...
DETAIL_CONFLICTS=...
ACTIONABLE_UNKNOWN_AFTER=...
P5G_RESULT=PASS
```

## Interpretation
`P5G_RESULT=PASS` means the bounded evidence-discovery process completed safely. It does **not** require that unknown offers are force-classified. A zero discovery result is valid evidence that the available official detail pages do not explicitly state applicability.
