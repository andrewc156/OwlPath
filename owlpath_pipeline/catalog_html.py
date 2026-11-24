"""Pure readers for cached KSU catalog pages (navigation, listings, program pages)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

_COURSE_ID = re.compile(r"^([A-Z]{2,5} \d{4}[A-Z]?)\b")
_SHOW_COURSE = re.compile(r"showCourse\('\d+',\s*'(\d+)'")
_POPUP_COID = re.compile(r"preview_course\.php\?catoid=\d+&(?:amp;)?coid=(\d+)")
_CPAGE = re.compile(r"filter(?:%5B|\[)cpage(?:%5D|\])=(\d+)")
_EXCLUDED = ("Minor", "Certificate", "Endorsement")
_DEGREE = re.compile(r"^(B|M|D|Ph\.D|Ed\.S|Ed\.D)", re.IGNORECASE)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def parse_nav(html: str) -> dict[str, int]:
    nav: dict[str, int] = {}
    for a in _soup(html).select("a[href*='navoid=']"):
        m = re.search(r"navoid=(\d+)", a["href"])
        text = a.get_text(" ", strip=True)
        if m and text:
            nav.setdefault(text, int(m.group(1)))
    return nav


def parse_prefixes(html: str) -> list[str]:
    sel = _soup(html).select_one("select[name='filter[27]']")
    if sel is None:
        return []
    values = {o.get("value", "").strip() for o in sel.find_all("option")}
    return sorted(v for v in values if v and v != "-1")


def listing_page_count(html: str) -> int:
    pages = [int(n) for n in _CPAGE.findall(html)]
    return max(pages, default=1)


def course_coids(html: str) -> dict[str, int]:
    coids: dict[str, int] = {}
    for a in _soup(html).find_all("a"):
        onclick = a.get("onclick", "")
        text = a.get_text(" ", strip=True)
        popup = _POPUP_COID.search(onclick)
        if popup and _COURSE_ID.match(text):
            coids.setdefault(_COURSE_ID.match(text).group(1), int(popup.group(1)))
            continue
        show = _SHOW_COURSE.search(onclick)
        if show:
            m = _COURSE_ID.match(text.split(":")[0].strip())
            if m:
                coids.setdefault(m.group(1), int(show.group(1)))
    return coids


@dataclass(frozen=True)
class ProgramRef:
    name: str
    poid: int
    college: str = ""  # the index heading the program is listed under


def parse_program_index(html: str) -> list[ProgramRef]:
    refs: list[ProgramRef] = []
    seen: set[int] = set()
    for a in _soup(html).select("a[href*='preview_program.php']"):
        qs = parse_qs(urlparse(a["href"]).query)
        poid = qs.get("poid", [""])[0]
        name = a.get_text(" ", strip=True)
        if poid.isdigit() and name and int(poid) not in seen:
            seen.add(int(poid))
            heading = a.find_previous("h2")
            refs.append(ProgramRef(name, int(poid), heading.get_text(" ", strip=True) if heading else ""))
    return refs


def in_scope(name: str) -> bool:
    if any(word in name for word in _EXCLUDED):
        return False
    if "," not in name:
        return False
    return bool(_DEGREE.match(name.rsplit(",", 1)[1].strip()))


def parse_program_page(html: str) -> dict:
    soup = _soup(html)
    h1 = soup.select_one("h1#acalog-content")
    sections = []
    for div in soup.select("div.acalog-core"):
        heading = div.find(re.compile(r"^h[1-6]$"))
        items: list[dict] = []
        for li in div.find_all("li"):
            classes = li.get("class", [])
            text = li.get_text(" ", strip=True)
            if "acalog-course" in classes:
                m = _COURSE_ID.match(text)
                if m:
                    title = text[len(m.group(1)):].lstrip(": ").strip()
                    items.append({"kind": "course", "id": m.group(1), "title": title})
            elif text.lower() == "or":
                items.append({"kind": "or"})
            elif text:
                items.append({"kind": "text", "text": text})
        sections.append({
            "heading": heading.get_text(" ", strip=True) if heading else "",
            "level": int(heading.name[1]) if heading else 0,
            "items": items,
        })
    return {"name": h1.get_text(" ", strip=True) if h1 else "", "sections": sections}
