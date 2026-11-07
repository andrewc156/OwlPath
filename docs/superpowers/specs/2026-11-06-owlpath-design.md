# OwlPath Design

**Status:** approved · 2026-11-06
**Builds on:** `docs/mvp-spec.md`. The spec stays authoritative for scope, the data source and polite-scraping rules, the prerequisite rules, eligibility and what's out of scope. This document adds the stack, the final data schema, the folder layout and the frontend design. Wherever the two disagree, this document wins, and the spec gets updated to match.

## Intent

KSU CS students need to see, at a glance, what a course requires and what it unlocks. They also need to know what they can take next given what they've done. OwlPath is a free, static prerequisite map for the BS in Computer Science (2026–27 catalog), inspired by GradGT (Georgia Tech) but built independently.

## Goals, non-goals and anti-goals

- **Goals:**
  - Pick a course and see its prerequisite chain and what it unlocks.
  - Mark courses as taken or in progress and see what's eligible now and next term.
  - Filter by concentration.
  - Trust the data: every course links to the official catalog.
- **Non-goals:** everything in the spec's "Out of scope" list, such as accounts, degree audit and semester planning.
- **Anti-goals (failure even if it technically works):**
  - Showing a wrong prerequisite as fact.
  - Looking like an official KSU tool.
  - Copying GradGT's look or code wholesale.
  - Needing a server.

## Constraints

- A static site on GitHub Pages under the base path `/OwlPath/`, with no backend and no runtime calls to KSU.
- The data is built offline by the Python pipeline (`docs/superpowers/plans/2026-11-06-owlpath-data-pipeline.md`), hand-reviewed and committed.
- Student status lives only in `localStorage`. Every read and write must survive storage being unavailable.

## Approaches considered (data schema leaves)

How a prerequisite tree marks a minimum grade or an alternative outside the program:

- **A. Plain IDs by default, an object only when needed** (chosen). `"MATH 2345"` means an in-graph course with the default grade C. `{ "course": "CSE 1322", "minGrade": "B" }` or `{ "external": "MTRE 2610", "minGrade": "B" }` is used only when needed. It reads like the user's brief and keeps each grade next to the logic it belongs to. The cost is that TypeScript sees a union, which one load-time function turns into a single shape.
- B. Always objects. Uniform, but wordy and harder to hand-edit.
- C. String-only trees plus side lists on the course (`minGrades`, `external`). The trees stay pure strings, but grades sit apart from their branch, and one course can't have different grades in different branches.

## Stack (decided by the user)

React + Vite + TypeScript, React Flow (`@xyflow/react`) with dagre for automatic layout, course data as static JSON, deployed to GitHub Pages, no backend.

## Data schema (final)

File: `data/2026-2027/courses.json`. Contract: `data/schema/courses.schema.json`.

```ts
type Grade = "A" | "B" | "C" | "D";
type Leaf = string                                   // in-graph course, minGrade "C"
          | { course: string; minGrade?: Grade }     // in-graph course, explicit grade
          | { external: string; minGrade?: Grade };  // alternative outside the program: text, not a node
type Logic = Leaf | { and: Logic[] } | { or: Logic[] };

type Group = "core-field" | "major-required" | "conc-data-science" | "conc-cyber"
           | "conc-ai" | "major-elective" | "gen-ed-math" | "prereq-only";

interface Course {
  id: string;            // "CS 3305", pattern ^[A-Z]{2,4} \d{4}[A-Z]?$
  title: string;
  credits: string;       // "3", or a range like "1-3"
  description: string;
  catalogYear: string;   // "2026-2027"
  catalogUrl: string;
  groups: Group[];       // non-empty
  prereqs: Logic | null;
  coreqs: Logic | null;
  notes: string[];       // placement, standing, permission, etc.; never block eligibility
}

interface Dataset { catalogYear: string; source: string; courses: Course[] }
```

Rules:
- A string leaf is always an in-graph course with grade C. External alternatives are always objects.
- The pipeline writes the shortest form: a string when the leaf is an in-graph course with grade C, otherwise an object.
- `{ "course": "X", "minGrade": "C" }` is never written. An object leaf only appears when the grade isn't C or the course is external.

**Changes the pipeline plan must absorb:**
- Rename `prereq`/`coreq` to `prereqs`/`coreqs`.
- Add `description`, parsed from the course page.
- Allow string leaves in the schema and validator, and have the build emit the short form.

**Who makes those changes (my call):** the pipeline plan hasn't started yet, so it gets revised in place to this schema before anyone builds from it. This document's schema is the only one that will land. The frontend is built and tested against a small hand-written sample, `web/src/data/sample.json`, which follows this schema and covers the tricky cases: CSE 1322's B grades, CS 3305's nested OR with externals, the mutual corequisites CSE 1321 ↔ CSE 1321L, and a notes-only course. The app switches to `data/2026-2027/courses.json` once the reviewed data is committed.

## Folder structure

