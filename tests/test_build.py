import pytest

from owlpath_pipeline.build import build_dataset
from owlpath_pipeline.model import RawCourse
from owlpath_pipeline.validate import validate_dataset


def raw(id, prereq=None, coreq=None, title=None, description="desc"):
    return RawCourse(id=id, title=title or f"Title {id}", credits="3", description=description,
                     prereq_text=prereq, coreq_text=coreq, url=f"https://catalog.example/{id.replace(' ', '')}")


class Pages:
    """Fake get_raw: serves RawCourse by id and records what was requested."""

    def __init__(self, *courses):
        self.by_id = {c.id: c for c in courses}
        self.requested = []

    def __call__(self, id):
        self.requested.append(id)
        return self.by_id[id]


def ids(dataset):
    return [c["id"] for c in dataset["courses"]]


def course(dataset, id):
    return next(c for c in dataset["courses"] if c["id"] == id)


def test_required_prereq_outside_program_is_added_as_prereq_only():
    pages = Pages(raw("CS 3305", prereq="MATH 2345"), raw("MATH 2345"))
    ds, _ = build_dataset({"CS 3305": ["major-required"]}, pages, {})
    assert course(ds, "MATH 2345")["groups"] == ["prereq-only"]
    assert course(ds, "CS 3305")["prereqs"] == "MATH 2345"


def test_or_alternative_outside_program_becomes_external():
    pages = Pages(raw("CS 3305", prereq="(MATH 2345 or CSE 2300)"), raw("MATH 2345"))
    ds, _ = build_dataset({"CS 3305": ["major-required"], "MATH 2345": ["core-field"]}, pages, {})
    assert course(ds, "CS 3305")["prereqs"] == {"or": ["MATH 2345", {"external": "CSE 2300"}]}
    assert "CSE 2300" not in pages.requested


def test_or_with_no_in_program_alternative_warns():
    pages = Pages(raw("CS 3305", prereq="(MTRE 2610 or CPE 3000)"))
    _, warnings = build_dataset({"CS 3305": ["major-required"]}, pages, {})
    assert any(w.startswith("CS 3305:") and "no in-program alternative" in w for w in warnings)


def test_parser_warnings_are_prefixed_with_course_id():
    pages = Pages(raw("CS 3305", prereq="Approval of the dean"))
    _, warnings = build_dataset({"CS 3305": ["major-required"]}, pages, {})
    assert warnings and all(w.startswith("CS 3305: ") for w in warnings)


def test_override_replaces_prereq_and_clears_that_courses_warnings():
    pages = Pages(raw("CS 3305", prereq="(MTRE 2610 or CPE 3000)"), raw("MATH 2345"))
    program = {"CS 3305": ["major-required"], "MATH 2345": ["core-field"]}
    overrides = {"CS 3305": {"reason": "catalog typo", "prereqs": "MATH 2345"}}
    ds, warnings = build_dataset(program, pages, overrides)
    assert course(ds, "CS 3305")["prereqs"] == "MATH 2345"
    assert not any(w.startswith("CS 3305:") for w in warnings)


def test_override_for_course_not_in_graph_is_error():
    pages = Pages(raw("CS 3305"))
    with pytest.raises(ValueError, match="CS 9999"):
        build_dataset({"CS 3305": ["major-required"]}, pages, {"CS 9999": {"reason": "x", "prereqs": None}})


def test_override_without_reason_is_error():
    pages = Pages(raw("CS 3305"))
    with pytest.raises(ValueError, match="reason"):
        build_dataset({"CS 3305": ["major-required"]}, pages, {"CS 3305": {"prereqs": None}})


def test_output_is_sorted_and_valid():
    pages = Pages(raw("MATH 2345"), raw("CS 3305", prereq="MATH 2345"), raw("CSE 1321", coreq="CSE 1321L"),
                  raw("CSE 1321L", coreq="CSE 1321"))
    program = {"CS 3305": ["major-required"], "CSE 1321": ["core-field"], "CSE 1321L": ["core-field"]}
    ds, _ = build_dataset(program, pages, {})
    assert ids(ds) == sorted(ids(ds))
    assert validate_dataset(ds) == []


def test_notes_description_catalog_year_and_url_carried_through():
    pages = Pages(raw("MATH 1190", prereq="MATH 1113, or By Placement", description="Calculus I."), raw("MATH 1113"))
    ds, _ = build_dataset({"MATH 1190": ["gen-ed-math"], "MATH 1113": ["gen-ed-math"]}, pages, {})
    c = course(ds, "MATH 1190")
    assert c["notes"] == ["By Placement"] and c["description"] == "Calculus I."
    assert c["catalogYear"] == "2026-2027" and c["catalogUrl"] == "https://catalog.example/MATH1190"


def test_output_uses_short_form_leaves():
    pages = Pages(raw("CS 3305", prereq='MATH 2345 and CSE 1322 with a "B" or better and (CSE 1322L or CPE 3000)'),
                  raw("MATH 2345"), raw("CSE 1322"), raw("CSE 1322L"))
    ds, _ = build_dataset({"CS 3305": ["major-required"], "CSE 1322L": ["core-field"]}, pages, {})
    assert course(ds, "CS 3305")["prereqs"] == {"and": [
        "MATH 2345", {"course": "CSE 1322", "minGrade": "B"}, {"or": ["CSE 1322L", {"external": "CPE 3000"}]}]}


def test_cli_keeps_reviewed_dataset_when_warnings_remain(tmp_path, monkeypatch):
    import json
    from owlpath_pipeline import build, config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    (tmp_path / "program.json").write_text(json.dumps({"courses": {"CS 3305": ["major-required"]}}))
    (tmp_path / "overrides.json").write_text("{}")

    def missing(cid):
        raise KeyError(cid)

    monkeypatch.setattr(build, "catalog_get_raw", lambda: missing)
    assert build.main([]) == 1
    assert not (tmp_path / "courses.json").exists() and (tmp_path / "build-report.md").exists()
    assert build.main(["--draft"]) == 0
    assert (tmp_path / "courses.json").exists()
