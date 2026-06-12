# tests_manual/find_titles.py — inspect titles classified as 'other'
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
con = sqlite3.connect("data/db.sqlite3")
for url, title in con.execute(
        "SELECT beoe_url, title_raw FROM notices WHERE notice_type='other'"):
    print(url, "|", title)
