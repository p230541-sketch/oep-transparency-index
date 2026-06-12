# tests/test_resolution.py
#
# Unit tests for entity resolution: identity rules, thresholds, and the
# decision log.
#
# Run from the project root: python -m pytest

from pipeline.entity_resolution import Resolver, normalize_name


def make_factory():
    """A fake create_agency callback that hands out sequential IDs."""
    created = []

    def create(name, oepl):
        created.append((name, oepl))
        return len(created)  # 1-based fake agency_id

    return create, created


def test_normalize_strips_ms_prefix_and_punctuation():
    assert normalize_name("M/s. Shandur Travels") == "shandur travels"
    assert normalize_name("M/s Shandur   Travels.") == "shandur travels"
    assert normalize_name("SHANDUR-TRAVELS") == "shandur travels"


def test_oepl_number_is_authoritative():
    r = Resolver()
    create, created = make_factory()
    r.register(42, "Shandur Travels", "2974/PWR")
    # Same number, wildly different spelling -> still the same agency.
    assert r.resolve("Shandoor Travel Agency", "2974/PWR", create) == 42
    assert created == []  # nothing new created


def test_unknown_oepl_creates_record_with_number():
    r = Resolver()
    create, created = make_factory()
    aid = r.resolve("Lapsed Agency", "1234/QTA", create)
    assert aid == 1
    assert created == [("Lapsed Agency", "1234/QTA")]
    # ...and is found by number next time.
    assert r.resolve("Lapsed Agency (different spelling)", "1234/QTA", create) == 1


def test_high_score_auto_merges():
    r = Resolver()
    create, created = make_factory()
    r.register(7, "Shandur Travels", "2974/PWR")
    aid = r.resolve("M/s. Shandur Travels", None, create)  # normalizes identically
    assert aid == 7
    assert created == []
    assert r.merge_log[-1][3] == "auto_merge"


def test_borderline_score_goes_to_review_not_merge():
    r = Resolver()
    create, created = make_factory()
    r.register(7, "Pharmic Enterprises", "4480/RWP")
    # Similar but NOT the same agency — must stay separate.
    aid = r.resolve("Harmain Enterprises", None, create)
    assert aid != 7
    assert len(created) == 1
    assert len(r.review_queue) == 1


def test_low_score_is_silent_new_record():
    r = Resolver()
    create, created = make_factory()
    r.register(7, "Shandur Travels", "2974/PWR")
    aid = r.resolve("Completely Different Name Ltd", None, create)
    assert aid != 7
    assert r.review_queue == []
    assert r.merge_log[-1][3] == "new_record"


def test_digits_only_name_matches_unique_licence():
    # Seen live (complaints/results/9468): the complainant typed the licence
    # number "4584" into the agency-name field.
    r = Resolver()
    create, created = make_factory()
    r.register(3, "Future 4 U Services", "4584/RWP")
    assert r.resolve("4584", None, create) == 3
    assert created == []
    assert r.merge_log[-1][3] == "oepl_digits_match"


def test_digits_only_name_ambiguous_stays_new():
    # Same digits in two regions -> ambiguous, must NOT guess.
    r = Resolver()
    create, created = make_factory()
    r.register(101, "Agency A", "1234/RWP")
    r.register(202, "Agency B", "1234/LHR")
    aid = r.resolve("1234", None, create)
    assert aid not in (101, 202)
    assert len(created) == 1


def test_variant_learned_from_oepl_match_helps_later():
    # The bug we actually hit: a news title carries the OEPL number and a
    # name spelling; a later complaint page has ONLY that spelling.
    r = Resolver()
    create, created = make_factory()
    r.register(9, "Pharmic Enterprize (Pvt) Limited", "4480/RWP")
    r.resolve("Pharmic Enterprises", "4480/RWP", create)   # learns variant
    aid = r.resolve("Pharmic Enterprises", None, create)   # name-only mention
    assert aid == 9
    assert created == []
