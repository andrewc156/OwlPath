"""Draft, build and sort every major; write each courses.json and build-report.md, majors.json and STATUS.md.

A major is "checked" (program.json has "checked": true, a person reviewed it), "auto" (unchecked, built cleanly:
published and labeled not yet checked) or "held" (draft warnings, build warnings or validation errors: nothing
shipped). A checked major that cannot build makes the CLI exit 1 and keeps its committed courses.json. A checked
major whose clean build differs from its courses.json is never written without the user's OK: STATUS shows the
before and after, the CLI exits 1, and `--accept-checked <id>` writes it.

Drafting refreshes every untouched draft from the snapshot. An untouched draft folder that no in-scope program
drafted to this run (renamed, removed, re-slugged) is retired: deleted, since it is generated and git keeps it.
An edited draft in that case is held instead, and its folder is never deleted.

CLI: .venv/bin/python -m owlpath_pipeline.publish [--from-pdfs] [--accept-checked <id> ...]
     (default: the committed catalog snapshot)
"""
import argparse
import json
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .build import build_major, major_report
from .draft import assign_ids, draft_diff, draft_hash, draft_program, write_draft
from .model import RawCourse

GetRaw = Callable[[str], RawCourse]


@dataclass
class MajorResult:
    id: str
    name: str
    level: str
    state: str  # "checked", "auto" or "held"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    draft_warnings: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)  # course ids that differ from the committed courses.json
    accepted: bool = False  # a checked major's change was written because of --accept-checked
    unreadable: bool = False  # program.json couldn't be read: its courses.json is never touched, and it blocks
    checked: bool = False  # reviewed by a person; a checked major can be "held" when its build fails
    college: str = config.OTHER_COLLEGE  # the picker's college group
    orphaned: str = ""  # an edited draft that no program drafted to this run: why (it is held)
    courses: set[str] = field(default_factory=set)  # course ids of this run's build


@dataclass
class Drafting:
    """What drafting the snapshot found. Empty when nothing was drafted (--from-pdfs, no snapshot)."""
    out_of_scope: dict[str, list[str]] = field(default_factory=dict)  # level -> program names left out
    page_changes: dict[str, dict] = field(default_factory=dict)  # checked major id -> added/removed courses
    edited_changes: dict[str, dict] = field(default_factory=dict)  # edited draft id -> added/removed courses
    skipped: list[str] = field(default_factory=list)  # levels with programs.json but no catalog-courses.json
    drafted: dict[str, dict[int, str]] = field(default_factory=dict)  # level -> {poid: id drafted this run}


@dataclass
class Retirement:
    retired: list[tuple[str, str, str]] = field(default_factory=list)  # (id, level, why): folder deleted
    orphaned: dict[str, tuple[str, str]] = field(default_factory=dict)  # id -> (level, why): edited, held
    missing_checked: list[tuple[str, str, str]] = field(default_factory=list)  # (id, level, why)


def _colleges(data_dir: Path) -> dict[tuple[int, int], str]:
    """(catoid, poid) -> the picker's college name, from each level's snapshot programs.json."""
    out: dict[tuple[int, int], str] = {}
    for level in config.CATALOGS:
        f = data_dir / "catalog" / level / "programs.json"
        if f.exists():
            snap = json.loads(f.read_text(encoding="utf-8"))
            for p in snap.get("programs", []):
                out[(snap.get("catoid", config.catoid(level)), p["poid"])] = config.college_name(p.get("college", ""))
    return out


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def _page_diff(old: dict, fresh: dict) -> dict:
    """Courses a fresh draft adds or drops against a kept program.json. The drafter skips general education by
    design, so a course the program.json lists only as gen-ed-math is not a page change."""
    courses = {c: g for c, g in old.get("courses", {}).items() if set(g) != {"gen-ed-math"}}
    return draft_diff({**old, "courses": courses}, fresh)


