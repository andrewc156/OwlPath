# OwlPath Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python pipeline that politely fetches the KSU 2026–27 catalog and turns BS CS course pages into a validated, hand-reviewed `data/2026-2027/courses.json` for the frontend.

**Architecture:** A caching, robots-respecting fetcher collects raw HTML. The pipeline then parses each course page and its prerequisite prose into AND/OR trees. A build step finds the full set of needed courses, decides which leaves are in-graph courses and which are text-only "external" alternatives, applies hand-written overrides, validates against a JSON Schema, and writes deterministic JSON. A separate check compares the result against Banner and lists every disagreement.

**Tech Stack:** Python 3.13 (`.venv`), `requests`, `beautifulsoup4`, `jsonschema`, `pytest`.

**Spec:** `docs/mvp-spec.md` + `docs/superpowers/specs/2026-11-06-owlpath-design.md` (the design wins on schema)

## Global Constraints

- Python 3.13 in `.venv/`. Run tools as `.venv/bin/python` / `.venv/bin/pytest`.
- Catalog year string is `"2026-2027"`. The catalog is `catoid=84` at `https://catalog.kennesaw.edu/`.
- Honor `robots.txt`. Use `crawl-delay: 120` (also the default when a host specifies none). Never request `/search_advanced.php`, `/ajax/` or `/portfolio*.php`.
- User-Agent is exactly `OwlPath-data-builder/0.1 (+https://github.com/andrewc156/OwlPath)`. Never spoof a browser.
- The catalog is the authority. Banner is a cross-check only, and the catalog wins unless a human overrides it.
- Output follows the design's schema (`docs/superpowers/specs/2026-11-06-owlpath-design.md`): fields `prereqs`/`coreqs`/`description`. A leaf is a plain string for an in-graph course with grade C, `{"course", "minGrade"}` only for a grade other than C, and `{"external", "minGrade"?}` for an alternative outside the program. `{"course": X, "minGrade": "C"}` is never written.
- Notes (placement, standing, permission, unrecognized text) are displayed, never blocking.
- Output is deterministic: courses sorted by `id`, keys sorted, no timestamps, 2-space indent, trailing newline.
- Raw HTML caches live in `.cache/http/` (gitignored). Only `data/` outputs and test fixtures are committed.

## Review Focus

1. **Blocked or empty catalog responses.** Research saw empty bodies from `catoid=84`. The fetcher must raise `EmptyResponseError` and never cache an empty body, or the build would silently drop courses. Covered by a Task 2 test.
2. **Curly quotes and odd spacing in HTML text.** For example `“B”` and non-breaking spaces. These must parse the same as straight quotes. Covered by a Task 3 test.
3. **An OR group with no alternative in the program.** It must produce a warning, not silently become impossible to satisfy. Covered by a Task 5 test.
4. **Prerequisite cycles.** These are an error, while mutual corequisites like CSE 1321 ↔ CSE 1321L are allowed. Covered by a Task 1 test.
5. **Stale overrides.** An override for a course that isn't in the graph must be an error, not silently ignored. Covered by a Task 5 test.

## File Structure

```
pyproject.toml                         project + deps + pytest config
owlpath_pipeline/
  __init__.py
  config.py                            URLs, catoid, UA, delay, cache dir, year
  model.py                             Expr type alias, RawCourse, ParseResult, DEFAULT_MIN_GRADE
  validate.py                          schema + referential + cycle validation
  fetch.py                             PoliteFetcher, errors, CLI to fetch one URL
  prereq_parser.py                     prose -> ParseResult
  catalog_pages.py                     course page + course index HTML parsers
  build.py                             graph closure, classification, overrides, CLI
  banner.py                            Banner parser, diff, CLI
data/
  schema/courses.schema.json           the contract shared with the frontend
  2026-2027/program.json               hand-written program membership (groups)
  2026-2027/overrides.json             hand fixes, each with a reason
  2026-2027/courses.json               build output (committed)
  2026-2027/build-report.md            build warnings (committed)
  2026-2027/banner-diff.md             Banner discrepancies (committed)
tests/
  fixtures/catalog/*.html              real pages captured in Task 4
  fixtures/banner/*.html               real pages captured in Task 6
  test_validate.py  test_fetch.py  test_prereq_parser.py
  test_catalog_pages.py  test_build.py  test_banner.py
```

