# scraper/fetch.py
#
# Polite, cached, logged fetcher for beoe.gov.pk.
# - Cache-first: never refetches a page that's already in data/raw_html/
# - 3-5 second randomized delay before every live request
# - Exponential backoff on 5xx errors, max 3 retries
# - Every live fetch is logged to data/scrape_log.sqlite3
#
# This module is imported by enumerate_ids.py; it isn't run directly.

import os
import sys
import time
import random
import sqlite3
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import USER_AGENT, RAW_HTML_DIR

SCRAPE_LOG_DB = "data/scrape_log.sqlite3"

# Markers that identify a REAL Cloudflare challenge page (not the harmless
# beacon script Cloudflare injects into normal pages).
CF_CHALLENGE_MARKERS = ("<title>just a moment", "cf_chl_opt")

# Headings shown when the site soft-404s (returns a listing page with
# HTTP 200 instead of a 404 for a nonexistent notice ID).
LISTING_HEADINGS = {
    "complaints", "news", "news & updates", "news updates",
    "news / updates", "latest news", "news and updates",
}


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return session


def url_to_filename(url: str) -> str:
    """Turn a URL into a safe local filename, e.g. complaints_results_9495.html"""
    path = url.replace("https://beoe.gov.pk/", "").replace("?", "_").replace("=", "_")
    safe = path.replace("/", "_").replace("&", "_")
    return safe + ".html"


def cache_path(url: str) -> str:
    return os.path.join(RAW_HTML_DIR, url_to_filename(url))


def _log_fetch(url: str, status_code: int, file_path: str):
    con = sqlite3.connect(SCRAPE_LOG_DB)
    con.execute("""CREATE TABLE IF NOT EXISTS fetch_log (
        url TEXT, status_code INTEGER, fetched_at TEXT, file_path TEXT)""")
    con.execute(
        "INSERT INTO fetch_log VALUES (?, ?, ?, ?)",
        (url, status_code, datetime.now(timezone.utc).isoformat(), file_path),
    )
    con.commit()
    con.close()


def is_cloudflare_block(status_code: int, html: str) -> bool:
    if status_code in (403, 503):
        return True
    lower = html.lower()
    return any(m in lower for m in CF_CHALLENGE_MARKERS)


def fetch(session: requests.Session, url: str, max_retries: int = 3):
    """
    Fetch a URL politely with caching.

    Returns (html, from_cache) on success.
    Returns (None, False) on a permanent failure (404, repeated 5xx, network).
    Raises RuntimeError on a Cloudflare block — that's a stop-everything event.
    """
    path = cache_path(url)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read(), True

    os.makedirs(RAW_HTML_DIR, exist_ok=True)

    for attempt in range(max_retries):
        # Polite delay before EVERY live request, including retries.
        time.sleep(random.uniform(3, 5))
        try:
            response = session.get(url, timeout=20)
        except requests.RequestException as exc:
            print(f"    network error ({exc}); retry {attempt + 1}/{max_retries}")
            continue

        status = response.status_code

        if is_cloudflare_block(status, response.text):
            _log_fetch(url, status, "")
            raise RuntimeError(
                f"BLOCKED at {url} (HTTP {status}). Stopping — do not work around blocks."
            )

        if status == 404:
            _log_fetch(url, 404, "")
            return None, False

        if status >= 500:
            # Exponential backoff: 5s, 10s, 20s — the server is struggling,
            # so we wait longer each time instead of hammering it.
            wait = 5 * (2 ** attempt)
            print(f"    HTTP {status}; backing off {wait}s (retry {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue

        if status == 200:
            with open(path, "w", encoding="utf-8") as f:
                f.write(response.text)
            _log_fetch(url, 200, path)
            return response.text, False

        # Unexpected status (3xx that requests didn't follow, 4xx other than 404)
        _log_fetch(url, status, "")
        return None, False

    _log_fetch(url, -1, "")  # -1 = gave up after retries
    return None, False


def is_soft_404(html: str) -> bool:
    """
    BEOE returns the generic listing page (HTTP 200) for nonexistent notice
    IDs. A real notice page has a content <h1> with the notice title; a
    soft-404 has a generic listing heading like "Complaints" or "News".
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all("h1"):
        text = el.get_text(" ", strip=True)
        if text and "bureau of emigration" not in text.lower():
            return text.strip().lower() in LISTING_HEADINGS
    return True  # no content h1 at all — treat as a miss
