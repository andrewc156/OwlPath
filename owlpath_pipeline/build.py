"""Build data/<year>/courses.json from the saved catalog listing PDFs.

Pass 1 collects every course the program needs (required leaves pull new courses in).
Pass 2 marks each leaf as an in-graph course or an external alternative, then the
trees are converted to the short output form and hand-written overrides are applied.

CLI: .venv/bin/python -m owlpath_pipeline.build [--draft]
"""
import argparse
import json
import sys
from collections.abc import Callable

from . import config
from .model import Expr, Logic, ParseResult, RawCourse
from .prereq_parser import parse_requirement
from .validate import validate_dataset

SOURCE = f"KSU Undergraduate Catalog {config.CATALOG_YEAR} ({config.CATALOG_BASE}, catoid={config.CATOID})"


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


def _check_overrides(overrides: dict, graph: set[str]) -> None:
    for cid, o in overrides.items():
        if cid not in graph:
            raise ValueError(f"override for {cid}: course is not in the graph (stale override?)")
        if not isinstance(o, dict) or not str(o.get("reason", "")).strip():
            raise ValueError(f"override for {cid}: a non-empty reason is required")
        unknown = set(o) - {"reason", "prereqs", "coreqs", "notes"}
        if unknown:
            raise ValueError(f"override for {cid}: unknown fields {sorted(unknown)}")


def build_dataset(program: dict[str, list[str]], get_raw: Callable[[str], RawCourse],
                  overrides: dict) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    raws: dict[str, RawCourse] = {}
    parsed: dict[str, tuple[ParseResult, ParseResult]] = {}
    groups = {cid: list(g) for cid, g in program.items()}

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
        pre = parse_requirement(r.prereq_text) if r.prereq_text else ParseResult(None)
        co = parse_requirement(r.coreq_text) if r.coreq_text else ParseResult(None)
        parsed[cid] = (pre, co)
        warnings.extend(f"{cid}: {w}" for w in pre.warnings + co.warnings)
        for req in _required_ids(pre.expr) + _required_ids(co.expr):
            if req not in groups:
                groups[req] = ["prereq-only"]
                worklist.append(req)
    graph = set(raws)
    _check_overrides(overrides, graph)

    # Pass 2: classify leaves, convert, apply overrides.
    courses = []
    for cid in sorted(graph):
        r, (pre, co) = raws[cid], parsed[cid]
        prereqs = _classify(pre.expr, graph, cid, warnings)
        coreqs = _classify(co.expr, graph, cid, warnings)
        notes = list(dict.fromkeys(pre.notes + co.notes))
        c = {
            "id": cid, "title": r.title, "credits": r.credits, "description": r.description,
            "catalogYear": config.CATALOG_YEAR, "catalogUrl": r.url, "groups": groups[cid],
            "prereqs": to_output(prereqs) if prereqs else None,
            "coreqs": to_output(coreqs) if coreqs else None,
            "notes": notes,
        }
        if cid in overrides:
            c.update({k: v for k, v in overrides[cid].items() if k != "reason"})
        courses.append(c)

    warnings = [w for w in warnings if w.split(":", 1)[0] not in overrides]
    return {"catalogYear": config.CATALOG_YEAR, "source": SOURCE, "courses": courses}, warnings


def catalog_get_raw(directory=config.CATALOG_PDF_DIR) -> Callable[[str], RawCourse]:
    """Look courses up in the saved catalog listing PDFs; a missing id raises KeyError."""
    from .catalog_pdf import load_catalog

    return load_catalog(directory).__getitem__


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
    ap.add_argument("--draft", action="store_true", help="write output even with unresolved warnings")
    args = ap.parse_args(argv)

    program = json.loads((config.DATA_DIR / "program.json").read_text())["courses"]
    overrides = json.loads((config.DATA_DIR / "overrides.json").read_text())
    dataset, warnings = build_dataset(program, catalog_get_raw(), overrides)
    errors = validate_dataset(dataset)

    if not errors:  # never write a dataset that fails validation
        (config.DATA_DIR / "courses.json").write_text(json.dumps(dataset, sort_keys=True, indent=2) + "\n")
    (config.DATA_DIR / "build-report.md").write_text(_report(warnings, errors))
    print(f"{len(dataset['courses'])} courses, {len(warnings)} unresolved warnings, {len(errors)} validation errors")
    if errors or (warnings and not args.draft):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
