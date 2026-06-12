# scraper/enumerate_ids.py
#
# Walks BEOE notice IDs (or agency-list pages) and caches each page locally.
# Resumable: cached pages are skipped instantly, so Ctrl-C and rerun is safe.
#
# How to run (from project root, venv active):
#   python scraper/enumerate_ids.py complaints 9395 9510
#   python scraper/enumerate_ids.py news 7000 7155
#   python scraper/enumerate_ids.py list            (all pages of active OEPs)
#
# Without an explicit end ID, the walker stops after 25 consecutive misses
# (404s or soft-404 listing pages).

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scraper.fetch import make_session, fetch, is_soft_404

URL_PATTERNS = {
    "complaints": "https://beoe.gov.pk/complaints/results/{id}",
    "news": "https://beoe.gov.pk/news-updates/{id}",
}

LIST_URL = "https://beoe.gov.pk/list-of-oeps?show=active&page={page}"

MAX_CONSECUTIVE_MISSES = 25


def walk_ids(kind: str, start: int, end: int | None):
    url_pattern = URL_PATTERNS[kind]
    session = make_session()
    misses = 0
    fetched = cached = skipped = 0
    current = start

    while True:
        if end is not None and current > end:
            print(f"Reached end ID {end}.")
            break
        if end is None and misses >= MAX_CONSECUTIVE_MISSES:
            print(f"{MAX_CONSECUTIVE_MISSES} consecutive misses — assuming end of range.")
            break

        url = url_pattern.format(id=current)
        html, from_cache = fetch(session, url)

        if html is None:
            misses += 1
            skipped += 1
            print(f"  {kind} {current}: MISS (404/error)  [{misses} consecutive]")
        elif is_soft_404(html):
            misses += 1
            skipped += 1
            # Soft-404 pages were saved to cache by fetch(); remove them so
            # the parser never sees them and reruns re-check the ID.
            from scraper.fetch import cache_path
            try:
                os.remove(cache_path(url))
            except OSError:
                pass
            print(f"  {kind} {current}: MISS (soft 404)  [{misses} consecutive]")
        else:
            misses = 0
            if from_cache:
                cached += 1
            else:
                fetched += 1
                print(f"  {kind} {current}: fetched OK")
        current += 1

    print(f"\nDone. {fetched} fetched live, {cached} already cached, {skipped} misses.")


def walk_list_pages():
    session = make_session()
    page = 1
    fetched = cached = 0

    while True:
        url = LIST_URL.format(page=page)
        html, from_cache = fetch(session, url)
        if html is None:
            print(f"  list page {page}: fetch failed — stopping.")
            break

        # A page past the end has no agency rows in its table body.
        # Licence numbers look like "0008  / RWP" inside <td> cells.
        if "<tbody>" not in html or html.count("<tr>") < 2:
            print(f"  list page {page}: no rows — end of list.")
            # Don't keep the empty page in cache.
            from scraper.fetch import cache_path
            if not from_cache:
                try:
                    os.remove(cache_path(url))
                except OSError:
                    pass
            break

        if from_cache:
            cached += 1
        else:
            fetched += 1
            print(f"  list page {page}: fetched OK")
        page += 1

    print(f"\nDone. {fetched} list pages fetched live, {cached} already cached.")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("complaints", "news", "list"):
        print(__doc__)
        sys.exit(1)

    kind = sys.argv[1]
    if kind == "list":
        walk_list_pages()
    else:
        start_id = int(sys.argv[2])
        end_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
        walk_ids(kind, start_id, end_id)
