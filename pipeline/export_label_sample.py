# pipeline/export_label_sample.py
#
# Measures entity-resolution accuracy from hand labels.
#
# Step 1 — export a random sample of merge decisions to label:
#   python pipeline/export_label_sample.py export
#   -> writes data/label_sample.csv with an empty "correct" column.
#      Open it, put y or n in each row ("was this decision right?").
#
# Step 2 — compute accuracy from your labels:
#   python pipeline/export_label_sample.py score
#   -> prints precision for auto-merges and overall accuracy.

import csv
import random
import sys

MERGE_LOG = "data/merge_log.csv"
SAMPLE_PATH = "data/label_sample.csv"
SAMPLE_SIZE = 100


def export():
    with open(MERGE_LOG, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("merge_log.csv is empty — build the database first.")
        return
    sample = random.sample(rows, min(SAMPLE_SIZE, len(rows)))
    with open(SAMPLE_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mention", "matched_name", "score", "decision", "correct"])
        for r in sample:
            w.writerow([r["mention"], r["matched_name"], r["score"],
                        r["decision"], ""])
    print(f"Wrote {len(sample)} decisions to {SAMPLE_PATH}.")
    print('Fill the "correct" column with y or n, then run:')
    print("  python pipeline/export_label_sample.py score")


def score():
    with open(SAMPLE_PATH, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["correct"].strip()]
    if not rows:
        print("No labeled rows found — fill the 'correct' column first.")
        return

    def accuracy(subset):
        if not subset:
            return None
        right = sum(1 for r in subset if r["correct"].strip().lower() == "y")
        return right, len(subset), 100.0 * right / len(subset)

    merges = [r for r in rows if r["decision"] == "auto_merge"]
    overall = accuracy(rows)
    merge_acc = accuracy(merges)

    print(f"Labeled rows: {overall[1]}")
    print(f"Overall decision accuracy: {overall[2]:.1f}% ({overall[0]}/{overall[1]})")
    if merge_acc:
        print(f"Auto-merge precision:      {merge_acc[2]:.1f}% ({merge_acc[0]}/{merge_acc[1]})")
    else:
        print("No auto_merge rows in the sample.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "score":
        score()
    else:
        export()
