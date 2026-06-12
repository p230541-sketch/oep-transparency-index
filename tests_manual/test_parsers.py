# tests_manual/test_parsers.py
#
# Quick manual check of the three parsers against cached pages.
# Run: python tests_manual/test_parsers.py

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.parse_notices import (
    parse_news_page, parse_complaint_page, parse_list_page, extract_agencies,
)

for f in ["news-updates_7151", "news-updates_7100", "news-updates_7000"]:
    html = open(f"data/raw_html/{f}.html", encoding="utf-8").read()
    r = parse_news_page(html, f)
    print(f, "->", r.get("notice_type"), "|", r.get("date"), "|", r.get("agencies"))

for f in ["complaints_results_9495", "complaints_results_9400"]:
    html = open(f"data/raw_html/{f}.html", encoding="utf-8").read()
    r = parse_complaint_page(html, f)
    print(f, "->", r.get("notice_type"), "|", r.get("date"), "|", r.get("agencies"))

html = open("data/raw_html/list-of-oeps_show_active.html", encoding="utf-8").read()
rows = parse_list_page(html)
print("list page:", len(rows), "agencies; first:", rows[0] if rows else None)

t = ("Personal Hearing Notice To M/s. Pharmic Enterprises, OEPL No.4480/RWP , "
     "M/s. Al Sofi Group Manpower Consultants,OEPL No.4156/RWP & "
     "M/s. Key Technical Services,OEPL No.1111/KAR")
for a in extract_agencies(t):
    print("  multi:", a)
print("  no-oepl:", extract_agencies("Blacklisting of M/s. Super Star Trade Test Center, Rawalpindi"))
print("  parens:", extract_agencies("Complaint against M/s China Manpower Services (OEPL No. 4859/LHR) is under process"))
