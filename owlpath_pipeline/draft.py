"""Draft a program.json from a parsed catalog program page (see docs: all-majors plan, Task 7)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config
from .model import RawCourse

_TRAILING_HOURS = re.compile(r"\s*\([^()]*credit hours?\)\s*$", re.IGNORECASE)
_SKIP = re.compile(r"core impacts|general education|university electives|free electives|program total|\bminor\b")
_CONC_END = re.compile(r"\b(concentration|track|option|emphasis)$")
_LEFT_OUT_TITLE = re.compile(
    r"\b(internship|co-?op|cooperative (study|education)|special topics|advanced topics|selected topics"
    r"|(undergraduate|graduate|directed|doctoral|dissertation|thesis) research"
    r"|directed (study|readings)|independent study|thesis|dissertation)\b")
_NAMES_COURSE = re.compile(r"\b[A-Z]{2,5} \d{4}[A-Z]?\b")

# Permission-only prerequisite text (ruling R27): nothing is left once the permission, consent or approval
# phrases, connective words and punctuation are removed. An approver ends in a head noun ("the American Studies
# graduate program director"), so "junior standing", "admission to the X program" or "Dance Major" never read as
# one: they are left over, and the course stays (its non-course phrases become notes in the build).
_KEY = r"\b(?:permission|consent|approval)\b"
_HEAD = (r"(?:instructor|professor|faculty|advis[eo]r|chair(?:person)?|head|director|coordinator|dean|lead"
         r"|department(?:al)?|dept\.?|school|committee|office)s?(?:['’]s)?(?![\w'’])")
_STOP = (r"(?:and|or|nor|of|for|from|by|with|to|in|on|at|is|are|the|a|an|prior|required|permission|consent"
         r"|approval|admission|admitted|acceptance|accepted|standing|status|level|majors?|minors?|gpa|hours?"
         r"|credits?|completion|completed?|audition|enroll\w*|declared|junior|senior|sophomore|freshman|courses?)")
_QUALIFIER = rf"(?!{_STOP}(?![\w.'’/&-]))[A-Za-z][\w.'’/&-]*"
_APPROVER = rf"(?:(?:the|a|an)\s+)?(?:{_QUALIFIER}\s+){{0,6}}{_HEAD}"
_APPROVERS = rf"{_APPROVER}(?:(?:\s*,\s*(?:(?:and|or)\s+)?|\s+(?:and/or|and|or)\s+){_APPROVER})*"
_PERMISSION_PHRASE = re.compile(
    rf"(?:\bby\s+)?(?:{_APPROVERS}\s+)?{_KEY}(?:\s+(?:of|from|by)\s+{_APPROVERS})?"
    r"(?:\s+(?:is\s+)?required)?(?:\s+prior\s+to\s+registration)?", re.IGNORECASE)
_CONNECTIVES = re.compile(r"(?:[\s,;:.()/&-]+|\b(?:and|or|with|by)\b)*", re.IGNORECASE)


def _permission_only(prereq: str) -> bool:
    if not prereq or _NAMES_COURSE.search(prereq) or not re.search(_KEY, prereq, re.IGNORECASE):
        return False
    return _CONNECTIVES.fullmatch(_PERMISSION_PHRASE.sub(" ", prereq)) is not None


def _slug(text: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", " ", text.lower().replace("&", " and ")).split())


def _clean_heading(heading: str) -> str:
    return _TRAILING_HOURS.sub("", heading).strip()


def program_identity(name: str, poid: int, catoid: int) -> tuple[str, str]:
    field, comma, degree = name.rpartition(",")
    if not comma:
        field, degree = name, ""
    field, degree = field.strip(), degree.strip().replace(".", "")
    known = config.KNOWN_PROGRAM_IDS.get((catoid, poid))
    label = f"{degree} {field}".strip()
    if known:
        return known, label
    return (f"{_slug(degree)}-{_slug(field)}" if degree else _slug(field)), label


def assign_ids(pages: list[dict], catoid: int) -> dict[int, tuple[str, str]]:
    idents = {p["poid"]: program_identity(p["name"], p["poid"], catoid) for p in pages}
    counts: dict[str, int] = {}
    for pid, _ in idents.values():
        counts[pid] = counts.get(pid, 0) + 1
    result = {}
    for poid, (pid, name) in idents.items():
        if counts[pid] > 1 and (catoid, poid) not in config.KNOWN_PROGRAM_IDS:
            pid = f"{pid}-{poid}"
        result[poid] = (pid, name)
    return result


@dataclass
class Draft:
    program_json: dict
    warnings: list[str]
    left_out: list[str]


def draft_hash(program_json: dict) -> str:
    body = {k: v for k, v in program_json.items() if k != "draftHash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_left_out(item: dict, catalog: dict[str, RawCourse]) -> bool:
    raw = catalog.get(item["id"])
    title = item.get("title") or (raw.title if raw else "")
    if _LEFT_OUT_TITLE.search(title.lower()):
        return True
    return _permission_only((raw.prereq_text if raw else None) or "")


def _group_for(heading: str) -> str | None:
    if "core field" in heading or "field of study" in heading:
        return "core-field"
    if "elective" in heading:
        return "major-elective"
    if "project" in heading or "capstone" in heading:
        return "major-project"
    if "requirement" in heading or "required" in heading or re.search(r"\bcore\b", heading):
        return "major-required"
    return None


_CHOOSE = re.compile(r"\b(select|choose|chosen|from the following|one of|elective)", re.IGNORECASE)


def _unnamed_group(items: list[dict]) -> str:
    texts = " ".join(i["text"] for i in items if i["kind"] == "text")
    return "major-elective" if _CHOOSE.search(texts) else "major-required"


def draft_program(page: dict, ident: tuple[str, str], level: str, catalog: dict[str, RawCourse]) -> Draft:
    courses: dict[str, list[str]] = {}
    choices: list[list[str]] = []
    left_out: list[str] = []
    warnings: list[str] = []
    conc_labels: list[tuple[str, str]] = []  # (label, group), page order
    conc: tuple[int, str] | None = None  # (heading level, group)
    skipped: int | None = None  # level of the skipped heading whose subtree we are in
    named: list[tuple[int, str]] = []  # (heading level, group) of the recognized headings above this one

    def add_left_out(entry: str) -> None:
        if entry not in left_out:
            left_out.append(entry)

    for section in page["sections"]:
        raw_heading = _clean_heading(section["heading"])
        heading = raw_heading.lower()
        level_no = section["level"]
        if conc and level_no <= conc[0]:
            conc = None
        if skipped is not None and level_no <= skipped:
            skipped = None
        if skipped is not None:
            continue
        if _SKIP.search(heading):
            skipped = level_no
            continue
        ends = _CONC_END.search(heading)
        if ends and "elective" not in heading:
            label = raw_heading[:ends.start()].strip()
            group = f"conc-{_slug(label)}"
            conc = (level_no, group)
            if (label, group) not in conc_labels:
                conc_labels.append((label, group))
        items = section["items"]
        for item in items:
            if item["kind"] == "text":
                add_left_out(f"text: {item['text']}")
        while named and named[-1][0] >= level_no:
            named.pop()
        own = _group_for(heading)
        if own:
            named.append((level_no, own))
        if not any(i["kind"] == "course" for i in items):
            continue
        # A heading the rules don't name ("Group A", "Teaching Field Courses") takes its parent's group;
        # at the top it is an elective list when its text says to choose, otherwise required.
        group = conc[1] if conc else own or (named[-1][1] if named else _unnamed_group(items))
        chain: list[str] = []
        pending_or = False

        def flush() -> None:
            if len(chain) >= 2 and chain not in choices:
                choices.append(list(chain))
            chain.clear()

        for item in items:
            if item["kind"] == "or":
                pending_or = True
                continue
            if item["kind"] == "text":
                flush()
                pending_or = False
                continue
            if not pending_or:
                flush()
            pending_or = False
            if _is_left_out(item, catalog):
                add_left_out(item["id"])
                continue
            groups = courses.setdefault(item["id"], [])
            if group not in groups:
                groups.append(group)
            chain.append(item["id"])
        flush()

    for cid in courses:
        if cid not in catalog:
            warnings.append(f"{cid} is not in the catalog listings")
    if not courses:
        warnings.append("no courses found")

    used = {g for gs in courses.values() for g in gs}

    def present(groups: list[str]) -> list[str]:
        return [g for g in groups if g in used]

    filters = []
    for label, groups in [("Required courses", ["core-field", "major-required"])] \
            + [(lab, [g]) for lab, g in conc_labels] \
            + [("Electives", ["major-elective"]), ("Project", ["major-project"])]:
        if present(groups):
            filters.append({"label": label, "groups": present(groups)})

    program_json = {
        "catalogYear": config.CATALOG_YEAR,
        "level": level,
        # The catalog program this draft came from: publish retires the folder once no program drafts to it.
        "catoid": config.catoid(level),
        "poid": page.get("poid"),
        "program": {"id": ident[0], "name": ident[1], "filters": filters},
        "choices": choices,
        "courses": dict(sorted(courses.items())),
        "draftWarnings": warnings,
        "leftOut": left_out,
    }
    program_json["draftHash"] = draft_hash(program_json)
    return Draft(program_json, warnings, left_out)


def write_draft(draft: Draft, data_dir: Path = config.DATA_DIR) -> str:
    path = data_dir / draft.program_json["program"]["id"] / "program.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("checked"):
            return "kept-checked"
        if existing.get("draftHash") != draft_hash(existing):
            return "kept-edited"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft.program_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "written"


def draft_diff(old: dict, new: dict) -> dict:
    before, after = set(old.get("courses", {})), set(new.get("courses", {}))
    return {"added": sorted(after - before), "removed": sorted(before - after)}
