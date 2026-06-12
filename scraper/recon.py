# scraper/recon.py
#
# Phase 0 reconnaissance script.
# Fetches a small sample of BEOE pages, saves the raw HTML, and
# prints what it finds so we can confirm the URL patterns and page
# structure are still as documented before writing the real scraper.
#
# How to run (from the project root, with venv active):
#   python scraper/recon.py

import os
import sys
import time
import random

import requests
from bs4 import BeautifulSoup

# Windows consoles default to a legacy encoding (cp1252) that can't print
# many Unicode characters. Force UTF-8 so page titles (which may contain
# Urdu or special dashes) print instead of crashing the script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
# We import config.py from the project root.  If it doesn't exist yet the
# user sees a friendly message instead of a confusing ImportError.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import USER_AGENT, RAW_HTML_DIR
except ImportError:
    print("ERROR: config.py not found.")
    print("Copy config.py.example to config.py and fill in your email, then retry.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Target URLs
# ---------------------------------------------------------------------------
# Three complaint-notice pages, three news/action pages, one agency-list page.
# IDs are sequential integers on the BEOE site; these are recent known-good ones.
SAMPLE_URLS = [
    ("complaint", "https://beoe.gov.pk/complaints/results/9495"),
    ("complaint", "https://beoe.gov.pk/complaints/results/9400"),
    ("complaint", "https://beoe.gov.pk/complaints/results/9300"),
    ("news",      "https://beoe.gov.pk/news-updates/7151"),
    ("news",      "https://beoe.gov.pk/news-updates/7100"),
    ("news",      "https://beoe.gov.pk/news-updates/7000"),
    ("list",      "https://beoe.gov.pk/list-of-oeps?show=active"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def url_to_filename(url: str) -> str:
    """Turn a URL into a safe local filename, e.g. complaints_results_9495.html"""
    path = url.replace("https://beoe.gov.pk/", "").replace("?", "_").replace("=", "_")
    safe = path.replace("/", "_").replace("&", "_")
    return safe + ".html"


def is_cloudflare_block(status_code: int, html: str) -> bool:
    """
    Cloudflare sometimes returns a 403 or 503 with a JavaScript challenge page
    instead of the real content.

    Careful: Cloudflare also injects a harmless monitoring script
    ("challenge-platform") into NORMAL pages, so we must only look for
    markers that appear on the actual challenge page itself:
    its <title> is "Just a moment..." and it defines a cf_chl_opt object.
    """
    if status_code in (403, 503):
        return True
    lower = html.lower()
    return "<title>just a moment" in lower or "cf_chl_opt" in lower


def extract_headline(soup: BeautifulSoup) -> str:
    """
    Best-effort headline extraction — not production-grade, just recon.

    Every BEOE page has the site name "Bureau of Emigration & Overseas
    Employment" in a banner <h1> near the top, and the actual notice title
    in a SECOND <h1> further down the page.  So we look at all h1/h2
    elements and return the first one that is NOT the site banner.
    """
    for tag in ("h1", "h2", "h3"):
        for el in soup.find_all(tag):
            text = el.get_text(" ", strip=True)
            if text and "bureau of emigration" not in text.lower():
                return text[:200]
    return "(no headline found)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RAW_HTML_DIR, exist_ok=True)

    # A requests.Session reuses the same TCP connection and lets us set
    # headers once for all requests — like a persistent logged-in browser tab.
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        # These headers make the request look like a normal browser visit.
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    results = []  # collect summary rows

    print(f"User-Agent: {USER_AGENT}")
    print(f"Saving HTML to: {RAW_HTML_DIR}/")
    print(f"Fetching {len(SAMPLE_URLS)} pages with 3-5 s delays...\n")

    for i, (page_type, url) in enumerate(SAMPLE_URLS):
        # Polite delay between requests — we're a guest on a public server.
        if i > 0:
            delay = random.uniform(3, 5)
            print(f"  (waiting {delay:.1f}s...)")
            time.sleep(delay)

        print(f"[{i+1}/{len(SAMPLE_URLS)}] {page_type.upper():10s} {url}")

        try:
            response = session.get(url, timeout=15)
        except requests.RequestException as exc:
            print(f"  --> NETWORK ERROR: {exc}")
            results.append((url, "ERR", "—", "—"))
            continue

        status = response.status_code
        html = response.text
        print(f"  --> HTTP {status}  ({len(html):,} bytes)")

        # ---- Cloudflare / access block detection -------------------------
        if is_cloudflare_block(status, html):
            print()
            print("  [!] BLOCKED by Cloudflare or server access control.")
            print("     This means the site is refusing automated requests.")
            print("     STOP HERE — do not try to work around the block.")
            print("     Paste this output in the chat and we'll decide next steps.")
            print()
            results.append((url, f"BLOCKED ({status})", "—", "—"))
            continue

        # ---- Save raw HTML -----------------------------------------------
        filename = url_to_filename(url)
        filepath = os.path.join(RAW_HTML_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        # ---- Parse for headline ------------------------------------------
        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.string.strip() if soup.title else "(no <title>)"
        headline = extract_headline(soup)

        print(f"  <title>  : {page_title}")
        print(f"  Headline : {headline}")

        results.append((url, status, filename, headline[:80]))

    # ---- Summary table ---------------------------------------------------
    print()
    print("=" * 80)
    print(f"{'URL':<50} {'STATUS':<15} {'HEADLINE FOUND?'}")
    print("-" * 80)
    for url, status, fname, headline in results:
        found = "YES" if fname != "—" else "NO"
        short_url = url.replace("https://beoe.gov.pk", "")
        print(f"{short_url:<50} {str(status):<15} {found}  {headline[:30]}")
    print("=" * 80)
    print()

    saved = [r for r in results if r[2] != "—"]
    blocked = [r for r in results if "BLOCKED" in str(r[1])]

    if blocked:
        print(f"RESULT: {len(blocked)} page(s) were BLOCKED.")
        print("Paste this full output in the chat before we go any further.")
    else:
        print(f"RESULT: {len(saved)}/{len(SAMPLE_URLS)} pages saved to {RAW_HTML_DIR}/")
        print("Paste this output in the chat so we can review what the site looks like.")


if __name__ == "__main__":
    main()