---

### Task 1: Scaffold, data contract and validator

**Files:**
- Create: `pyproject.toml`, `owlpath_pipeline/__init__.py`, `owlpath_pipeline/config.py`, `owlpath_pipeline/model.py`, `owlpath_pipeline/validate.py`, `data/schema/courses.schema.json`
- Modify: `.gitignore` (add `.cache/`), `CLAUDE.md` (add a Commands section)
- Test: `tests/test_validate.py`

**Interfaces:**
- Produces:
  - `model.Logic` is the **output** form (see Global Constraints): a `str` leaf, `{"course": str, "minGrade": str}`, `{"external": str, "minGrade"?: str}`, `{"and": [Logic, ...]}` or `{"or": [Logic, ...]}`.
  - `model.Expr` is the **internal** parser/build form, where every leaf is an object. It is exactly one of `{"and": [Expr, ...]}`, `{"or": [Expr, ...]}`, `{"course": str, "minGrade"?: str}` or `{"external": str, "minGrade"?: str}`.
  - `model.DEFAULT_MIN_GRADE = "C"`
  - `config.CATALOG_YEAR = "2026-2027"`, `config.CATOID = 84`, `config.CATALOG_BASE = "https://catalog.kennesaw.edu"`, `config.USER_AGENT`, `config.DEFAULT_CRAWL_DELAY = 120.0`, `config.CACHE_DIR = Path(".cache/http")`
  - `validate.validate_dataset(data: dict) -> list[str]` returns error strings. An empty list means the dataset is valid.

The dataset shape is enforced by `courses.schema.json`:
- Top level: `{"catalogYear": "2026-2027", "source": str, "courses": [Course, ...]}`
- `Course` fields: `id` (pattern `^[A-Z]{2,4} \d{4}[A-Z]?$`), `title` str, `credits` str (e.g. `"3"`, `"1-3"`), `catalogYear` str, `description` str, `catalogUrl` str, `groups` (non-empty array of the enum below), `prereqs` Logic|null, `coreqs` Logic|null, `notes` str[]
- `groups` enum: `core-field`, `major-required`, `conc-data-science`, `conc-cyber`, `conc-ai`, `major-elective`, `gen-ed-math`, `prereq-only`
- `minGrade` enum: `A`, `B`, `C`, `D`. No additional properties are allowed anywhere.

- [ ] **Step 1: Write `pyproject.toml` and install**

Project `owlpath-pipeline`, `requires-python = ">=3.13"`, deps `requests`, `beautifulsoup4`, `jsonschema`, optional `dev = ["pytest"]`, `packages = ["owlpath_pipeline"]`, pytest `testpaths = ["tests"]`.
Run: `.venv/bin/pip install -e '.[dev]'`. Expected: it installs without errors.

- [ ] **Step 2: Write the failing tests in `tests/test_validate.py`**

Use a helper `course(id, prereqs=None, coreqs=None, groups=("major-required",))` that builds a schema-valid Course dict.