def _draft_levels(data_dir: Path) -> Drafting:
    """Draft every in-scope program of each level with a snapshot."""
    from .snapshot import load_courses, load_programs

    out = Drafting()
    for level in config.CATALOGS:
        programs_file = data_dir / "catalog" / level / "programs.json"
        if not programs_file.exists():
            continue
        if not (data_dir / "catalog" / level / "catalog-courses.json").exists():
            out.skipped.append(level)
            continue
        pages = load_programs(level, data_dir)
        catalog = load_courses(level, data_dir)
        idents = assign_ids(pages, config.catoid(level))
        out.drafted[level] = {}
        for page in pages:
            draft = draft_program(page, idents[page["poid"]], level, catalog)
            mid = draft.program_json["program"]["id"]
            out.drafted[level][page["poid"]] = mid
            path = data_dir / mid / "program.json"
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            kept = write_draft(draft, data_dir)
            if kept in ("kept-checked", "kept-edited") and old:
                diff = _page_diff(old, draft.program_json)
                if diff["added"] or diff["removed"]:
                    (out.page_changes if kept == "kept-checked" else out.edited_changes)[mid] = diff
        out.out_of_scope[level] = [p["name"] for p in
                                   json.loads(programs_file.read_text(encoding="utf-8")).get("outOfScope", [])]
    return out


def _retire_drafts(data_dir: Path, drafting: Drafting) -> Retirement:
    """Compare each major folder of a level drafted this run with that run's drafts: retire an untouched draft no
    program drafted to, hold an edited one, and report a checked major whose program the catalog no longer has."""
    out = Retirement()
    drafted_ids = {mid for ids in drafting.drafted.values() for mid in ids.values()}
    known = {mid: key for key, mid in config.KNOWN_PROGRAM_IDS.items()}
    for mid in config.programs(data_dir):
        try:
            spec = json.loads((data_dir / mid / "program.json").read_text(encoding="utf-8"))
            level = spec["level"]
        except Exception:
            continue  # unreadable: the build loop reports it and touches nothing
        if level not in drafting.drafted:
            continue  # no snapshot of this level was drafted this run: nothing to compare with
        catoid, poid = spec.get("catoid"), spec.get("poid")
        if spec.get("checked") and (catoid is None or poid is None):
            catoid, poid = known.get(mid, (None, None))
        if catoid is None or poid is None:
            why = "no catalog program recorded (catoid, poid)"
        elif catoid != config.catoid(level) or poid not in drafting.drafted[level]:
            why = f"catoid {catoid}, poid {poid} is not among the {level} catalog's programs in scope"
        elif drafting.drafted[level][poid] != mid:
            why = f"catoid {catoid}, poid {poid} is now drafted as {drafting.drafted[level][poid]}"
        else:
            continue  # drafted this run: in the catalog
        if spec.get("checked"):
            out.missing_checked.append((mid, level, why))
        elif mid in drafted_ids:
            continue  # another program drafts to this folder now: it was refreshed this run
        elif spec.get("draftHash") is not None and spec.get("draftHash") == draft_hash(spec):
            shutil.rmtree(data_dir / mid)
            out.retired.append((mid, level, why))
        else:
            out.orphaned[mid] = (level, why)
    return out


def _course_changes(old: dict, new: dict) -> dict[str, tuple[dict | None, dict | None]]:
    """{course id: (before, after)} for every course added, removed or different. Metadata differences
    (program, choices, ...) are reported under the id "(program data)"."""
    a, b = {c["id"]: c for c in old.get("courses", [])}, {c["id"]: c for c in new.get("courses", [])}
    changes = {cid: (a.get(cid), b.get(cid)) for cid in sorted(set(a) | set(b)) if a.get(cid) != b.get(cid)}
    meta_old = {k: v for k, v in old.items() if k not in ("courses", "checked")}
    meta_new = {k: v for k, v in new.items() if k not in ("courses", "checked")}
    if meta_old != meta_new:
        changes["(program data)"] = (meta_old, meta_new)
    return changes


