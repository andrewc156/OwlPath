"""Cross-check catalog prerequisites against Banner's public course pages.

Banner lists corequisites under "Prerequisites" too, so the catalog side uses
prereqs and coreqs together. Every disagreement goes to a report for a human;
the catalog stays the authority.

CLI: .venv/bin/python -m owlpath_pipeline.banner <program>   (reads <program>/courses.json, writes banner-diff.md)
"""
import json
import re
import sys
from dataclasses import dataclass

from bs4 import BeautifulSoup

from . import config
from .model import DEFAULT_MIN_GRADE, Logic

_GRADE = re.compile(r"([A-Z]{2,4} \d{4}[A-Z]?)\s+Minimum Grade of ([A-F])")


@dataclass(frozen=True)
class Discrepancy:
    course: str
    ref: str
    catalog_grade: str | None
    banner_grade: str | None


def parse_banner_prereqs(html: str) -> dict[str, str]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    grades: dict[str, str] = {}
    for ref, grade in _GRADE.findall(text):
        grades.setdefault(ref, grade)
    return grades


def _leaves(logic: Logic | None, out: dict[str, str]) -> None:
    if logic is None:
        return
    if isinstance(logic, str):
        out.setdefault(logic, DEFAULT_MIN_GRADE)
    elif "and" in logic or "or" in logic:
        for child in logic.get("and", logic.get("or", [])):
            _leaves(child, out)
    else:
        ref = logic.get("course") or logic["external"]
        out.setdefault(ref, logic.get("minGrade", DEFAULT_MIN_GRADE))


def diff_course(course: dict, banner: dict[str, str]) -> list[Discrepancy]:
    catalog: dict[str, str] = {}
    _leaves(course.get("prereqs"), catalog)
    _leaves(course.get("coreqs"), catalog)
    return [
        Discrepancy(course["id"], ref, catalog.get(ref), banner.get(ref))
        for ref in sorted(set(catalog) | set(banner))
        if catalog.get(ref) != banner.get(ref)
    ]


def _report(diffs: dict[str, list[Discrepancy]], failures: dict[str, str]) -> str:
    lines = [f"# Banner cross-check — {config.CATALOG_YEAR} (term {config.BANNER_TERM})", "",
             "The catalog is the authority. Fill in **Resolution** for each row; record any change as an override.", ""]
    if not diffs and not failures:
        lines.append("No discrepancies.")
    for cid in sorted(diffs):
        lines += [f"## {cid}", "", "| Ref | Catalog | Banner | Resolution |", "|---|---|---|---|"]
        lines += [f"| {d.ref} | {d.catalog_grade or '—'} | {d.banner_grade or '—'} | |" for d in diffs[cid]]
        lines.append("")
    if failures:
        lines += ["## Could not check", ""] + [f"- {cid}: {why}" for cid, why in sorted(failures.items())]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    import argparse

    from .fetch import FetchError, PoliteFetcher

    ap = argparse.ArgumentParser(prog="python -m owlpath_pipeline.banner")
    ap.add_argument("program", choices=config.PROGRAMS, help="which major to check, e.g. bs-dsa")
    out = config.program_dir(ap.parse_args(argv).program)
    dataset = json.loads((out / "courses.json").read_text())
    fetcher = PoliteFetcher.default()
    diffs: dict[str, list[Discrepancy]] = {}
    failures: dict[str, str] = {}
    for course in dataset["courses"]:
        subj, num = course["id"].split()
        url = config.BANNER_URL.format(term=config.BANNER_TERM, subj=subj, num=num)
        try:
            found = diff_course(course, parse_banner_prereqs(fetcher.fetch(url)))
        except FetchError as e:
            failures[course["id"]] = str(e)
            continue
        if found:
            diffs[course["id"]] = found
    (out / "banner-diff.md").write_text(_report(diffs, failures))
    print(f"{len(diffs)} courses with discrepancies, {len(failures)} not checked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
