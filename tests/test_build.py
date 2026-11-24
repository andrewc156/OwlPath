import pytest

from owlpath_pipeline.build import build_dataset, check_overrides, level_get_raw, load_overrides
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
    pages = Pages(raw("CS 3305", prereq="Dean's waiver"))
    _, warnings = build_dataset({"CS 3305": ["major-required"]}, pages, {}, META)
    assert warnings and all(w.startswith("CS 3305: ") for w in warnings)


def test_override_replaces_prereq_and_clears_that_courses_warnings():
    pages = Pages(raw("CS 3305", prereq="(MTRE 2610 or CPE 3000)"), raw("MATH 2345"))
    program = {"CS 3305": ["major-required"], "MATH 2345": ["core-field"]}
    overrides = {"CS 3305": {"reason": "catalog typo", "prereqs": "MATH 2345"}}
    ds, warnings = build_dataset(program, pages, overrides, META)
    assert course(ds, "CS 3305")["prereqs"] == "MATH 2345"
    assert not any(w.startswith("CS 3305:") for w in warnings)


def test_override_applies_before_closure_and_pulls_required_course():
    ds, _ = build_dataset({"AA 1000": ["major-required"]}, Pages(raw("AA 1000", prereq="junk"), raw("BB 2000")),
                          {"AA 1000": {"reason": "r", "prereqs": "BB 2000"}}, META)
    assert course(ds, "BB 2000")["groups"] == ["prereq-only"] and course(ds, "AA 1000")["prereqs"] == "BB 2000"


def test_shared_override_leaf_is_node_in_one_major_and_text_in_another():
    overrides = {"AA 1000": {"reason": "r", "prereqs": {"or": ["BB 2000", "CC 3000"]}}}
    pages = lambda: Pages(raw("AA 1000"), raw("BB 2000"), raw("CC 3000"))
    x, _ = build_dataset({"AA 1000": ["major-required"], "CC 3000": ["major-required"]}, pages(), overrides, META)
    y, _ = build_dataset({"AA 1000": ["major-required"], "BB 2000": ["major-required"]}, pages(), overrides, META)
    assert course(x, "AA 1000")["prereqs"] == {"or": [{"external": "BB 2000"}, "CC 3000"]}
    assert course(y, "AA 1000")["prereqs"] == {"or": ["BB 2000", {"external": "CC 3000"}]}


def test_notes_only_override_keeps_parsed_prereqs_and_null_clears_them():
    pages = Pages(raw("AA 1000", prereq="BB 2000"), raw("BB 2000"), raw("CC 3000", prereq="BB 2000"))
    ds, _ = build_dataset({"AA 1000": ["major-required"], "CC 3000": ["major-required"]}, pages,
                          {"AA 1000": {"reason": "r", "notes": ["n"]}, "CC 3000": {"reason": "r", "prereqs": None}}, META)
    assert course(ds, "AA 1000")["prereqs"] == "BB 2000" and course(ds, "AA 1000")["notes"] == ["n"]
    assert course(ds, "CC 3000")["prereqs"] is None


def test_override_with_external_leaf_is_error():
    with pytest.raises(ValueError, match="external"):
        check_overrides({"AA 1000": {"reason": "r", "prereqs": {"or": ["BB 2000", {"external": "CC 3000"}]}}}, {"AA 1000"})


def test_override_for_course_missing_from_catalog_is_error():
    with pytest.raises(ValueError, match="stale override"):
        check_overrides({"CS 9999": {"reason": "x", "prereqs": None}}, {"CS 3305"})
    with pytest.raises(ValueError, match="stale override"):
        build_dataset({"CS 3305": ["major-required"]}, Pages(raw("CS 3305")), {"CS 9999": {"reason": "x", "prereqs": None}}, META)


def _write_snapshot(data_dir, level, ids):
    import json
    d = data_dir / "catalog" / level
    d.mkdir(parents=True)
    (d / "catalog-courses.json").write_text(json.dumps({"courses": {
        i: {"title": i, "credits": "3", "description": "", "prereqText": None, "coreqText": None, "url": "u", "warnings": []}
        for i in ids}}))


def test_course_missing_from_own_level_is_found_in_other_level(tmp_path, monkeypatch):
    from owlpath_pipeline import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _write_snapshot(tmp_path, "undergraduate", ["MATH 1113"])
    _write_snapshot(tmp_path, "graduate", ["DS 7020"])
    get = level_get_raw("graduate", source="snapshot")
    assert get("DS 7020").id == "DS 7020" and get("MATH 1113").id == "MATH 1113"
    with pytest.raises(KeyError):
        get("ZZ 0000")


def test_own_level_overrides_win_over_other_level(tmp_path):
    import json
    for level, reason in (("undergraduate", "u"), ("graduate", "g")):
        d = tmp_path / "catalog" / level
        d.mkdir(parents=True, exist_ok=True)
        (d / "overrides.json").write_text(json.dumps({"AA 1000": {"reason": reason}, **({"BB 2000": {"reason": "b"}} if level == "undergraduate" else {})}))
    merged = load_overrides("graduate", tmp_path)
    assert merged["AA 1000"]["reason"] == "g" and merged["BB 2000"]["reason"] == "b"


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
    (d / "program.json").write_text(json.dumps({**META, "catalogYear": "2026-2027", "level": "undergraduate", "courses": courses}))
    return d


