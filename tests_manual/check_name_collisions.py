# tests_manual/check_name_collisions.py
#
# Do any two DIFFERENT licensed agencies share the same normalized name?
# If yes, a 100-score name merge could still be wrong and labels must be
# checked harder. Run: python tests_manual/check_name_collisions.py

import sqlite3
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pipeline.entity_resolution import normalize_name

con = sqlite3.connect("data/db.sqlite3")
names = [(normalize_name(n), oepl) for n, oepl in
         con.execute("SELECT canonical_name, oepl_number FROM agencies WHERE oepl_number IS NOT NULL")]
counts = Counter(n for n, _ in names)
dupes = {n for n, c in counts.items() if c > 1}
if dupes:
    for n, oepl in sorted(names):
        if n in dupes:
            print(f"COLLISION: {n!r} -> {oepl}")
else:
    print("No normalized-name collisions among licensed agencies.")
