from pathlib import Path

import pytest

from owlpath_pipeline.catalog_html import (
    ProgramRef,
    course_coids,
    in_scope,
    listing_page_count,
    parse_nav,
    parse_prefixes,
    parse_program_index,
    parse_program_page,
)
from owlpath_pipeline.catalog_pdf import parse_listing

FIXTURES = Path(__file__).parent / "fixtures" / "catalog"


def fx(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_nav_has_courses_and_programs():
    assert {"Courses": 9372, "Academic Programs": 9371}.items() <= parse_nav(fx("ug-bs-cs.html")).items()


def test_prefixes():
    p = parse_prefixes(fx("ug-courses-stat.html"))
    assert len(p) == 154 and {"STAT", "CSE", "MATH"} <= set(p)
    assert p == sorted(p) and "-1" not in p and "" not in p


def test_page_count_default_and_paginated():
    assert listing_page_count(fx("ug-courses-stat.html")) == 1
    html = '<a href="content.php?filter%5Bcpage%5D=2">2</a><a href="content.php?filter%5Bcpage%5D=3">3</a>'
    assert listing_page_count(html) == 3
    assert listing_page_count("<p>none</p>") == 1


def test_coids_from_listing_and_program():
    assert course_coids(fx("ug-courses-stat.html"))["STAT 1401"] == 135058
    assert course_coids(fx("ug-bs-cs.html"))["CSE 1321"] == 136675


def test_program_index():
    refs = set(parse_program_index(fx("ug-programs-index.html")))
    assert {ProgramRef("Computer Science, B.S.", 11680, "College of Computing and Software Engineering"),
            ProgramRef("Data Science and Analytics, B.S.", 11867, "College of Computing and Software Engineering")} <= refs
    elementary = next(r for r in refs if r.name == "Elementary Education, B.S.")
    assert elementary.college == "Clarice C. and Leland Bagwell College of Education"
    grad = {r.name: r.college for r in parse_program_index(fx("grad-programs-index.html"))}
    assert grad["Data Science and Analytics, M.S."] == "College of Computing and Software Engineering"


@pytest.mark.parametrize(
    "name,ok",
    [
        ("Computer Science, B.S.", True),
        ("Accounting, B.B.A.", True),
        ("Accounting, BBA", True),
        ("Nursing, BSN", True),
        ("Mechanical Engineering, B.S.", True),
        ("Data Science and Analytics, M.S.", True),
        ("Analytics and Data Science, Ph.D.", True),
        ("Educational Leadership, Ed.S.", True),
        ("Computer Science Minor", False),
        ("Data Science and Analytics Minor", False),
        ("Cybersecurity Certificate", False),
        ("Graduate Certificate in Data Science", False),
        ("Teaching, Endorsement", False),
    ],
)
def test_in_scope(name, ok):
    assert in_scope(name) is ok


def test_in_scope_on_index_fixture_has_undotted_examples():
    names = {r.name for r in parse_program_index(fx("ug-programs-index.html"))}
    assert {"Accounting, BBA", "Nursing, BSN"} <= names
    assert in_scope("Accounting, BBA") and in_scope("Nursing, BSN")


def test_bs_cs_program_page():
    p = parse_program_page(fx("ug-bs-cs.html"))
    s = {x["heading"]: x for x in p["sections"]}
    assert p["name"] == "Computer Science, B.S."
    assert [i["id"] for i in s["Core Field of Study (18 Credit Hours)"]["items"]][:4] == [
        "CSE 1321", "CSE 1321L", "CSE 1322", "CSE 1322L"]
    ai = s["Artificial Intelligence Concentration"]
    assert ai["level"] == 3 and ai["items"] == []


def test_bs_dsa_or_items():
    kinds = [(i["kind"], i.get("id")) for sec in parse_program_page(fx("ug-bs-dsa.html"))["sections"]
             for i in sec["items"]]
    at = kinds.index(("course", "CSE 2300"))
    assert kinds[at + 1] == ("or", None) and kinds[at + 2] == ("course", "MATH 2345")


def test_text_items_and_titles():
    secs = parse_program_page(fx("ug-bs-dsa.html"))["sections"]
    items = [i for s in secs for i in s["items"]]
    assert {"kind": "course", "id": "MATH 2202", "title": "Calculus II"} in items
    assert any(i["kind"] == "text" and i["text"].startswith("One (1) credit hour") for i in items)


def test_stat_listing_text_parses():
    c = parse_listing(fx("ug-courses-stat.txt"), "")
    assert len(c) == 10 and c["STAT 3120"].prereq_text == "STAT 1401 or DATA 1501 or STAT 2332 or MATH 3332"
    assert all(not x.warnings for x in c.values())
