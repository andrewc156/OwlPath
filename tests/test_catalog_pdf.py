"""Catalog course listings saved from a browser as PDFs (the website blocks automated clients)."""
from pathlib import Path

import pytest

from owlpath_pipeline.catalog_pdf import load_catalog, parse_listing, pdf_text

CATALOG = Path(__file__).resolve().parent.parent / "data" / "2026-2027" / "catalog"
URL = "https://catalog.kennesaw.edu/listing?prefix=CS"


@pytest.fixture(scope="module")
def cs():
    return parse_listing(pdf_text(CATALOG / "cs.pdf"), URL)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG)


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
    assert {"AI 4267", "ENGL 1102", "CS 3305", "CSE 1322", "MATH 1190", "STAT 2332", "SWE 3313", "IT 1114", "TCOM 2010"} <= catalog.keys()
    assert "filter%5B27%5D=MATH" in catalog["MATH 1190"].url


def test_build_runs_on_saved_catalog():
    from owlpath_pipeline.build import catalog_get_raw, build_dataset
    from owlpath_pipeline.validate import validate_dataset

    dataset, _ = build_dataset({"CS 3305": ["major-required"], "CSE 1322": ["core-field"]},
                               catalog_get_raw(CATALOG), {})
    assert validate_dataset(dataset) == []
    assert {"CS 3305", "CSE 1322", "CSE 1321"} <= {c["id"] for c in dataset["courses"]}
    with pytest.raises(KeyError):
        catalog_get_raw(CATALOG)("ZZZ 9999")


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
    _, warnings = build_dataset({"XX 3000": ["major-required"]}, raw.__getitem__, {})
    assert "XX 3000: empty description" in warnings


def test_pdf_with_no_courses_is_an_error(tmp_path):
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(612, 792)
    with open(tmp_path / "blank.pdf", "wb") as f:
        w.write(f)
    with pytest.raises(ValueError, match="blank.pdf"):
        load_catalog(tmp_path)
