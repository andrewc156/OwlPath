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


# ---- snapshot drafting ----

def page(poid, name, sections):
    return {"name": name, "poid": poid, "url": f"https://catalog.example/p{poid}", "sections": sections}


def sec(heading, *ids, level=2):
    return {"heading": heading, "level": level,
            "items": [{"kind": "course", "id": i, "title": f"Title {i}"} for i in ids]}


def write_snapshot(data_dir, programs, out_of_scope=()):
    d = data_dir / "catalog" / "undergraduate"
    d.mkdir(parents=True)
    head = {"catalogYear": "2026-2027", "level": "undergraduate", "catoid": 84}
    (d / "programs.json").write_text(json.dumps({**head, "programs": programs,
                                                 "outOfScope": [{"poid": p, "name": n} for p, n in out_of_scope]}))
    (d / "catalog-courses.json").write_text(json.dumps({**head, "courses": {
        c.id: {"title": c.title, "credits": "3", "description": "d", "prereqText": c.prereq_text,
               "coreqText": None, "url": c.url, "warnings": []} for c in CATALOG.values()}}))
    (d / "overrides.json").write_text("{}")


def snap_publish(data_dir):
    return pub.publish(data_dir, source="snapshot")


def test_snapshot_drafts_builds_and_ships_clean_program_as_auto(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000", "CC 3000")])])
    r = by_id(snap_publish(tmp_path))["bs-alpha-studies"]
    spec = json.loads((tmp_path / "bs-alpha-studies" / "program.json").read_text())
    assert spec["draftHash"] and r.state == "auto"
    ds = json.loads((tmp_path / "bs-alpha-studies" / "courses.json").read_text())
    assert ds["checked"] is False
    assert "bs-alpha-studies" in [m["id"] for m in json.loads((tmp_path / "majors.json").read_text())]


def test_snapshot_program_with_draft_warnings_is_held(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Mystery Block", "AA 1000")])])
    r = by_id(snap_publish(tmp_path))["bs-alpha-studies"]
    assert r.state == "held"
    assert not (tmp_path / "bs-alpha-studies" / "courses.json").exists()
    held = (tmp_path / "STATUS.md").read_text().split("## Held majors")[1].split("\n## ")[0]
    assert "bs-alpha-studies" in held


def test_snapshot_keeps_checked_major_and_reports_page_change(tmp_path):
    write_major(tmp_path, "bs-cs", ["AA 1000"], checked=True)
    write_snapshot(tmp_path, [page(11680, "Computer Science, B.S.", [sec("Major Requirements", "AA 1000", "CC 3000")])])
    before = json.loads((tmp_path / "bs-cs" / "program.json").read_text())
    r = by_id(snap_publish(tmp_path))["bs-cs"]
    assert json.loads((tmp_path / "bs-cs" / "program.json").read_text()) == before  # kept-checked
    assert r.state == "checked"
    section = (tmp_path / "STATUS.md").read_text().split("## Checked majors whose catalog page changed")[1] \
        .split("\n## ")[0]
    assert "bs-cs" in section and "CC 3000" in section


def test_snapshot_out_of_scope_programs_are_listed(tmp_path):
    write_snapshot(tmp_path, [], out_of_scope=[(9, "Minor in Basket Weaving")])
    snap_publish(tmp_path)
    section = (tmp_path / "STATUS.md").read_text().split("## Programs left out of scope")[1]
    assert "Minor in Basket Weaving" in section


def test_hand_edited_draft_is_kept_on_rerun(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    path = tmp_path / "bs-alpha-studies" / "program.json"
    spec = json.loads(path.read_text())
    spec["courses"]["CC 3000"] = ["major-required"]
    path.write_text(json.dumps(spec))
    snap_publish(tmp_path)
    assert "CC 3000" in json.loads(path.read_text())["courses"]


def test_pdf_source_does_not_draft(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    pub.publish(tmp_path, get_raw_for=get_raw_for)
    assert not (tmp_path / "bs-alpha-studies").exists()


def test_level_with_programs_but_no_courses_is_skipped_and_noted(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    (tmp_path / "catalog" / "undergraduate" / "catalog-courses.json").unlink()
    snap_publish(tmp_path)
    assert "Skipped undergraduate" in (tmp_path / "STATUS.md").read_text()


def test_fresh_draft_warnings_never_hold_a_checked_major(tmp_path):
    write_major(tmp_path, "bs-cs", ["AA 1000"], checked=True)
    write_snapshot(tmp_path, [page(11680, "Computer Science, B.S.", [sec("Mystery Block", "AA 1000")])])
    assert by_id(snap_publish(tmp_path))["bs-cs"].state == "checked"


def test_malformed_program_json_holds_that_major_and_output_stays_consistent(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000"])
    bad = write_major(tmp_path, "bs-bad", ["AA 1000"])
    (bad / "program.json").write_text("{not json")
    results = by_id(run(tmp_path))
    assert results["bs-bad"].state == "held" and results["bs-bad"].errors
    assert [m["id"] for m in json.loads((tmp_path / "majors.json").read_text())] == ["bs-aa"]
    assert "bs-bad" in (tmp_path / "STATUS.md").read_text()


def test_unreadable_program_json_never_touches_courses_json_and_blocks(tmp_path, capsys):
    d = write_major(tmp_path, "bs-bad", ["AA 1000"], checked=True)
    (d / "courses.json").write_text('{"reviewed": true}\n')
    (d / "program.json").write_text("{not json")
    before = (d / "courses.json").read_bytes()
    assert pub.main(["--data-dir", str(tmp_path)], get_raw_for=get_raw_for) == 1
    assert (d / "courses.json").read_bytes() == before
    held = (tmp_path / "STATUS.md").read_text().split("## Held majors")[1].split("\n## ")[0]
    assert "bs-bad" in held and "program.json unreadable" in held and "BLOCKS PUBLISH" in held
    assert json.loads((tmp_path / "majors.json").read_text()) == []
