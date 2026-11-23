import json
from pathlib import Path

from owlpath_pipeline import config
from owlpath_pipeline.catalog_html import parse_program_page
from owlpath_pipeline.catalog_pdf import parse_listing
from owlpath_pipeline.draft import (assign_ids, draft_diff, draft_hash, draft_program, program_identity,
                                    write_draft)
from owlpath_pipeline.model import RawCourse

FIX = Path(__file__).parent / "fixtures" / "catalog"
IDENT = {"ug-bs-cs": ("bs-cs", "BS Computer Science"), "ug-bs-dsa": ("bs-dsa", "BS Data Science and Analytics"),
         "grad-ms-dsa": ("ms-dsa", "MS Data Science and Analytics")}


def load(major):
    return json.loads((config.DATA_DIR / major / "program.json").read_text())


def page_of(name):
    return parse_program_page((FIX / f"{name}.html").read_text())


def stub_catalog(page):
    cat = {}
    for f in ("ug-courses-stat", "grad-courses-ds"):
        cat.update(parse_listing((FIX / f"{f}.txt").read_text(), ""))
    for s in page["sections"]:
        for i in s["items"]:
            if i["kind"] == "course" and i["id"] not in cat:
                cat[i["id"]] = RawCourse(i["id"], i["title"], "3", "", None, None, "")
    return cat


def draft(name, level="undergraduate"):
    page = page_of(name)
    ident = IDENT.get(name, (name, name))
    return draft_program(page, ident, level, stub_catalog(page))


def test_bs_cs_draft_matches_reviewed_courses():
    d = draft("ug-bs-cs")
    rename = {"conc-artificial-intelligence": "conc-ai", "conc-cyber-and-network-security": "conc-cyber"}
    reviewed = {c: g for c, g in load("bs-cs")["courses"].items() if g != ["gen-ed-math"]}
    assert {c: [rename.get(x, x) for x in g] for c, g in d.program_json["courses"].items()} == reviewed
    assert {"CS 4491", "CS 4492", "CSE 4983"} <= set(d.left_out) and d.warnings == []
    assert [f["label"] for f in d.program_json["program"]["filters"]] == [
        "Required courses", "Artificial Intelligence", "Data Science", "Cyber and Network Security", "Electives"]


def test_bs_dsa_draft_choices():
    d = draft("ug-bs-dsa")
    assert sorted(map(sorted, d.program_json["choices"])) == sorted(map(sorted, load("bs-dsa")["choices"]))


def test_ms_dsa_draft_groups():
    d = draft("grad-ms-dsa", "graduate")
    assert d.program_json["courses"] == load("ms-dsa")["courses"]


def test_other_majors_draft_cleanly_or_warn():
    for name in ("ug-business", "ug-nursing", "ug-engineering"):
        d = draft(name)
        assert d.program_json["courses"] or d.warnings, name
    assert any("Business Core" in w for w in draft("ug-business").warnings)


def test_unrecognized_section_with_courses_warns():
    page = {"name": "X, B.S.", "sections": [{"heading": "Odd Stuff (3 Credit Hours)", "level": 2,
                                             "items": [{"kind": "course", "id": "AAA 1000", "title": "A"}]}]}
    d = draft_program(page, ("bs-x", "BS X"), "undergraduate", {"AAA 1000": RawCourse("AAA 1000", "A", "3", "", None, None, "")})
    assert "unrecognized section 'Odd Stuff (3 Credit Hours)'" in d.warnings


def test_missing_course_warns_and_page_without_courses_is_held():
    page = {"name": "X, B.S.", "sections": [{"heading": "Major Requirements", "level": 2,
                                             "items": [{"kind": "course", "id": "AAA 1000", "title": "A"}]}]}
    assert draft_program(page, ("bs-x", "BS X"), "undergraduate", {}).warnings == [
        "AAA 1000 is not in the catalog listings"]
    empty = {"name": "X, B.S.", "sections": [{"heading": "Major Requirements", "level": 2,
                                              "items": [{"kind": "text", "text": "any course"}]}]}
    d = draft_program(empty, ("bs-x", "BS X"), "undergraduate", {})
    assert d.warnings == ["no courses found"]


def test_permission_only_courses_are_left_out():
    cat = {"AAA 1000": RawCourse("AAA 1000", "Seminar", "3", "", "Permission of the program director.", None, ""),
           "AAA 2000": RawCourse("AAA 2000", "Basics", "3", "", None, None, ""),
           "AAA 3000": RawCourse("AAA 3000", "Lab Work", "3", "", "AAA 2000 and permission of instructor.", None, "")}
    page = {"name": "X, B.S.", "sections": [{"heading": "Major Requirements", "level": 2, "items": [
        {"kind": "course", "id": c, "title": ""} for c in cat]}]}
    d = draft_program(page, ("bs-x", "BS X"), "undergraduate", cat)
    assert d.left_out == ["AAA 1000"] and set(d.program_json["courses"]) == {"AAA 2000", "AAA 3000"}


def test_identity():
    assert program_identity("Analytics and Data Science, Ph.D.", 1, 83) == (
        "phd-analytics-and-data-science", "PhD Analytics and Data Science")
    assert program_identity("Accounting, BBA", 11863, 84) == ("bba-accounting", "BBA Accounting")


def test_known_ids_kept():
    assert program_identity("Computer Science, B.S.", 11680, 84) == ("bs-cs", "BS Computer Science")


def test_colliding_ids_get_poid_suffix():
    pages = [{"name": "Biology, B.S.", "poid": 501}, {"name": "Biology, B.S.", "poid": 502}]
    assert {i for i, _ in assign_ids(pages, 84).values()} == {"bs-biology-501", "bs-biology-502"}


def test_hand_edited_or_checked_program_is_not_overwritten(tmp_path):
    d = draft("ug-bs-dsa")
    assert write_draft(d, tmp_path) == "written"
    path = tmp_path / "bs-dsa" / "program.json"
    assert write_draft(d, tmp_path) == "written"  # untouched draft is refreshed
    data = json.loads(path.read_text())
    assert data["draftHash"] == draft_hash(data)
    data["choices"] = []
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    assert write_draft(d, tmp_path) == "kept-edited" and path.read_bytes() == before
    data["checked"] = True
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    assert write_draft(d, tmp_path) == "kept-checked" and path.read_bytes() == before


def test_draft_diff():
    assert draft_diff({"courses": {"A 1": [], "B 1": []}}, {"courses": {"B 1": [], "C 1": []}}) == {
        "added": ["C 1"], "removed": ["A 1"]}
