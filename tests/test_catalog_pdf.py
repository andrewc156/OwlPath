"""The PDF listing reader, run on a few saved listings kept as fixtures (the snapshot reads the same text)."""
from pathlib import Path

import pytest

from owlpath_pipeline.catalog_pdf import load_catalog, parse_listing, pdf_text

PDFS = Path(__file__).resolve().parent / "fixtures" / "pdf"
URL = "https://catalog.kennesaw.edu/listing?prefix=CS"
META = {"program": {"id": "bs-cs", "name": "BS Computer Science",
                    "filters": [{"label": "AI", "groups": ["conc-ai"]}]}, "choices": []}


@pytest.fixture(scope="module")
def cs():
    return parse_listing(pdf_text(PDFS / "cs.pdf"), URL)


@pytest.fixture(scope="module")
def ug_dir(tmp_path_factory):
    """The undergraduate listings (cs, cse, math, stat) in a folder of their own, as load_catalog reads one level."""
    import shutil

    d = tmp_path_factory.mktemp("undergraduate")
    for name in ("cs", "cse", "math", "stat"):
        shutil.copy(PDFS / f"{name}.pdf", d)
    return d


@pytest.fixture(scope="module")
def catalog(ug_dir):
    return load_catalog(ug_dir, 84)


def test_course_fields_cs3305(cs):
    c = cs["CS 3305"]
    assert (c.id, c.title, c.credits, c.url) == ("CS 3305", "Data Structures", "3", URL)
    assert c.prereq_text.startswith("(MATH 2345 or CSE 2300) and ((CSE 1322 and CSE 1322L)")
    assert c.coreq_text is None
    assert c.description.startswith("This course introduces data structures, specification")  # ligature normalized
    assert "Course Learning Outcomes" not in c.description


def test_concurrent_becomes_coreq(catalog):
    c = catalog["CSE 1321"]
    assert c.coreq_text == "CSE 1321L" and c.prereq_text is None


def test_prereq_wrapped_over_two_lines_is_joined(cs):
    p = cs["CS 4492"].prereq_text
    assert "CS 4524 or CS 4612" in p and p.endswith("AI 4732).")


def test_variable_credits_kept_as_string(cs):
    assert cs["CS 4400"].credits == "1-3"


def test_page_footers_and_catalog_notes_stay_out_of_fields(catalog):
    for c in catalog.values():
        for text in (c.description, c.prereq_text or "", c.coreq_text or ""):
            assert "https://" not in text and "Kennesaw State University" not in text
            assert "Notes:" not in text and "\xa0" not in text


def test_concurrent_and_corequisite_are_joined():
    text = ("Courses\nXX 1000: Lab Thing\n1 Credit Hours\nConcurrent: XX 1001\n"
            "Corequisite: XX 1002 or XX 1003\nDescription\nA lab.\n")
    c = parse_listing(text, URL)["XX 1000"]
    assert c.coreq_text == "(XX 1001) and (XX 1002 or XX 1003)"


def test_field_split_by_page_footer_is_rejoined():
    text = ("XX 2000: Thing\n3 Credit Hours\nPrerequisite: XX 1000 and\n"
            "11/8/26, 12:00 AM Courses - Kennesaw State University\n"
            "https://catalog.kennesaw.edu/content.php?x=1 1/2\n"
            "XX 1001\nDescription\nWords here.\n")
    assert parse_listing(text, URL)["XX 2000"].prereq_text == "XX 1000 and XX 1001"


def test_load_catalog_reads_every_pdf_with_prefix_urls(catalog):
    assert {"CS 3305", "CSE 1322", "MATH 1190", "STAT 2332"} <= catalog.keys()
    assert "filter%5B27%5D=MATH" in catalog["MATH 1190"].url


def test_build_runs_on_saved_catalog(ug_dir):
    from owlpath_pipeline.build import catalog_get_raw, build_dataset
    from owlpath_pipeline.validate import validate_dataset

    dataset, _ = build_dataset({"CS 3305": ["major-required"], "CSE 1322": ["core-field"]},
                               catalog_get_raw(directory=ug_dir), {}, META)
    assert validate_dataset(dataset) == []
    assert {"CS 3305", "CSE 1322", "CSE 1321"} <= {c["id"] for c in dataset["courses"]}
    with pytest.raises(KeyError):
        catalog_get_raw(directory=ug_dir)("ZZZ 9999")


def test_page_chrome_is_not_in_any_field(catalog):
    for c in catalog.values():
        for text in (c.title, c.description, c.prereq_text or "", c.coreq_text or ""):
            assert "Contract All Courses" not in text and "Undergraduate Catalog" not in text


def test_unrecognized_line_and_empty_description_warn():
    text = "XX 3000: Thing\n3 Credit Hours\nPrerequisites: XX 1000\n"
    c = parse_listing(text, URL)["XX 3000"]
    assert c.prereq_text is None
    assert any("unrecognized line: Prerequisites: XX 1000" in w for w in c.warnings)
    assert any("empty description" in w for w in c.warnings)


