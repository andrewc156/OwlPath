import json

from owlpath_pipeline import publish as pub
from owlpath_pipeline.draft import draft_hash
from owlpath_pipeline.model import RawCourse


def raw(id, prereq=None):
    return RawCourse(id=id, title=f"Title {id}", credits="3", description="desc", prereq_text=prereq,
                     coreq_text=None, url=f"https://catalog.kennesaw.edu/{id.replace(' ', '')}")


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


def section(data_dir, title):
    return (data_dir / "STATUS.md").read_text().split(f"\n## {title}\n")[1].split("\n## ")[0]


def test_status_ranks_courses_holding_two_or_more_majors_with_their_warning_text(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000", "ZZ 9999X"])
    write_major(tmp_path, "bs-bb", ["AA 1000", "ZZ 9999X", "YY 1"])
    run(tmp_path)
    ranked = section(tmp_path, "Courses holding the most majors")
    assert "- **ZZ 9999X**: 2 majors (bs-aa, bs-bb)\n  - course page not found ('ZZ 9999X')" in ranked
    assert "YY 1" not in ranked  # holds one major only


def test_held_majors_list_build_warnings_by_course_drafting_warnings_and_errors(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000", "NOPE 1"], extra={"draftWarnings": ["unrecognized section 'X'"]})
    write_major(tmp_path, "bs-bb", ["AA 1000"], extra={"choices": [["AA 1000", "ZZ 0"]]})
    run(tmp_path)
    held = section(tmp_path, "Held majors")
    assert ("### bs-aa (undergraduate)\n\n- Build warnings:\n  - **NOPE 1**\n    - course page not found ('NOPE 1')\n"
            "- Drafting warnings:\n  - unrecognized section 'X'") in held
    assert "### bs-bb (undergraduate)\n\n- Errors:\n  - build failed: ValueError: choices: ZZ 0" in held


def test_status_has_sections_in_order(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000"])
    run(tmp_path)
    status = (tmp_path / "STATUS.md").read_text()
    heads = [l for l in status.splitlines() if l.startswith("## ")]
    assert heads == ["## Summary", "## Held majors", "## Courses holding the most majors",
                     "## Checked majors changed by this build", "## Checked majors whose catalog page changed",
                     "## Edited drafts whose catalog page changed", "## Checked majors missing from the catalog",
                     "## Retired drafts", "## Fixes (shared overrides)", "## Programs left out of scope"]


def test_checked_major_change_is_never_written_without_the_users_ok(tmp_path, capsys):
    d = write_major(tmp_path, "bs-aa", ["AA 1000"], checked=True)
    auto = write_major(tmp_path, "bs-bb", ["AA 1000"])
    run(tmp_path)
    old = json.loads((d / "courses.json").read_text())
    old["courses"][0]["title"] = "Old title"
    (d / "courses.json").write_text(json.dumps(old, sort_keys=True, indent=2) + "\n")
    before = (d / "courses.json").read_bytes()
    for _ in range(2):  # the change keeps being reported, run after run
        (auto / "courses.json").unlink()
        assert pub.main(["--data-dir", str(tmp_path)], get_raw_for=get_raw_for) == 1
        assert (d / "courses.json").read_bytes() == before
        assert "rerun with --accept-checked bs-aa" in capsys.readouterr().out
        changed = section(tmp_path, "Checked majors changed by this build")
        assert "not written: needs the user's OK, then rerun with --accept-checked bs-aa" in changed
        assert "Old title" in changed and "Title AA 1000" in changed
        assert (auto / "courses.json").exists()  # everything else is still written
    assert pub.main(["--data-dir", str(tmp_path), "--accept-checked", "bs-aa"], get_raw_for=get_raw_for) == 0
    assert json.loads((d / "courses.json").read_text())["courses"][0]["title"] == "Title AA 1000"
    assert "written (--accept-checked)" in section(tmp_path, "Checked majors changed by this build")
    assert pub.main(["--data-dir", str(tmp_path)], get_raw_for=get_raw_for) == 0
    assert section(tmp_path, "Checked majors changed by this build").strip() == "None."


def test_status_lists_every_shared_override_with_its_reason_and_the_majors_it_touches(tmp_path):
    write_major(tmp_path, "bs-aa", ["AA 1000"])
    write_major(tmp_path, "bs-bb", ["CC 3000"])
    write_major(tmp_path, "ms-zz", ["AA 1000"], level="graduate")
    for level, fixes in (("undergraduate", {"AA 1000": {"reason": "Catalog typo.", "notes": []},
                                            "BB 2000": {"reason": "Unused here.", "notes": []}}),
                         ("graduate", {"CC 3000": {"reason": "Graduate fix.", "notes": []}})):
        (tmp_path / "catalog" / level).mkdir(parents=True)
        (tmp_path / "catalog" / level / "overrides.json").write_text(json.dumps(fixes))
    run(tmp_path)
    fixes = section(tmp_path, "Fixes (shared overrides)")
    assert ("### graduate\n\n- **CC 3000**: Graduate fix. (majors: bs-bb)\n\n### undergraduate\n\n"
            "- **AA 1000**: Catalog typo. (majors: bs-aa, ms-zz)\n- **BB 2000**: Unused here. (majors: none)") in fixes


def test_from_pdfs_refuses_when_a_level_in_use_has_no_listing_pdfs(tmp_path, capsys):
    d = write_major(tmp_path, "bs-aa", ["AA 1000"])
    (d / "courses.json").write_text("{}")
    (tmp_path / "catalog" / "undergraduate").mkdir(parents=True)
    assert pub.main(["--data-dir", str(tmp_path), "--from-pdfs"]) == 2
    err = capsys.readouterr().err
    assert len(err.splitlines()) == 1 and str(tmp_path / "catalog" / "undergraduate") in err
    assert (d / "courses.json").read_text() == "{}" and not (tmp_path / "STATUS.md").exists()


def test_from_pdfs_reads_the_listing_pdfs_in_the_data_folder(tmp_path):
    import shutil
    from pathlib import Path

    write_major(tmp_path, "bs-aa", ["CS 3305"])
    (tmp_path / "catalog" / "undergraduate").mkdir(parents=True)
    shutil.copy(Path(__file__).parent / "fixtures" / "pdf" / "cs.pdf", tmp_path / "catalog" / "undergraduate")
    assert pub.main(["--data-dir", str(tmp_path), "--from-pdfs"]) == 0
    report = (tmp_path / "bs-aa" / "build-report.md").read_text()
    # CS 3305 was read from the PDF: its options (MATH, CSE) are in no saved listing, so its prerequisites warn.
    assert "course page not found ('CS 3305')" not in report and "no in-program alternative" in report


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
    return {"name": name, "poid": poid, "url": f"https://catalog.kennesaw.edu/p{poid}", "sections": sections}


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
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "QQ 4040")])])
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
    pub.publish(tmp_path, "pdf", get_raw_for)
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


