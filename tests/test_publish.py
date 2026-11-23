import json

from owlpath_pipeline import publish as pub
from owlpath_pipeline.model import RawCourse


def raw(id, prereq=None):
    return RawCourse(id=id, title=f"Title {id}", credits="3", description="desc", prereq_text=prereq,
                     coreq_text=None, url=f"https://catalog.example/{id.replace(' ', '')}")


CATALOG = {c.id: c for c in [raw("AA 1000"), raw("ZZ 9999", prereq="AA 1000 or BB 2000"), raw("BB 2000"),
                             raw("CC 3000")]}


def get_raw_for(level):
    return CATALOG.__getitem__


def write_major(data_dir, mid, courses, *, checked=False, name=None, level="undergraduate", extra=None):
    spec = {"catalogYear": "2026-2027", "level": level, "checked": checked,
            "program": {"id": mid, "name": name or mid, "filters": [{"label": "All", "groups": ["major-required"]}]},
            "choices": [], "courses": {c: ["major-required"] for c in courses}, **(extra or {})}
    d = data_dir / mid
    d.mkdir(parents=True, exist_ok=True)
    (d / "program.json").write_text(json.dumps(spec))
    return d


def run(data_dir):
    return pub.publish(data_dir, get_raw_for=get_raw_for)


def by_id(results):
    return {r.id: r for r in results}


def test_clean_unchecked_major_ships_as_auto(tmp_path):
    d = write_major(tmp_path, "bs-aa", ["ZZ 9999"])  # AA 1000 or BB 2000: neither on the map, so one is pulled in
    r = by_id(run(tmp_path))["bs-aa"]
    assert r.state == "auto", r.warnings
    assert json.loads((d / "courses.json").read_text())["checked"] is False
    assert [m["id"] for m in json.loads((tmp_path / "majors.json").read_text())] == ["bs-aa"]
    assert "## Notes" in (d / "build-report.md").read_text()


def test_major_with_warnings_is_held_and_old_courses_json_removed(tmp_path):
    d = write_major(tmp_path, "bs-aa", ["AA 1000", "NOPE 1"])  # NOPE 1 is not in the catalog
    (d / "courses.json").write_text("{}")
    r = by_id(run(tmp_path))["bs-aa"]
    assert r.state == "held" and r.warnings
    assert not (d / "courses.json").exists()
    assert "NOPE 1" in (d / "build-report.md").read_text()


def test_major_with_draft_warnings_is_held(tmp_path):
    d = write_major(tmp_path, "bs-aa", ["AA 1000"], extra={"draftWarnings": ["unrecognized section 'X'"],
                                                           "leftOut": ["text: pick a minor"]})
    r = by_id(run(tmp_path))["bs-aa"]
    assert r.state == "held"
    assert not (d / "courses.json").exists()
    report = (d / "build-report.md").read_text()
    assert "## Drafting warnings" in report and "unrecognized section 'X'" in report
    assert "## Left out on purpose" in report and "pick a minor" in report


def test_left_out_alone_does_not_hold(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000"], extra={"leftOut": ["CS 4000"]})
    assert by_id(run(tmp_path))["bs-aa"].state == "auto"


def test_broken_checked_major_fails_publish(tmp_path):
    d = write_major(tmp_path, "bs-aa", ["AA 1000", "NOPE 1"], checked=True)
    (d / "courses.json").write_text('{"keep": "me"}\n')
    before = (d / "courses.json").read_bytes()
    assert pub.main(["--data-dir", str(tmp_path)], get_raw_for=get_raw_for) == 1
    assert (d / "courses.json").read_bytes() == before


def test_status_ranks_courses_by_majors_held(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000", "ZZ 9999X"])
    write_major(tmp_path, "bs-bb", ["AA 1000", "ZZ 9999X", "YY 1"])
    run(tmp_path)
    status = (tmp_path / "STATUS.md").read_text()
    section = status.split("## Courses holding the most majors")[1].split("\n## ")[0]
    assert section.index("ZZ 9999X") < section.index("YY 1")
    assert "2 majors" in section


def test_status_has_sections_in_order(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000"])
    run(tmp_path)
    status = (tmp_path / "STATUS.md").read_text()
    heads = [l for l in status.splitlines() if l.startswith("## ")]
    assert heads == ["## Summary", "## Held majors", "## Courses holding the most majors",
                     "## Checked majors changed by this build", "## Checked majors whose catalog page changed",
                     "## Programs left out of scope"]


def test_checked_major_change_is_listed_with_before_and_after(tmp_path, capsys):
    d = write_major(tmp_path, "bs-aa", ["AA 1000"], checked=True)
    run(tmp_path)
    old = json.loads((d / "courses.json").read_text())
    old["courses"][0]["title"] = "Old title"
    (d / "courses.json").write_text(json.dumps(old, sort_keys=True, indent=2) + "\n")
    assert pub.main(["--data-dir", str(tmp_path)], get_raw_for=get_raw_for) == 0
    assert "checked majors changed: bs-aa" in capsys.readouterr().out
    section = (tmp_path / "STATUS.md").read_text().split("## Checked majors changed by this build")[1] \
        .split("\n## ")[0]
    assert "AA 1000" in section and "Old title" in section and "Title AA 1000" in section
    assert by_id(run(tmp_path))["bs-aa"].state == "checked"


def test_majors_index_lists_only_shipped_majors(tmp_path):
    write_major(tmp_path, "ms-zz", ["CC 3000"], name="Zeta", level="graduate", checked=True)
    write_major(tmp_path, "bs-bb", ["AA 1000"], name="Beta")
    write_major(tmp_path, "bs-aa", ["AA 1000"], name="Alpha")
    write_major(tmp_path, "bs-held", ["NOPE 1"], name="Held")
    run(tmp_path)
    assert json.loads((tmp_path / "majors.json").read_text()) == [
        {"id": "ms-zz", "name": "Zeta", "level": "graduate", "checked": True},
        {"id": "bs-aa", "name": "Alpha", "level": "undergraduate", "checked": False},
        {"id": "bs-bb", "name": "Beta", "level": "undergraduate", "checked": False}]
