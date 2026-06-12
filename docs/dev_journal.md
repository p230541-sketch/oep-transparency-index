# Dev Journal — OEP Transparency Index

Raw material for the README's "How it was built" section and interview stories.

---

## Phase 0 — Reconnaissance (2026-06-13)

**What was built:** project skeleton, git repo, venv, and a recon script that
fetched 7 sample pages from beoe.gov.pk with an honest User-Agent and 3-5 s delays.

**What broke:**
1. The Cloudflare block detector fired on a *successful* page — Cloudflare
   injects a harmless `challenge-platform` beacon script into normal pages,
   so that string is useless as a block marker. Real challenges have
   `<title>Just a moment...` and `cf_chl_opt`.
2. `UnicodeEncodeError` printing the ⚠️ emoji — Windows consoles default to
   cp1252. Fixed with `sys.stdout.reconfigure(encoding="utf-8")`.

**What was learned:** nonexistent notice IDs return HTTP 200 with a generic
listing page (a "soft 404") — so end-of-range detection must inspect page
content, never trust status codes alone.

## Phases 1–3 — Scraper, pipeline, webapp (2026-06-13)

**What was built:** cache-first polite fetcher with exponential backoff and a
SQLite scrape log; resumable ID enumerator with content-based soft-404
detection; parsers for three page types; entity resolution (OEPL number
exact-match first, rapidfuzz token_sort_ratio fallback: ≥92 auto-merge,
80–91 review queue, every decision logged with its score); Flask app with
search, agency profile timeline, and CSS-only stats charts.

**What broke:** a complaint page yielded "Best Human Resources Consultancy,"
with a trailing comma — fixed by stripping punctuation after removing the
M/s prefix. PowerShell also mangled inline `python -c` quotes, which is why
parser checks live in `tests_manual/` as files.

**What was learned / proudest moment:** the first interim build seeded
exactly 2,756 agencies (matching BEOE's published count) and the acid test
passed: a complaint page that names "M/s.China Manpower Services" with NO
license number was fuzzy-linked (score 100) to the canonical record carrying
OEPL 4859/LHR. The search result shows a license number the source page
never mentioned — that's the entire value of entity resolution in one row.

## Full-data build (2026-06-13, same session)

**Scrape results:** 273 pages cached (57 list pages = all 2,756 active
agencies; 117 news notices; 99 complaint pages). 17 soft-404 misses
correctly detected and discarded — complaint IDs turn out to be sparse
(withdrawn complaints leave gaps mid-range).

**What broke, round 2:**
1. The site wrote "OEPL No.3768./RWP" — stray period before the slash —
   which leaked license text into an agency name. Regex now allows it.
2. Complaints parsed before news (alphabetical glob order), so name-only
   complaint mentions missed variants that OEPL-bearing news titles would
   have registered. Now news parses first, deliberately.
3. Two "unparsed" complaints turned out to be the "General Complaint"
   category — complaints against no agency at all. Recognized as valid
   notices with zero agency links instead of failures.

**Final numbers:** 216/216 notices parsed (100.0% coverage), 2,781 agencies,
218 notice-agency links, 4 borderline fuzzy matches in the review queue —
all four genuinely different agencies the threshold correctly refused to
auto-merge (e.g., "Pharmic Enterprises" vs "Harmain Enterprises").

**End-to-end proof:** /agency/2767 (Pharmic Enterprises, 4480/RWP) shows 5
official actions assembled from two different BEOE feeds — complaints AND
news notices — each with a date, action badge, and link to the original
government notice. That page is the product pitch in one screenshot.

## Hardening round ("make it perfect", 2026-06-13)

**What was built:** a 27-test pytest suite encoding every documented title
format; a measured accuracy number (100 random merge decisions hand-reviewed:
100% auto-merge precision, 99% overall); an incremental `scraper/sync.py`;
deploy config (`render.yaml` + gunicorn); the 0.9 MB sample DB committed so
cloners run the site with zero setup.

**What the data taught us this round:**
1. The site also writes "OEP No." (missing the L) — regex widened, test added.
2. "Suspension of Licence" is a distinct serious action hiding in the
   "other" bucket — added to the taxonomy, badges, and status tiers.
3. Complainants type junk into the official form: one entered the licence
   number "4584" as the agency *name*. New resolver rule: a digits-only name
   matching exactly one licence is an unambiguous identity — it correctly
   linked that complaint to Suhaib & Associates (4584's real holder).
4. The one honest failure (the 1% in the accuracy number): a form entry of
   just "sufyan" scored 44 against the real "Sufyan Recruiting Agency" —
   below every threshold, so a junk record was created. Source garbage is
   the limit of name matching; thresholds prevented a false merge.
5. Found one normalized-name collision in the register (two "Talagang
   International" licences) — documented as a known limitation.

**A test caught my own bug:** the ambiguous-digits test failed because the
fake ID factory in the *test fixture* collided with manually registered IDs.
Even test code needs review.

**Interview stories captured so far:**
1. *Polite scraping:* robots.txt check first, honest UA with contact email,
   3-5 s delays, cache-first so no page is fetched twice, resumable batches,
   and a hard stop (never evade) if Cloudflare challenges appear.
2. *Entity resolution:* messy government titles, multi-agency notices,
   missing license numbers — solved with a two-tier identity rule and a
   measurable, logged decision trail.
3. *Republish-only ethics:* every displayed fact is a restatement of an
   official notice with a link to the source; status tiers are neutral
   ("Open actions on record"), never invented risk scores.
