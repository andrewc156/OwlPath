from pathlib import Path

from owlpath_pipeline.banner import Discrepancy, diff_course, parse_banner_prereqs

FIXTURES = Path(__file__).parent / "fixtures" / "banner"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_banner_extracts_grades():
    grades = parse_banner_prereqs(read("cse-1322.html"))
    assert grades["CSE 1321"] == "C"   # catalog says B: the known disagreement
    assert set(grades) == {"CSE 1321", "CSE 1321L", "CSE 1322L", "MATH 1113", "MATH 1190", "MATH 1179", "MATH 2202"}


def test_known_cse1322_grade_disagreement_is_reported():
    course = {"id": "CSE 1322", "prereqs": {"and": [{"course": "CSE 1321", "minGrade": "B"}, {"course": "CSE 1321L", "minGrade": "B"}]}}
    d = diff_course(course, {"CSE 1321": "C", "CSE 1321L": "B"})
    assert d == [Discrepancy("CSE 1322", "CSE 1321", "B", "C")]


def test_reference_missing_from_one_side():
    d = diff_course({"id": "CS 3305", "prereqs": "MATH 2345"}, {"CSE 2300": "C"})
    assert set((x.ref, x.catalog_grade, x.banner_grade) for x in d) == {("MATH 2345", "C", None), ("CSE 2300", None, "C")}


def test_matching_sources_have_no_discrepancies():
    course = {"id": "CS 3305", "prereqs": {"or": ["MATH 2345", {"external": "CSE 2300"}]}}
    assert diff_course(course, {"MATH 2345": "C", "CSE 2300": "C"}) == []


def test_corequisites_count_because_banner_merges_them_into_prerequisites():
    # Seen on the real CSE 1322 page: Banner lists CSE 1322L and the MATH options under "Prerequisites".
    course = {"id": "CSE 1322", "prereqs": "CSE 1321", "coreqs": {"and": ["CSE 1322L", {"or": ["MATH 1113", {"external": "MATH 1179"}]}]}}
    banner = {"CSE 1321": "C", "CSE 1322L": "C", "MATH 1113": "C", "MATH 1179": "C"}
    assert diff_course(course, banner) == []
