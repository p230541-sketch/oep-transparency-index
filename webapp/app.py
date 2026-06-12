# webapp/app.py
#
# The OEP Transparency Index web app: search Pakistani overseas-recruitment
# agencies and see their full official BEOE track record.
# Reads ONLY data/db.sqlite3 (built by pipeline/build_db.py).
#
# How to run (from project root, venv active):
#   python webapp/app.py
# then open http://127.0.0.1:5000

import os
import re
import sqlite3
import sys

from flask import Flask, g, render_template, request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
DB_PATH = os.path.join(PROJECT_ROOT, "data", "db.sqlite3")

from pipeline.entity_resolution import normalize_name

app = Flask(__name__)

ACTION_LABELS = {
    "complaint_opened": ("Complaint opened", "badge-open"),
    "complaint_closed": ("Complaint closed", "badge-closed"),
    "show_cause": ("Show-cause notice", "badge-warn"),
    "warning": ("Warning issued", "badge-warn"),
    "personal_hearing": ("Personal hearing", "badge-warn"),
    "suspension": ("Licence suspended", "badge-black"),
    "blacklisting": ("Blacklisting", "badge-black"),
    "restoration": ("License restored", "badge-restore"),
    "other": ("Official notice", "badge-other"),
}


@app.before_request
def require_database():
    """Friendly setup message instead of a 500 when the DB hasn't been built."""
    if not os.path.exists(DB_PATH):
        return (
            "<h1>Database not built yet</h1>"
            "<p>Run <code>python pipeline/build_db.py</code> from the project "
            "root first (see README), then reload this page.</p>", 503,
        )
    return None


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.context_processor
def inject_globals():
    try:
        row = get_db().execute(
            "SELECT value FROM meta WHERE key='last_synced'").fetchone()
        last_synced = row["value"] if row else "unknown"
    except sqlite3.Error:
        last_synced = "unknown"
    return {"last_synced": last_synced, "action_labels": ACTION_LABELS}


def status_tier(agency_id: int) -> tuple[str, str]:
    """
    Neutral, factual status tiers derived strictly from official notices.
    Returns (label, css_class).
    """
    db = get_db()
    rows = db.execute(
        """SELECT n.notice_type, n.date_published
           FROM notices n JOIN notice_agencies na ON n.notice_id = na.notice_id
           WHERE na.agency_id = ? AND n.parsed_ok = 1""",
        (agency_id,),
    ).fetchall()

    if not rows:
        return "No official actions on record", "tier-none"

    types = [r["notice_type"] for r in rows]

    def last_of(notice_type):
        return max((r["date_published"] or "" for r in rows
                    if r["notice_type"] == notice_type), default=None)

    last_restore = last_of("restoration")
    for serious, label in (("blacklisting", "Currently blacklisted"),
                           ("suspension", "Licence suspended (per BEOE notice)")):
        last = last_of(serious)
        if last is not None and (last_restore is None or last_restore < last):
            return label, "tier-black"

    opened = types.count("complaint_opened")
    closed = types.count("complaint_closed")
    if opened > closed:
        return "Open actions on record", "tier-open"
    return "Past actions on record", "tier-past"


@app.route("/")
def home():
    db = get_db()
    n_agencies = db.execute("SELECT COUNT(*) FROM agencies").fetchone()[0]
    n_notices = db.execute(
        "SELECT COUNT(*) FROM notices WHERE parsed_ok=1").fetchone()[0]
    return render_template("home.html", n_agencies=n_agencies,
                           n_notices=n_notices)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("results.html", q=q, agencies=[])

    db = get_db()
    # If the query looks like a licence number ("2974", "2974/PWR"),
    # search the OEPL field; otherwise search names and known variants.
    m = re.match(r"^(\d{1,4})\s*(?:/\s*([A-Za-z]{2,5}))?$", q)
    if m:
        oepl_like = f"{int(m.group(1)):04d}/%"
        if m.group(2):
            oepl_like = f"{int(m.group(1)):04d}/{m.group(2).upper()}"
        rows = db.execute(
            """SELECT a.*, COUNT(na.notice_id) AS action_count
               FROM agencies a
               LEFT JOIN notice_agencies na ON na.agency_id = a.agency_id
               WHERE a.oepl_number LIKE ?
               GROUP BY a.agency_id ORDER BY a.canonical_name LIMIT 50""",
            (oepl_like,),
        ).fetchall()
    else:
        # Variants are stored normalized (lowercase, no M/s, no punctuation),
        # so normalize the query for that column; raw LIKE for canonical names.
        like = f"%{q}%"
        norm_like = f"%{normalize_name(q)}%"
        rows = db.execute(
            """SELECT a.*, COUNT(DISTINCT na.notice_id) AS action_count
               FROM agencies a
               LEFT JOIN name_variants v ON v.agency_id = a.agency_id
               LEFT JOIN notice_agencies na ON na.agency_id = a.agency_id
               WHERE a.canonical_name LIKE ? OR v.variant_text LIKE ?
               GROUP BY a.agency_id ORDER BY action_count DESC,
                        a.canonical_name LIMIT 50""",
            (like, norm_like),
        ).fetchall()

    agencies = [dict(r) | {"tier": status_tier(r["agency_id"])} for r in rows]
    return render_template("results.html", q=q, agencies=agencies)


@app.route("/agency/<int:agency_id>")
def agency(agency_id):
    db = get_db()
    a = db.execute("SELECT * FROM agencies WHERE agency_id=?",
                   (agency_id,)).fetchone()
    if a is None:
        return render_template("404.html"), 404

    notices = db.execute(
        """SELECT n.* FROM notices n
           JOIN notice_agencies na ON n.notice_id = na.notice_id
           WHERE na.agency_id = ? AND n.parsed_ok = 1
           ORDER BY n.date_published IS NULL, n.date_published DESC""",
        (agency_id,),
    ).fetchall()

    return render_template("agency.html", a=a, notices=notices,
                           tier=status_tier(agency_id))


@app.route("/stats")
def stats():
    db = get_db()
    by_type = db.execute(
        """SELECT notice_type, COUNT(*) AS n FROM notices
           WHERE parsed_ok=1 GROUP BY notice_type ORDER BY n DESC"""
    ).fetchall()
    by_year = db.execute(
        """SELECT substr(date_published, 1, 4) AS year, COUNT(*) AS n
           FROM notices WHERE parsed_ok=1 AND date_published IS NOT NULL
           GROUP BY year ORDER BY year"""
    ).fetchall()
    by_region = db.execute(
        """SELECT a.region_code, COUNT(DISTINCT na.notice_id) AS n
           FROM notice_agencies na
           JOIN agencies a ON a.agency_id = na.agency_id
           WHERE a.region_code IS NOT NULL
           GROUP BY a.region_code ORDER BY n DESC"""
    ).fetchall()

    def with_pct(rows):
        mx = max((r["n"] for r in rows), default=1)
        return [dict(r) | {"pct": round(100 * r["n"] / mx)} for r in rows]

    return render_template("stats.html", by_type=with_pct(by_type),
                           by_year=with_pct(by_year),
                           by_region=with_pct(by_region))


if __name__ == "__main__":
    app.run(debug=False)
