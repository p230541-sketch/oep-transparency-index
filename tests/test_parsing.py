# tests/test_parsing.py
#
# Unit tests for title classification and agency extraction — the messy
# real-world formats documented from beoe.gov.pk, including their
# inconsistencies.
#
# Run from the project root: python -m pytest

from pipeline.parse_notices import classify_title, extract_agencies, normalize_oepl


# ---------------------------------------------------------------------------
# Action taxonomy
# ---------------------------------------------------------------------------

def test_complaint_opened():
    assert classify_title(
        "Complaint against M/s China Manpower Services (OEPL No. 4859/LHR) is under process"
    ) == "complaint_opened"


def test_complaint_closed():
    assert classify_title(
        "Closure of complaint against M/s Shandur Travels (OEPL No. 2974/PWR)"
    ) == "complaint_closed"


def test_show_cause():
    assert classify_title(
        "Show Cause Notice To M/s. Ihtisham Overseas Employment Promoter, OEPL No.2056/RWP"
    ) == "show_cause"


def test_warning():
    assert classify_title(
        "Issuance of warning to M/s FQ Shaheen Manpower (OEPL No. 3951/PWR)"
    ) == "warning"


def test_restoration():
    assert classify_title(
        "Restoration of License M/s. A Z Company International, OEPL No.2765/LHR"
    ) == "restoration"


def test_blacklisting():
    assert classify_title(
        "Blacklisting of M/s. Super Star Trade Test Center, Rawalpindi"
    ) == "blacklisting"


def test_personal_hearing():
    assert classify_title(
        "Personal Hearing Notice To M/s. Taqvi International,OEPL No.3768/RWP"
    ) == "personal_hearing"


def test_suspension():
    assert classify_title(
        "Suspension of Licence of M/s. Johar International,OEPL No.1788/RWP"
    ) == "suspension"


def test_unrecognized_never_crashes():
    assert classify_title("Office timings during Ramzan") == "other"
    assert classify_title("") == "other"


# ---------------------------------------------------------------------------
# OEPL normalization
# ---------------------------------------------------------------------------

def test_oepl_zero_padding():
    assert normalize_oepl("848", "lhr") == "0848/LHR"
    assert normalize_oepl("8", "RWP") == "0008/RWP"
    assert normalize_oepl("2974", "PWR") == "2974/PWR"


# ---------------------------------------------------------------------------
# Agency extraction — the documented format inconsistencies
# ---------------------------------------------------------------------------

def test_parentheses_format():
    out = extract_agencies(
        "Complaint against M/s China Manpower Services (OEPL No. 4859/LHR) is under process")
    assert out == [{"name": "China Manpower Services", "oepl": "4859/LHR"}]


def test_missing_space_after_no():
    out = extract_agencies(
        "Show Cause Notice To M/s. Ihtisham Overseas Employment Promoter, OEPL No.2056/RWP")
    assert out == [{"name": "Ihtisham Overseas Employment Promoter", "oepl": "2056/RWP"}]


def test_stray_period_before_slash():
    # Seen live: "OEPL No.3768./RWP"
    out = extract_agencies(
        "Personal Hearing Notice To M/s. Taqvi International,OEPL No.3768./RWP")
    assert out == [{"name": "Taqvi International", "oepl": "3768/RWP"}]


def test_oep_without_l_spelling():
    # Seen live: "OEP No." instead of "OEPL No." (news-updates/7112)
    out = extract_agencies(
        "Show Cause Notice  To M/s. Johar International,OEP No.1788/RWP")
    assert out == [{"name": "Johar International", "oepl": "1788/RWP"}]


def test_multiple_agencies_ampersand():
    out = extract_agencies(
        "Personal Hearing Notice To M/s. Taqvi International,OEPL No.3768/RWP "
        "& M/s. Al-Hasola International Recruiting Agency,OEPL No.5009/RWP")
    assert out == [
        {"name": "Taqvi International", "oepl": "3768/RWP"},
        {"name": "Al-Hasola International Recruiting Agency", "oepl": "5009/RWP"},
    ]


def test_three_agencies_commas_and_ampersand():
    out = extract_agencies(
        "Personal Hearing Notice To M/s. Pharmic Enterprises, OEPL No.4480/RWP , "
        "M/s. Al Sofi Group Manpower Consultants,OEPL No.4156/RWP & "
        "M/s. Key Technical Services,OEPL No.1111/KAR")
    assert [a["oepl"] for a in out] == ["4480/RWP", "4156/RWP", "1111/KAR"]
    assert out[1]["name"] == "Al Sofi Group Manpower Consultants"


def test_no_license_number():
    # Blacklisted trade test centers have no OEPL — matched by name later.
    out = extract_agencies("Blacklisting of M/s. Super Star Trade Test Center, Rawalpindi")
    assert out == [{"name": "Super Star Trade Test Center, Rawalpindi", "oepl": None}]


def test_no_agency_at_all():
    assert extract_agencies("Office timings during Ramzan") == []