def test_reader_warnings_reach_the_build_report():
    from owlpath_pipeline.build import build_dataset

    raw = parse_listing("XX 3000: Thing\n3 Credit Hours\nDescription\n", URL)
    _, warnings = build_dataset({"XX 3000": ["major-required"]}, raw.__getitem__, {}, META)
    assert "XX 3000: empty description" in warnings


def test_pdf_with_no_courses_is_an_error(tmp_path):
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(612, 792)
    with open(tmp_path / "blank.pdf", "wb") as f:
        w.write(f)
    with pytest.raises(ValueError, match="blank.pdf"):
        load_catalog(tmp_path, 84)


def test_graduate_listing_without_description_label():
    # Graduate listings print the description straight after the field lines.
    text = ("STAT 7210: Applied Regression Analysis\n3 Credit Hours\n"
            "Prerequisite: DS 7020 and STAT 7100\n"
            "Topics include simple linear regression, inferences,\nand multiple regression.\n"
            "Course Learning Outcomes\n1. Fit models.\n")
    c = parse_listing(text, "")["STAT 7210"]
    assert c.prereq_text == "DS 7020 and STAT 7100"
    assert c.description == "Topics include simple linear regression, inferences, and multiple regression."
    assert c.warnings == []


def test_saved_graduate_listing_splits_prereq_from_description():
    c = parse_listing(pdf_text(PDFS / "stat-graduate.pdf"), "")["STAT 7010"]
    assert c.prereq_text == "STAT 7220 and STAT 7210"
    assert c.description.startswith("Fundamental concepts of probability")


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "catalog"
CHROME_TEXT = ("Page: 1 | 2\nContract All Courses | Print this Page\nAdd to Portfolio (opens a new window)\n"
               "All publications © 2026 Kennesaw State University.\nPowered by Modern Campus Catalog™.")


@pytest.mark.parametrize("name", ["ug-courses-stat", "grad-courses-ds"])
def test_last_course_of_a_listing_page_has_no_footer_text(name):
    courses = parse_listing((FIXTURES / f"{name}.txt").read_text(encoding="utf-8"), "")
    last = list(courses.values())[-1]
    for text in (last.title, last.description, last.prereq_text or "", last.coreq_text or ""):
        for chrome in ("Contract All Courses", "Print this Page", "Add to Portfolio", "Modern Campus", "Page:"):
            assert chrome not in text


def test_crawled_stat_listing_gives_the_same_records_as_the_saved_pdf():
    """Spec testing list: the crawled page text of the undergraduate STAT listing and the PDF saved by hand give
    the same courses, prerequisites and descriptions. They agree field for field, so the comparison needs no
    whitespace or hyphen-break normalization."""
    page = parse_listing((FIXTURES / "ug-courses-stat.txt").read_text(encoding="utf-8"), "")
    saved = parse_listing(pdf_text(PDFS / "stat.pdf"), "")
    assert len(page) == 10 and page == saved


def test_pagination_and_footer_end_the_listing():
    text = "XX 1000: Thing\n3 Credit Hours\nDescription\nWords here.\n" + CHROME_TEXT
    assert parse_listing(text, "")["XX 1000"].description == "Words here."


def test_bare_print_this_page_ends_the_listing():
    text = "XX 1000: Thing\n3 Credit Hours\nDescription\nWords here.\nPrint this Page\n"
    assert parse_listing(text, "")["XX 1000"].description == "Words here."


def test_footer_above_the_first_course_still_parses_every_course():
    text = ("Contract All Courses | Print this Page\nAdd to Portfolio (opens a new window)\n"
            "XX 1000: One\n3 Credit Hours\nDescription\nFirst.\nXX 1001: Two\n3 Credit Hours\nDescription\nSecond.\n"
            + CHROME_TEXT)
    courses = parse_listing(text, "")
    assert list(courses) == ["XX 1000", "XX 1001"] and courses["XX 1001"].description == "Second."


def test_graduate_course_with_no_field_lines_keeps_its_description():
    text = "XX 7000: Thing\n3 Credit Hours\nA course about things.\nNote: This course may be cross-leveled with XX 4000.\n"
    c = parse_listing(text, "")["XX 7000"]
    assert c.description == "A course about things. Note: This course may be cross-leveled with XX 4000."
    assert c.prereq_text is None and c.warnings == []


@pytest.mark.parametrize("line, credits", [
    ("Variable 1-12 Credit Hours", "1-12"), ("Variable 1-3 Credit Hours", "1-3"),
    ("1-3 (Repeatable) Credit Hours", "1-3"), ("1-4 Variable Credit Hours", "1-4"),
    ("1-9 repeatable Credit Hours", "1-9"), ("1 - 3 Credit Hours", "1-3"), ("3 Credit Hours", "3")])
def test_credit_hour_forms(line, credits):
    c = parse_listing(f"XX 1000: Thing\n{line}\nDescription\nWords.\n", "")["XX 1000"]
    assert c.credits == credits and c.warnings == []
