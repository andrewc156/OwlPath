"""Crawl a whole catalog level (every course listing, every in-scope program page) into a committed snapshot."""
import dataclasses
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config
from .catalog_html import (ProgramRef, course_coids, in_scope, listing_page_count, parse_nav, parse_prefixes,
                           parse_program_index, parse_program_page)
from .catalog_pdf import parse_listing
from .crawl import Crawler, CrawlStopped
from .fetch import cache_path
from .model import RawCourse


@dataclass
class Snapshot:
    level: str
    courses: dict[str, RawCourse]
    programs: list[dict]
    out_of_scope: list[ProgramRef]


def crawl_level(level: str, crawler: Crawler) -> Snapshot:
    catoid = config.catoid(level)
    index_url = config.PROGRAMS_INDEX_URL.format(catoid=catoid, navoid=config.CATALOGS[level]["programs_navoid"])
    index_html = crawler.get(index_url, "preview_program.php").html
    refs = parse_program_index(index_html)

    nav = parse_nav(index_html)
    if "Courses" not in nav:
        raise CrawlStopped(f"{index_url} has no Courses link in its navigation")
    navoid = nav["Courses"]
    courses_html = crawler.get(config.COURSES_PAGE_URL.format(catoid=catoid, navoid=navoid), "filter[27]").html

    coids: dict[str, int] = {}
    listed: dict[str, RawCourse] = {}
    for prefix in parse_prefixes(courses_html):
        def listing_url(page: int) -> str:
            return config.LISTING_PAGE_URL.format(prefix=prefix, page=page, catoid=catoid, navoid=navoid)
        first = crawler.get(listing_url(1), "Credit Hour")
        pages = [first] + [crawler.get(listing_url(n), "Credit Hour")
                           for n in range(2, listing_page_count(first.html) + 1)]
        for page in pages:
            for cid, found in course_coids(page.html).items():
                coids.setdefault(cid, found)
            for cid, course in parse_listing(page.text, "").items():
                if cid in listed:
                    raise ValueError(f"{cid} appears in more than one listing ({prefix})")
                listed[cid] = course

    programs: list[dict] = []
    out_of_scope: list[ProgramRef] = []
    for ref in refs:
        if not in_scope(ref.name):
            out_of_scope.append(ref)
            continue
        url = config.PROGRAM_PAGE_URL.format(catoid=catoid, poid=ref.poid)
        html = crawler.get(url, "acalog-core").html
        for cid, found in course_coids(html).items():
            coids.setdefault(cid, found)
        programs.append({**parse_program_page(html), "poid": ref.poid, "url": url, "college": ref.college})

    courses = {}
    for cid, course in listed.items():
        if cid in coids:
            url = config.COURSE_PAGE_URL.format(catoid=catoid, coid=coids[cid])
        else:
            url = config.COURSE_LISTING_URL.format(prefix=cid.split()[0], catoid=catoid)
        courses[cid] = dataclasses.replace(course, url=url)
    return Snapshot(level, courses, programs, out_of_scope)


def _dir(level: str, data_dir: Path) -> Path:
    return Path(data_dir) / "catalog" / level


def _dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def write_snapshot(snap: Snapshot, data_dir: Path = config.DATA_DIR) -> None:
    out = _dir(snap.level, data_dir)
    out.mkdir(parents=True, exist_ok=True)
    head = {"catalogYear": config.CATALOG_YEAR, "level": snap.level, "catoid": config.catoid(snap.level)}
    _dump(out / "catalog-courses.json", {**head, "courses": {
        cid: {"title": c.title, "credits": c.credits, "description": c.description,
              "prereqText": c.prereq_text, "coreqText": c.coreq_text, "url": c.url, "warnings": c.warnings}
        for cid, c in snap.courses.items()}})
    _dump(out / "programs.json", {**head, "programs": snap.programs,
                                  "outOfScope": [{"poid": r.poid, "name": r.name} for r in snap.out_of_scope]})


def load_courses(level: str, data_dir: Path = config.DATA_DIR) -> dict[str, RawCourse]:
    raw = json.loads((_dir(level, data_dir) / "catalog-courses.json").read_text(encoding="utf-8"))
    return {cid: RawCourse(id=cid, title=c["title"], credits=c["credits"], description=c["description"],
                           prereq_text=c["prereqText"], coreq_text=c["coreqText"], url=c["url"],
                           warnings=list(c["warnings"]))
            for cid, c in raw["courses"].items()}


def load_programs(level: str, data_dir: Path = config.DATA_DIR) -> list[dict]:
    return json.loads((_dir(level, data_dir) / "programs.json").read_text(encoding="utf-8"))["programs"]


def clear_catalog_cache(cache_dir: Path, catoid: int) -> int:
    """Delete cached pages of one catalog (its URL names `catoid=` or `cur_cat_oid=`); returns how many."""
    pattern = re.compile(rf"(?:catoid|cur_cat_oid)={catoid}(?!\d)")
    deleted = 0
    for url_file in Path(cache_dir).glob("*.url"):
        url = url_file.read_text(encoding="utf-8").strip()
        if not pattern.search(url):
            continue
        for suffix in (".html", ".txt", ".url"):
            cache_path(cache_dir, url, suffix).unlink(missing_ok=True)
        deleted += 1
    return deleted