```python
def test_valid_dataset_has_no_errors():
    data = dataset([course("CSE 1321"), course("CSE 1321L"),
                    course("CSE 1322", prereqs={"and": [{"course": "CSE 1321", "minGrade": "B"}, "CSE 1321L"]})])
    assert validate_dataset(data) == []

def test_string_leaf_is_a_course_reference():
    data = dataset([course("CS 3305", prereqs={"or": ["MATH 2345", {"external": "CSE 2300"}]})])
    assert any("MATH 2345" in e and "unknown" in e for e in validate_dataset(data))

def test_object_leaf_with_default_grade_is_error():
    data = dataset([course("CSE 1321"), course("CSE 1322", prereqs={"course": "CSE 1321", "minGrade": "C"})])
    assert any("short form" in e for e in validate_dataset(data))

def test_dangling_course_reference_is_error():
    data = dataset([course("CSE 1322", prereqs="CSE 1321")])
    assert any("CSE 1321" in e and "unknown" in e for e in validate_dataset(data))

def test_external_reference_need_not_exist():
    data = dataset([course("CS 3305", prereqs={"or": [{"external": "MTRE 2610"}, {"external": "CPE 3000"}]})])
    assert validate_dataset(data) == []

def test_prereq_cycle_is_error():
    data = dataset([course("CS 1000", prereqs="CS 2000"), course("CS 2000", prereqs="CS 1000")])
    assert any("cycle" in e for e in validate_dataset(data))

def test_mutual_corequisites_are_allowed():
    data = dataset([course("CSE 1321", coreqs="CSE 1321L"), course("CSE 1321L", coreqs="CSE 1321")])
    assert validate_dataset(data) == []

def test_schema_violation_is_error():
    bad = course("CS 3305"); bad["groups"] = ["not-a-group"]
    assert validate_dataset(dataset([bad])) != []
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_validate.py -v`. Expected: FAIL (an ImportError).

- [ ] **Step 4: Implement the schema, `model.py`, `config.py` and `validate_dataset`**

Validate with `jsonschema.Draft202012Validator` first and return its error messages. Then check that every course leaf (a string, or an object with `course`) in `prereqs` and `coreqs` names an existing `id`. Report `"CSE 1322: object leaf CSE 1321 with grade C must use short form"` for a `{"course", "minGrade": "C"}` leaf. Report a missing one as `"CSE 1322: unknown course reference CSE 1321"`. Then find prerequisite cycles with a DFS over `prereqs` course leaves only; coreqs are excluded. Report errors as `"cycle: CS 1000 -> CS 2000 -> CS 1000"`.

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/test_validate.py -v`. Expected: 8 passed.

- [ ] **Step 6: Add `.cache/` to `.gitignore` and a Commands section to `CLAUDE.md`**

The Commands section covers install (`.venv/bin/pip install -e '.[dev]'`), the full test suite (`.venv/bin/pytest`) and a single test (`.venv/bin/pytest tests/test_validate.py::test_prereq_cycle_is_error -v`).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml owlpath_pipeline data/schema tests/test_validate.py .gitignore CLAUDE.md
git commit -m "feat: add data contract schema and dataset validator"
```

---

### Task 2: Polite caching fetcher