def test_cli_keeps_reviewed_dataset_when_warnings_remain(tmp_path, monkeypatch):
    from owlpath_pipeline import build

    d = _program_dir(tmp_path, monkeypatch, {"CS 3305": ["major-required"]})

    def missing(cid):
        raise KeyError(cid)

    monkeypatch.setattr(build, "level_get_raw", lambda level, source="snapshot", data_dir=None: missing)
    assert build.main(["bs-cs"]) == 1
    assert not (d / "courses.json").exists() and (d / "build-report.md").exists()
    assert build.main(["bs-cs", "--draft"]) == 0
    assert (d / "courses.json").exists()


def test_meta_is_copied_to_output():
    pages = Pages(raw("CS 3305"))
    ds, _ = build_dataset({"CS 3305": ["major-required"]}, pages, {}, META)
    assert ds["program"] == META["program"] and ds["choices"] == META["choices"] and ds["lessCommon"] == []
    ds, _ = build_dataset({"CS 3305": ["major-required"]}, pages, {}, {**META, "lessCommon": ["CS 3305"]})
    assert ds["lessCommon"] == ["CS 3305"]


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


@pytest.mark.parametrize("major", ["bs-cs", "bs-dsa", "ms-dsa"])
def test_checked_majors_rebuild_unchanged_from_snapshot(major):
    """Pins the reviewed datasets: the committed snapshot + shared overrides rebuild exactly the committed courses.json."""
    import json
    from owlpath_pipeline import config
    from owlpath_pipeline.build import build_major

    folder = config.program_dir(major)
    _, dataset, warnings, errors, _ = build_major(folder)
    assert warnings == [] and errors == []
    assert dataset == json.loads((folder / "courses.json").read_text())


def test_cli_requires_a_catalog_level(tmp_path, monkeypatch):
    import json

    from owlpath_pipeline import build

    d = _program_dir(tmp_path, monkeypatch, {"CS 3305": ["major-required"]})
    spec = json.loads((d / "program.json").read_text())
    del spec["level"]
    (d / "program.json").write_text(json.dumps(spec))
    with pytest.raises(SystemExit, match="level"):
        build.main(["bs-cs"])


def test_source_names_the_catalog_level():
    from owlpath_pipeline.build import source

    assert source("undergraduate").startswith("KSU Undergraduate Catalog 2026-2027")
    assert "catoid=84" in source("undergraduate")


def test_catalog_levels_have_their_own_folders():
    from owlpath_pipeline import config

    assert config.catalog_pdf_dir("undergraduate") == config.DATA_DIR / "catalog" / "undergraduate"
    assert (config.DATA_DIR / "catalog" / "graduate").is_dir()
    assert config.catalog_pdf_dir("graduate") == config.DATA_DIR / "catalog" / "graduate"
    assert config.catoid("graduate") == 83 and config.catoid("undergraduate") == 84
    with pytest.raises(ValueError, match="unknown catalog level"):
        config.catoid("doctoral")


def test_auto_major_pulls_first_or_option_onto_map():
    notes = []
    ds, w = build_dataset({"AA 1000": ["major-required"]},
                          Pages(raw("AA 1000", prereq="BB 2000 or CC 3000"), raw("BB 2000"), raw("CC 3000")),
                          {}, META, auto=True, notes_out=notes)
    assert w == [] and course(ds, "BB 2000")["groups"] == ["prereq-only"]
    assert course(ds, "AA 1000")["prereqs"] == {"or": ["BB 2000", {"external": "CC 3000"}]} and notes


def test_checked_major_keeps_no_option_warning():
    pages = Pages(raw("AA 1000", prereq="BB 2000 or CC 3000"), raw("BB 2000"), raw("CC 3000"))
    ds, w = build_dataset({"AA 1000": ["major-required"]}, pages, {}, META)
    assert any("no in-program alternative" in x for x in w) and ids(ds) == ["AA 1000"]


def test_permission_alternative_is_not_an_option_on_the_map():
    pages = Pages(raw("AA 1000", prereq="BB 2000 or CC 3000 or permission of the instructor"),
                  raw("BB 2000"), raw("CC 3000"))
    ds, w = build_dataset({"AA 1000": ["major-required"]}, pages, {}, META, auto=True)
    assert w == [] and ids(ds) == ["AA 1000", "BB 2000"]
    assert course(ds, "AA 1000")["notes"] == ["permission of the instructor"]


def test_cli_uses_auto_for_unchecked_and_holds_on_draft_warnings(tmp_path, monkeypatch):
    import json

    from owlpath_pipeline import build

    d = _program_dir(tmp_path, monkeypatch, {"CS 3305": ["major-required"]})
    pages = Pages(raw("CS 3305", prereq="MATH 1111 or MATH 2222"), raw("MATH 1111"), raw("MATH 2222"))
    monkeypatch.setattr(build, "level_get_raw", lambda level, source="snapshot", data_dir=None: pages)
    assert build.main(["bs-cs"]) == 0  # auto pulls an option in instead of warning
    assert "MATH 1111" in (d / "courses.json").read_text()
    spec = json.loads((d / "program.json").read_text())
    (d / "program.json").write_text(json.dumps({**spec, "draftWarnings": ["unrecognized section 'X'"]}))
    (d / "courses.json").unlink()
    assert build.main(["bs-cs"]) == 1 and not (d / "courses.json").exists()