```
CLAUDE.md
docs/                     mvp-spec.md, superpowers/specs/, superpowers/plans/
pyproject.toml
owlpath_pipeline/         Python data pipeline (see pipeline plan)
tests/                    pipeline tests + fixtures
data/
  schema/courses.schema.json
  2026-2027/              program.json, overrides.json, courses.json, reports
web/                      Vite + React + TS app
  index.html  vite.config.ts  package.json  tsconfig.json
  src/
    data/                 load + normalize dataset, types
    logic/                eligibility, graph building, layout, highlighting
    components/           graph, course node, junction node, detail panel, filters, list view
    state/                status store (localStorage)
    App.tsx  main.tsx
.github/workflows/deploy.yml
```

The app **imports** `data/2026-2027/courses.json` directly, so it's bundled at build time and never fetched. Vite needs `server.fs.allow` to reach the repo root.

## Frontend design

**Loading.** `normalize(dataset)` turns every leaf into an object, `{ kind: "course" | "external", id, minGrade }` with grade defaulting to C. All later code uses only the normalized form.

**Graph.**
- One node per course.
- Prerequisite links run from the required course to the course that needs it.
- A top-level `and` becomes direct links.
- Every `or` becomes a small **junction node**. Its course alternatives link into it, and it links to the target course.
- An `and` nested inside an `or` (CS 3305's "CSE 1322 and CSE 1322L") gets its own junction marked AND.
- External alternatives aren't nodes. The junction shows a small "+N other" marker, and the detail panel lists them as text with their grades.
- A minimum grade other than C appears as a label on its link, for example "B".

**Corequisites** are dashed links. They're **left out of the dagre layout** because mutual pairs like CSE 1321 ↔ CSE 1321L would form cycles. They're drawn after positions are computed. *(My call:)*
- **No junction nodes** for corequisites, because junctions need a layout position. Each in-graph course anywhere in a coreq tree gets one dashed link to the course. The AND/OR structure and any externals appear only in the detail panel, for example "Take with: CSE 1322L, and one of MATH 1113 / MATH 1190 / MATH 2202 (or MATH 1179, outside program)".
- **Highlighting doesn't follow corequisite links.** The prerequisite chain and unlock sets use prerequisite links only. The selected course's direct corequisites get a lighter "take with" highlight, which isn't followed any further.

**Layout.** dagre, left to right (roughly freshman to senior), using prerequisite links and junctions only. Positions are computed once at load and memoized.

**Selecting a course** does three things:
- It highlights its **whole prerequisite chain**, following every link backward through junctions.
- It highlights **everything it unlocks**, following every link forward.
- It dims everything else.

Clicking empty space clears the selection.

**Detail panel** for the selected course shows:
- Title, credits and description
- Prerequisites as readable text with grades, for example: *MATH 2345 or CSE 2300 (outside program), and CSE 1322 + CSE 1322L (B or better), or MTRE 2610 (B) …*
- Corequisites
- Notes
- A link to the catalog page
- The status control

**Status and eligibility.**
- Each course is **not taken**, **in progress** or **complete**. The status is stored in `localStorage` under `owlpath:v1:2026-2027:status`, wrapped in try/catch, and defaults to all not taken.
- A course leaf counts as satisfied when it's complete, or, for the "next term" check, when it's complete or in progress. An external leaf never counts as satisfied. `and` and `or` are evaluated normally.
- Node states:
  - **complete**
  - **in progress**
  - **eligible now:** prerequisites met using completed courses
  - **eligible next term:** met only by also counting in-progress courses
  - **locked**
  - **no prerequisites:** eligible now
- Each state has a distinct colour **and** an icon or text label, so it isn't conveyed by colour alone.
- **Corequisites never block eligibility.** The panel shows each one as met (complete or in progress) or as "take with".
- Notes never block eligibility.

**Concentration filter.** A control with All, Data Science, Cyber & Network Security, AI and General electives. Choosing one emphasizes that group's courses and their prerequisite chains and dims the rest. When a course is selected, the selection highlight takes precedence.

**Search.** A box to find and select a course by ID or title.

**Small screens** (width under 768px): instead of the graph, show a searchable course list with each course's state. Tapping a course opens the detail panel.

**Notice.** A persistent footer says "Not official advising. Always confirm with the KSU catalog and your advisor," with a link to the catalog.

**Deploy.** A GitHub Actions workflow builds `web/` with `base: "/OwlPath/"` and publishes to Pages. The pipeline doesn't run in CI, because the data is committed.
- **Until the reviewed dataset is committed, the workflow runs only on manual trigger** (`workflow_dispatch`), as the user decided. Sample data must never be published.
- As a safeguard, the build **fails** if the bundled dataset is the sample, or if `data/2026-2027/courses.json` is missing.
- After the data review is finished, the user switches the trigger to deploy on every push to `main`.

**Testing.** Vitest covers `normalize`, eligibility, graph building (junctions and externals) and the transitive highlight sets. The pipeline keeps its pytest suite.

## Left to the builder

Visual styling and colours (within the accessibility rule above), the component breakdown, React Flow node styling, the dagre spacing values, the exact node sizes and whether to use a state library.