**Files:**
- Create: `owlpath_pipeline/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `config.USER_AGENT`, `config.DEFAULT_CRAWL_DELAY`, `config.CACHE_DIR`
- Produces:
  - `class FetchError(Exception)`, `class DisallowedError(FetchError)`, `class EmptyResponseError(FetchError)`
  - `PoliteFetcher(cache_dir: Path, user_agent: str, http_get: Callable[[str, dict[str, str]], tuple[int, str]], sleep: Callable[[float], None], clock: Callable[[], float])`
  - `PoliteFetcher.fetch(url: str) -> str` returns the cached body when present. Otherwise it obeys that host's robots.txt (fetched once per host through the same `http_get`, never cached to disk), waits out the crawl delay, then fetches and caches.
  - `PoliteFetcher.default() -> PoliteFetcher` uses `requests` and the real `time` functions.
  - CLI: `.venv/bin/python -m owlpath_pipeline.fetch <url>` fetches through the cache and prints the cache file path.

- [ ] **Step 1: Write the failing tests in `tests/test_fetch.py`**

Use a fake `http_get` that records calls and serves a robots.txt (`User-agent: *\nCrawl-delay: 120\nDisallow: /ajax/\n`) and page bodies from a dict. Use a fake clock and a `sleep` that advances the clock and records how long it waited.

```python
def test_second_fetch_is_served_from_cache(tmp_path): ...       # page requested over http exactly once
def test_waits_crawl_delay_between_requests_same_host(tmp_path): ...  # second uncached fetch at t=10 sleeps 110
def test_default_delay_120_when_robots_has_none(tmp_path): ...
def test_disallowed_path_raises(tmp_path): ...                   # pytest.raises(DisallowedError) for /ajax/x
def test_empty_body_raises_and_is_not_cached(tmp_path): ...      # body "  \n" -> EmptyResponseError; nothing in cache_dir
def test_non_200_raises_fetch_error(tmp_path): ...               # status 503 -> FetchError, not cached
def test_sends_configured_user_agent(tmp_path): ...              # headers["User-Agent"] == config.USER_AGENT
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_fetch.py -v`. Expected: FAIL (an ImportError).

- [ ] **Step 3: Implement `PoliteFetcher`**

Parse robots with `urllib.robotparser.RobotFileParser.parse(lines)`. Read the delay from `crawl_delay(user_agent)` and fall back to `DEFAULT_CRAWL_DELAY`. Name each cache file `sha256(url).html`, with a sidecar `.url` file holding the URL.

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/test_fetch.py -v`. Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add owlpath_pipeline/fetch.py tests/test_fetch.py
git commit -m "feat: add robots-respecting caching fetcher"
```

---

### Task 3: Prerequisite prose parser

**Files:**
- Create: `owlpath_pipeline/prereq_parser.py`
- Test: `tests/test_prereq_parser.py`

**Interfaces:**
- Consumes: `model.Expr`
- Produces:
  - `model.ParseResult` (dataclass): `expr: Expr | None`, `notes: list[str]`, `warnings: list[str]`
  - `prereq_parser.parse_requirement(text: str) -> ParseResult`. Every leaf it emits is `{"course": ...}`. Task 5 decides which leaves become `external`.

- [ ] **Step 1: Write the failing tests in `tests/test_prereq_parser.py`**

The input strings are the spec's verbatim examples. `C = lambda i, g=None: {"course": i, **({"minGrade": g} if g else {})}`.

```python
def test_grade_prefix_applies_to_all_courses():
    r = parse_requirement('A grade of "B" or higher in CSE 1321 and CSE 1321L')
    assert r.expr == {"and": [C("CSE 1321", "B"), C("CSE 1321L", "B")]} and r.warnings == []

def test_concurrent_with_nested_or():
    r = parse_requirement("CSE 1322L and (MATH 1113 or MATH 1190 or MATH 1179 or MATH 2202)")
    assert r.expr == {"and": [C("CSE 1322L"), {"or": [C("MATH 1113"), C("MATH 1190"), C("MATH 1179"), C("MATH 2202")]}]}

def test_cs3305_mixed_brackets_each_with_and_with():
    r = parse_requirement('(MATH 2345 or CSE 2300) and [(CSE 1322 and CSE 1322L each with a "B" or better), '
                          'or MTRE 2610 with a "B" or better, or CPE 3000 with a "B" or better]')
    assert r.expr == {"and": [
        {"or": [C("MATH 2345"), C("CSE 2300")]},
        {"or": [{"and": [C("CSE 1322", "B"), C("CSE 1322L", "B")]}, C("MTRE 2610", "B"), C("CPE 3000", "B")]}]}
    assert r.warnings == []

def test_placement_alternative_becomes_note():
    r = parse_requirement("MATH 1113, or By Placement")
    assert r.expr == C("MATH 1113") and r.notes == ["By Placement"]

def test_standing_only_has_no_expr():
    r = parse_requirement("Senior standing")
    assert r.expr is None and r.notes == ["Senior standing"] and r.warnings == []

def test_permission_is_note():
    r = parse_requirement("CS 3305 or By Instructor's or Department's permission.")
    assert r.expr == C("CS 3305") and r.notes == ["By Instructor's or Department's permission"]

def test_glued_typo_and_curly_quotes_and_nbsp():
    r = parse_requirement("A grade of “B” or higher inCSE 1321")
    assert r.expr == C("CSE 1321", "B") and r.warnings == []

def test_or_higher_and_or_better_are_equivalent():
    assert parse_requirement('CS 3305 with a "B" or higher').expr == parse_requirement('CS 3305 with a "B" or better').expr

