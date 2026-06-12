# Phase 0 Reconnaissance Findings

Verified 2026-06-13 against live beoe.gov.pk. All sample pages cached in `data/raw_html/`.

## Access

- **robots.txt:** `User-agent: * → Allow: /` — our honest custom User-Agent is permitted.
  Cloudflare content signal `search=yes` (building a search index is explicitly allowed),
  `ai-train=no`. Named AI crawler bots are individually disallowed (doesn't apply to us).
- **Cloudflare:** site is behind it, but plain `requests` with our honest UA gets
  HTTP 200 on every page tested (7/7). Cloudflare injects a harmless
  `challenge-platform` beacon script into normal pages — do NOT use that string
  to detect blocks. A real challenge page has `<title>Just a moment...` and `cf_chl_opt`.

## URL patterns — all CONFIRMED as documented

| Type | Pattern | Status |
|---|---|---|
| Complaints | `/complaints/results/{id}` | ✅ works (e.g., 9495, 9400) |
| News/notices | `/news-updates/{id}` | ✅ works (e.g., 7151, 7100, 7000) |
| Agency list | `/list-of-oeps?show=active` | ✅ works, paginated via `&page=N` |

## ⚠️ Soft 404s (critical for Phase 1)

Nonexistent complaint IDs (e.g., 9300) return **HTTP 200** with the generic
complaints *listing* page instead of a 404. End-of-range detection must check
page content (`<h1>View Complaint Result` present?) — NOT the status code.

## Page structures

### News/notice pages (`/news-updates/{id}`)

Notice title + date live together in the second `<h1>` on the page
(first `<h1>` is the site banner):

```html
<h1>Show Cause Notice To M/s. Ihtisham Overseas Employment Promoter, OEPL No.2056/RWP
    <br><small>Jun 8, 2026</small></h1>
```

Title formats match the spec's documented examples exactly, inconsistencies included
(`M/s` vs `M/s.`, missing spaces after `No.`, multiple agencies joined by `,` and `&`).

### Complaint pages (`/complaints/results/{id}`)

Better than expected — structured labeled fields, not just a title:

```html
<h1>View Complaint Result : 09495</h1>
Category: Against OEP
Licence Title: China Manpower Services
Licence Status: Licence will expire after 1 year
OEP Name: M/s.China Manpower Services
Complaint Status: Under Investigation        ← e.g. "Under Investigation"
Result Fine (Rs.): Rs. 0
Added On: Jun 8, 2026
<img src=".../uploads/complaints/results/{hash}.png">   ← scanned original notice
```

**Note:** the detail page has the agency NAME but no OEPL number. The OEPL number
appears in complaint *titles on listing pages* (e.g., "Complaint against M/s
Professional Visa Services (OEPL No. 3555/RWP) is under process"). Phase 2 may
need to match complaints by Licence Title against the seeded agency list, or also
parse listing pages.

### Agency list (`/list-of-oeps`)

Clean `<table class="table table-bordered table-striped">` with columns:
Licence No. (format `0008  / RWP` — extra whitespace around slash), Proprietor Name,
Licence Title, Status, Expiry Date, Head Office (address + phone numbers),
Branch Office(s).

Status filters available: `show=` active / invalid / expired / canceled /
surrendered / suspended / **all**. For a complete database we want `show=all`.

Protectorate (region) filters seen: Rawalpindi, Lahore, Karachi, Peshawar, Quetta,
**Malakand, Multan**, Sialkot — Malakand and Multan were not in the original spec's
region list (spec correctly said treat codes as open-ended).

## Known-live ID ranges (from sidebar links, June 2026)

- Complaints: at least up to ~9507
- News: at least up to ~7153
