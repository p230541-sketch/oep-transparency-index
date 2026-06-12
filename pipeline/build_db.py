# pipeline/build_db.py
#
# Rebuilds data/db.sqlite3 from scratch out of the cached HTML in
# data/raw_html/. Reads ONLY the local cache — never the live site.
#
# Steps:
#   1. Create the schema
#   2. Seed agencies from cached list-of-oeps pages
#   3. Parse every cached notice page (news + complaints)
#   4. Resolve agency mentions (OEPL exact match, then fuzzy names)
#   5. Write unparsed.csv, review_queue.csv, merge_log.csv + print stats
#
# How to run (from project root, venv active):
#   python pipeline/build_db.py

import csv
import glob
import os
import re
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.parse_notices import parse_news_page, parse_complaint_page, parse_list_page
from pipeline.entity_resolution import Resolver

DB_PATH = "data/db.sqlite3"
RAW_DIR = "data/raw_html"
UNPARSED_PATH = "data/unparsed.csv"

SCHEMA = """
CREATE TABLE agencies (
    agency_id   INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    oepl_number TEXT UNIQUE,          -- NULL for name-only records
    region_code TEXT,
    license_status TEXT,
    address     TEXT,
    phone       TEXT,
    beoe_profile_url TEXT
);
CREATE TABLE notices (
    notice_id   INTEGER PRIMARY KEY,
    beoe_url    TEXT UNIQUE NOT NULL,
    notice_type TEXT NOT NULL,
    title_raw   TEXT NOT NULL,
    date_published TEXT,              -- ISO yyyy-mm-dd when parseable
    raw_html_path TEXT,
    parsed_ok   INTEGER NOT NULL
);
CREATE TABLE notice_agencies (
    notice_id INTEGER NOT NULL REFERENCES notices(notice_id),
    agency_id INTEGER NOT NULL REFERENCES agencies(agency_id),
    PRIMARY KEY (notice_id, agency_id)
);
CREATE TABLE name_variants (
    agency_id INTEGER NOT NULL REFERENCES agencies(agency_id),
    variant_text TEXT NOT NULL
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX idx_agencies_name ON agencies(canonical_name);
CREATE INDEX idx_na_agency ON notice_agencies(agency_id);
"""


def to_iso(date_text: str | None) -> str | None:
    """'Jun 8, 2026' -> '2026-06-08'. Returns None if unparseable."""
    if not date_text:
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def cache_file_to_url(filename: str) -> str:
    """complaints_results_9495.html -> https://beoe.gov.pk/complaints/results/9495"""
    stem = os.path.basename(filename)[:-len(".html")]
    if stem.startswith("complaints_results_"):
        return "https://beoe.gov.pk/complaints/results/" + stem.split("_")[-1]
    if stem.startswith("news-updates_"):
        return "https://beoe.gov.pk/news-updates/" + stem.split("_")[-1]
    return "https://beoe.gov.pk/" + stem


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    resolver = Resolver()

    def create_agency(name, oepl, status=None, address=None, phone=None,
                      proprietor=None):
        region = oepl.split("/")[1] if oepl else None
        cur = con.execute(
            """INSERT INTO agencies
               (canonical_name, oepl_number, region_code, license_status,
                address, phone, beoe_profile_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, oepl, region, status, address, phone,
             "https://beoe.gov.pk/list-of-oeps"),
        )
        return cur.lastrowid

    # ---- Step 1: seed agencies from list pages ----------------------------
    list_files = sorted(glob.glob(os.path.join(RAW_DIR, "list-of-oeps*.html")))
    seeded = 0
    for path in list_files:
        with open(path, encoding="utf-8") as f:
            html = f.read()
        for row in parse_list_page(html):
            if row["oepl"] in resolver.by_oepl:
                continue  # duplicate across pages
            aid = create_agency(row["name"], row["oepl"], status=row["status"],
                                address=row["address"], phone=row["phone"])
            resolver.register(aid, row["name"], row["oepl"])
            seeded += 1
    print(f"Seeded {seeded} licensed agencies from {len(list_files)} list pages.")

    # ---- Steps 2-3: parse notices and resolve agencies ---------------------
    unparsed = []
    n_total = n_ok = 0

    notice_files = sorted(
        glob.glob(os.path.join(RAW_DIR, "news-updates_*.html"))
        + glob.glob(os.path.join(RAW_DIR, "complaints_results_*.html"))
    )

    for path in notice_files:
        n_total += 1
        url = cache_file_to_url(path)
        with open(path, encoding="utf-8") as f:
            html = f.read()

        if "complaints_results_" in path:
            result = parse_complaint_page(html, url)
        else:
            result = parse_news_page(html, url)

        if not result["ok"]:
            unparsed.append((url, path, result["reason"]))
            con.execute(
                """INSERT OR IGNORE INTO notices
                   (beoe_url, notice_type, title_raw, date_published,
                    raw_html_path, parsed_ok)
                   VALUES (?, 'other', '(unparsed)', NULL, ?, 0)""",
                (url, path),
            )
            continue

        n_ok += 1
        cur = con.execute(
            """INSERT OR IGNORE INTO notices
               (beoe_url, notice_type, title_raw, date_published,
                raw_html_path, parsed_ok)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (url, result["notice_type"], result["title"],
             to_iso(result["date"]), path),
        )
        notice_id = cur.lastrowid

        for mention in result["agencies"]:
            agency_id = resolver.resolve(mention["name"], mention["oepl"],
                                         create_agency)
            con.execute(
                "INSERT OR IGNORE INTO notice_agencies VALUES (?, ?)",
                (notice_id, agency_id),
            )

    # ---- Step 4: persist variants, logs, stats ----------------------------
    seen = set()
    for norm, aid in resolver.names:
        if (aid, norm) not in seen:
            seen.add((aid, norm))
            con.execute("INSERT INTO name_variants VALUES (?, ?)", (aid, norm))

    con.execute("INSERT INTO meta VALUES ('last_synced', ?)",
                (datetime.now().strftime("%Y-%m-%d"),))
    con.commit()

    resolver.write_logs()
    with open(UNPARSED_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "file", "reason"])
        w.writerows(unparsed)

    # ---- Stats -------------------------------------------------------------
    coverage = (100.0 * n_ok / n_total) if n_total else 0.0
    n_agencies = con.execute("SELECT COUNT(*) FROM agencies").fetchone()[0]
    n_links = con.execute("SELECT COUNT(*) FROM notice_agencies").fetchone()[0]
    print(f"Parsed {n_ok}/{n_total} notices  ({coverage:.1f}% coverage)")
    print(f"{len(unparsed)} unparsed -> {UNPARSED_PATH}")
    print(f"{n_agencies} agencies, {n_links} notice-agency links")
    print(f"{len(resolver.review_queue)} fuzzy matches need review -> data/review_queue.csv")
    con.close()


if __name__ == "__main__":
    main()
