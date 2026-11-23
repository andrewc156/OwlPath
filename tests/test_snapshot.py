import json
from urllib.robotparser import RobotFileParser

import pytest

from owlpath_pipeline import config
from owlpath_pipeline.crawl import Crawler, LoadedPage
from owlpath_pipeline.fetch import cache_path
from owlpath_pipeline.snapshot import (clear_catalog_cache, crawl_level, load_courses, load_programs,
                                       write_snapshot)

CAT = 84
INDEX = config.PROGRAMS_INDEX_URL.format(catoid=CAT, navoid=config.CATALOGS["undergraduate"]["programs_navoid"])
COURSES_URL = config.COURSES_PAGE_URL.format(catoid=CAT, navoid=9372)


def listing_url(prefix):
    return config.LISTING_PAGE_URL.format(prefix=prefix, page=1, catoid=CAT, navoid=9372)


def program_url(poid):
    return config.PROGRAM_PAGE_URL.format(catoid=CAT, poid=poid)


def listing(cid, title, link=""):
    return (f"<div>{link}</div>",
            f"{cid}: {title}\n3 Credit Hours\nA course about {title}.\nPrerequisite: None\n")


def site(dup=False):
    link = ("<a onclick=\"showCourse('84', '111', this);\">AA 1000: Alpha</a>")
    aa_html, aa_text = listing("AA 1000", "Alpha", link)
    bb_html, bb_text = listing("BB 2000", "Beta")
    if dup:
        bb_text += "AA 1000: Alpha again\n3 Credit Hours\nDuplicate.\n"
    prefix_select = ("<select name='filter[27]'><option value='-1'>All</option>"
                     "<option value='AA'>AA</option><option value='BB'>BB</option></select>")
    return {
        INDEX: LoadedPage(200, "<a href='/preview_program.php?catoid=84&poid=5'>Aa, BS in Alpha</a>"
                               "<a href='/preview_program.php?catoid=84&poid=6'>Aa Minor</a>"
                               "<a href='content.php?catoid=84&navoid=9372'>Courses</a>", "index"),
        COURSES_URL: LoadedPage(200, prefix_select, "courses"),
        listing_url("AA"): LoadedPage(200, aa_html + "Credit Hour", aa_text),
        listing_url("BB"): LoadedPage(200, bb_html + "Credit Hour", bb_text),
        program_url(5): LoadedPage(
            200, "<h1 id='acalog-content'>Aa, BS in Alpha</h1><div class='acalog-core'><h2>Core</h2>"
                 "<ul><li class='acalog-course'>AA 1000 - Alpha</li></ul></div>", "program"),
    }


class FakeLoader:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def load(self, url):
        self.calls.append(url)
        return self.pages[url]


def make_crawler(tmp_path, pages):
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Crawl-delay: 0"])
    return Crawler(tmp_path, FakeLoader(pages), rp, lambda s: None, lambda: 0.0)


def test_crawl_level_builds_snapshot(tmp_path):
    snap = crawl_level("undergraduate", make_crawler(tmp_path, site()))
    assert set(snap.courses) == {"AA 1000", "BB 2000"}
    assert [p.name for p in snap.out_of_scope] == ["Aa Minor"]
    assert snap.courses["AA 1000"].url.endswith("coid=111")
    assert "filter%5B27%5D=BB" in snap.courses["BB 2000"].url
    assert [p["poid"] for p in snap.programs] == [5]
    assert snap.programs[0]["url"] == program_url(5) and snap.programs[0]["name"] == "Aa, BS in Alpha"


def test_snapshot_round_trip(tmp_path):
    snap = crawl_level("undergraduate", make_crawler(tmp_path / "c", site()))
    snap.courses["BB 2000"].warnings.append("odd prereq")
    write_snapshot(snap, tmp_path)
    assert load_courses("undergraduate", tmp_path) == snap.courses
    assert load_programs("undergraduate", tmp_path) == snap.programs
    out = json.loads((tmp_path / "catalog" / "undergraduate" / "programs.json").read_text())
    assert out["outOfScope"] == [{"poid": 6, "name": "Aa Minor"}] and out["catoid"] == CAT


def test_duplicate_course_across_listings_is_error(tmp_path):
    with pytest.raises(ValueError, match="AA 1000"):
        crawl_level("undergraduate", make_crawler(tmp_path, site(dup=True)))


def test_refresh_clears_only_that_catalog(tmp_path):
    urls = {
        "https://x/content.php?catoid=84&navoid=1": True,
        "https://x/content.php?filter%5B27%5D=AA&cur_cat_oid=84&expand=1": True,
        "https://x/content.php?catoid=83&navoid=1": False,
        "https://x/content.php?catoid=840&navoid=1": False,
    }
    for url in urls:
        for suffix, body in ((".html", "h"), (".txt", "t"), (".url", url + "\n")):
            cache_path(tmp_path, url, suffix).write_text(body)
    assert clear_catalog_cache(tmp_path, 84) == 2
    for url, gone in urls.items():
        assert cache_path(tmp_path, url).exists() is not gone
        assert cache_path(tmp_path, url, ".txt").exists() is not gone
