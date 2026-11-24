# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Brief

OwlPath is an interactive prerequisite map for every degree program at Kennesaw State University. It is inspired by GradGT (Georgia Tech's prerequisite chart) but built independently. Students pick a course and see what it requires and what it unlocks. They can mark courses as complete or in progress and see what they're eligible for now or next term.

**Scope:** every degree program (bachelor's, master's, specialist, doctoral) of the 2026–27 undergraduate and graduate catalogs, picked from a searchable dropdown. No minors, certificates or endorsements. Three majors are **checked** (a person reviewed them): the **BS in Computer Science** (`bs-cs`), the **BS in Data Science and Analytics** (`bs-dsa`) and the graduate **MS in Data Science and Analytics** (`ms-dsa`). The rest are **auto-built** from the catalog, labeled "not yet checked" in the picker and on the map, until a person reviews them. Each map covers the program's requirements and listed electives (and concentrations where it has them), plus every course needed to reach them, including MATH and other prefixes. KSU's intro sequence is **CSE 1321/1322**.

**Stack:** React + Vite + TypeScript, React Flow (`@xyflow/react`) with dagre for automatic layout, course data as static JSON bundled into the app (one `courses.json` per major, loaded lazily when picked), deployed to GitHub Pages. There is no backend. A Python pipeline (`owlpath_pipeline/`) builds the JSON offline from a crawled snapshot of the KSU catalog.

**Source documents. Read the relevant one before designing or building, and don't reopen settled questions:**
- `docs/mvp-spec.md` covers scope, the data source and polite-scraping rules, the prerequisite rules, eligibility and what's out of scope.
- `docs/superpowers/specs/2026-11-06-owlpath-design.md` covers the stack, the final schema, the folder layout and the frontend design. It wins over the spec where they differ.
- `docs/superpowers/specs/2026-11-11-owlpath-multi-major-design.md` covers the second major, the dropdown, either/or requirements and the reset button.
- `docs/superpowers/specs/2026-11-22-owlpath-all-majors-design.md` covers every degree program: the honest crawler, the catalog snapshot, drafting `program.json`, the checked / auto-built / held states and the lazy-loaded picker. It is binding for all-majors work and wins over the documents above where they differ.
- `docs/superpowers/plans/` holds the build plans: the data pipeline, the web app, multi-major and all-majors.

## Folder structure

```
docs/                     spec, design, plans
pyproject.toml            (optional `crawl` extra: Playwright, used only by the crawler)
owlpath_pipeline/         Python data pipeline: crawl, snapshot, draft, build, publish, Banner cross-check
tests/                    pipeline tests + captured catalog pages (fixtures/catalog) and a few listing PDFs (fixtures/pdf)
data/
  schema/courses.schema.json   contract between the pipeline and the app
  2026-2027/
    catalog/
      undergraduate/  graduate/   one per catalog level:
        catalog-courses.json  every course of the level, from the crawl (committed)
        programs.json         every in-scope program page, parsed (committed)
        overrides.json        hand fixes shared by every major of the level, each with a reason
    <major>/              per major: program.json, courses.json, build-report.md; checked majors also program-page.pdf, banner-diff.md
    majors.json           the dropdown list, written by publish (id, name, level, checked)
    STATUS.md             written by publish: checked / auto-built / held majors, changes to checked majors, retired drafts, shared fixes, programs left out
web/                      Vite + React + TS app
  src/data/  src/logic/  src/components/  src/state/  scripts/check-data.mjs (the build guard)
.github/workflows/deploy.yml
```

## Data schema

Each `data/2026-2027/<major>/courses.json` is `{ catalogYear, source, program, choices, lessCommon, courses: Course[] }`.
- `program` is `{ id, name, filters: { label, groups: Group[] }[] }`; it gives the dropdown name and the "Show" filter options.
- `choices` is `string[][]`, the major's either/or requirements (take one course from each list). Every id must be a course in the dataset.
- `lessCommon` is `string[]` (optional in `program.json`, default `[]`): either/or options most students skip. The map hides them until the popular option is selected, the hidden one is opened from search, or the student marks it. The layout puts each one in its popular partner's column. Each must share a choice with a shown option and may only appear inside an `or` in other courses' prerequisites, so hiding it never hides a required course.

```ts
type Grade = "A" | "B" | "C" | "D";
type Leaf = string                                   // in-graph course, minGrade "C"
          | { course: string; minGrade?: Grade }     // in-graph course, grade other than C
          | { external: string; minGrade?: Grade };  // alternative outside the program: text, not a node
type Logic = Leaf | { and: Logic[] } | { or: Logic[] };

interface Course {
  id: string;            // "CS 3305"
  title: string;
  credits: string;       // "3", or a range like "1-3"
  description: string;
  catalogYear: string;   // "2026-2027"
  catalogUrl: string;
  groups: string[];      // "core-field" | "major-required" | "major-elective" | "major-project" | "gen-ed-math" | "prereq-only",
                         // or a concentration "conc-<slug>" (e.g. "conc-ai"); the program's `filters` name the ones it uses
  prereqs: Logic | null;
  coreqs: Logic | null;
  notes: string[];       // placement, standing, permission: shown, never blocking
}
```

For example, `"CS 1321 and (MATH 1113 or MATH 1190)"` is stored as `{ "and": ["CSE 1321", { "or": ["MATH 1113", "MATH 1190"] }] }`. The pipeline writes the shortest form: an object leaf appears only for a grade other than C or an external course.

## Rules that are easy to get wrong

- **Crawling the catalog** (`owlpath_pipeline/crawl.py`, a real browser through Playwright, only when the user asks for a crawl):
  - Wait `crawl-delay: 120` seconds between catalog page loads. The bot check's automatic reload belongs to the same visit, and the next page waits 120 s from the end of the visit.
  - Never request `/ajax/`, `/search_advanced.php`, `/portfolio.php` or `/portfolio_nopop.php`.
  - Use exactly `config.USER_AGENT`. No stealth plugins, fingerprint changes, proxies or CAPTCHA services.
  - Allow only catalog-host (`catalog.kennesaw.edu`) documents and any request to a host ending in `.token.awswaf.com`. Abort everything else.
  - **Stop and report** when robots.txt isn't readable (anything but 200), the bot check doesn't pass within 60 s, a page ends on a non-200 status, or a page lacks its expected content. Never retry in a loop and never escalate. Rerunning resumes from the cache.
  - **One crawl at a time.** A run that can make requests (`capture`, or a level without `--from-cache`) holds an exclusive lock on `.cache/http/.crawl.lock` for the whole run, and a second one stops at once with `STOPPED: another crawl is running`. Never work around it: two crawls would wait out the delay from the same record and hit the host seconds apart.
  - Share `.cache/http/.last-request.json` (written atomically) with `PoliteFetcher`. Cache everything in `.cache/http` (git-ignored) and never delete it by hand. `--from-cache` rebuilds a snapshot from cached pages with no network.
  - CI never needs a browser: Playwright is an optional extra and no test imports it.
- **The catalog is the authority.** Banner is only a cross-check. Every hand fix goes in the level's shared `overrides.json` with a reason.
- **Fix rule for checked majors:** a fix that would change a **checked** major's data waits for the user's OK before it is committed. `publish` never overwrites a checked major's `courses.json` with a different build: it keeps the file, lists the before and after under STATUS.md's "Checked majors changed by this build" (`not written: needs the user's OK`), and exits 1 on every run until then. Ask the user; after their OK, rerun with `--accept-checked <id>` (repeatable) to write it, and commit. The one approved change so far is each course's `catalogUrl`.
- **Corequisites and notes never block eligibility.** Corequisites stay out of the dagre layout and the highlight traversal.
- **Lines never cross a course they don't connect to.** Prerequisite edges are drawn through dagre's routes (`layout.ts` routes + `RoutedEdge`): straight across columns, bending only in the gaps. Corequisite lines aren't laid out, so they show only while one of their courses is selected.
- **Deploys run on every push to `main`**, after all tests pass (`.github/workflows/deploy.yml` calls `test.yml`). The build guard (`web/scripts/check-data.mjs`) ships a checked major, and an auto-built one only when it built clean. It holds the rest (draft or build warnings, validation errors: no `courses.json`), and it refuses when a checked major has no `courses.json`, a `courses.json` is the sample, invalid or in the wrong state, or `majors.json` is out of date. The guard can't build anything: the pin tests in `tests/test_build.py` are what block a checked major from changing or failing. CI fails unless every folder whose `program.json` is checked (found by glob) rebuilds clean and identical to its committed `courses.json`, and every shipped auto-built major rebuilds identical too, so a forgotten republish fails.
- **Auto-built majors** carry the label `Auto-built from the catalog and not yet checked by a person. Confirm with the catalog and your advisor.` and the picker tag `not yet checked`. Never drop either.
- **Progress is shared across majors** under `owlpath:v1:2026-2027:status`, keyed by course id. Never rename that key or drop ids from other majors when loading, or students lose progress.

## Environment and commands

- Python 3.13 virtual environment at `.venv/`. Shell state doesn't persist between Bash calls, so call `.venv/bin/python` / `.venv/bin/pip` / `.venv/bin/pytest` directly.
- Web app needs Node ≥ 22.12 (Vite 8). Run these from `web/`:
  - `npm ci` installs dependencies.
  - `npm run dev` starts the dev server.
  - `npm test` runs all Vitest tests.
  - `npm test -- normalize` runs one test file, matched by name.
  - `npm run build` typechecks and builds for production. The guard above can **refuse** it.
  - `npm run build:sample` builds against whatever data is present, for local previews only.
  - CI: `test.yml` runs pytest and the web tests and build on every pull request and every push to another branch. A push to `main` runs the same tests, then deploys to GitHub Pages. You can also start a deploy by hand: Actions → "Deploy web app to GitHub Pages".
- Data pipeline commands, run from the repo root:
  - `.venv/bin/pip install -e '.[dev]'` installs the pipeline (`'.[dev,crawl]'` adds Playwright for crawling).
  - `.venv/bin/pytest` runs all pipeline tests.
  - `.venv/bin/pytest tests/test_validate.py::test_prereq_cycle_is_error -v` runs a single test.
  - `.venv/bin/python -m owlpath_pipeline.crawl <undergraduate|graduate> [--refresh | --from-cache]` crawls a whole catalog level into `catalog/<level>/catalog-courses.json` and `programs.json`. It is slow (120 s per uncached page) and opens a browser, so run it only when asked. Rerunning resumes from the cache. `--refresh` clears that level's cached pages first. `--from-cache` rebuilds the snapshot from cached pages only.
  - `.venv/bin/python -m owlpath_pipeline.publish` drafts every in-scope program in the snapshot: a new draft for a program without a folder, a refresh of an untouched draft, and never a change to an edited or checked `program.json` (STATUS.md lists how a fresh draft differs). Each draft records its `catoid` and `poid`. An untouched draft folder that no in-scope program drafted to this run (renamed, removed or re-slugged) is retired: deleted and listed under STATUS.md's "Retired drafts". An edited one is held and kept instead. Then publish builds every major from the snapshot and writes each `courses.json` and `build-report.md`, then `majors.json` and `STATUS.md`. A checked major that fails to build keeps its committed `courses.json` and exits 1, and so does a checked major whose build changed until `--accept-checked <id>` (see the fix rule). `--from-pdfs` reads hand-saved listing PDFs instead (see below), drafts and retires nothing, and refuses (exit 2) when a level in use has no PDFs.
  - `.venv/bin/python -m owlpath_pipeline.build <major> [--draft]` (e.g. `bs-dsa`) builds one major's `courses.json` and `build-report.md` from the snapshot. Without `--draft` it only writes `courses.json` when there are no unresolved warnings. Like publish, it never overwrites a checked major's `courses.json` with a different build unless given `--accept-checked` (after the user's OK).
  - `.venv/bin/python -m owlpath_pipeline.banner <major>` writes that major's `banner-diff.md`. It fetches politely (about 2 minutes per uncached course), so run it in the background.
- **Catalog input:** catalog.kennesaw.edu blocks plain HTTP clients (HTTP 202), so the crawler drives a real browser politely and saves each level as the committed snapshot in `data/<year>/catalog/<level>/` (`<level>` is `undergraduate` or `graduate`; KSU publishes them as separate catalogs with their own catoid). Each major's `program.json` names its catalog with `"level"`. The old route, listing PDFs printed by hand to `catalog/<level>/<prefix>.pdf`, still works through `--from-pdfs`; the only PDFs left in the repo are test fixtures in `tests/fixtures/pdf/`. A checked major's `program-page.pdf` is a reference copy, not read by the build.
- **Adding or checking a major:** `publish` drafts a `program.json` for every in-scope program in the snapshot and auto-builds it. To check one, review its `build-report.md` and map with the user, put the fixes in the level's `overrides.json` with reasons (and `choices` / `lessCommon` in `program.json`), run the Banner check, spot-check with the user, then set `"checked": true` in its `program.json`, clear its `draftWarnings` (publish holds a major that still has them, and a held checked major blocks the publish), add its `(catoid, poid)` to `config.KNOWN_PROGRAM_IDS` so its id never changes, and republish. The pin test finds checked majors by glob, so from then on CI fails unless it rebuilds clean and identical. Its `courses.json` is now the reviewed copy: publish never overwrites it with a different build, and later changes follow the fix rule above (`--accept-checked <id>` after the user's OK).
