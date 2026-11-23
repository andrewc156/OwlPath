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
