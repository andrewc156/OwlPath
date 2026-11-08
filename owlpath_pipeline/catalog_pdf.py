"""Read catalog course listings saved from a browser as PDFs.

catalog.kennesaw.edu answers automated clients with HTTP 202 (a bot check), so the
2026-27 "Courses" listing is saved by hand, one expanded PDF per prefix, into
data/<year>/catalog/. Labels are found by their text, not by position.
"""
import dataclasses
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from . import config
from .model import RawCourse

HEADER = re.compile(r"^([A-Z]{2,4} \d{4}[A-Z]?): (.+)$")
CREDITS = re.compile(r"^(\d+(?:-\d+)?) Credit Hours?$")
FIELD = re.compile(r"^(Prerequisite|Concurrent|Corequisite):\s*(.*)$")
FOOTER = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2}, \d{1,2}:\d{2} [AP]M\b|https?://)")
SECTION_END = re.compile(r"^(Course Learning Outcomes|Notes:)")


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def _lines(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text)  # ligatures, NBSP
    text = re.sub(r" (?=Notes: )", "\n", text)  # PDF text sometimes runs Notes onto the description
    lines = (" ".join(line.split()) for line in text.splitlines())
    return [line for line in lines if line and not FOOTER.match(line)]


def _course(cid: str, title: str, body: list[str], url: str) -> RawCourse:
    credits = ""
    fields: dict[str, list[str]] = {}
    description: list[str] = []
    current: list[str] | None = None
    for line in body:
        if not credits and (m := CREDITS.match(line)):
            credits = m.group(1)
        elif m := FIELD.match(line):
            current = fields.setdefault(m.group(1), [])
            current.append(m.group(2))
        elif line == "Description":
            current = description
        elif SECTION_END.match(line):
            current = None
        elif current is not None:
            current.append(line)

    def joined(label: str) -> str | None:
        parts = fields.get(label)
        return " ".join(" ".join(parts).split()) or None if parts else None

    coreq_parts = [p for p in (joined("Concurrent"), joined("Corequisite")) if p]
    coreq = coreq_parts[0] if len(coreq_parts) == 1 else (
        " and ".join(f"({p})" for p in coreq_parts) or None)
    return RawCourse(id=cid, title=title, credits=credits, description=" ".join(description),
                     prereq_text=joined("Prerequisite"), coreq_text=coreq, url=url)


def parse_listing(text: str, url: str) -> dict[str, RawCourse]:
    """Map course id to RawCourse for one expanded listing's text."""
    courses: dict[str, RawCourse] = {}
    head: tuple[str, str] | None = None
    body: list[str] = []
    for line in _lines(text) + ["ZZZZ 0000: end"]:
        if m := HEADER.match(line):
            if head:
                courses[head[0]] = _course(*head, body, url)
            head, body = (m.group(1), m.group(2)), []
        elif head:
            body.append(line)
    return courses


def load_catalog(directory: Path) -> dict[str, RawCourse]:
    """Every course in every saved listing PDF, each with its prefix's listing URL."""
    catalog: dict[str, RawCourse] = {}
    for path in sorted(directory.glob("*.pdf")):
        for cid, course in parse_listing(pdf_text(path), "").items():
            if cid in catalog:
                raise ValueError(f"{cid} appears in more than one saved listing ({path.name})")
            url = config.COURSE_LISTING_URL.format(prefix=cid.split()[0])
            catalog[cid] = dataclasses.replace(course, url=url)
    return catalog
