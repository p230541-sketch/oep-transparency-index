# tests_manual/test_db.py
#
# Sanity checks on the built database.
# Run: python tests_manual/test_db.py

import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
con = sqlite3.connect("data/db.sqlite3")
con.row_factory = sqlite3.Row

print("--- agencies with NULL oepl (created from notices) ---")
for r in con.execute("SELECT agency_id, canonical_name FROM agencies WHERE oepl_number IS NULL"):
    print(dict(r))

print("\n--- the spec acid test: every notice for one agency via JOIN ---")
for r in con.execute("""
    SELECT a.canonical_name, a.oepl_number, n.date_published, n.notice_type, n.title_raw
    FROM notices n
    JOIN notice_agencies na ON na.notice_id = n.notice_id
    JOIN agencies a ON a.agency_id = na.agency_id
    WHERE a.canonical_name LIKE '%China Manpower%'
    ORDER BY n.date_published DESC"""):
    print(dict(r))

print("\n--- notice counts by type ---")
for r in con.execute("SELECT notice_type, COUNT(*) n FROM notices GROUP BY notice_type"):
    print(dict(r))
