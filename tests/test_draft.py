import json
from pathlib import Path

import pytest

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
    biz = draft("ug-business")
    assert biz.warnings == []
    assert biz.program_json["courses"]["BUSA 1000"] == ["major-required"]


def test_bs_dsa_internships_left_out_and_groups_match_reviewed():
    d = draft("ug-bs-dsa")
    assert {"DATA 3396", "DATA 3398"} <= set(d.left_out)
    assert not {"DATA 3396", "DATA 3398"} & set(d.program_json["courses"])
    reviewed = {c: g for c, g in load("bs-dsa")["courses"].items() if g != ["gen-ed-math"]}
    assert d.program_json["courses"] == reviewed


def test_text_only_sections_go_to_left_out_but_skipped_ones_do_not():
    rule = "Select 6 hours from the following prefixes: DS, DATA, STAT."
    page = {"name": "X, M.S.", "sections": [
        {"heading": "Required Courses", "level": 2, "items": [{"kind": "course", "id": "AAA 1000", "title": "A"}]},
        {"heading": "Related Studies (6 Credit Hours)", "level": 2, "items": [{"kind": "text", "text": rule}]},
        {"heading": "Core IMPACTS Curriculum", "level": 2, "items": [{"kind": "text", "text": "skip me"}]},
        {"heading": "Free Electives", "level": 3, "items": [{"kind": "text", "text": "skip me too"}]}]}
    cat = {"AAA 1000": RawCourse("AAA 1000", "A", "3", "", None, None, "")}
    d = draft_program(page, ("ms-x", "MS X"), "graduate", cat)
    assert d.left_out == [f"text: {rule}"]


def C(cid, title="T", prereq=None):
    return RawCourse(cid, title, "3", "", prereq, None, "")


def P(*sections):
    return {"name": "X, B.S.", "sections": [
        {"heading": h, "level": lv, "items": [
            {"kind": "course", "id": i, "title": t} if isinstance(i, str) else i for i, t in
            [(x, "T") if isinstance(x, (str, dict)) else x for x in items]]} for h, lv, items in sections]}


def run(page, cat):
    return draft_program(page, ("bs-x", "BS X"), "undergraduate", cat)


def test_three_warning_kinds_and_empty_page():
    d = run(P(("Odd Stuff", 2, ["AAA 1000"]), ("Major Requirements", 2, ["AAA 2000"])), {"AAA 1000": C("AAA 1000")})
    assert d.warnings == ["unrecognized section 'Odd Stuff'", "AAA 2000 is not in the catalog listings"]
    text_only = P(("Major Requirements", 2, [{"kind": "text", "text": "any course"}]))
    assert run(text_only, {}).warnings == ["no courses found"]


def test_elective_heading_does_not_open_concentration_and_concentration_closes_by_level():
    page = P(("Major Electives or Concentration (15 Credit Hours)", 2, []),
             ("Major Electives", 3, ["AAA 1000"]),
             ("Robotics Track", 3, []),
             ("Required Courses", 4, ["AAA 2000"]),
             ("Capstone", 3, ["AAA 3000"]),
             ("Major Requirements", 2, ["AAA 4000"]))
    d = run(page, {c: C(c) for c in ("AAA 1000", "AAA 2000", "AAA 3000", "AAA 4000")})
    assert d.program_json["courses"] == {"AAA 1000": ["major-elective"], "AAA 2000": ["conc-robotics"],
                                         "AAA 3000": ["major-project"], "AAA 4000": ["major-required"]}
    assert [f["label"] for f in d.program_json["program"]["filters"]] == [
        "Required courses", "Robotics", "Electives", "Project"]


def test_permission_rule_and_no_prereq_text_kept():
    cat = {"AAA 1000": C("AAA 1000", prereq="Permission of the program director."),
           "AAA 2000": C("AAA 2000", prereq=None),
           "AAA 3000": C("AAA 3000", prereq="Consent of instructor and AAA 2000.")}
    d = run(P(("Major Requirements", 2, list(cat))), cat)
    assert d.left_out == ["AAA 1000"] and set(d.program_json["courses"]) == {"AAA 2000", "AAA 3000"}


@pytest.mark.parametrize("text,left_out", [
    # R27: left out only when the text is nothing but permission, consent or approval.
    ("Admission to the MS in Criminal Justice program or permission of the program director", False),
    ("Permission of the instructor.", True),
    ("Permission of instructor and junior standing", False),
    # Real catalog phrasings (2026-27).
    ("Approval of the instructor, program director, and department chair", True),
    ("Permission of the American Studies graduate program director.", True),
    ("Permission of MEBU Director and class instructor", True),
    ("Permission of an advisor, and the instructor.", True),
    ("Department Chair approval", True),
    ("By Instructor’s or Department’s permission.", True),
    ("Approval of instructor and department chair prior to registration.", True),
    ("Permission of department is required.", True),
    ("Audition and permission of the instructor.", False),
    ("Dance Major, or Dance Minor, or permission of instructor", False),
    ("Program Admission or Permission of Director", False),
    ("Junior level status; consent of the instructor and chair.", False),
    ("HS majors or Non-majors with permission of the department", False),
    ("Permission of the professor and admission to the Ed.S. or Ed.D. program.", False),
    ("60+ credit hours; permission of the instructor.", False),
])
def test_permission_only_text_is_left_out_and_any_other_clause_keeps_the_course(text, left_out):
    cat = {"AAA 1000": C("AAA 1000", prereq=text)}
    d = run(P(("Major Requirements", 2, ["AAA 1000"])), cat)
    assert (d.left_out == ["AAA 1000"]) is left_out
    assert ("AAA 1000" in d.program_json["courses"]) is not left_out


def test_left_out_title_rule_uses_word_boundaries_and_page_title():
    items = [("AAA 1000", "Synthesis of Organic Compounds"), ("AAA 2000", "Research Methods in Psychology"),
             ("AAA 3000", "Undergraduate Research"), ("AAA 4000", "Senior Thesis"),
             ("AAA 5000", "Work Internship")]
    cat = {c: C(c, "Calculus") for c, _ in items}  # catalog title is ignored when the page has one
    d = run(P(("Major Requirements", 2, items)), cat)
    assert set(d.program_json["courses"]) == {"AAA 1000", "AAA 2000"}
    assert d.left_out == ["AAA 3000", "AAA 4000", "AAA 5000"]


def test_skipped_heading_skips_its_subtree():
    page = P(("General Education", 2, []), ("Area A", 3, ["AAA 1000"]), ("Major Requirements", 2, ["AAA 2000"]))
    d = run(page, {"AAA 2000": C("AAA 2000")})
    assert d.warnings == [] and set(d.program_json["courses"]) == {"AAA 2000"}


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


def test_identity_slugs_the_degree_part_too():
    assert program_identity("Business Administration, MBA (Evening)", 1, 83) == (
        "mba-evening-business-administration", "MBA (Evening) Business Administration")
