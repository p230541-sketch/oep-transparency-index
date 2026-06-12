# pipeline/parse_notices.py
#
# Turns cached BEOE HTML pages into structured records.
# Reads ONLY from data/raw_html/ — never touches the live site.
#
# Three page types, three parsers:
#   - news-updates_{id}.html      -> notice title, date, type, agency mentions
#   - complaints_results_{id}.html -> structured complaint fields
#   - list-of-oeps_*.html          -> licensed agency rows (seeds the DB)
#
# Imported by build_db.py; not usually run directly.

import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Matches "OEPL No. 1234/RWP", "OEPL No.1234/RWP", "(OEPL No. 0848/LHR)" etc.
OEPL_RE = re.compile(r"OEPL\s*No\.?\s*(\d{1,4})\s*/\s*([A-Za-z]{2,5})", re.IGNORECASE)

# Matches an agency-name mention: "M/s Foo Bar" or "M/s. Foo Bar"
MS_RE = re.compile(r"M/s\.?\s*", re.IGNORECASE)


def normalize_oepl(digits: str, region: str) -> str:
    """'848', 'lhr' -> '0848/LHR' (zero-padded, uppercase, no spaces)."""
    return f"{int(digits):04d}/{region.upper()}"


def content_h1(soup: BeautifulSoup):
    """The notice <h1> — the first h1 that is not the site banner."""
    for el in soup.find_all("h1"):
        text = el.get_text(" ", strip=True)
        if text and "bureau of emigration" not in text.lower():
            return el
    return None


def classify_title(title: str) -> str:
    """Map a notice title to the action taxonomy. Never raises."""
    t = title.lower()
    if t.startswith("closure of complaint") or "closure of complaint" in t:
        return "complaint_closed"
    if t.startswith("complaint against") and "under process" in t:
        return "complaint_opened"
    if t.startswith("complaint against"):
        return "complaint_opened"
    if "show cause" in t:
        return "show_cause"
    if "warning" in t:
        return "warning"
    if "personal hearing" in t:
        return "personal_hearing"
    if "blacklist" in t:
        return "blacklisting"
    if "restoration" in t or "restored" in t:
        return "restoration"
    return "other"


def extract_agencies(title: str) -> list[dict]:
    """
    Pull every (agency name, OEPL number) pair out of a notice title.

    Strategy: find each "M/s" mention; the agency name runs from there until
    the next OEPL number / "(" / "&" / next "M/s". The OEPL number belonging
    to that agency is the first one appearing after its name and before the
    next "M/s" mention. Agencies with no number (e.g., blacklisted trade
    centers) get oepl=None and are matched by name later.
    """
    agencies = []
    ms_positions = [m for m in MS_RE.finditer(title)]
    if not ms_positions:
        return agencies

    for i, m in enumerate(ms_positions):
        name_start = m.end()
        next_ms = ms_positions[i + 1].start() if i + 1 < len(ms_positions) else len(title)
        segment = title[name_start:next_ms]

        # The name ends where the license reference (or a bracket/&) begins.
        cut = len(segment)
        oepl_match = OEPL_RE.search(segment)
        if oepl_match:
            cut = min(cut, oepl_match.start())
        paren = segment.find("(")
        if paren != -1:
            cut = min(cut, paren)
        amp = segment.find("&")
        if amp != -1 and (not oepl_match or amp < oepl_match.start()):
            cut = min(cut, amp)

        name = segment[:cut].strip().strip(",").strip()
        oepl = None
        if oepl_match:
            oepl = normalize_oepl(oepl_match.group(1), oepl_match.group(2))

        if name:
            agencies.append({"name": name, "oepl": oepl})
    return agencies


# ---------------------------------------------------------------------------
# News / notice pages
# ---------------------------------------------------------------------------

