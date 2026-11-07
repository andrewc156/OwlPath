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
tests/                    pipeline tests + captured HTML fixtures
data/
  schema/courses.schema.json   contract between the pipeline and the app
  2026-2027/              program.json, overrides.json, courses.json (committed), reports
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
- **Deploys are manual-only** (`workflow_dispatch`) until the reviewed dataset is committed. Sample data must never be published.

## Environment and commands

- Python 3.13 virtual environment at `.venv/`. Shell state doesn't persist between Bash calls, so call `.venv/bin/python` / `.venv/bin/pip` / `.venv/bin/pytest` directly.
- No code exists yet. Add build, lint and test commands here as the plans create them.