def _read_overrides(data_dir: Path) -> tuple[dict[str, dict], dict[str, str]]:
    """Each level's shared overrides.json, and the levels whose file can't be read (with why)."""
    found, broken = {}, {}
    for level in config.CATALOGS:
        path = data_dir / "catalog" / level / "overrides.json"
        if path.exists():
            try:
                found[level] = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as e:
                broken[level] = f"{type(e).__name__}: {e}"
    return found, broken


def publish(data_dir: Path = config.DATA_DIR, source: str = "snapshot",
            get_raw_for: Callable[[str], GetRaw] | None = None,
            accept_checked: set[str] | frozenset[str] = frozenset()) -> list[MajorResult]:
    """get_raw_for(level) overrides how courses are looked up (tests); default is level_get_raw(level, source).
    accept_checked: checked majors whose changed build the user approved, so it is written."""
    data_dir = Path(data_dir)
    # PDF builds never draft (they build the program folders that already exist), so they never retire either.
    drafting = _draft_levels(data_dir) if source == "snapshot" else Drafting()
    retirement = _retire_drafts(data_dir, drafting)

    colleges = _colleges(data_dir)
    known = {mid: key for key, mid in config.KNOWN_PROGRAM_IDS.items()}
    results: list[MajorResult] = []
    details: dict[str, dict] = {}  # changed checked majors: id -> {course id: (before, after)}
    for mid in config.programs(data_dir):
        folder = data_dir / mid
        result = MajorResult(mid, mid, "unknown", "held")
        notes: list[str] = []
        left_out: list[str] = []
        dataset = None
        try:
            spec = json.loads((folder / "program.json").read_text(encoding="utf-8"))
            result.checked = bool(spec.get("checked"))
            result.name, result.level = spec["program"]["name"], spec["level"]
            key = (spec["catoid"], spec["poid"]) if "poid" in spec and "catoid" in spec else known.get(mid)
            result.college = colleges.get(key, config.OTHER_COLLEGE)
            result.draft_warnings, left_out = list(spec.get("draftWarnings", [])), spec.get("leftOut", [])
        except Exception as e:  # can't tell whether the major was checked: touch nothing, block the publish
            result.unreadable = True
            result.errors = [f"program.json unreadable: {type(e).__name__}: {e}"]
        result.orphaned = retirement.orphaned.get(mid, ("", ""))[1]
        if not result.unreadable:
            try:
                _, dataset, result.warnings, result.errors, notes = build_major(folder, source, data_dir, get_raw_for)
                result.courses = {c["id"] for c in dataset["courses"]}
            except Exception as e:  # one bad major must not stop the others or leave the index stale
                dataset, result.errors = None, [f"build failed: {type(e).__name__}: {e}"]
        courses_file = folder / "courses.json"
        if (dataset and not result.errors and not result.warnings and not result.draft_warnings
                and not result.orphaned):
            result.state = "checked" if result.checked else "auto"
            changes = (_course_changes(json.loads(courses_file.read_text()), dataset)
                       if result.checked and courses_file.exists() else {})
            if changes:  # a reviewed file changes only with the user's OK
                result.changed, details[mid] = list(changes), changes
                result.accepted = mid in accept_checked
            if not changes or result.accepted:
                _write_json(courses_file, dataset)
        elif not result.checked and not result.unreadable:
            courses_file.unlink(missing_ok=True)
        if not result.unreadable:
            report_drafting = result.draft_warnings + (
                [f"no longer drafted from the catalog: {result.orphaned}"] if result.orphaned else [])
            (folder / "build-report.md").write_text(
                major_report(result.warnings, result.errors, notes, report_drafting, left_out))
        results.append(result)

    shipped = [r for r in results if r.state != "held" or (r.checked and (data_dir / r.id / "courses.json").exists())]
    shipped.sort(key=lambda r: (r.level, r.name))
    _write_json(data_dir / "majors.json", [{"id": r.id, "name": r.name, "level": r.level, "checked": r.checked,
                                            "college": r.college} for r in shipped])
    (data_dir / "STATUS.md").write_text(_status(results, details, drafting, retirement, *_read_overrides(data_dir)))
    return results


