# OEP Transparency Index

**Search any Pakistani overseas-recruitment agency's complete official disciplinary history in seconds — data that exists publicly but was never searchable.**

> Status: working end-to-end locally (scraper → database → web app). Deployment is the next step.

---

## The problem

Millions of Pakistani workers migrate to the Gulf, and recruitment fraud — fake agents, illegal overcharging, contract substitution — is widespread. Most victims are low-income and low-literacy. Pakistan's Bureau of Emigration & Overseas Employment (BEOE) licenses ~2,750 recruitment agencies ("Overseas Employment Promoters") and publishes every complaint, warning, show-cause notice, blacklisting, and license restoration against them.

But it publishes them **only as a chronological news feed**. There is no way to look up one agency and see its history. Searching "best recruitment agency Pakistan" returns marketing listicles written by the agencies themselves.

**The data exists; the access doesn't.** This project fixes the access.

## What it does

1. **Scrapes politely** — every official notice page and the full licensed-agency list, cached locally, 3–5 s between requests, honest User-Agent with contact email.
2. **Re-indexes per agency** — parses messy real-world notice titles, resolves agency identities (fuzzy name matching where license numbers are missing), and loads everything into SQLite.
3. **Serves a search site** — type an agency name or license number, see its full official track record, every entry linking back to the original government notice.

## Architecture

```
beoe.gov.pk ──(polite scraper: 3-5s delays, cache-first, resumable)──> data/raw_html/
                                                                            │
                                              pipeline/parse_notices.py ◄───┘
                                              pipeline/entity_resolution.py
                                              pipeline/build_db.py
                                                        │
                                                        ▼
                                                 data/db.sqlite3
                                                        │
                                                        ▼
                                        webapp/app.py (Flask + Jinja2)
                                     search · agency profiles · statistics
```

The scraper and the web app never talk to each other — everything flows through the local HTML cache, so the dataset survives even if the source site changes or goes offline.

## The hardest problem: entity resolution

One notice can name several agencies; names are written inconsistently (`M/s` vs `M/s.`, missing spaces, names with commas inside them); complaint pages name the agency but omit its license number entirely.

Resolution rules, in order:
1. **OEPL license number = primary identity.** Exact match wins instantly.
2. **No number? Fuzzy-match the name** (rapidfuzz `token_sort_ratio`) against every canonical name and known variant:
   - score ≥ 92 → auto-merge (and remember the variant spelling)
   - 80–91 → human review queue (`data/review_queue.csv`)
   - < 80 → new agency record
3. **Every decision is logged with its score** (`data/merge_log.csv`) so accuracy is measurable: `python pipeline/export_label_sample.py export` produces a random sample to hand-label, and `... score` computes precision from the labels.

Real example from the data: a complaint page names "M/s.China Manpower Services" with **no license number**. Fuzzy matching links it (score 100) to the canonical record carrying OEPL 4859/LHR — so the search result shows the license number the original page never mentioned.

## Ethical design decisions

- **Republish-only rule:** the site never displays any claim about an agency that is not a direct restatement of an official BEOE notice, and every record links to its source. Status labels are neutral and factual ("Open actions on record"), never invented risk scores.
- **Polite scraping:** robots.txt verified first (`User-agent: * → Allow: /`); honest User-Agent with contact email; 3–5 s randomized delays; exponential backoff on server errors; cache-first so no page is ever fetched twice; small batches.
- **Soft-404 honesty:** nonexistent notice IDs return HTTP 200 with a listing page; the scraper detects this by content and never stores junk.

## How to run locally

```powershell
git clone <repo>
cd oep-transparency-index
python -m venv venv
.\venv\Scripts\Activate.ps1        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy config.py.example config.py   # then put your email in config.py

# 1. Scrape (small batches; resumable; Ctrl-C safe)
python scraper/enumerate_ids.py list
python scraper/enumerate_ids.py news 7000 7155
python scraper/enumerate_ids.py complaints 9395 9510

# 2. Build the database from the local cache
python pipeline/build_db.py

# 3. Run the site
python webapp/app.py               # open http://127.0.0.1:5000
```

## Data sources

All data from the Bureau of Emigration & Overseas Employment, Government of Pakistan:
- Notices: `beoe.gov.pk/news-updates/{id}` and `beoe.gov.pk/complaints/results/{id}`
- Licensed agencies: `beoe.gov.pk/list-of-oeps`

Verified page structures are documented in [docs/recon_findings.md](docs/recon_findings.md).

## Disclaimer

Independent open-data project. All records are republished from public notices of the Bureau of Emigration & Overseas Employment (beoe.gov.pk), Government of Pakistan, and every record links to its original source. This site adds no allegations of its own. For authoritative verification, consult beoe.gov.pk or your nearest Protectorate of Emigrants office.
