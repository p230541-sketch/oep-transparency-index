# OEP Transparency Index

**Search any Pakistani recruitment agency's complete official disciplinary history in seconds.**

Pakistan's Bureau of Emigration & Overseas Employment (BEOE) publishes complaints, warnings, blacklistings, and restorations for ~2,750 licensed recruitment agencies — but only as an un-searchable chronological news feed. This tool re-indexes that public data so a worker or journalist can look up one agency and instantly see its full official track record, with every item linking back to the original government notice.

---

## Status: Phase 0 — Reconnaissance ✅ complete

Data sources verified live (7/7 sample pages fetched, all URL patterns confirmed).
See [docs/recon_findings.md](docs/recon_findings.md) for the verified page structures,
including the soft-404 behavior that shapes the Phase 1 scraper design.

---

## How to run (Phase 0 — recon script)

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy config and fill in your email
copy config.py.example config.py
# (edit config.py to set your email)

# 4. Run the reconnaissance script
python scraper/recon.py
```

Expected output: 7 fetched pages, saved to `data/raw_html/`, with a summary table.

---

## Disclaimer

Independent open-data project. All records are republished from public notices of the Bureau of Emigration & Overseas Employment (beoe.gov.pk), Government of Pakistan, and every record links to its original source. This site adds no allegations of its own.