def _short(value) -> str:
    return "(absent)" if value is None else json.dumps(value, sort_keys=True)


def _by_course(warnings: list[str]) -> dict[str, list[str]]:
    """Build warnings ("<course id>: <message>") grouped by course, in first-seen order."""
    grouped: dict[str, list[str]] = {}
    for w in warnings:
        cid, _, msg = w.partition(": ")
        grouped.setdefault(cid, []).append(msg)
    return grouped


def _trim(lines: list[str]) -> list[str]:
    while lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _status(results: list[MajorResult], details: dict, drafting: Drafting, retirement: Retirement,
            overrides: dict[str, dict], broken_overrides: dict[str, str]) -> str:
    sections: list[tuple[str, list[str]]] = []
    by_id = {r.id: r for r in results}

    summary = ["| Level | Checked | Auto | Held |", "|---|---|---|---|"]
    for lv in sorted({r.level for r in results}):
        counts = [sum(1 for r in results if r.level == lv and r.state == s) for s in ("checked", "auto", "held")]
        summary.append(f"| {lv} | " + " | ".join(map(str, counts)) + " |")
    sections.append(("Summary", summary))

    held = sorted((r for r in results if r.state == "held"), key=lambda r: (r.level, r.name))
    body: list[str] = []
    for r in held:
        body += [f"### {r.id} ({r.level}){' [BLOCKS PUBLISH]' if r.checked or r.unreadable else ''}", ""]
        if r.orphaned:
            body.append(f"- No longer drafted from the catalog: {r.orphaned}")
        if r.errors:
            body += ["- Errors:", *[f"  - {e}" for e in r.errors]]
        if r.warnings:
            body.append("- Build warnings:")
            for cid, msgs in _by_course(r.warnings).items():
                body += [f"  - **{cid}**", *[f"    - {m}" for m in msgs if m]]
        if r.draft_warnings:
            body += ["- Drafting warnings:", *[f"  - {w}" for w in r.draft_warnings]]
        body.append("")
    sections.append(("Held majors", _trim(body) or ["None."]))

    by_course: dict[str, dict[str, list[str]]] = {}  # course id -> {held major id: its warnings for that course}
    for r in held:
        for cid, msgs in _by_course(r.warnings).items():
            by_course.setdefault(cid, {})[r.id] = msgs
    body = []
    for cid, majors in sorted(((c, m) for c, m in by_course.items() if len(m) >= 2),
                              key=lambda kv: (-len(kv[1]), kv[0])):
        body.append(f"- **{cid}**: {len(majors)} majors ({', '.join(sorted(majors))})")
        body += [f"  - {m}" for m in dict.fromkeys(m for mid in sorted(majors) for m in majors[mid] if m)]
    sections.append(("Courses holding the most majors", body or ["None."]))

    body = []
    for mid, changes in sorted(details.items()):
        note = ("written (--accept-checked)" if by_id[mid].accepted
                else f"not written: needs the user's OK, then rerun with --accept-checked {mid}")
        body += [f"### {mid}", "", note, ""]
        for cid, (before, after) in changes.items():
            body += [f"- **{cid}**", f"  - before: `{_short(before)}`", f"  - after: `{_short(after)}`"]
        body.append("")
    sections.append(("Checked majors changed by this build", _trim(body) or ["None."]))

    for title, diffs in (("Checked majors whose catalog page changed", drafting.page_changes),
                         ("Edited drafts whose catalog page changed", drafting.edited_changes)):
        sections.append((title, [f"- **{mid}**: added {', '.join(d['added']) or 'none'}; "
                                 f"removed {', '.join(d['removed']) or 'none'}"
                                 for mid, d in sorted(diffs.items())] or ["None."]))

    sections.append(("Checked majors missing from the catalog",
                     [f"- **{mid}** ({lv}): {why}. It still builds."
                      for mid, lv, why in sorted(retirement.missing_checked)] or ["None."]))
    sections.append(("Retired drafts",
                     [f"- **{mid}** ({lv}): folder deleted (an untouched draft): {why}"
                      for mid, lv, why in sorted(retirement.retired)]
                     + [f"- **{mid}** ({lv}): held, folder kept (edited by a person; its courses.json removed): {why}"
                        for mid, (lv, why) in sorted(retirement.orphaned.items())] or ["None."]))

    body = []
    for lv in sorted(set(overrides) | set(broken_overrides)):
        body += [f"### {lv}", ""]
        if lv in broken_overrides:
            body.append(f"overrides.json unreadable: {broken_overrides[lv]}")
        for cid in sorted(overrides.get(lv, {})):
            fix = overrides[lv][cid]
            # A major uses its own level's override for a course, else the other level's.
            users = sorted(r.id for r in results
                           if cid in r.courses and (r.level == lv or cid not in overrides.get(r.level, {})))
            reason = fix.get("reason", "") if isinstance(fix, dict) else ""
            body.append(f"- **{cid}**: {reason} (majors: {', '.join(users) or 'none'})")
        if lv not in broken_overrides and not overrides.get(lv):
            body.append("None.")
        body.append("")
    sections.append(("Fixes (shared overrides)", _trim(body) or ["None."]))

    body = []
    for lv in sorted(drafting.out_of_scope):
        body += [f"### {lv}", "", *([f"- {n}" for n in sorted(drafting.out_of_scope[lv])] or ["None."]), ""]
    body += [f"Skipped {lv}: programs.json found but catalog-courses.json is missing." for lv in drafting.skipped]
    sections.append(("Programs left out of scope", _trim(body) or ["No catalog snapshot used."]))

    lines = ["# Publishing status"]
    for title, section_lines in sections:
        lines += ["", f"## {title}", "", *section_lines]
    return "\n".join(lines) + "\n"