def parse_news_page(html: str, url: str) -> dict:
    """
    Returns {"ok": True, title, date, notice_type, agencies: [...]}
    or {"ok": False, "reason": ...}. Never raises.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        h1 = content_h1(soup)
        if h1 is None:
            return {"ok": False, "reason": "no content h1 found"}

        small = h1.find("small")
        date = small.get_text(strip=True) if small else None
        if small:
            small.extract()  # remove the date so it's not part of the title
        title = h1.get_text(" ", strip=True)
        if not title:
            return {"ok": False, "reason": "empty title"}

        return {
            "ok": True,
            "title": title,
            "date": date,
            "notice_type": classify_title(title),
            "agencies": extract_agencies(title),
        }
    except Exception as exc:
        return {"ok": False, "reason": f"exception: {exc}"}


# ---------------------------------------------------------------------------
# Complaint result pages
# ---------------------------------------------------------------------------

def parse_complaint_page(html: str, url: str) -> dict:
    """
    Complaint pages have labeled fields instead of a descriptive title:
      OEP Name: M/s.China Manpower Services
      Complaint Status: Under Investigation
      Added On: Jun 8, 2026
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        h1 = content_h1(soup)
        if h1 is None or "view complaint result" not in h1.get_text(strip=True).lower():
            return {"ok": False, "reason": "not a complaint result page"}

        head = soup.find(class_="complaint_head")
        if head is None:
            return {"ok": False, "reason": "no complaint_head block"}

        fields = {}
        for p in head.find_all("p"):
            text = p.get_text(" ", strip=True)
            if ":" in text:
                label, _, value = text.partition(":")
                fields[label.strip().lower()] = value.strip()

        oep_name = fields.get("oep name") or fields.get("licence title")
        if not oep_name:
            return {"ok": False, "reason": "no OEP name field"}
        # Strip the M/s. prefix and stray trailing punctuation
        oep_name = MS_RE.sub("", oep_name).strip().strip(",.").strip()

        status = fields.get("complaint status", "").lower()
        if any(w in status for w in ("closed", "disposed", "resolved", "decided")):
            notice_type = "complaint_closed"
        else:
            notice_type = "complaint_opened"

        status_display = fields.get("complaint status", "unknown status")
        title = f"Complaint against M/s {oep_name} — status: {status_display}"

        return {
            "ok": True,
            "title": title,
            "date": fields.get("added on"),
            "notice_type": notice_type,
            "agencies": [{"name": oep_name, "oepl": None}],
            "extra_fields": fields,
        }
    except Exception as exc:
        return {"ok": False, "reason": f"exception: {exc}"}


# ---------------------------------------------------------------------------
# Agency list pages
# ---------------------------------------------------------------------------

def parse_list_page(html: str) -> list[dict]:
    """
    Returns one dict per agency row:
      {oepl, region, proprietor, name, status, expiry, address, phone}
    Rows that can't be parsed are skipped (the table also has spacer rows).
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="table")
    if table is None:
        return []

    rows = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 6:
            continue
        licence_text = cells[0].get_text(" ", strip=True)
        m = re.match(r"(\d{1,4})\s*/\s*([A-Za-z]{2,5})", licence_text)
        if not m:
            continue
        oepl = normalize_oepl(m.group(1), m.group(2))

        head_office = cells[5].get_text(" ", strip=True)
        # Address and phones share a cell; phones follow icon spans, so just
        # split on the first phone-looking run of digits.
        phone_match = re.search(r"0\d{2,4}[\s-]?\d{6,8}", head_office)
        address = head_office[: phone_match.start()].strip(" ,") if phone_match else head_office
        phone = phone_match.group(0) if phone_match else None

        rows.append({
            "oepl": oepl,
            "region": oepl.split("/")[1],
            "proprietor": cells[1].get_text(" ", strip=True),
            "name": cells[2].get_text(" ", strip=True),
            "status": cells[3].get_text(" ", strip=True),
            "expiry": cells[4].get_text(" ", strip=True),
            "address": address,
            "phone": phone,
        })
    return rows