def test_unbracketed_mixed_and_or_warns():
    r = parse_requirement("MATH 1113 or MATH 1190 and CSE 1321")
    assert any("ambiguous" in w for w in r.warnings)

def test_unrecognized_text_warns_and_is_kept_as_note():
    r = parse_requirement("Approval of the dean")
    assert r.expr is None and r.notes == ["Approval of the dean"] and any("unrecognized" in w for w in r.warnings)

def test_oxford_list_inherits_operator():
    assert parse_requirement("CS 3305, CS 3503, and CS 3502").expr == {"and": [C("CS 3305"), C("CS 3503"), C("CS 3502")]}
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_prereq_parser.py -v`. Expected: FAIL (an ImportError).

- [ ] **Step 3: Implement `parse_requirement`**

The parser works in this order:

1. **Normalize.** Replace curly quotes with straight quotes and NBSP with a space. Insert a space where a subject prefix is glued to a word (`inCSE` → `in CSE`). Collapse whitespace and strip a trailing period.
2. **Tokenize** with one ordered regex. The token types are:
   - `COURSE` (`[A-Z]{2,4} \d{4}[A-Z]?`)
   - `GRADE_PREFIX` (`a grade of "X" or (higher|better) in`)
   - `GRADE_SUFFIX` (`(each )?with a "X" or (higher|better)`, where the `each` flag is recorded)
   - `AND`, `OR`, `(`/`[`, `)`/`]`, `,` (dropped)
   - `NOTE`, matched case-insensitively against `by placement`, `(freshman|sophomore|junior|senior) standing`, `(by )?(instructor's|department's)( or department's)? permission`, `permission of (the )?(instructor|department)`

   Any leftover text becomes one `NOTE` with a `"unrecognized: <text>"` warning.
3. **Recursive descent** with this grammar:

   ```
   or_expr  := and_expr (OR and_expr)*
   and_expr := unary (AND? unary)*
   unary    := GRADE_PREFIX unary | primary GRADE_SUFFIX?
   primary  := COURSE | '(' or_expr ')' | '[' or_expr ']' | NOTE
   ```

   An operand next to another operand with no operator between them takes the next operator at the same level (the Oxford-list rule).
4. **Grades.** A grade (prefix, suffix or `each` suffix) applies to every leaf of its operand.
5. **Ambiguity.** If one bracket level contains both a bare `AND` and a bare `OR`, add the warning `"ambiguous and/or precedence: <text>"`.
6. **Notes.** Remove NOTE operands from the tree and append their original text to `notes`. When removing a note leaves a single-child `and` or `or`, replace it with that child. A tree emptied entirely becomes `None`.
7. **Flatten** nested same-operator nodes.
8. **Omit** `minGrade` when it is `"C"`.

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/test_prereq_parser.py -v`. Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add owlpath_pipeline/prereq_parser.py owlpath_pipeline/model.py tests/test_prereq_parser.py
git commit -m "feat: parse catalog prerequisite prose into AND/OR trees"
```

---

### Task 4: Catalog page parsers (with real fixtures)

**Files:**
- Create: `owlpath_pipeline/catalog_pages.py`, `tests/fixtures/catalog/{index-cse.html,cse-1322.html,cs-3305.html,math-1190.html,cse-4983.html}`
- Modify: `owlpath_pipeline/config.py` (add `COURSE_URL`, `COURSE_INDEX_URL`)
- Test: `tests/test_catalog_pages.py`

**Interfaces:**
- Consumes: `PoliteFetcher.default().fetch` (via the Task 2 CLI)
- Produces:
  - `model.RawCourse` (dataclass): `id: str`, `title: str`, `credits: str`, `description: str`, `prereq_text: str | None`, `coreq_text: str | None`, `url: str`
  - `catalog_pages.parse_course_page(html: str, url: str) -> RawCourse`. `coreq_text` joins the `Concurrent:` and `Corequisite:` texts with `" and "`, wrapping each part in parentheses when there is more than one.
  - `catalog_pages.parse_course_index(html: str) -> tuple[dict[str, int], str | None]` returns a map of course id to `coid`, plus the next page URL or `None`.
  - `config.COURSE_URL = CATALOG_BASE + "/preview_course_nopop.php?catoid=84&coid={coid}"` and `config.COURSE_INDEX_URL`, a template with a `{prefix}` placeholder (found in Step 1)

- [ ] **Step 1: Find the course index URL and capture fixtures**

In a browser, open the 2026–27 catalog's "Course Descriptions" page and filter it to the CSE prefix. Record that URL as the `COURSE_INDEX_URL` template with `{prefix}`. Capture each page with `.venv/bin/python -m owlpath_pipeline.fetch <url>`, then copy it from the printed cache path into `tests/fixtures/catalog/`.
Expected: each fixture is non-empty HTML containing its course id.

**Stop condition:** if the fetch raises `EmptyResponseError` or `FetchError`, stop and report to the human. Do not change the User-Agent or retry quickly.

- [ ] **Step 2: Write the failing tests in `tests/test_catalog_pages.py`**

Copy the expected values from the live 2026–27 pages as shown in a browser.

```python
def test_course_page_fields_cse1322():
    c = parse_course_page(read("cse-1322.html"), URL)
    assert (c.id, c.credits) == ("CSE 1322", "<from page>") and "CSE 1321" in c.prereq_text
    assert "CSE 1322L" in c.coreq_text
    assert c.description.strip() != "" and "Prerequisite" not in c.description

def test_prereq_and_coreq_absent_are_none():   # pick a fixture with no Concurrent line (cse-4983 or math-1190)
    ...

def test_variable_credits_kept_as_string():    # cse-4983 if variable; otherwise assert credits matches r"^\d+(-\d+)?$"
    ...

def test_course_index_maps_ids_to_coids():
    ids, next_url = parse_course_index(read("index-cse.html"))
    assert "CSE 1321" in ids and isinstance(ids["CSE 1321"], int)
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_catalog_pages.py -v`. Expected: FAIL (an ImportError).

- [ ] **Step 4: Implement both parsers with BeautifulSoup**

Find the field labels (`Prerequisite:`, `Concurrent:`, `Corequisite:`, credit hours) by their text, not by fixed positions in the HTML, so markup changes break less.

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/test_catalog_pages.py -v`. Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add owlpath_pipeline/catalog_pages.py owlpath_pipeline/config.py owlpath_pipeline/model.py tests/test_catalog_pages.py tests/fixtures/catalog
git commit -m "feat: parse catalog course and index pages"
```

---

### Task 5: Build the dataset

**Files:**
- Create: `owlpath_pipeline/build.py`, `data/2026-2027/program.json`, `data/2026-2027/overrides.json` (as `{}`)
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `parse_requirement`, `RawCourse`, `parse_course_page`, `parse_course_index`, `validate_dataset`, `PoliteFetcher`, `config.*`
- Produces:
  - `program.json` shape: `{"catalogYear": "2026-2027", "courses": {"<id>": ["<group>", ...]}}`
  - `overrides.json` shape: `{"<id>": {"reason": str, "prereqs"?: Logic|null, "coreqs"?: Logic|null, "notes"?: [str]}}`. A field that is present replaces the parsed value. Override trees are written in the output (short) form and copied through unchanged.
  - `build.to_output(expr: Expr) -> Logic` converts to the short form: an in-graph course with grade C becomes a plain string.
  - `build.build_dataset(program: dict[str, list[str]], get_raw: Callable[[str], RawCourse], overrides: dict) -> tuple[dict, list[str]]` returns `(dataset, warnings)`. Each warning is prefixed with its course id, e.g. `"CS 3305: ..."`.
  - CLI: `.venv/bin/python -m owlpath_pipeline.build [--draft]` writes `data/2026-2027/courses.json` and `build-report.md`. It exits with code 1 if `validate_dataset` returns errors, or if a warning's course has no override and `--draft` is not set.

- [ ] **Step 1: Write `program.json`**

Use the spec's "BS CS structure" section, mapped to the groups enum. Every lab course (`CSE 1321L`, `CSE 1322L`) gets the same group as its lecture.

- [ ] **Step 2: Write the failing tests in `tests/test_build.py`**

Use a fake `get_raw` backed by a dict of `RawCourse`, with real-looking ids.

```python
def test_required_prereq_outside_program_is_added_as_prereq_only(): ...   # A AND-requires B (not in program) -> B in courses, groups == ["prereq-only"], leaf {"course": B}
def test_or_alternative_outside_program_becomes_external(): ...          # CS 3305 "(MATH 2345 or CSE 2300)" with only MATH 2345 in program -> {"external": "CSE 2300"}; CSE 2300 not fetched
def test_or_with_no_in_program_alternative_warns(): ...                  # "(MTRE 2610 or CPE 3000)" alone -> warning containing "no in-program alternative"
def test_parser_warnings_are_prefixed_with_course_id(): ...
def test_override_replaces_prereq_and_clears_that_courses_warnings(): ...
def test_override_for_course_not_in_graph_is_error(): ...                # raises ValueError mentioning the id
def test_override_without_reason_is_error(): ...
def test_output_is_sorted_and_valid(): ...                               # ids sorted; validate_dataset(dataset) == []
def test_notes_description_catalog_year_and_url_carried_through(): ...
def test_output_uses_short_form_leaves(): ...                             # in-graph grade-C leaf -> "MATH 2345"; grade B -> {"course": ..., "minGrade": "B"}; external keeps object
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_build.py -v`. Expected: FAIL (an ImportError).

- [ ] **Step 4: Implement `build_dataset` and the CLI**

Build in two passes so the result doesn't depend on processing order:
- **Pass 1 (closure):** use a worklist seeded with the program ids. Parse each course's `prereq_text` and `coreq_text`. Every leaf under no `or` ancestor is required. Add any new required id to the worklist with group `prereq-only`. Continue until the worklist is empty; the final set is the **graph**.
- **Pass 2 (classify):** a leaf whose id is in the graph becomes `course`, and any other leaf becomes `external`. Required leaves are always in the graph. An `or` with zero `course` leaves raises the warning above.

Convert every tree with `to_output`, then apply overrides (already in output form) and drop warnings for overridden courses. For the CLI's `get_raw`, build the id-to-coid map lazily per prefix from `COURSE_INDEX_URL` (following `next_url`), then fetch and parse `COURSE_URL`. Write JSON with `sort_keys=True, indent=2` plus a trailing newline. The report is a markdown list of warnings grouped by course.

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/test_build.py -v`. Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add owlpath_pipeline/build.py data/2026-2027/program.json data/2026-2027/overrides.json tests/test_build.py
git commit -m "feat: build validated course dataset with overrides"
```

---

### Task 6: Banner cross-check

**Files:**
- Create: `owlpath_pipeline/banner.py`, `tests/fixtures/banner/cse-1322.html`
- Modify: `owlpath_pipeline/config.py` (add `BANNER_URL`, `BANNER_TERM`)
- Test: `tests/test_banner.py`

**Interfaces:**
- Consumes: the dataset dict from Task 5, `PoliteFetcher`
- Produces:
  - `config.BANNER_URL = "https://owlexpress.kennesaw.edu/prodban/bwckctlg.p_disp_course_detail?cat_term_in={term}&subj_code_in={subj}&crse_numb_in={num}"` and `config.BANNER_TERM`, the Fall 2026 term code found in Step 1 (research saw `202608`)
  - `banner.parse_banner_prereqs(html: str) -> dict[str, str]` maps course id to minimum grade (regex `([A-Z]{2,4} \d{4}[A-Z]?)\s+Minimum Grade of ([A-F])`)
  - `banner.Discrepancy` (dataclass): `course: str`, `ref: str`, `catalog_grade: str | None`, `banner_grade: str | None`
  - `banner.diff_course(course: dict, banner: dict[str, str]) -> list[Discrepancy]`. It reads `prereqs` and accepts string leaves. It compares all prerequisite leaves (`course` and `external`, with missing grades treated as `"C"`) against Banner. A reference present in only one source has `None` on the other side.
  - CLI: `.venv/bin/python -m owlpath_pipeline.banner` reads `courses.json` and writes `data/2026-2027/banner-diff.md`

- [ ] **Step 1: Confirm the term code and capture the fixture**

Open the Banner URL for CSE 1322 with `202608` in a browser and confirm it shows the Fall 2026 term; adjust the code if not. Then capture the page through `owlpath_pipeline.fetch`, which checks the owlexpress robots.txt. The same stop condition as Task 4 applies.

- [ ] **Step 2: Write the failing tests**

```python
def test_parse_banner_extracts_grades():
    assert parse_banner_prereqs(read("cse-1322.html"))["CSE 1321"] == "C"     # value as seen in research; confirm on fixture

def test_known_cse1322_grade_disagreement_is_reported():
    course = {"id": "CSE 1322", "prereqs": {"and": [{"course": "CSE 1321", "minGrade": "B"}, {"course": "CSE 1321L", "minGrade": "B"}]}}
    d = diff_course(course, {"CSE 1321": "C", "CSE 1321L": "B"})
    assert d == [Discrepancy("CSE 1322", "CSE 1321", "B", "C")]

def test_reference_missing_from_one_side():
    d = diff_course({"id": "CS 3305", "prereqs": "MATH 2345"}, {"CSE 2300": "C"})
    assert set((x.ref, x.catalog_grade, x.banner_grade) for x in d) == {("MATH 2345", "C", None), ("CSE 2300", None, "C")}

def test_matching_sources_have_no_discrepancies(): ...
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/test_banner.py -v`. Expected: FAIL.

- [ ] **Step 4: Implement the parser, `diff_course` and the CLI**

The report is one markdown table per course with discrepancies: Ref | Catalog | Banner | Resolution (left blank for the human).

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/test_banner.py -v`. Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add owlpath_pipeline/banner.py owlpath_pipeline/config.py tests/test_banner.py tests/fixtures/banner
git commit -m "feat: cross-check catalog prerequisites against Banner"
```

---

### Task 7: Full run and hand review (human in the loop)

**Files:**
- Modify: `data/2026-2027/program.json`, `data/2026-2027/overrides.json`
- Create (generated): `data/2026-2027/courses.json`, `build-report.md`, `banner-diff.md`

- [ ] **Step 1: Check `program.json` against the 2026–27 BS CS program page in a browser**

Fix any course list that changed from the 2025–26 sheet and update the spec's "BS CS structure" section to match.

- [ ] **Step 2: Run the draft build in the background, since it takes about 2–3 hours at 120 seconds per request**

Run: `.venv/bin/python -m owlpath_pipeline.build --draft`. Expected: `courses.json` and `build-report.md` are written. A re-run uses the cache and finishes in seconds.

- [ ] **Step 3: Resolve every `build-report.md` warning with an override that includes a reason**

The human approves each resolution.

- [ ] **Step 4: Run the Banner check and settle every discrepancy**

Run: `.venv/bin/python -m owlpath_pipeline.banner`. The human fills in the Resolution column. The catalog wins unless the human chooses otherwise, and a change is recorded as an override.

- [ ] **Step 5: Spot-check about 10 courses against the catalog**

Include CSE 1322, CS 3305, MATH 1190 and one course from each concentration. Compare title, credits, prerequisites, corequisites and notes.

- [ ] **Step 6: Run the final build**

Run: `.venv/bin/python -m owlpath_pipeline.build` (without `--draft`). Expected: exit code 0, with no unresolved warnings in `build-report.md`.

- [ ] **Step 7: Run the full test suite**

Run: `.venv/bin/pytest`. Expected: everything passes.

- [ ] **Step 8: Commit**

```bash
git add data/2026-2027 docs/mvp-spec.md
git commit -m "data: add reviewed 2026-27 BS CS course dataset"
```
