"""Build data/<year>/<major>/courses.json from the saved catalog listing PDFs in catalog/<level>/.

Pass 1 collects every course the program needs (required leaves pull new courses in). Shared per-level
overrides (catalog/<level>/overrides.json) replace a course's parsed prerequisites there, so they steer the closure.
Pass 2 marks each leaf as an in-graph course or an external alternative, then the
trees are converted to the short output form.

CLI: .venv/bin/python -m owlpath_pipeline.build <program> [--draft]   (reads/writes data/<year>/<program>/)
"""
import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from . import config
from .model import Expr, Logic, ParseResult, RawCourse
from .prereq_parser import parse_requirement
from .validate import validate_dataset

def source(level: str) -> str:
    return (f"KSU {config.CATALOGS[level]['name']} Catalog {config.CATALOG_YEAR} "
            f"({config.CATALOG_BASE}, catoid={config.catoid(level)})")


def _required_ids(expr: Expr | None, under_or: bool = False) -> list[str]:
    if expr is None:
        return []
    if "course" in expr:
        return [] if under_or else [expr["course"]]
    if "and" in expr:
        return [i for child in expr["and"] for i in _required_ids(child, under_or)]
    return [i for child in expr["or"] for i in _required_ids(child, True)]


def _classify(expr: Expr | None, graph: set[str], owner: str, warnings: list[str]) -> Expr | None:
    """Turn leaves into course (in graph) or external; warn on an OR with no in-graph alternative."""
    if expr is None:
        return None
    if "course" in expr:
        kind = "course" if expr["course"] in graph else "external"
        return {kind: expr["course"], **({"minGrade": expr["minGrade"]} if "minGrade" in expr else {})}
    op = "and" if "and" in expr else "or"
    children = [_classify(c, graph, owner, warnings) for c in expr[op]]
    out = {op: children}
    if op == "or" and not _has_course(out):
        names = ", ".join(_leaf_ids(out))
        warnings.append(f"{owner}: no in-program alternative in ({names})")
    return out


def _has_course(expr: Expr) -> bool:
    if "course" in expr:
        return True
    if "external" in expr:
        return False
    return any(_has_course(c) for c in expr.get("and", expr.get("or", [])))


def _leaf_ids(expr: Expr) -> list[str]:
    if "course" in expr or "external" in expr:
        return [expr.get("course") or expr["external"]]
    return [i for c in expr.get("and", expr.get("or", [])) for i in _leaf_ids(c)]


def to_output(expr: Expr) -> Logic:
    """Short form: an in-graph course with grade C becomes a plain string."""
    if "course" in expr:
        return expr["course"] if "minGrade" not in expr else dict(expr)
    if "external" in expr:
        return dict(expr)
    op = "and" if "and" in expr else "or"
    return {op: [to_output(c) for c in expr[op]]}


def _has_external(logic) -> bool:
    if isinstance(logic, dict):
        return "external" in logic or any(_has_external(c) for k in ("and", "or") for c in logic.get(k, []))
    return False


def check_overrides(overrides: dict, known: set[str]) -> None:
    """Overrides are written in catalog terms: course leaves only (each major's build decides node or text)."""
    for cid, o in overrides.items():
        if cid not in known:
            raise ValueError(f"override for {cid}: stale override, the course is not in the catalog")
        if not isinstance(o, dict) or not str(o.get("reason", "")).strip():
            raise ValueError(f"override for {cid}: a non-empty reason is required")
        unknown = set(o) - {"reason", "prereqs", "coreqs", "notes"}
        if unknown:
            raise ValueError(f"override for {cid}: unknown fields {sorted(unknown)}")
        if _has_external(o.get("prereqs")) or _has_external(o.get("coreqs")):
            raise ValueError(f"override for {cid}: external leaf; overrides use course leaves, "
                             "each major's build decides node or text")


def _from_override(logic) -> Expr | None:
    """Override logic (output short form, course leaves) -> internal Expr."""
    if logic is None:
        return None
    if isinstance(logic, str):
        return {"course": logic}
    if "course" in logic:
        return dict(logic)
    op = "and" if "and" in logic else "or"
    return {op: [_from_override(c) for c in logic[op]]}


def load_overrides(level: str, data_dir: Path | None = None) -> dict:
    """The level's shared overrides (catalog/<level>/overrides.json) merged over the other level's."""
    data_dir = data_dir or config.DATA_DIR
    merged: dict = {}
    for lv in [l for l in config.CATALOGS if l != level] + [level]:
        path = data_dir / "catalog" / lv / "overrides.json"
        if path.exists():
            merged.update(json.loads(path.read_text()))
    return merged


def _in_catalog(get_raw: Callable[[str], RawCourse], cid: str) -> bool:
    try:
        get_raw(cid)
    except KeyError:
        return False
    return True


