# pipeline/entity_resolution.py
#
# Matches agency mentions from notices to canonical agency records.
#
# Identity rules:
#   1. An OEPL number is the primary key — exact match wins instantly.
#   2. Name-only mentions are fuzzy-matched (rapidfuzz token_sort_ratio)
#      against every canonical name + known variant:
#        score >= 92  -> auto-merge (and remember the variant)
#        80..91       -> goes to data/review_queue.csv for a human decision
#        < 80         -> create a new agency record
#   3. Every merge decision is logged with its score to data/merge_log.csv
#      so accuracy can be measured later on a hand-labeled sample.
#
# Imported by build_db.py.

import csv
import re

from rapidfuzz import fuzz

AUTO_MERGE_SCORE = 92
REVIEW_SCORE = 80

MERGE_LOG_PATH = "data/merge_log.csv"
REVIEW_QUEUE_PATH = "data/review_queue.csv"


def normalize_name(name: str) -> str:
    """Lowercase, drop M/s prefixes and punctuation, collapse whitespace."""
    n = name.lower()
    n = re.sub(r"\bm/s\.?\s*", "", n)
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


class Resolver:
    """
    Holds the in-memory index of known agencies and resolves mentions.

    self.by_oepl: {"0848/LHR": agency_id}
    self.names:   [(normalized_name, agency_id), ...]  (canonical + variants)
    """

    def __init__(self):
        self.by_oepl = {}
        self.names = []
        self.merge_log = []   # (mention, matched_name, score, decision)
        self.review_queue = []

    def register(self, agency_id: int, canonical_name: str, oepl: str | None):
        if oepl:
            self.by_oepl[oepl] = agency_id
        self.names.append((normalize_name(canonical_name), agency_id))

    def add_variant(self, agency_id: int, variant: str):
        norm = normalize_name(variant)
        if not any(n == norm and aid == agency_id for n, aid in self.names):
            self.names.append((norm, agency_id))

    def best_name_match(self, mention: str):
        """Returns (agency_id, matched_norm_name, score) for the best fuzzy hit."""
        norm = normalize_name(mention)
        best = (None, None, 0.0)
        for known_norm, agency_id in self.names:
            score = fuzz.token_sort_ratio(norm, known_norm)
            if score > best[2]:
                best = (agency_id, known_norm, score)
        return best

    def resolve(self, name: str, oepl: str | None, create_agency):
        """
        Resolve one mention to an agency_id.

        `create_agency(name, oepl)` is a callback that inserts a new agency
        row and returns its id — the resolver itself never touches the DB.
        """
        # Rule 1: OEPL number is authoritative.
        if oepl and oepl in self.by_oepl:
            agency_id = self.by_oepl[oepl]
            self.add_variant(agency_id, name)
            return agency_id
        if oepl:
            # Known number format but agency not seeded (lapsed licence etc.)
            agency_id = create_agency(name, oepl)
            self.register(agency_id, name, oepl)
            return agency_id

        # Rule 1b: some complaint forms put the licence NUMBER in the name
        # field ("4584"). If exactly one known agency has those digits,
        # that's an unambiguous identity.
        if re.fullmatch(r"\d{1,4}", name.strip()):
            digits = f"{int(name):04d}"
            hits = [aid for known, aid in self.by_oepl.items()
                    if known.split("/")[0] == digits]
            if len(hits) == 1:
                self.merge_log.append((name, digits, 100.0, "oepl_digits_match"))
                return hits[0]

        # Rule 2: fuzzy name matching.
        agency_id, matched, score = self.best_name_match(name)
        if agency_id is not None and score >= AUTO_MERGE_SCORE:
            self.merge_log.append((name, matched, round(score, 1), "auto_merge"))
            self.add_variant(agency_id, name)
            return agency_id
        if agency_id is not None and score >= REVIEW_SCORE:
            self.review_queue.append((name, matched, round(score, 1)))
            self.merge_log.append((name, matched, round(score, 1), "review_queue_new_record"))
            # Until a human approves the merge, keep records separate.
        else:
            self.merge_log.append((name, matched or "", round(score, 1), "new_record"))

        new_id = create_agency(name, None)
        self.register(new_id, name, None)
        return new_id

    def write_logs(self):
        with open(MERGE_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["mention", "matched_name", "score", "decision"])
            w.writerows(self.merge_log)
        with open(REVIEW_QUEUE_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["mention", "candidate_match", "score"])
            w.writerows(self.review_queue)
