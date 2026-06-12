# scraper/sync.py
#
# Incremental update: finds the highest notice ID already in the local cache
# for each feed, scrapes politely upward from there until it hits the
# 25-consecutive-miss end-of-range condition, then prints what's new and
# reminds you to rebuild the database.
#
# How to run (from project root, venv active):
#   python scraper/sync.py

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import RAW_HTML_DIR
from scraper.enumerate_ids import walk_ids

FEEDS = {
    # feed name -> cache filename prefix
    "news": "news-updates_",
    "complaints": "complaints_results_",
}


def max_cached_id(prefix: str) -> int | None:
    """Highest numeric ID present in the cache for this feed, or None."""
    ids = []
    for path in glob.glob(os.path.join(RAW_HTML_DIR, prefix + "*.html")):
        m = re.search(r"_(\d+)\.html$", path)
        if m:
            ids.append(int(m.group(1)))
    return max(ids) if ids else None


def main():
    for feed, prefix in FEEDS.items():
        latest = max_cached_id(prefix)
        if latest is None:
            print(f"{feed}: no cached pages yet — run enumerate_ids.py with "
                  f"an explicit range first.")
            continue
        before = len(glob.glob(os.path.join(RAW_HTML_DIR, prefix + "*.html")))
        print(f"{feed}: cache ends at ID {latest}; checking for newer notices...")
        walk_ids(feed, latest + 1, None)  # open-ended: stops after 25 misses
        after = len(glob.glob(os.path.join(RAW_HTML_DIR, prefix + "*.html")))
        print(f"{feed}: {after - before} new page(s).\n")

    print("Sync finished. If anything was new, rebuild the database:")
    print("  python pipeline/build_db.py")


if __name__ == "__main__":
    main()
