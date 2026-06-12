# OEP Transparency Index

**Search any Pakistani overseas-recruitment agency's complete official disciplinary history in seconds — data that exists publicly but was never searchable.**

> Status: fully working locally (scraper → pipeline → web app), deploy-ready via `render.yaml`. A 0.9 MB sample database is committed, so the site runs immediately after cloning — no scraping required.

---

## The problem

Millions of Pakistani workers migrate to the Gulf, and recruitment fraud — fake agents, illegal overcharging, contract substitution — is widespread. Most victims are low-income and low-literacy. Pakistan's Bureau of Emigration & Overseas Employment (BEOE) licenses ~2,750 recruitment agencies ("Overseas Employment Promoters") and publishes every complaint, warning, show-cause notice, suspension, blacklisting, and license restoration against them.

But it publishes them **only as a chronological news feed**. There is no way to look up one agency and see its history. Searching "best recruitment agency Pakistan" returns marketing listicles written by the agencies themselves.

**The data exists; the access doesn't.** This project fixes the access.

## Measured results

| Metric | Result |
|---|---|
| Parsing coverage | **100.0%** (216/216 cached notices parsed) |
| Auto-merge precision | **100%** (87/87 on a hand-reviewed random sample) |
| Overall resolution accuracy | **99%** (99/100 decisions; the 1 failure is documented below) |
| Licensed agencies indexed | 2,756 (the complete active register) |
| Unit tests | 27 passing (`python -m pytest`) |
| Time to an agency's full history | 2 clicks (search → profile) vs. reading a 9,500-item feed |

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

One notice can name several agencies; names are written inconsistently (`M/s` vs `M/s.`, `OEPL No.` vs `OEP No.`, stray periods inside license numbers — all seen live); complaint pages name the agency but omit its license number entirely; complainants sometimes type junk into the form ("4584" or just "sufyan" as the agency name).

Resolution rules, in order:
1. **OEPL license number = primary identity.** Exact match wins instantly.
2. **Digits-only "name"?** If exactly one agency holds that license number, that's an unambiguous identity (a real case: a complainant entered `4584` as the agency name).
3. **Otherwise fuzzy-match the name** (rapidfuzz `token_sort_ratio`) against every canonical name and learned variant: score ≥ 92 → auto-merge; 80–91 → human review queue; < 80 → new record.
4. **Every decision is logged with its score** (`data/merge_log.csv`). `python pipeline/export_label_sample.py export` produces a random sample for hand-labeling; `... score` computes precision from the labels.

Showcase example: a complaint page names "M/s.China Manpower Services" with **no license number**. Fuzzy matching links it (score 100) to the canonical record carrying OEPL 4859/LHR — the search result shows a license number the source page never mentioned.

**The one measured failure (1/100):** a complaint where the official form contains just "sufyan" as the agency name. The likely real agency ("Sufyan Recruiting Agency") scored 44 — below every threshold — so a junk record was created instead of a link. Garbage in the source form is the limit of name matching; the review thresholds keep it from causing a *false* merge.

**Known limitation:** two licensed agencies share the normalized name "Talagang International" (OEPL 2600/RWP and 2660/RWP). No notice mentions either yet; if one ever does without a license number, name matching alone cannot distinguish them.

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

python webapp/app.py               # works immediately on the committed sample DB
# open http://127.0.0.1:5000 and search "Pharmic" or "4480/RWP"
```

To scrape fresh data yourself (optional):

```powershell
copy config.py.example config.py   # put your contact email in config.py
python scraper/enumerate_ids.py list                # full agency register
python scraper/enumerate_ids.py news 7000 7155      # notice ranges, batched
python scraper/enumerate_ids.py complaints 9395 9510
python scraper/sync.py                              # later: fetch only what's new
python pipeline/build_db.py                         # rebuild from local cache
```

Run the tests with `python -m pytest`.

## Deploying (Render, free tier)

1. Push this repo to GitHub.
2. On [render.com](https://render.com): **New + → Blueprint → select the repo → Apply.**
   Render reads `render.yaml`, installs requirements, and serves the app with gunicorn.
3. The committed sample database ships with the deploy; the scraper stays on your machine. To update the live data, rebuild locally, commit `data/db.sqlite3`, and push.

## Data sources

All data from the Bureau of Emigration & Overseas Employment, Government of Pakistan:
- Notices: `beoe.gov.pk/news-updates/{id}` and `beoe.gov.pk/complaints/results/{id}`
- Licensed agencies: `beoe.gov.pk/list-of-oeps`

Verified page structures are documented in [docs/recon_findings.md](docs/recon_findings.md); the build story lives in [docs/dev_journal.md](docs/dev_journal.md).

## Disclaimer

Independent open-data project. All records are republished from public notices of the Bureau of Emigration & Overseas Employment (beoe.gov.pk), Government of Pakistan, and every record links to its original source. This site adds no allegations of its own. For authoritative verification, consult beoe.gov.pk or your nearest Protectorate of Emigrants office.
