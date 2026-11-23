# OwlPath All-Majors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. The user chose subagent-driven execution. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** approved 2026-11-22. **Not started.** Don't begin until the user says to run it.

**Goal:** Cover every KSU degree program (2026–27 undergraduate and graduate catalogs) by crawling the catalog honestly, drafting each major automatically, and publishing clean builds labeled "not yet checked".

**Architecture:**
- A Playwright-driven crawler, which honors robots.txt and identifies itself honestly, caches catalog pages and writes a committed per-level snapshot.
- The pipeline drafts `program.json` from each program page, then builds every major from the snapshot with shared per-level overrides. It sorts majors into checked, auto-built and held, and writes `STATUS.md` and a `majors.json` index.
- The web app bundles only the index and lazy-loads each major's `courses.json`.

**Tech Stack:** Python 3.13, Playwright (Chromium), BeautifulSoup, jsonschema, pytest; React 19, Vite 8, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-22-owlpath-all-majors-design.md`. Read it before any task. It wins over this plan where they differ.

## Global Constraints

- **robots.txt:**
  - Wait `crawl-delay: 120` seconds between catalog page loads. The bot check's automatic reload belongs to the same visit, and the next page waits 120 s from the end of the visit.
  - Never request `/ajax/`, `/search_advanced.php`, `/portfolio.php` or `/portfolio_nopop.php`.
- **User-Agent:** exactly `config.USER_AGENT` (`OwlPath-data-builder/0.1 (+https://github.com/andrewc156/OwlPath)`). No stealth plugins, fingerprint changes, proxies or CAPTCHA services.
- **Allowed requests:** only catalog-host (`catalog.kennesaw.edu`) **documents** and any request to a host ending in `.token.awswaf.com`. Abort everything else.
- **Stopping the crawl:** stop and report when any of these happen:
  - robots.txt isn't readable (anything but 200);
  - the bot check doesn't pass within 60 s;
  - a page ends on a non-200 status;
  - a page lacks its expected content.

  Never retry in a loop, and never escalate. Rerunning resumes from the cache.
- **Last-request record:** share `.cache/http/.last-request.json` with `PoliteFetcher`.
- **Catalogs:**
  - Undergraduate: catoid 84, Academic Programs navoid 9371, Courses navoid 9372.
  - Graduate: catoid 83, Academic Programs navoid 9027 (verify from the graduate catalog's navigation). Its Courses navoid is discovered from the navigation.
- **Existing major ids stay:** `bs-cs` (catoid 84, poid 11680), `bs-dsa` (84, 11867) and `ms-dsa` (83, 11541).
- **Scope:** degree programs only (bachelor's, master's, specialist, doctoral). No minors, certificates or endorsements.
- **Progress:** stored under `owlpath:v1:2026-2027:status` and keyed by course id. Never rename the key, and never drop a well-formed id.
- **Label copy** on auto-built majors: `Auto-built from the catalog and not yet checked by a person. Confirm with the catalog and your advisor.` The picker tag is `not yet checked`.
- **Fix rule:** a fix that would change any **checked** major waits for the user's OK before it's committed (user decision).
- **CI:** CI never needs a browser. Playwright is an optional `crawl` extra, and no test imports it.
- **Versions:** Python 3.13, and Node ≥ 22.12 for the web app.
- **Branch:** work on `feat/all-majors`, created from `main`, with one PR at the end (Task 12).
- **Commit messages** end with these two lines:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Afq1LGu4UMPodxjfQzhEjQ
  ```

## Review Focus

1. **The bot check starts failing partway through a long crawl.** The crawl should stop, keep every page fetched so far, and resume later without refetching them. Test in Task 1: `test_stop_midway_keeps_cache_and_resumes`.
2. **A program page has no recognizable courses** (all free text). The major should be held with "no courses found", never shipped as an empty map. Test in Task 7: `test_page_without_courses_is_held`.
3. **Two programs produce the same id.** Both should be kept, with distinct ids, and neither folder overwrites the other. Test in Task 7: `test_colliding_ids_get_poid_suffix`.
4. **A shared link or saved choice names a major that's now held or gone.** It should open `bs-cs` without errors. Test in Task 10: `resolveMajor falls back to bs-cs for an unknown major`.
5. **A major's data fails to load** (offline, or an old tab after a deploy). The app should show "Couldn't load this major." with a Retry button, not a blank page. Test in Task 10: `fetchMajor returns an error state when loading fails`.

---

### Task 1: Crawler core

**Files:**
- Create: `owlpath_pipeline/crawl.py`
- Modify: `owlpath_pipeline/fetch.py` (move the last-request and cache-path logic into module functions; `PoliteFetcher` calls them)
- Modify: `owlpath_pipeline/config.py`
- Test: `tests/test_crawl.py`

**Interfaces:**
- Produces in `fetch.py`:
  - `load_last_request(cache_dir: Path) -> dict[str, float]`
  - `save_last_request(cache_dir: Path, origin: str, when: float) -> None`
  - `cache_path(cache_dir: Path, url: str, suffix: str = ".html") -> Path`, using the same sha256 naming as today.
- Produces in `config.py`:
  - `BOT_CHECK_HOST_SUFFIX = ".token.awswaf.com"`
  - `CRAWL_CHALLENGE_TIMEOUT = 60.0`
  - `CATALOGS[level]["programs_navoid"]`: 9371 for undergraduate, 9027 for graduate.
  - `PROGRAMS_INDEX_URL`, `COURSES_PAGE_URL` (both `/content.php?catoid={catoid}&navoid={navoid}`)
  - `LISTING_PAGE_URL`: the spec's expanded print listing, with `{prefix}`, `{page}`, `{catoid}` and `{navoid}`.
  - `PROGRAM_PAGE_URL = CATALOG_BASE + "/preview_program.php?catoid={catoid}&poid={poid}&print"`
  - `COURSE_PAGE_URL = CATALOG_BASE + "/preview_course_nopop.php?catoid={catoid}&coid={coid}"`
  - `KNOWN_PROGRAM_IDS = {(84, 11680): "bs-cs", (84, 11867): "bs-dsa", (83, 11541): "ms-dsa"}`
- Produces in `crawl.py`:
  - `@dataclass(frozen=True) LoadedPage(status: int, html: str, text: str)`
  - `class PageLoader(Protocol): def load(self, url: str) -> LoadedPage`
  - `class CrawlStopped(Exception)`
  - `read_robots(origin: str, http_get: HttpGet, user_agent: str = config.USER_AGENT) -> RobotFileParser`. Raises `CrawlStopped` unless the status is 200.
  - `allow_request(url: str, resource_type: str, robots: RobotFileParser, user_agent: str = config.USER_AGENT) -> bool`
  - `Crawler(cache_dir: Path, loader: PageLoader, robots: RobotFileParser, sleep: Callable[[float], None], clock: Callable[[], float], origin: str = config.CATALOG_BASE)`, with these methods:
    - `get(url: str, expect: str) -> LoadedPage`: serves from the cache, or loads after the delay. Writes `.html`, `.txt` and `.url` beside each other. Raises `fetch.DisallowedError` before loading a disallowed URL. Raises `CrawlStopped` on a non-200 status or when `expect` isn't in the html, and caches nothing in either case.
    - `cached(url: str) -> LoadedPage | None`

- [ ] **Step 1: Write the failing tests.** Use a `FakeLoader` (url → `LoadedPage`, recording calls) and the fake clock and sleep pattern from `tests/test_fetch.py`.

```python
def test_disallowed_url_is_never_loaded(tmp_path): ...          # robots "Disallow: /ajax/"; get(f"{HOST}/ajax/x") raises DisallowedError; loader.calls == []
def test_waits_crawl_delay_between_pages_and_across_crawlers(tmp_path):
    # two crawlers on the same cache dir; second page waits 120 s after the first load ends
    assert slept == [120.0]
    assert load_last_request(tmp_path)[HOST] == clock_after_second_load
def test_polite_fetcher_honours_crawler_last_request(tmp_path): ...  # PoliteFetcher after a Crawler load sleeps 120 s
def test_cached_page_is_not_loaded_again(tmp_path): ...         # new Crawler, same dir: loader.calls has the url once; text and html round-trip
def test_non_200_stops_and_caches_nothing(tmp_path): ...        # status 202 -> CrawlStopped; cache_path(...).exists() is False
def test_missing_expected_content_stops(tmp_path): ...           # expect="Credit Hour" absent -> CrawlStopped
def test_unreadable_robots_stops(): ...                          # read_robots with status 503 -> CrawlStopped
def test_stop_midway_keeps_cache_and_resumes(tmp_path):
    # loader fails on the 3rd of 4 urls; rerun with a healthy loader loads only urls 3 and 4
    assert healthy.calls == [u3, u4]
def test_allow_request_rules():
    assert allow_request(f"{CAT}/content.php?catoid=84", "document", robots)
    assert not allow_request(f"{CAT}/js/jquery.js", "script", robots)
    assert not allow_request(f"{CAT}/ajax/preview_course.php", "document", robots)
    assert allow_request("https://x.y.us-east-1.token.awswaf.com/a/challenge.js", "script", robots)
    assert not allow_request("https://ssl.google-analytics.com/ga.js", "script", robots)
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_crawl.py -v`
  Expected: FAIL with `ModuleNotFoundError: owlpath_pipeline.crawl`.
- [ ] **Step 3: Implement the `fetch.py` helpers, the `config.py` values and `crawl.py` with the signatures above.** The delay is `robots.crawl_delay(user_agent) or config.DEFAULT_CRAWL_DELAY`. Wait from `max(shared record, own last)`. Save the record after each load returns.
- [ ] **Step 4: Run the whole suite and confirm it passes.**
  Run: `.venv/bin/pytest -q`
  Expected: all pass, including every existing `test_fetch.py` test.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline/crawl.py owlpath_pipeline/fetch.py owlpath_pipeline/config.py tests/test_crawl.py
  git commit -m "feat: polite catalog crawler core with shared crawl delay"
  ```

### Task 2: Browser loader and fixture capture

**Files:**
- Create: `owlpath_pipeline/browser.py`
- Modify: `owlpath_pipeline/crawl.py` (add the CLI with a `capture` subcommand)
- Modify: `pyproject.toml` (`[project.optional-dependencies] crawl = ["playwright"]`)
- Create: `tests/fixtures/catalog/*.html` and `*.txt` (captured live)

**Interfaces:**
- Consumes: `LoadedPage`, `CrawlStopped`, `allow_request`, `read_robots` and `Crawler` from Task 1.
- Produces:
  - `PlaywrightLoader(robots: RobotFileParser, user_agent: str = config.USER_AGENT, challenge_timeout: float = config.CRAWL_CHALLENGE_TIMEOUT)`
    - It's a context manager: `__enter__` launches headless Chromium with `user_agent` and routes every request through `allow_request`. `__exit__` closes the browser.
    - `load(url) -> LoadedPage` navigates and waits until the main document's last response is 200, meaning the bot check passed and the page reloaded. It returns `page.content()` and `inner_text("body")`. It raises `CrawlStopped("bot check not passed within 60 s")` on timeout.
    - Import `playwright` inside `__enter__` only.
  - CLI: `.venv/bin/python -m owlpath_pipeline.crawl capture <url> <name> --expect <text>` writes `tests/fixtures/catalog/<name>.html` and `<name>.txt` through a real `Crawler`.

- [ ] **Step 1: Install the extra and Chromium.**
  Run: `.venv/bin/pip install -e '.[dev,crawl]' && .venv/bin/python -m playwright install chromium`
  Expected: both finish without errors.
- [ ] **Step 2: Implement `PlaywrightLoader` and the `capture` subcommand.** No unit test here: the live capture in the next step is the check.
- [ ] **Step 3: Capture the fixtures live.** That's 10 pages at 120 s each, about 20 minutes, so run it in the background.
  - Capture order and expected text:
    1. `ug-programs-index`: the undergraduate Academic Programs page, expecting `preview_program.php`.
    2. `ug-courses-stat`: the undergraduate STAT listing page 1, expecting `Credit Hour`.
    3. `ug-bs-cs`, `ug-bs-dsa` and `grad-ms-dsa`: program pages for poids 11680, 11867 and 11541, expecting `acalog-core`.
    4. `grad-programs-index`: navoid 9027.
    5. `grad-courses-ds`: the graduate DS listing, using the Courses navoid read from the graduate index's navigation.
    6. Three differently structured undergraduate majors picked from `ug-programs-index`: a BBA, a nursing degree and an engineering degree, saved as `ug-business`, `ug-nursing` and `ug-engineering`.
  - Expected: every capture succeeds, and the first one logs that the bot check passed under the allow rules. If the bot check fails with scripts blocked, allow only the catalog-host scripts the spike loaded, record why in `browser.py`, and recapture.
- [ ] **Step 4: Confirm CI stays browser-free.**
  Run: `.venv/bin/pytest -q`
  Expected: all pass. `grep -rn "playwright" tests/` prints nothing.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline/browser.py owlpath_pipeline/crawl.py pyproject.toml tests/fixtures/catalog
  git commit -m "feat: Playwright page loader and captured catalog fixtures"
  ```

### Task 3: Catalog page readers

**Files:**
- Create: `owlpath_pipeline/catalog_html.py`
- Test: `tests/test_catalog_html.py`

**Interfaces:**
- Consumes: the fixtures from Task 2, and `catalog_pdf.parse_listing(text, url)`, which is reused as-is for listing text.
- Produces:
  - `parse_nav(html: str) -> dict[str, int]`: navigation link text mapped to navoid.
  - `parse_prefixes(html: str) -> list[str]`: the options of `select[name='filter[27]']`, sorted, excluding `-1` and empty.
  - `listing_page_count(html: str) -> int`: the highest `filter[cpage]=N` in pagination links, or 1 if there are none.
  - `course_coids(html: str) -> dict[str, int]`, read from two kinds of link:
    - prerequisite links whose `onclick` holds `preview_course.php?catoid=…&coid=N` (the link text is the course id);
    - program items holding `showCourse('<catoid>', '<coid>'` (the id is the item text before the colon).
  - `@dataclass(frozen=True) ProgramRef(name: str, poid: int)`
  - `parse_program_index(html: str) -> list[ProgramRef]`
  - `in_scope(name: str) -> bool`
  - `parse_program_page(html: str) -> dict`, which returns:
    ```
    {"name": str,
     "sections": [{"heading": str, "level": int,
                   "items": [{"kind": "course", "id": str, "title": str}
                             | {"kind": "or"}
                             | {"kind": "text", "text": str}]}]}
    ```
    `level` is the heading tag number, h2 → 2. There's one section per `div.acalog-core`, in page order.

- [ ] **Step 1: Write the failing tests.**

```python
def test_nav_has_courses_and_programs(): assert {"Courses": 9372, "Academic Programs": 9371}.items() <= parse_nav(fx("ug-bs-cs.html")).items()
def test_prefixes(): p = parse_prefixes(fx("ug-courses-stat.html")); assert len(p) == 154 and {"STAT", "CSE", "MATH"} <= set(p)
def test_page_count_default_and_paginated():
    assert listing_page_count(fx("ug-courses-stat.html")) == 1
    assert listing_page_count('<a href="content.php?filter%5Bcpage%5D=2">2</a><a href="content.php?filter%5Bcpage%5D=3">3</a>') == 3
def test_coids_from_listing_and_program():
    assert course_coids(fx("ug-courses-stat.html"))["STAT 1401"] == 135058
    assert course_coids(fx("ug-bs-cs.html"))["CSE 1321"] == 136675
def test_program_index(): assert {ProgramRef("Computer Science, B.S.", 11680), ProgramRef("Data Science and Analytics, B.S.", 11867)} <= set(parse_program_index(fx("ug-programs-index.html")))
@pytest.mark.parametrize("name,ok", [("Computer Science, B.S.", True), ("Accounting, B.B.A.", True), ("Data Science and Analytics, M.S.", True),
    ("Analytics and Data Science, Ph.D.", True), ("Educational Leadership, Ed.S.", True), ("Computer Science Minor", False),
    ("Cybersecurity Certificate", False), ("Graduate Certificate in Data Science", False)])
def test_in_scope(name, ok): assert in_scope(name) is ok
def test_bs_cs_program_page():
    p = parse_program_page(fx("ug-bs-cs.html")); s = {x["heading"]: x for x in p["sections"]}
    assert p["name"] == "Computer Science, B.S."
    assert [i["id"] for i in s["Core Field of Study (18 Credit Hours)"]["items"]][:4] == ["CSE 1321", "CSE 1321L", "CSE 1322", "CSE 1322L"]
    assert s["Artificial Intelligence Concentration"]["level"] == 3 and s["Artificial Intelligence Concentration"]["items"] == []
def test_bs_dsa_or_items(): # CSE 2300, or, MATH 2345 appear consecutively in one section
    kinds = [(i["kind"], i.get("id")) for sec in parse_program_page(fx("ug-bs-dsa.html"))["sections"] for i in sec["items"]]
    assert ("course", "CSE 2300") in kinds and kinds[kinds.index(("course", "CSE 2300")) + 1] == ("or", None)
def test_stat_listing_text_parses(): # the spike's result, without PDFs
    c = parse_listing(fx("ug-courses-stat.txt"), "")
    assert len(c) == 10 and c["STAT 3120"].prereq_text == "MATH 1190 or MATH 1179" and all(not x.warnings for x in c.values())
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_catalog_html.py -v`
  Expected: FAIL with an `ImportError`.
- [ ] **Step 3: Implement `catalog_html.py`.** `in_scope` is true when the text after the last comma is a degree abbreviation starting with B, M, D, Ph.D., Ed.S. or Ed.D., and the name contains none of "Minor", "Certificate" or "Endorsement". `bs-dsa`'s "or" marker may be a list item or text between items. Match what the fixture shows.
- [ ] **Step 4: Run the tests and confirm they pass.**
  Run: `.venv/bin/pytest tests/test_catalog_html.py -v`
  Expected: PASS.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline/catalog_html.py tests/test_catalog_html.py
  git commit -m "feat: read catalog navigation, listings and program pages"
  ```

### Task 4: Snapshot crawl, then start the full crawl

**Files:**
- Create: `owlpath_pipeline/snapshot.py`
- Modify: `owlpath_pipeline/crawl.py` (add `<level> [--refresh]` to the CLI)
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `@dataclass Snapshot(level: str, courses: dict[str, RawCourse], programs: list[dict], out_of_scope: list[ProgramRef])`. Each entry in `programs` is `parse_program_page(...)` plus `poid` and `url`.
  - `crawl_level(level: str, crawler: Crawler) -> Snapshot`. Order:
    1. the programs index (expect `preview_program.php`);
    2. the Courses navoid from `parse_nav`;
    3. the courses page (expect `filter[27]`);
    4. every prefix listing page (expect `Credit Hour`);
    5. every in-scope program page (expect `acalog-core`).

    A course URL is `COURSE_PAGE_URL` when its coid was seen on any crawled page, otherwise `COURSE_LISTING_URL`. A course id in two listings raises `ValueError`, as `load_catalog` does.
  - `write_snapshot(snap: Snapshot, data_dir: Path = config.DATA_DIR) -> None` writes two files under `catalog/<level>/`, with `sort_keys` and `indent=1`:
    - `catalog-courses.json`: `{"catalogYear", "level", "catoid", "courses": {id: {"title", "credits", "description", "prereqText", "coreqText", "url", "warnings"}}}`
    - `programs.json`: `{"catalogYear", "level", "catoid", "programs": [...], "outOfScope": [{"poid", "name"}]}`
  - `load_courses(level: str, data_dir: Path = config.DATA_DIR) -> dict[str, RawCourse]`
  - `load_programs(level: str, data_dir: Path = config.DATA_DIR) -> list[dict]`
  - `clear_catalog_cache(cache_dir: Path, catoid: int) -> int`: deletes the cached entries whose `.url` contains `catoid=<c>` or `cur_cat_oid=<c>`, and returns how many it deleted.
  - CLI: `.venv/bin/python -m owlpath_pipeline.crawl undergraduate|graduate [--refresh]`

- [ ] **Step 1: Write the failing tests.** Use a fake site: a `FakeLoader` serving small synthetic pages with an index of one degree and one minor, a courses page with prefixes `AA` and `BB`, one listing each, and one program page.

```python
def test_crawl_level_builds_snapshot(tmp_path):
    snap = crawl_level("undergraduate", crawler)
    assert set(snap.courses) == {"AA 1000", "BB 2000"} and [p.name for p in snap.out_of_scope] == ["Aa Minor"]
    assert snap.courses["AA 1000"].url.endswith("coid=111") and "filter%5B27%5D=BB" in snap.courses["BB 2000"].url
def test_snapshot_round_trip(tmp_path): write_snapshot(snap, tmp_path); assert load_courses("undergraduate", tmp_path) == snap.courses
def test_duplicate_course_across_listings_is_error(): ...       # pytest.raises(ValueError, match="AA 1000")
def test_refresh_clears_only_that_catalog(tmp_path): ...        # entries for catoid 84 deleted, catoid 83 kept; returns count
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_snapshot.py -v`
  Expected: FAIL with an `ImportError`.
- [ ] **Step 3: Implement `snapshot.py` and the level CLI.**
- [ ] **Step 4: Run the whole suite and confirm it passes.**
  Run: `.venv/bin/pytest -q`
  Expected: all pass.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline/snapshot.py owlpath_pipeline/crawl.py tests/test_snapshot.py
  git commit -m "feat: crawl a whole catalog level into a committed snapshot"
  ```
- [ ] **Step 6: Start the full crawl in the background, and don't wait for it.**
  Run: `.venv/bin/python -m owlpath_pipeline.crawl undergraduate && .venv/bin/python -m owlpath_pipeline.crawl graduate`
  Expected: it runs about 15–18 hours, then writes both snapshot files. Tasks 5–10 don't need it. If it stops, read the reason. Rerun only when the cause wasn't a block. On a block, tell the user and stop.

### Task 5: Shared per-level overrides

**Files:**
- Modify: `owlpath_pipeline/build.py`
- Create: `data/2026-2027/catalog/undergraduate/overrides.json` (CS 3622, CSE 3801, CSE 2300, STAT 3125)
- Create: `data/2026-2027/catalog/graduate/overrides.json` (DS 7020, STAT 7100, DS 7900, STAT 7010, STAT 8220)
- Delete: `data/2026-2027/{bs-cs,bs-dsa,ms-dsa}/overrides.json`
- Test: `tests/test_build.py`

**Interfaces:**
- Produces in `build.py`:
  - `check_overrides(overrides: dict, known: set[str]) -> None`. Raises `ValueError` in four cases:
    - the course isn't in `known` ("stale override");
    - the reason is missing or blank;
    - a field outside `reason`, `prereqs`, `coreqs` and `notes`;
    - any `external` leaf ("overrides use course leaves; each major's build decides node or text").
  - `load_overrides(level: str, data_dir: Path = config.DATA_DIR) -> dict`: own level merged over the other level.
  - `level_get_raw(level: str, source: str = "pdf") -> Callable[[str], RawCourse]`: the own level first, then the other level, and `KeyError` if neither has the course. `source` is `"pdf"` or `"snapshot"`. The default flips to `"snapshot"` in Task 11.
  - `build_dataset(program, get_raw, overrides, meta, *, auto: bool = False, notes_out: list[str] | None = None) -> tuple[dict, list[str]]`. Overrides now apply in pass 1, in place of parsing that course's text. String leaves become `{"course": id}`. An override's `notes` replaces that course's notes. Warnings for overridden courses are still dropped.

- [ ] **Step 1: Move the nine overrides.** Keep their reasons, and turn each `{"external": X}` into the plain leaf `"X"` (CSE 2300's MATH 1179).
- [ ] **Step 2: Write the failing tests.** Replace `test_override_for_course_not_in_graph_is_error` and `test_cs_dataset_courses_unchanged_after_move`.

```python
def test_override_applies_before_closure_and_pulls_required_course():
    ds, _ = build_dataset({"AA 1000": ["major-required"]}, Pages(raw("AA 1000", prereq="junk"), raw("BB 2000")),
                          {"AA 1000": {"reason": "r", "prereqs": "BB 2000"}}, META)
    assert course(ds, "BB 2000")["groups"] == ["prereq-only"] and course(ds, "AA 1000")["prereqs"] == "BB 2000"
def test_shared_override_leaf_is_node_in_one_major_and_text_in_another(): ...  # same override {"or": ["BB 2000", "CC 3000"]}; CC 3000 node in major X, {"external": "CC 3000"} in major Y
def test_override_with_external_leaf_is_error(): ...            # check_overrides raises ValueError(match="external")
def test_override_for_course_missing_from_catalog_is_error(): ...  # ValueError(match="stale override")
def test_course_missing_from_own_level_is_found_in_other_level(tmp_path): ...  # level_get_raw("graduate") finds an undergraduate id
@pytest.mark.parametrize("major", ["bs-cs", "bs-dsa", "ms-dsa"])
def test_checked_majors_rebuild_unchanged(major):  # PDF source + shared overrides == committed courses.json
    assert warnings == [] and built == committed
```

- [ ] **Step 3: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_build.py -v`
  Expected: the new tests FAIL.
- [ ] **Step 4: Implement the build changes.** `main` stops reading the major's `overrides.json` and uses `load_overrides(spec["level"])`.
- [ ] **Step 5: Run the whole suite, then rebuild.**
  Run: `.venv/bin/pytest -q && for m in bs-cs bs-dsa ms-dsa; do .venv/bin/python -m owlpath_pipeline.build $m; done && git diff --stat data/`
  Expected: all pass. The `courses.json` diffs show 0 changed lines.
- [ ] **Step 6: Commit.**
  ```bash
  git add -A owlpath_pipeline/build.py tests/test_build.py data/2026-2027
  git commit -m "feat: shared per-level course overrides applied before the closure"
  ```

### Task 6: Phrase notes and the auto-built OR rule

**Files:**
- Modify: `owlpath_pipeline/prereq_parser.py`
- Modify: `owlpath_pipeline/build.py`
- Test: `tests/test_prereq_parser.py`, `tests/test_build.py`

**Interfaces:**
- Produces:
  - In the parser: before tokenizing, whole phrases become NOTE tokens holding their exact text, without the trailing period. The phrases are:
    - `admission to … program` and `acceptance into … program`, matched non-greedily up to the word "program";
    - `(freshman|sophomore|junior|senior|graduate) standing`;
    - `(permission|consent|approval) of (the )?` followed by instructor, department (chair), program director or coordinator (optionally preceded by an uppercase program abbreviation), advisor or dean;
    - `Ph.D. candidacy`.
  - In `build_dataset`, when `auto=True`, after the closure:
    1. Find every OR in a graph course's prerequisites or corequisites with no leaf in the graph.
    2. Add its first course leaf as `prereq-only`, and extend the closure.
    3. Repeat until stable.
    4. Append `"<owner>: added <id> so (<ids>) has an option on the map"` to `notes_out`.

    These are not warnings. `main` writes `notes_out` under a `## Notes` heading in `build-report.md`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_admission_phrase_with_and_inside_is_one_note():
    r = parse_requirement("Admission to the Data Science and Analytics, MS program")
    assert r.expr is None and r.notes == ["Admission to the Data Science and Analytics, MS program"] and r.warnings == []
def test_permission_of_program_coordinator_is_note(): assert parse_requirement("Permission of MSDSA Program Coordinator").warnings == []
def test_course_and_permission_keeps_course_and_note():
    r = parse_requirement("STAT 7210 and permission of the instructor")
    assert r.expr == {"course": "STAT 7210"} and r.notes == ["permission of the instructor"]
# build
def test_auto_major_pulls_first_or_option_onto_map():
    notes = []; ds, w = build_dataset(prog, Pages(raw("AA 1000", prereq="BB 2000 or CC 3000"), raw("BB 2000"), raw("CC 3000")), {}, META, auto=True, notes_out=notes)
    assert w == [] and course(ds, "BB 2000")["groups"] == ["prereq-only"]
    assert course(ds, "AA 1000")["prereqs"] == {"or": ["BB 2000", {"external": "CC 3000"}]} and notes
def test_checked_major_keeps_no_option_warning(): ...   # auto=False -> warning contains "no in-program alternative"
def test_permission_alternative_is_not_an_option_on_the_map(): ...  # "BB 2000 or CC 3000 or permission of the instructor", auto -> BB 2000 node, note kept
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_prereq_parser.py tests/test_build.py -v`
  Expected: the new tests FAIL.
- [ ] **Step 3: Implement the phrase pass and the auto rule.**
- [ ] **Step 4: Run the whole suite and confirm it passes.**
  Run: `.venv/bin/pytest -q`
  Expected: all pass, and `test_checked_majors_rebuild_unchanged` stays green.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline/prereq_parser.py owlpath_pipeline/build.py tests/
  git commit -m "feat: non-course phrases become notes; auto-built majors keep OR courses reachable"
  ```

### Task 7: Program drafter

**Files:**
- Create: `owlpath_pipeline/draft.py`
- Test: `tests/test_draft.py`

**Interfaces:**
- Consumes: the program page dicts from Task 3 and Task 4, and `RawCourse`.
- Produces:
  - `program_identity(name: str, poid: int, catoid: int) -> tuple[str, str]`
    - `KNOWN_PROGRAM_IDS` wins.
    - Otherwise the degree is the text after the last comma with the dots removed (`B.B.A.` → `BBA`, `Ph.D.` → `PhD`), and the field is the text before it.
    - It returns (`f"{degree.lower()}-{slug(field)}"`, `f"{degree} {field}"`).
  - `assign_ids(pages: list[dict], catoid: int) -> dict[int, tuple[str, str]]`: poid → (id, name). Colliding ids get `-<poid>` appended, except known ids.
  - `@dataclass Draft(program_json: dict, warnings: list[str], left_out: list[str])`
  - `draft_program(page: dict, ident: tuple[str, str], level: str, catalog: dict[str, RawCourse]) -> Draft`
    - `program_json` holds `catalogYear`, `level`, `program{id, name, filters}`, `choices`, `courses`, `draftWarnings`, `leftOut` and `draftHash`.
  - `draft_hash(program_json: dict) -> str`: sha256 of canonical JSON, without `draftHash`.
  - `write_draft(draft: Draft, data_dir: Path = config.DATA_DIR) -> str`. Returns one of:
    - `"written"`: there was no file, or the file is an untouched draft (`draftHash` matches and it isn't checked);
    - `"kept-checked"`;
    - `"kept-edited"`.
  - `draft_diff(old: dict, new: dict) -> dict`: `{"added": [...], "removed": [...]}` over course ids.
- **Rules:** heading match is case-insensitive, with any trailing `(… Credit Hours)` removed.
  - Skip: `core impacts|general education|university electives|free electives|program total|\bminor\b`.
  - Concentration context: a heading matching `\b(concentration|track|option|emphasis)\b` opens it. The label is the heading without that word. It lasts until a heading at the same level or shallower. Inside it, any section with courses goes to `conc-<slug(label)>`.
  - Outside a concentration:
    - `core field|field of study` → `core-field`
    - `elective` → `major-elective`
    - `project|capstone` → `major-project`
    - `requirement|required` → `major-required`

    Check them in that order. Any other section with courses is the warning `unrecognized section '<heading>'`.
  - Left out: a title matching `internship|co-?op\b|cooperative (study|education)|special topics|advanced topics|selected topics|(undergraduate|graduate) research|directed (study|research|readings)|independent study|thesis|dissertation`, or a title containing "research" whose catalog prerequisite text names no course.
  - Free-text items inside a mapped section, such as "any CS 3000–4000 course", aren't nodes. They go into `leftOut` as `text: <line>`.
  - Choices: course items joined by `or` items within a section become one choice.
  - A course id found in neither catalog is the warning `<id> is not in the catalog listings`. No courses left at all is the warning `no courses found`.
  - Filters, in this order, each only if non-empty:
    1. "Required courses" (`core-field`, `major-required`);
    2. each concentration, in page order, labeled with its name;
    3. "Electives";
    4. "Project".

- [ ] **Step 1: Write the failing tests.**

```python
def test_bs_cs_draft_matches_reviewed_courses():
    d = draft("ug-bs-cs")  # helper: parse fixture, identity, draft against a catalog stub containing every id
    rename = {"conc-artificial-intelligence": "conc-ai", "conc-cyber-and-network-security": "conc-cyber"}
    reviewed = {c: g for c, g in load("bs-cs")["courses"].items() if g != ["gen-ed-math"]}
    assert {c: [rename.get(x, x) for x in g] for c, g in d.program_json["courses"].items()} == reviewed
    assert {"CS 4491", "CS 4492", "CSE 4983"} <= set(d.left_out) and d.warnings == []
    assert [f["label"] for f in d.program_json["program"]["filters"]] == ["Required courses", "Artificial Intelligence", "Data Science", "Cyber and Network Security", "Electives"]
def test_bs_dsa_draft_choices(): assert sorted(map(sorted, draft("ug-bs-dsa").program_json["choices"])) == sorted(map(sorted, load("bs-dsa")["choices"]))
def test_ms_dsa_draft_groups(): ...                              # same course->group map as ms-dsa/program.json
def test_other_majors_draft_cleanly_or_warn(): ...               # ug-business/nursing/engineering: courses non-empty or warnings non-empty, never both empty
def test_unrecognized_section_with_courses_warns(): ...
def test_page_without_courses_is_held(): assert draft_program(text_only_page, ...).warnings == ["no courses found"]
def test_identity(): assert program_identity("Analytics and Data Science, Ph.D.", 1, 83) == ("phd-analytics-and-data-science", "PhD Analytics and Data Science")
def test_known_ids_kept(): assert program_identity("Computer Science, B.S.", 11680, 84) == ("bs-cs", "BS Computer Science")
def test_colliding_ids_get_poid_suffix(): assert {i for i, _ in assign_ids(two_same_name_pages, 84).values()} == {"bs-biology-501", "bs-biology-502"}
def test_hand_edited_or_checked_program_is_not_overwritten(tmp_path): ...  # returns "kept-edited" / "kept-checked"; file bytes unchanged
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_draft.py -v`
  Expected: FAIL with an `ImportError`.
- [ ] **Step 3: Implement `draft.py` with the rules above.** Mark the three existing `program.json` files `"checked": true`.
- [ ] **Step 4: Run the tests and confirm they pass.**
  Run: `.venv/bin/pytest -q`
  Expected: all pass.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline/draft.py tests/test_draft.py data/2026-2027/*/program.json
  git commit -m "feat: draft program.json from catalog program pages"
  ```

### Task 8: Publishing states, STATUS.md and the majors index

**Files:**
- Create: `owlpath_pipeline/publish.py`
- Modify: `owlpath_pipeline/config.py` (replace `PROGRAMS` with `programs()`)
- Modify: `owlpath_pipeline/build.py`, `owlpath_pipeline/banner.py` (use `config.programs()`; the dataset gains `checked`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `level_get_raw`, `load_overrides` and `build_dataset` (Tasks 5–6); `load_programs` (Task 4); `assign_ids`, `draft_program`, `write_draft` and `draft_diff` (Task 7).
- Produces:
  - `config.programs(data_dir: Path = DATA_DIR) -> list[str]`: the sorted folders that hold `program.json`.
  - `@dataclass MajorResult(id: str, name: str, level: str, state: str, warnings: list[str], errors: list[str], changed: list[str])`. `state` is `"checked"`, `"auto"` or `"held"`.
  - `publish(data_dir: Path = config.DATA_DIR, source: str = "pdf") -> list[MajorResult]`
    1. Draft every in-scope program of each level that has a snapshot.
    2. Build every program folder, with `auto = not checked`.
    3. Write `courses.json` (with `"checked": bool`) for every checked major and for clean auto majors. Delete a held major's `courses.json`.
    4. Write `build-report.md` for each major. Besides today's sections, it lists draft warnings under `## Drafting warnings`, the `leftOut` entries under `## Left out on purpose`, and the auto-rule notes under `## Notes`.
    5. Write `data_dir/majors.json`: `[{"id", "name", "level", "checked"}]` for the shipped majors, sorted by level, then name.
    6. Write `data_dir/STATUS.md` with these sections, in order:
       - `## Summary`: a level × state count table;
       - `## Held majors`;
       - `## Courses holding the most majors`;
       - `## Checked majors changed by this build`: each changed course's before and after;
       - `## Checked majors whose catalog page changed`;
       - `## Programs left out of scope`.
  - Held means draft warnings, build warnings or validation errors.
  - CLI: `.venv/bin/python -m owlpath_pipeline.publish [--from-pdfs]`. It exits 1 if any checked major has errors or warnings, leaving that major's `courses.json` untouched. It prints `checked majors changed: <ids>` whenever that list isn't empty.

- [ ] **Step 1: Write the failing tests.** They run on a temporary data dir with a fake `get_raw`.

```python
def test_clean_unchecked_major_ships_as_auto(tmp_path): ...       # state "auto"; courses.json has "checked": false; listed in majors.json
def test_major_with_warnings_is_held_and_old_courses_json_removed(tmp_path): ...
def test_major_with_draft_warnings_is_held(tmp_path): ...
def test_broken_checked_major_fails_publish(tmp_path): ...       # main() == 1; committed courses.json bytes unchanged
def test_status_ranks_courses_by_majors_held(tmp_path): ...      # "ZZ 9999" holding 2 majors listed above one holding 1
def test_checked_major_change_is_listed_with_before_and_after(tmp_path): ...
def test_majors_index_lists_only_shipped_majors(tmp_path): ...
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `.venv/bin/pytest tests/test_publish.py -v`
  Expected: FAIL with an `ImportError`.
- [ ] **Step 3: Implement `publish.py`, `config.programs()` and the CLI changes.**
- [ ] **Step 4: Run the whole suite and publish locally.**
  Run: `.venv/bin/pytest -q && .venv/bin/python -m owlpath_pipeline.publish --from-pdfs`
  Expected: all pass. All three majors come out `checked`, `majors.json` lists them, and the only `courses.json` change is the new `"checked": true`.
- [ ] **Step 5: Commit.**
  ```bash
  git add owlpath_pipeline tests/test_publish.py data/2026-2027
  git commit -m "feat: publish majors as checked, auto-built or held with a status report"
  ```

### Task 9: Schema and build guard

**Files:**
- Modify: `data/schema/courses.schema.json`
- Modify: `web/src/data/types.ts`, `web/src/data/normalize.ts`
- Modify: `web/scripts/validate-dataset.mjs`, `web/scripts/check-data.mjs`
- Test: `tests/test_validate.py`, `web/scripts/check-data.test.ts`, `web/src/data/validateDataset.test.ts`

**Interfaces:**
- Produces:
  - **Schema:** the group becomes `{"type": "string", "pattern": "^(core-field|major-required|major-elective|major-project|gen-ed-math|prereq-only|conc-[a-z0-9]+(-[a-z0-9]+)*)$"}`, plus an optional top-level `"checked": {"type": "boolean"}`.
  - **Types:**
    - `type Group = string` (comment the pattern);
    - `Dataset.checked?: boolean`;
    - `NDataset.checked: boolean`, set by normalize to `d.checked ?? false`.
  - **`validateDataset`:** every course group matches the pattern, and every filter group is used by some course.
  - **`checkPrograms(dataRoot)`** has these rules:
    1. A checked major (`program.json` `"checked": true`) needs a valid, current `courses.json` with `checked === true`.
    2. An unchecked major with a `courses.json` ships only if all of these hold:
       - it's valid and current;
       - `checked` is false or absent;
       - `draftWarnings` is empty;
       - `build-report.md` contains `## Warnings needing review\n\nNone.` and no `## Validation errors`.
    3. An unchecked major without a `courses.json` is held. Log `held: <id>`; it isn't an error.
    4. `majors.json` lists exactly the shipped majors, with matching `name`, `level` and `checked`.

- [ ] **Step 1: Write the failing tests.** Extend the `root()` helper to write `build-report.md` and `majors.json`.

```ts
test('a checked major without courses.json refuses', ...)
test('a clean auto-built major ships', ...)
test('a held major with courses.json refuses', ...)          // draftWarnings non-empty
test('an auto-built major whose report has warnings refuses', ...)
test('checked flag mismatch refuses', ...)
test('majors.json out of date refuses', ...)
test('a held major without courses.json is skipped and the build passes', ...)
```

```python
def test_concentration_groups_follow_pattern():  # validate_dataset accepts "conc-cyber-and-network-security", rejects "Conc AI"
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `cd web && npm test -- check-data validateDataset; cd .. && .venv/bin/pytest tests/test_validate.py -v`
  Expected: the new tests FAIL.
- [ ] **Step 3: Implement the schema, types, validator and guard.**
- [ ] **Step 4: Run all the checks and confirm they pass.**
  Run: `.venv/bin/pytest -q && cd web && npm test && npm run build`
  Expected: all pass, and the guard prints `dataset ok` for all three majors.
- [ ] **Step 5: Commit.**
  ```bash
  git add data/schema web/src/data web/scripts tests/test_validate.py
  git commit -m "feat: program-defined groups and a guard for checked, auto-built and held majors"
  ```

### Task 10: Web app: lazy loading, searchable picker, auto-built label

**Files:**
- Modify: `web/src/data/dataset.ts`, `web/src/state/status.ts`, `web/src/state/major.ts`, `web/src/logic/programView.ts`, `web/src/App.tsx`, `web/src/components/MajorPicker.tsx`, `web/src/styles.css`
- Create: `web/src/logic/majorSearch.ts`, `web/src/logic/majorLoad.ts`, `web/src/components/AutoBuiltNote.tsx`
- Modify: `web/src/components/stateLabels.ts`
- Test: `web/src/logic/majorSearch.test.ts`, `web/src/logic/majorLoad.test.ts`, `web/src/state/status.test.ts`, `web/src/state/major.test.ts`, `web/src/data/dataset.test.ts`, `web/src/components/stateLabels.test.ts`

**Interfaces:**
- Consumes: `majors.json` from Task 8, and `NDataset.checked` from Task 9.
- Produces:
  - `type MajorEntry = { id: string; name: string; level: 'undergraduate' | 'graduate'; checked: boolean }`
  - `loadIndex(): MajorEntry[]`
    - It bundles only `data/2026-2027/majors.json`.
    - In dev with no index, it falls back to the sample.
    - With an empty index, a production build throws `no reviewed dataset`.
  - `loadMajor(id: string): Promise<NDataset>`, a non-eager `import.meta.glob` of `*/courses.json`. It rejects for an unknown id.
  - `groupMajors(entries: MajorEntry[], query: string): { label: 'Undergraduate' | 'Graduate'; items: MajorEntry[] }[]`
    - Case-insensitive substring match on name or id.
    - A–Z by name within each group.
    - Empty groups are dropped.
  - `type LoadState = { status: 'loading' } | { status: 'ready'; data: NDataset } | { status: 'error' }`
  - `fetchMajor(id: string, load = loadMajor): Promise<LoadState>`. It never rejects.
  - `defaultMajor(ids: string[]): string` returns `'bs-cs'` if present, otherwise `ids[0]`. `resolveMajor` uses it as the last fallback.
  - `loadStatus(storage: Storage | null): StatusMap` keeps every id matching `/^[A-Z]{2,4} \d{4}[A-Z]?$/` that has a valid value. `useStatus()` takes no parameter, and `allCourseIds` is removed.
  - `RESET_TEXT = 'Reset all progress? This marks every course as not taken in every major.'`
  - `MajorPicker({ majors: MajorEntry[]; value: string; onChange: (id: string) => void })`
    - A text input that opens a listbox with `Undergraduate` and `Graduate` headers.
    - Unchecked entries carry the tag `not yet checked`.
    - Keys: ↑/↓ to move, Enter to choose, Escape to close.
  - `AUTO_BUILT_TEXT` (the label copy from Global Constraints) and `autoBuiltText(checked: boolean): string | null` in `web/src/components/stateLabels.ts`.
  - `AutoBuiltNote({ checked: boolean })` renders `autoBuiltText(checked)` when it isn't null.
  - `pickPrograms` and its tests in `dataset.test.ts` are replaced by `loadIndex` and its tests.
  - The App shows `Loading <name>…` while loading. On error it shows `Couldn't load this major.` with a `Retry` button.

- [ ] **Step 1: Write the failing tests.**

```ts
test('groups by level, A–Z, and filters by query', () => {
  const g = groupMajors([e('bba-accounting', 'BBA Accounting', 'undergraduate', false), e('bs-cs', 'BS Computer Science', 'undergraduate', true), e('ms-dsa', 'MS Data Science and Analytics', 'graduate', true)], '')
  expect(g.map((x) => [x.label, x.items.map((i) => i.id)])).toEqual([['Undergraduate', ['bba-accounting', 'bs-cs']], ['Graduate', ['ms-dsa']]])
  expect(groupMajors(entries, 'data')[0].items.map((i) => i.id)).toEqual(['ms-dsa'])
})
test('fetchMajor returns an error state when loading fails', async () => {
  expect(await fetchMajor('x', () => Promise.reject(new Error('chunk')))).toEqual({ status: 'error' })
})
test('keeps progress for majors not loaded and drops malformed ids', () => {
  storage.setItem(STATUS_KEY, JSON.stringify({ 'NURS 3000': 'complete', 'bad id': 'complete', 'CS 3305': 'nope' }))
  expect(loadStatus(storage)).toEqual({ 'NURS 3000': 'complete' })
})
test('resolveMajor falls back to bs-cs for an unknown major', () => {
  expect(resolveMajor('?major=held-x', null, ['ms-dsa', 'bs-cs'])).toBe('bs-cs')
})
test('loadIndex throws in production when the index is empty', ...)
test('auto-built text only for unchecked majors', () => {   // web/src/components/stateLabels.test.ts
  expect(autoBuiltText(false)).toBe('Auto-built from the catalog and not yet checked by a person. Confirm with the catalog and your advisor.')
  expect(autoBuiltText(true)).toBeNull()
})
```

- [ ] **Step 2: Run them and confirm they fail.**
  Run: `cd web && npm test`
  Expected: the new tests FAIL.
- [ ] **Step 3: Implement the modules, components and App wiring above.** Style the picker and note with the existing CSS tokens in `styles.css`.
- [ ] **Step 4: Run the tests and build, and confirm no course data is in the main bundle.**
  Run: `cd web && npm test && npm run build && grep -c "Programming and Problem Solving" dist/assets/index-*.js`
  Expected: tests and build pass, and the grep prints `0`, meaning course data sits in per-major chunks.
- [ ] **Step 5: Check it in the real app.** Run `npm run dev`. Open `?major=ms-dsa`, search "data", switch majors, and mark a course. Reload. Confirm the progress is still there and no console errors appear.
- [ ] **Step 6: Commit.**
  ```bash
  git add web/src
  git commit -m "feat: lazy-load majors with a searchable picker and an auto-built label"
  ```

### Task 11: Switch to the snapshot, regression gate, retire the PDFs, update the docs

Start only when Task 4's crawl has finished and both `catalog/<level>/catalog-courses.json` files exist.

**Files:**
- Add: `data/2026-2027/catalog/{undergraduate,graduate}/{catalog-courses.json,programs.json}`
- Modify: `owlpath_pipeline/build.py`, `owlpath_pipeline/publish.py` (default `source="snapshot"`; `--from-pdfs` keeps the PDF path)
- Move: `data/2026-2027/catalog/undergraduate/cs.pdf` and `stat.pdf` → `tests/fixtures/pdf/`; graduate `stat.pdf` → `tests/fixtures/pdf/stat-graduate.pdf`
- Delete: the other PDFs under `data/2026-2027/catalog/`
- Modify: `tests/test_catalog_pdf.py`, `tests/test_build.py`, `CLAUDE.md`, `README.md`, `data/2026-2027/catalog/graduate/README.md`

**Interfaces:**
- Consumes: Tasks 4–9.
- Produces: snapshot-based builds by default, and the test `test_checked_majors_rebuild_unchanged_from_snapshot`.

- [ ] **Step 1: Write the regression test.** For each of `bs-cs`, `bs-dsa` and `ms-dsa`, rebuild from the snapshot. The result must equal the committed `courses.json` with every course's `catalogUrl` ignored.
- [ ] **Step 2: Run it.**
  Run: `.venv/bin/pytest tests/test_build.py -k from_snapshot -v`
  Expected: PASS. **If it fails, stop.** List each difference for the user. These would be catalog changes since the PDFs were saved (Nov 8–20). Get their decision before going on, because these are checked majors.
- [ ] **Step 3: Flip the default source and point the PDF tests at `tests/fixtures/pdf/`.** Then remove the remaining PDFs.
- [ ] **Step 4: Update the docs.**
  - `CLAUDE.md`:
    - the scope (all degree programs);
    - the crawl rules and stop rules from Global Constraints, replacing "stop and ask if blocked";
    - the folder layout (snapshot, shared overrides, `majors.json`, `STATUS.md`);
    - adding or checking a major;
    - the fix rule for checked majors.
  - `README.md`:
    - the majors section, including what "not yet checked" means;
    - the crawl and publish commands.
- [ ] **Step 5: Run every check and confirm it passes.**
  Run: `.venv/bin/pytest -q && cd web && npm test && npm run build`
  Expected: all pass.
- [ ] **Step 6: Commit.**
  ```bash
  git add -A data/2026-2027/catalog tests owlpath_pipeline CLAUDE.md README.md
  git commit -m "feat: build from the crawled catalog snapshot; retire hand-saved PDFs"
  ```

### Task 12: Publish every major, verify, open the PR

**Files:**
- Modify: `data/2026-2027/**` (generated by publish)

- [ ] **Step 1: Publish.**
  Run: `.venv/bin/python -m owlpath_pipeline.publish`
  Expected: exit 0. `STATUS.md` shows counts per level and state. The three checked majors are listed under "changed by this build" for their new course links only.
- [ ] **Step 2: Read `STATUS.md`.** Confirm every held major has a reason and every out-of-scope program is listed. Pick the three largest auto-built majors by course count.
- [ ] **Step 3: Verify the site.**
  - Run: `cd web && npm test && npm run build`. Expected: pass.
  - Run a headless routing check (Playwright, `npm run dev`) on the three largest auto-built majors and on `bs-cs`, both with nothing selected and with each course selected in turn.
    - For every `.react-flow__edge` path, sample a point every 2 px along it.
    - Assert that no point falls more than 2 px inside a `.react-flow__node` box other than the boxes nearest the path's two ends.
    - Assert that every junction node is the source of some edge.
    - Expected: 0 crossings and 0 dangling junctions.
  - In `npm run dev`, confirm three things:
    - the picker lists every shipped major;
    - auto-built majors show the label;
    - `?major=` for a held id opens `bs-cs`.
- [ ] **Step 4: Commit, push and open the PR.**
  ```bash
  git add -A data/2026-2027
  git commit -m "data: publish every clean 2026-27 degree program"
  git push -u origin feat/all-majors
  gh pr create --base main --title "feat: cover every KSU degree program" --body "<summary, STATUS counts, test plan; end with the two PR attribution lines>"
  ```
- [ ] **Step 5: Hand back to the user.** Report the STATUS summary and the PR link. Merge only when they say so, because merging deploys.
