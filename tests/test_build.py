import pytest

from owlpath_pipeline.build import build_dataset
from owlpath_pipeline.model import RawCourse
from owlpath_pipeline.validate import validate_dataset

META = {"program": {"id": "bs-cs", "name": "BS Computer Science",
                    "filters": [{"label": "AI", "groups": ["conc-ai"]}]}, "choices": []}


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
    ds, _ = build_dataset({"CS 3305": ["major-required"]}, pages, {}, META)
    assert course(ds, "MATH 2345")["groups"] == ["prereq-only"]
    assert course(ds, "CS 3305")["prereqs"] == "MATH 2345"


def test_or_alternative_outside_program_becomes_external():
    pages = Pages(raw("CS 3305", prereq="(MATH 2345 or CSE 2300)"), raw("MATH 2345"))
    ds, _ = build_dataset({"CS 3305": ["major-required"], "MATH 2345": ["core-field"]}, pages, {}, META)
    assert course(ds, "CS 3305")["prereqs"] == {"or": ["MATH 2345", {"external": "CSE 2300"}]}
    assert "CSE 2300" not in pages.requested


def test_or_with_no_in_program_alternative_warns():
    pages = Pages(raw("CS 3305", prereq="(MTRE 2610 or CPE 3000)"))
    _, warnings = build_dataset({"CS 3305": ["major-required"]}, pages, {}, META)
    assert any(w.startswith("CS 3305:") and "no in-program alternative" in w for w in warnings)


def test_parser_warnings_are_prefixed_with_course_id():
    pages = Pages(raw("CS 3305", prereq="Approval of the dean"))
    _, warnings = build_dataset({"CS 3305": ["major-required"]}, pages, {}, META)
    assert warnings and all(w.startswith("CS 3305: ") for w in warnings)


def test_override_replaces_prereq_and_clears_that_courses_warnings():
    pages = Pages(raw("CS 3305", prereq="(MTRE 2610 or CPE 3000)"), raw("MATH 2345"))
    program = {"CS 3305": ["major-required"], "MATH 2345": ["core-field"]}
    overrides = {"CS 3305": {"reason": "catalog typo", "prereqs": "MATH 2345"}}
    ds, warnings = build_dataset(program, pages, overrides, META)
    assert course(ds, "CS 3305")["prereqs"] == "MATH 2345"
    assert not any(w.startswith("CS 3305:") for w in warnings)


def test_override_for_course_not_in_graph_is_error():
    pages = Pages(raw("CS 3305"))
    with pytest.raises(ValueError, match="CS 9999"):
        build_dataset({"CS 3305": ["major-required"]}, pages, {"CS 9999": {"reason": "x", "prereqs": None}}, META)


def test_override_without_reason_is_error():
    pages = Pages(raw("CS 3305"))
    with pytest.raises(ValueError, match="reason"):
        build_dataset({"CS 3305": ["major-required"]}, pages, {"CS 3305": {"prereqs": None}}, META)


def test_output_is_sorted_and_valid():
    pages = Pages(raw("MATH 2345"), raw("CS 3305", prereq="MATH 2345"), raw("CSE 1321", coreq="CSE 1321L"),
                  raw("CSE 1321L", coreq="CSE 1321"))
    program = {"CS 3305": ["major-required"], "CSE 1321": ["core-field"], "CSE 1321L": ["core-field"]}
    ds, _ = build_dataset(program, pages, {}, META)
    assert ids(ds) == sorted(ids(ds))
    assert validate_dataset(ds) == []


def test_notes_description_catalog_year_and_url_carried_through():
    pages = Pages(raw("MATH 1190", prereq="MATH 1113, or By Placement", description="Calculus I."), raw("MATH 1113"))
    ds, _ = build_dataset({"MATH 1190": ["gen-ed-math"], "MATH 1113": ["gen-ed-math"]}, pages, {}, META)
    c = course(ds, "MATH 1190")
    assert c["notes"] == ["By Placement"] and c["description"] == "Calculus I."
    assert c["catalogYear"] == "2026-2027" and c["catalogUrl"] == "https://catalog.example/MATH1190"


def test_output_uses_short_form_leaves():
    pages = Pages(raw("CS 3305", prereq='MATH 2345 and CSE 1322 with a "B" or better and (CSE 1322L or CPE 3000)'),
                  raw("MATH 2345"), raw("CSE 1322"), raw("CSE 1322L"))
    ds, _ = build_dataset({"CS 3305": ["major-required"], "CSE 1322L": ["core-field"]}, pages, {}, META)
    assert course(ds, "CS 3305")["prereqs"] == {"and": [
        "MATH 2345", {"course": "CSE 1322", "minGrade": "B"}, {"or": ["CSE 1322L", {"external": "CPE 3000"}]}]}


def _program_dir(tmp_path, monkeypatch, courses):
    import json
    from owlpath_pipeline import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    d = tmp_path / "bs-cs"
    d.mkdir()
    (d / "program.json").write_text(json.dumps({**META, "catalogYear": "2026-2027", "courses": courses}))
    (d / "overrides.json").write_text("{}")
    return d


def test_cli_keeps_reviewed_dataset_when_warnings_remain(tmp_path, monkeypatch):
    from owlpath_pipeline import build

    d = _program_dir(tmp_path, monkeypatch, {"CS 3305": ["major-required"]})

    def missing(cid):
        raise KeyError(cid)

    monkeypatch.setattr(build, "catalog_get_raw", lambda: missing)
    assert build.main(["bs-cs"]) == 1
    assert not (d / "courses.json").exists() and (d / "build-report.md").exists()
    assert build.main(["bs-cs", "--draft"]) == 0
    assert (d / "courses.json").exists()


def test_meta_is_copied_to_output():
    pages = Pages(raw("CS 3305"))
    ds, _ = build_dataset({"CS 3305": ["major-required"]}, pages, {}, META)
    assert ds["program"] == META["program"] and ds["choices"] == META["choices"]


def test_choice_not_in_program_is_error():
    pages = Pages(raw("CS 3305"))
    with pytest.raises(ValueError, match="ZZZ 9999"):
        build_dataset({"CS 3305": ["major-required"]}, pages, {},
                      {**META, "choices": [["CS 3305", "ZZZ 9999"]]})


def test_cli_rejects_unknown_program():
    from owlpath_pipeline import build

    with pytest.raises(SystemExit) as e:
        build.main(["bs-ee"])
    assert e.value.code == 2


def test_cs_dataset_courses_unchanged_after_move():
    """Pins the reviewed CS dataset: an in-memory rebuild from bs-cs/ must equal the committed file."""
    import json
    from owlpath_pipeline import config
    from owlpath_pipeline.build import catalog_get_raw

    d = config.program_dir("bs-cs")
    prog = json.loads((d / "program.json").read_text())
    built, warnings = build_dataset(prog["courses"], catalog_get_raw(), json.loads((d / "overrides.json").read_text()),
                                    {"program": prog["program"], "choices": prog["choices"]})
    assert warnings == [] and built == json.loads((d / "courses.json").read_text())