def build_dataset(program: dict[str, list[str]], get_raw: Callable[[str], RawCourse],
                  overrides: dict, meta: dict) -> tuple[dict, list[str]]:
    """meta = {"program": {...}, "choices": [[id, ...], ...], "lessCommon": [id, ...]}, copied to the output as-is.
    lessCommon is optional and defaults to []; level (which catalog, for `source`) defaults to undergraduate."""
    for choice in meta["choices"]:
        for cid in choice:
            if cid not in program:
                raise ValueError(f"choices: {cid} is not in program.json")
    warnings: list[str] = []
    raws: dict[str, RawCourse] = {}
    parsed: dict[str, tuple[ParseResult, ParseResult]] = {}
    groups = {cid: list(g) for cid, g in program.items()}
    check_overrides(overrides, {cid for cid in overrides if _in_catalog(get_raw, cid)})

    # Pass 1: closure over required leaves.
    worklist = sorted(program)
    while worklist:
        cid = worklist.pop(0)
        if cid in raws:
            continue
        try:
            raws[cid] = get_raw(cid)
        except KeyError as e:
            warnings.append(f"{cid}: course page not found ({e})")
            groups.pop(cid, None)
            continue
        r = raws[cid]
        o = overrides.get(cid, {})
        pre = (ParseResult(_from_override(o["prereqs"])) if "prereqs" in o
               else parse_requirement(r.prereq_text) if r.prereq_text else ParseResult(None))
        co = (ParseResult(_from_override(o["coreqs"])) if "coreqs" in o
              else parse_requirement(r.coreq_text) if r.coreq_text else ParseResult(None))
        parsed[cid] = (pre, co)
        warnings.extend(f"{cid}: {w}" for w in r.warnings + pre.warnings + co.warnings)
        for req in _required_ids(pre.expr) + _required_ids(co.expr):
            if req not in groups:
                groups[req] = ["prereq-only"]
                worklist.append(req)
    graph = set(raws)

    # Pass 2: classify leaves, convert, apply overrides.
    courses = []
    for cid in sorted(graph):
        r, (pre, co) = raws[cid], parsed[cid]
        prereqs = _classify(pre.expr, graph, cid, warnings)
        coreqs = _classify(co.expr, graph, cid, warnings)
        notes = list(overrides.get(cid, {}).get("notes", dict.fromkeys(pre.notes + co.notes)))
        c = {
            "id": cid, "title": r.title, "credits": r.credits, "description": r.description,
            "catalogYear": config.CATALOG_YEAR, "catalogUrl": r.url, "groups": groups[cid],
            "prereqs": to_output(prereqs) if prereqs else None,
            "coreqs": to_output(coreqs) if coreqs else None,
            "notes": notes,
        }
        courses.append(c)

    warnings = [w for w in warnings if w.split(":", 1)[0] not in overrides]
    return {"catalogYear": config.CATALOG_YEAR, "source": source(meta.get("level", "undergraduate")),
            "program": meta["program"], "choices": meta["choices"], "lessCommon": meta.get("lessCommon", []), "courses": courses}, warnings


def catalog_get_raw(level: str = "undergraduate", directory: Path | None = None) -> Callable[[str], RawCourse]:
    """Look courses up in the saved listing PDFs for `level` (catalog/<level>/); a missing id raises KeyError."""
    from .catalog_pdf import load_catalog

    return load_catalog(directory or config.catalog_pdf_dir(level), config.catoid(level)).__getitem__


def level_get_raw(level: str, source: str = "pdf") -> Callable[[str], RawCourse]:
    """Look a course up in `level` first, then in the other level; KeyError if neither has it.
    source is "pdf" (saved listing PDFs) or "snapshot" (catalog-courses.json)."""
    if source not in ("pdf", "snapshot"):
        raise ValueError(f"unknown catalog source {source!r}; expected 'pdf' or 'snapshot'")
    levels = [level] + [l for l in config.CATALOGS if l != level]
    tables: list = []
    for lv in levels:
        if source == "snapshot":
            from .snapshot import load_courses
            tables.append(load_courses(lv, config.DATA_DIR).__getitem__)
        else:
            try:
                tables.append(catalog_get_raw(lv))
            except ValueError:  # level not set up (no catoid)
                continue

    def get_raw(cid: str) -> RawCourse:
        for table in tables:
            try:
                return table(cid)
            except KeyError:
                continue
        raise KeyError(cid)

    return get_raw


def _report(warnings: list[str], errors: list[str]) -> str:
    lines = [f"# Build report — {config.CATALOG_YEAR}", ""]
    if errors:
        lines += ["## Validation errors", "", *[f"- {e}" for e in errors], ""]
    lines += ["## Warnings needing review", ""]
    if not warnings:
        lines.append("None.")
    by_course: dict[str, list[str]] = {}
    for w in warnings:
        cid, msg = w.split(": ", 1)
        by_course.setdefault(cid, []).append(msg)
    for cid in sorted(by_course):
        lines.append(f"- **{cid}**")
        lines += [f"  - {m}" for m in by_course[cid]]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m owlpath_pipeline.build")
    ap.add_argument("program", choices=config.PROGRAMS, help="which major to build, e.g. bs-cs")
    ap.add_argument("--draft", action="store_true", help="write output even with unresolved warnings")
    args = ap.parse_args(argv)

    out = config.program_dir(args.program)
    spec = json.loads((out / "program.json").read_text())
    if "level" not in spec:
        raise SystemExit(f"{args.program}/program.json needs \"level\": one of {sorted(config.CATALOGS)}")
    overrides = load_overrides(spec["level"])
    meta = {"program": spec["program"], "choices": spec["choices"], "lessCommon": spec.get("lessCommon", []),
            "level": spec["level"]}
    dataset, warnings = build_dataset(spec["courses"], level_get_raw(spec["level"]), overrides, meta)
    errors = validate_dataset(dataset)

    # Never write a dataset that fails validation, and never replace the reviewed
    # one with output that still has unresolved warnings unless --draft is given.
    if not errors and (args.draft or not warnings):
        (out / "courses.json").write_text(json.dumps(dataset, sort_keys=True, indent=2) + "\n")
    (out / "build-report.md").write_text(_report(warnings, errors))
    print(f"{len(dataset['courses'])} courses, {len(warnings)} unresolved warnings, {len(errors)} validation errors")
    if errors or (warnings and not args.draft):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
