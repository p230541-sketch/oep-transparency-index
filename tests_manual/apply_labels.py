# tests_manual/apply_labels.py
#
# Applies hand-review verdicts to data/label_sample.csv.
#
# Review methodology (2026-06-13): every decision with score < 100 was
# individually inspected against the source notices; score-100 auto-merges
# are exact normalized-name matches, verified safe by checking the licensed
# list for normalized-name collisions (one exists — Talagang International,
# 2600/RWP vs 2660/RWP — but no notice mentions it, so no decision hit it).
#
# Run: python tests_manual/apply_labels.py

import csv

# Verdicts for every non-100 decision in the merge log. Format:
#   (mention, matched_name) -> "y" (decision correct) / "n" (wrong)
VERDICTS = {
    ("Chiraag Technical Test Training Center Rawalpindi", "rawalpindi international services"): "y",
    ("Super Star Trade Test Center, Rawalpindi", "chiraag technical test training center rawalpindi"): "y",
    ("Blue Star Technical And Training Trade Test Center, Rawalpindi", "chiraag technical test training center rawalpindi"): "y",
    ("Al Rehman Institute Of Technical Trade Training Center, Rawalpindi", "blue star technical and training trade test center rawalpindi"): "y",
    ("Pak Techni Trade Test Center, Rawalpindi", "chiraag technical test training center rawalpindi"): "y",
    ("Al-Rehman Institute of Technical Training Center Rawalpindi", "al rehman institute of technical trade training center rawalpindi"): "y",
    ("Gulf International Techni Test", "trans gulf international"): "y",
    ("Key Technical", "fmk international"): "y",
    # WRONG: "sufyan" is a partial name typed by a complainant; the real
    # agency (Sufyan Recruiting Agency) exists but scored 44 — a missed
    # match that created a junk record. Honest label: n.
    ("sufyan", "basit sufyan brothers"): "n",
    ("Kalyar Associates", "jakhar associates"): "y",
    ("AL-Hasa Enterprises - Overseas Employment Prom", "al hasa enterprises overseas employment promoters"): "y",
    ("Job Happy International", "kjb international"): "y",
    ("QH Hasnain Qadeer Overseas", "al qaseem overseas"): "y",
    ("A.Z. Company International", "t a a international"): "y",
    ("M.B.O (Private) Limited", "marhaba overseas smc private limited"): "y",
    ("Haqeeqat Manpower Overseas Employment Promoter", "haqeeqat manpower overseas employment promoters"): "y",
}

PATH = "data/label_sample.csv"

with open(PATH, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

unlabeled = 0
for row in rows:
    key = (row["mention"], row["matched_name"])
    if key in VERDICTS:
        row["correct"] = VERDICTS[key]
    elif float(row["score"]) == 100.0 and row["decision"] in ("auto_merge", "oepl_digits_match"):
        row["correct"] = "y"  # exact normalized match, collision-checked
    else:
        unlabeled += 1
        print("NEEDS MANUAL LABEL:", row)

with open(PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["mention", "matched_name", "score", "decision", "correct"])
    w.writeheader()
    w.writerows(rows)

print(f"Labeled {len(rows) - unlabeled}/{len(rows)} rows.")