def _page_change_section(tmp_path):
    return (tmp_path / "STATUS.md").read_text().split("## Checked majors whose catalog page changed")[1] \
        .split("\n## ")[0]


def test_checked_page_diff_ignores_courses_listed_only_as_gen_ed_math(tmp_path):
    write_major(tmp_path, "bs-cs", ["AA 1000"], checked=True)
    path = tmp_path / "bs-cs" / "program.json"
    spec = json.loads(path.read_text())
    spec["courses"]["BB 2000"] = ["gen-ed-math"]
    path.write_text(json.dumps(spec))
    write_snapshot(tmp_path, [page(11680, "Computer Science, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    assert "bs-cs" not in _page_change_section(tmp_path)


def test_checked_page_diff_still_reports_real_removals_and_shared_gen_ed_courses(tmp_path):
    write_major(tmp_path, "bs-cs", ["AA 1000", "CC 3000"], checked=True)
    path = tmp_path / "bs-cs" / "program.json"
    spec = json.loads(path.read_text())
    spec["courses"]["BB 2000"] = ["gen-ed-math", "major-required"]
    path.write_text(json.dumps(spec))
    write_snapshot(tmp_path, [page(11680, "Computer Science, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    section = _page_change_section(tmp_path)
    assert "bs-cs" in section and "CC 3000" in section and "BB 2000" in section


# ---- retiring drafts and edited-draft page changes ----

def set_programs(data_dir, programs, level="undergraduate"):
    """Replace a level's programs.json (the snapshot's program pages) between publish runs."""
    path = data_dir / "catalog" / level / "programs.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "programs": programs}))


def test_draft_records_catoid_and_poid(tmp_path):
    write_snapshot(tmp_path, [page(7, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    spec = json.loads((tmp_path / "bs-alpha-studies" / "program.json").read_text())
    assert (spec["catoid"], spec["poid"]) == (84, 7)


def test_renamed_program_retires_the_old_untouched_draft(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    set_programs(tmp_path, [page(1, "Beta Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    results = by_id(snap_publish(tmp_path))
    assert not (tmp_path / "bs-alpha-studies").exists() and "bs-alpha-studies" not in results
    assert results["bs-beta-studies"].state == "auto"
    assert [m["id"] for m in json.loads((tmp_path / "majors.json").read_text())] == ["bs-beta-studies"]
    retired = section(tmp_path, "Retired drafts")
    assert "**bs-alpha-studies** (undergraduate): folder deleted" in retired and "bs-beta-studies" in retired


def test_untouched_draft_without_a_recorded_program_is_retired(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    legacy = {"catalogYear": "2026-2027", "level": "undergraduate", "program": {"id": "bs-old", "name": "BS Old",
              "filters": []}, "choices": [], "courses": {"AA 1000": ["major-required"]}, "draftWarnings": []}
    (tmp_path / "bs-old").mkdir()
    (tmp_path / "bs-old" / "program.json").write_text(json.dumps({**legacy, "draftHash": draft_hash(legacy)}))
    snap_publish(tmp_path)
    assert not (tmp_path / "bs-old").exists()
    assert "**bs-old** (undergraduate): folder deleted" in section(tmp_path, "Retired drafts")


def test_edited_draft_no_longer_drafted_is_held_and_never_deleted(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    folder = tmp_path / "bs-alpha-studies"
    spec = json.loads((folder / "program.json").read_text())
    spec["courses"]["CC 3000"] = ["major-required"]
    (folder / "program.json").write_text(json.dumps(spec))
    edited = (folder / "program.json").read_bytes()
    set_programs(tmp_path, [])  # the program left the catalog
    r = by_id(snap_publish(tmp_path))["bs-alpha-studies"]
    assert r.state == "held" and (folder / "program.json").read_bytes() == edited
    assert not (folder / "courses.json").exists()
    assert "bs-alpha-studies" not in (tmp_path / "majors.json").read_text()
    assert "**bs-alpha-studies** (undergraduate): held" in section(tmp_path, "Retired drafts")
    assert "### bs-alpha-studies (undergraduate)" in section(tmp_path, "Held majors")


def test_checked_major_missing_from_the_catalog_is_reported_and_still_builds(tmp_path):
    write_major(tmp_path, "bs-cs", ["AA 1000"], checked=True)
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    r = by_id(snap_publish(tmp_path))["bs-cs"]
    assert r.state == "checked" and (tmp_path / "bs-cs" / "courses.json").exists()
    assert "**bs-cs** (undergraduate): catoid 84, poid 11680" in section(tmp_path, "Checked majors missing from the catalog")


def test_skipped_level_and_pdf_builds_retire_nothing(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    set_programs(tmp_path, [])
    pub.publish(tmp_path, "pdf", get_raw_for)
    (tmp_path / "catalog" / "undergraduate" / "catalog-courses.json").unlink()
    snap_publish(tmp_path)
    assert (tmp_path / "bs-alpha-studies" / "program.json").exists()


def test_edited_draft_page_change_is_reported(tmp_path):
    write_snapshot(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000")])])
    snap_publish(tmp_path)
    path = tmp_path / "bs-alpha-studies" / "program.json"
    spec = json.loads(path.read_text())
    spec["courses"]["BB 2000"] = ["major-required"]
    path.write_text(json.dumps(spec))
    set_programs(tmp_path, [page(1, "Alpha Studies, B.S.", [sec("Major Requirements", "AA 1000", "CC 3000")])])
    snap_publish(tmp_path)
    assert "- **bs-alpha-studies**: added CC 3000; removed BB 2000" in section(
        tmp_path, "Edited drafts whose catalog page changed")
    assert "bs-alpha-studies" not in section(tmp_path, "Checked majors whose catalog page changed")
