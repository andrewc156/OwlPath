"""Draft, build and sort every major; write each courses.json and build-report.md, majors.json and STATUS.md.

A major is "checked" (program.json has "checked": true, a person reviewed it), "auto" (unchecked, built cleanly:
published and labeled not yet checked) or "held" (draft warnings, build warnings or validation errors: nothing
shipped). A checked major that cannot build makes the CLI exit 1 and keeps its committed courses.json.

CLI: .venv/bin/python -m owlpath_pipeline.publish [--from-pdfs]   (default: the committed catalog snapshot)
"""
import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .build import build_major, major_report
from .draft import assign_ids, draft_diff, draft_program, write_draft
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
    changed: list[str] = field(default_factory=list)  # course ids that differ from the committed courses.json
    unreadable: bool = False  # program.json couldn't be read: its courses.json is never touched, and it blocks
    checked: bool = False  # reviewed by a person; a checked major can be "held" when its build fails


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def _draft_levels(data_dir: Path) -> tuple[dict[str, list[str]], dict[str, dict], list[str]]:
    """Draft every in-scope program of each level with a snapshot.
    Returns (out of scope names per level, {checked major id: its catalog page's added/removed courses},
    levels skipped because catalog-courses.json is missing)."""
    from .snapshot import load_courses, load_programs

    out_of_scope: dict[str, list[str]] = {}
    page_changes: dict[str, dict] = {}
    skipped: list[str] = []
    for level in config.CATALOGS:
        programs_file = data_dir / "catalog" / level / "programs.json"
        if not programs_file.exists():
            continue
        if not (data_dir / "catalog" / level / "catalog-courses.json").exists():
            skipped.append(level)
            continue
        pages = load_programs(level, data_dir)
        catalog = load_courses(level, data_dir)
        idents = assign_ids(pages, config.catoid(level))
        for page in pages:
            draft = draft_program(page, idents[page["poid"]], level, catalog)
            path = data_dir / draft.program_json["program"]["id"] / "program.json"
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if write_draft(draft, data_dir) == "kept-checked" and old:
                # The drafter skips general education by design, so a course the checked program lists
                # only as gen-ed-math is not a page change.
                gen_ed = {c for c, groups in old.get("courses", {}).items() if set(groups) == {"gen-ed-math"}}
                diff = draft_diff({**old, "courses": {c: g for c, g in old.get("courses", {}).items()
                                                      if c not in gen_ed}}, draft.program_json)
                if diff["added"] or diff["removed"]:
                    page_changes[draft.program_json["program"]["id"]] = diff
        out_of_scope[level] = [p["name"] for p in
                               json.loads(programs_file.read_text(encoding="utf-8")).get("outOfScope", [])]
    return out_of_scope, page_changes, skipped


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


def publish(data_dir: Path = config.DATA_DIR, source: str = "snapshot",
            get_raw_for: Callable[[str], GetRaw] | None = None) -> list[MajorResult]:
    """get_raw_for(level) overrides how courses are looked up (tests); default is level_get_raw(level, source)."""
    data_dir = Path(data_dir)
    if source == "snapshot":
        out_of_scope, page_changes, skipped = _draft_levels(data_dir)
    else:  # PDF builds never draft: they build the program folders that already exist
        out_of_scope, page_changes, skipped = {}, {}, []

    results: list[MajorResult] = []
    details: dict[str, dict] = {}  # changed checked majors: id -> {course id: (before, after)}
    for mid in config.programs(data_dir):
        folder = data_dir / mid
        result = MajorResult(mid, mid, "unknown", "held")
        notes: list[str] = []
        draft_warnings: list[str] = []
        left_out: list[str] = []
        dataset = None
        try:
            spec = json.loads((folder / "program.json").read_text(encoding="utf-8"))
            result.checked = bool(spec.get("checked"))
            result.name, result.level = spec["program"]["name"], spec["level"]
        except Exception as e:  # can't tell whether the major was checked: touch nothing, block the publish
            result.unreadable = True
            result.errors = [f"program.json unreadable: {type(e).__name__}: {e}"]
        if not result.unreadable:
            try:
                spec, dataset, result.warnings, result.errors, notes = build_major(
                    folder, source, data_dir, get_raw_for)
                draft_warnings, left_out = spec.get("draftWarnings", []), spec.get("leftOut", [])
            except Exception as e:  # one bad major must not stop the others or leave the index stale
                dataset, result.errors = None, [f"build failed: {type(e).__name__}: {e}"]
        if dataset and not result.errors and not result.warnings and not draft_warnings:
            result.state = "checked" if result.checked else "auto"
            courses_file = folder / "courses.json"
            if result.checked and courses_file.exists():
                changes = _course_changes(json.loads(courses_file.read_text()), dataset)
                if changes:
                    result.changed, details[mid] = list(changes), changes
            _write_json(courses_file, dataset)
        elif not result.checked and not result.unreadable:
            (folder / "courses.json").unlink(missing_ok=True)
        if not result.unreadable:
            (folder / "build-report.md").write_text(
                major_report(result.warnings, result.errors, notes, draft_warnings, left_out))
        results.append(result)

    shipped = [r for r in results if r.state != "held" or (r.checked and (data_dir / r.id / "courses.json").exists())]
    shipped.sort(key=lambda r: (r.level, r.name))
    _write_json(data_dir / "majors.json", [{"id": r.id, "name": r.name, "level": r.level, "checked": r.checked}
                                           for r in shipped])
    (data_dir / "STATUS.md").write_text(_status(results, details, page_changes, out_of_scope, skipped))
    return results


