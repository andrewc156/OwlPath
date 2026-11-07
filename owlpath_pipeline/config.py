"""Fixed settings for the 2026-27 build. See docs/mvp-spec.md (polite-scraping rules)."""
from pathlib import Path

CATALOG_YEAR = "2026-2027"
CATOID = 84
CATALOG_BASE = "https://catalog.kennesaw.edu"

# Honest, generic identification. Never spoof a browser.
USER_AGENT = "OwlPath-data-builder/0.1 (+https://github.com/andrewc156/OwlPath)"

# robots.txt asks for 120 s; also used when a host gives no crawl-delay.
DEFAULT_CRAWL_DELAY = 120.0

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(".cache/http")
DATA_DIR = REPO_ROOT / "data" / CATALOG_YEAR
SCHEMA_PATH = REPO_ROOT / "data" / "schema" / "courses.schema.json"

# Banner (Owl Express) public course detail pages: cross-check only, the catalog wins.
BANNER_TERM = "202608"  # Fall Semester 2026 (confirmed on the CSE 1322 page)
BANNER_URL = ("https://owlexpress.kennesaw.edu/prodban/bwckctlg.p_disp_course_detail"
              "?cat_term_in={term}&subj_code_in={subj}&crse_numb_in={num}")
