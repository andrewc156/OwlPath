# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Brief

OwlPath is an interactive prerequisite map for Kennesaw State's College of Computing and Software Engineering. It is inspired by GradGT (Georgia Tech's prerequisite chart) but built independently. Students pick a course and see what it requires and what it unlocks. They can mark courses as complete or in progress and see what they're eligible for now or next term.

**MVP scope:** the BS in Computer Science, 2026–27 catalog. That means the core field of study, the major requirements, the three concentrations and the elective list, plus every course needed to reach them, including MATH and other prefixes. KSU's intro sequence is **CSE 1321/1322**.

**Stack:** React + Vite + TypeScript, React Flow (`@xyflow/react`) with dagre for automatic layout, course data as a static JSON file bundled into the app, deployed to GitHub Pages. There is no backend. A Python pipeline (`owlpath_pipeline/`) builds the JSON offline from the KSU catalog.

**Source documents. Read the relevant one before designing or building, and don't reopen settled questions:**
- `docs/mvp-spec.md` covers scope, the data source and polite-scraping rules, the prerequisite rules, eligibility and what's out of scope.
- `docs/superpowers/specs/2026-11-06-owlpath-design.md` covers the stack, the final schema, the folder layout and the frontend design. It wins over the spec where they differ.
- `docs/superpowers/plans/` holds the build plans: the data pipeline and the web app.

## Folder structure

```
docs/                     spec, design, plans
pyproject.toml
owlpath_pipeline/         Python data pipeline: fetch, parse, build, Banner cross-check
tests/                    pipeline tests + a captured Banner HTML fixture
data/
  schema/courses.schema.json   contract between the pipeline and the app
  2026-2027/              catalog/*.pdf, program-page.pdf, program.json, overrides.json, courses.json (committed), reports
web/                      Vite + React + TS app
  src/data/  src/logic/  src/components/  src/state/
.github/workflows/deploy.yml
```

## Data schema

`data/2026-2027/courses.json` is `{ catalogYear, source, courses: Course[] }`.

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
  groups: ("core-field" | "major-required" | "conc-data-science" | "conc-cyber"
          | "conc-ai" | "major-elective" | "gen-ed-math" | "prereq-only")[];
  prereqs: Logic | null;
  coreqs: Logic | null;
  notes: string[];       // placement, standing, permission: shown, never blocking
}
```

For example, `"CS 1321 and (MATH 1113 or MATH 1190)"` is stored as `{ "and": ["CSE 1321", { "or": ["MATH 1113", "MATH 1190"] }] }`. The pipeline writes the shortest form: an object leaf appears only for a grade other than C or an external course.

## Rules that are easy to get wrong

- **Fetching the catalog:** honor `robots.txt` (`crawl-delay: 120`), use the honest User-Agent in `owlpath_pipeline/config.py` and cache everything. Never spoof a browser. If the catalog returns empty or blocked responses, stop and ask the user.
- **The catalog is the authority.** Banner is only a cross-check. Every hand fix goes in `overrides.json` with a reason.
- **Corequisites and notes never block eligibility.** Corequisites stay out of the dagre layout and the highlight traversal.
- **Deploys run on every push to `main`**, after all tests pass (`.github/workflows/deploy.yml` calls `test.yml`). The build refuses sample data, so it must never be published.

## Environment and commands

- Python 3.13 virtual environment at `.venv/`. Shell state doesn't persist between Bash calls, so call `.venv/bin/python` / `.venv/bin/pip` / `.venv/bin/pytest` directly.
- Web app needs Node ≥ 22.12 (Vite 8). Run these from `web/`:
  - `npm ci` installs dependencies.
  - `npm run dev` starts the dev server.
  - `npm test` runs all Vitest tests.
  - `npm test -- normalize` runs one test file, matched by name.
  - `npm run build` typechecks and builds for production. It **refuses to run** until the reviewed `data/2026-2027/courses.json` exists and isn't the sample.
  - `npm run build:sample` builds against whatever data is present, for local previews only.
  - CI: `test.yml` runs pytest and the web tests and build on every pull request and every push to another branch. A push to `main` runs the same tests, then deploys to GitHub Pages. You can also start a deploy by hand: Actions → "Deploy web app to GitHub Pages".
- Data pipeline commands, run from the repo root:
  - `.venv/bin/pip install -e '.[dev]'` installs the pipeline.
  - `.venv/bin/pytest` runs all pipeline tests.
  - `.venv/bin/pytest tests/test_validate.py::test_prereq_cycle_is_error -v` runs a single test.
  - `.venv/bin/python -m owlpath_pipeline.build [--draft]` builds `courses.json` and `build-report.md`. Without `--draft` it only writes `courses.json` when there are no unresolved warnings.
  - `.venv/bin/python -m owlpath_pipeline.banner` writes `banner-diff.md`. It fetches politely (about 2 minutes per course), so run it in the background.
- **Catalog input:** catalog.kennesaw.edu blocks automated clients (HTTP 202), so the course data comes from PDFs saved by hand. In a browser, open the catalog's Courses listing, filter to one prefix, expand all courses, and print to PDF as `data/<year>/catalog/<prefix>.pdf`. The program page goes in `data/<year>/program-page.pdf`, outside `catalog/`, because every PDF in `catalog/` is read as a course listing.