def _levels_without_pdfs(data_dir: Path) -> list[Path]:
    """The catalog/<level>/ folders, for levels some major uses, that hold no listing PDF."""
    levels = set()
    for mid in config.programs(data_dir):
        try:
            levels.add(json.loads((data_dir / mid / "program.json").read_text(encoding="utf-8"))["level"])
        except Exception:
            continue  # the build reports an unreadable program.json
    return [d for d in (data_dir / "catalog" / lv for lv in sorted(levels)) if not any(d.glob("*.pdf"))]


def main(argv: list[str], get_raw_for: Callable[[str], GetRaw] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m owlpath_pipeline.publish")
    ap.add_argument("--from-pdfs", action="store_true", help="read courses from listing PDFs saved by hand instead of the catalog snapshot; drafts no new majors")
    ap.add_argument("--accept-checked", action="append", default=[], metavar="ID",
                    help="write this checked major's changed build, after the user's OK (repeatable)")
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.from_pdfs and (missing := _levels_without_pdfs(args.data_dir)):
        # Building without them would hold every auto-built major and delete its courses.json.
        print(f"refusing --from-pdfs: no listing PDFs (*.pdf) in {', '.join(map(str, missing))}", file=sys.stderr)
        return 2
    results = publish(args.data_dir, "pdf" if args.from_pdfs else "snapshot", get_raw_for, set(args.accept_checked))
    counts = {s: sum(1 for r in results if r.state == s) for s in ("checked", "auto", "held")}
    print(", ".join(f"{n} {s}" for s, n in counts.items()))
    written = [r.id for r in results if r.accepted]
    if written:
        print(f"checked majors changed and written (--accept-checked): {', '.join(written)}")
    pending = [r.id for r in results if r.changed and not r.accepted]
    for mid in pending:
        print(f"checked major {mid} changed: not written; needs the user's OK, then rerun with --accept-checked {mid}")
    broken = [r for r in results if (r.checked or r.unreadable) and r.state == "held"]
    for r in broken:
        print(f"checked major {r.id} failed to build: {len(r.errors)} errors, {len(r.warnings)} warnings",
              file=sys.stderr)
    return 1 if broken or pending else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
