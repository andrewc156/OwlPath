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