def _short(value) -> str:
    return "(absent)" if value is None else json.dumps(value, sort_keys=True)


def _status(results: list[MajorResult], details: dict, page_changes: dict, out_of_scope: dict,
            skipped: list[str]) -> str:
    levels = sorted({r.level for r in results})
    lines = ["# Publishing status", "", "## Summary", "",
             "| Level | Checked | Auto | Held |", "|---|---|---|---|"]
    for lv in levels:
        counts = [sum(1 for r in results if r.level == lv and r.state == s) for s in ("checked", "auto", "held")]
        lines.append(f"| {lv} | " + " | ".join(map(str, counts)) + " |")

    lines += ["", "## Held majors", ""]
    held = sorted((r for r in results if r.state == "held"), key=lambda r: (r.level, r.name))
    for r in held:
        why = [f"{len(r.warnings)} warning(s)"] if r.warnings else []
        why += [f"{len(r.errors)} error(s)"] if r.errors else []
        if r.unreadable:
            why = r.errors
        lines.append(f"- **{r.id}** ({r.level}){' [BLOCKS PUBLISH]' if r.checked or r.unreadable else ''}: "
                     + (", ".join(why) or "drafting warnings")
                     + ("" if r.unreadable else " (see its build-report.md)"))
    if not held:
        lines.append("None.")

    by_course: dict[str, set[str]] = {}
    for r in held:
        for w in r.warnings:
            by_course.setdefault(w.split(": ", 1)[0], set()).add(r.id)
    lines += ["", "## Courses holding the most majors", ""]
    for cid, majors in sorted(by_course.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"- {cid}: {len(majors)} majors ({', '.join(sorted(majors))})")
    if not by_course:
        lines.append("None.")

    lines += ["", "## Checked majors changed by this build", ""]
    for mid, changes in sorted(details.items()):
        lines += [f"### {mid}", ""]
        for cid, (before, after) in changes.items():
            lines += [f"- **{cid}**", f"  - before: `{_short(before)}`", f"  - after: `{_short(after)}`"]
        lines.append("")
    if not details:
        lines += ["None.", ""]

    lines += ["## Checked majors whose catalog page changed", ""]
    for mid, diff in sorted(page_changes.items()):
        lines.append(f"- **{mid}**: added {', '.join(diff['added']) or 'none'}; "
                     f"removed {', '.join(diff['removed']) or 'none'}")
    if not page_changes:
        lines.append("None.")

    lines += ["", "## Programs left out of scope", ""]
    for lv in sorted(out_of_scope):
        lines += [f"### {lv}", ""] + ([f"- {n}" for n in sorted(out_of_scope[lv])] or ["None."]) + [""]
    lines += [f"Skipped {lv}: programs.json found but catalog-courses.json is missing." for lv in skipped]
    if not out_of_scope and not skipped:
        lines.append("No catalog snapshot used.")
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: list[str], get_raw_for: Callable[[str], GetRaw] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m owlpath_pipeline.publish")
    ap.add_argument("--from-pdfs", action="store_true", help="read courses from listing PDFs saved by hand instead of the catalog snapshot; drafts no new majors")
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    results = publish(args.data_dir, "pdf" if args.from_pdfs else "snapshot", get_raw_for)
    counts = {s: sum(1 for r in results if r.state == s) for s in ("checked", "auto", "held")}
    print(", ".join(f"{n} {s}" for s, n in counts.items()))
    changed = [r.id for r in results if r.changed]
    if changed:
        print(f"checked majors changed: {', '.join(changed)}")
    broken = [r for r in results if (r.checked or r.unreadable) and r.state == "held"]
    for r in broken:
        print(f"checked major {r.id} failed to build: {len(r.errors)} errors, {len(r.warnings)} warnings",
              file=sys.stderr)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
