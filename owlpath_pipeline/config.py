"""Fixed settings for the 2026-27 build. See docs/mvp-spec.md (polite-scraping rules)."""
from pathlib import Path

CATALOG_YEAR = "2026-2027"
CATALOG_BASE = "https://catalog.kennesaw.edu"

# Honest, generic identification. Never spoof a browser.
USER_AGENT = "OwlPath-data-builder/0.1 (+https://github.com/andrewc156/OwlPath)"

# robots.txt asks for 120 s; also used when a host gives no crawl-delay.
DEFAULT_CRAWL_DELAY = 120.0

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(".cache/http")
DATA_DIR = REPO_ROOT / "data" / CATALOG_YEAR
SCHEMA_PATH = REPO_ROOT / "data" / "schema" / "courses.schema.json"

# One folder per major under DATA_DIR: program.json, overrides.json, courses.json, reports.
PROGRAMS = ("bs-cs", "bs-dsa", "ms-dsa")


def program_dir(program: str) -> Path:
    return DATA_DIR / program

# Banner (Owl Express) public course detail pages: cross-check only, the catalog wins.
BANNER_TERM = "202608"  # Fall Semester 2026 (confirmed on the CSE 1322 page)
BANNER_URL = ("https://owlexpress.kennesaw.edu/prodban/bwckctlg.p_disp_course_detail"
              "?cat_term_in={term}&subj_code_in={subj}&crse_numb_in={num}")

# KSU publishes separate undergraduate and graduate catalogs, each with its own catoid. Every major names
# its catalog with "level" in program.json. catoid None means not set up yet: building refuses.
CATALOGS = {
    "undergraduate": {"name": "Undergraduate", "catoid": 84},
    "graduate": {"name": "Graduate", "catoid": 83},  # from the MS DSA program page URL
}

# The catalog site blocks automated clients (HTTP 202), so its expanded "Courses"
# listing is saved by hand as one PDF per prefix, in catalog/<level>/. Each course links to its listing.
CATALOG_DIR = DATA_DIR / "catalog"
COURSE_LISTING_URL = (CATALOG_BASE + "/content.php?filter%5B27%5D={prefix}&filter%5B32%5D=1"
                      "&cur_cat_oid={catoid}&expand=1")


def catoid(level: str) -> int:
    if level not in CATALOGS:
        raise ValueError(f"unknown catalog level {level!r}; expected one of {sorted(CATALOGS)}")
    oid = CATALOGS[level]["catoid"]
    if oid is None:
        raise ValueError(f"the {level} catalog's catoid isn't set; add it to CATALOGS in owlpath_pipeline/config.py")
    return oid


def catalog_pdf_dir(level: str) -> Path:
    catoid(level)  # reject unknown or unset levels before reading any PDFs
    return CATALOG_DIR / level
