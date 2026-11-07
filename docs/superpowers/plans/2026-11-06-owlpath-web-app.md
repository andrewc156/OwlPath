# OwlPath Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the static OwlPath site. It shows the BS CS prerequisite graph, highlights what a selected course requires and unlocks, tracks course status in the browser and filters by concentration.

**Architecture:** The app bundles the dataset at build time and converts every prerequisite leaf to one internal shape. Pure TypeScript modules then compute eligibility, the graph (course nodes plus AND/OR junction nodes), the dagre layout, highlight sets and display props, all tested with Vitest. Thin React components render those results with React Flow. The data source is a small sample until the reviewed `data/2026-2027/courses.json` exists. A build guard and a manual-only deploy keep the sample off the public site.

**Tech Stack:** React + Vite + TypeScript, `@xyflow/react`, `@dagrejs/dagre`, Vitest + jsdom, GitHub Actions → GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-11-06-owlpath-design.md`, which builds on `docs/mvp-spec.md`.

## Global Constraints

- Everything lives under `web/`. Run commands from `web/` with `npm run …`. Use Node 22 LTS.
- Vite `base: "/OwlPath/"`. `server.fs.allow: [".."]` so the app can import `../data/`.
- The data schema is exactly the design's `Course`/`Logic` types. A string leaf is an in-graph course with grade C. Missing `minGrade` means `"C"`.
- `localStorage` key `owlpath:v1:2026-2027:status`. Every access is in try/catch, and the app works with storage unavailable.
- **Corequisites and notes never block eligibility.** Corequisite links are left out of the layout and the highlight traversal.
- Node states are `complete`, `in-progress`, `eligible-now`, `eligible-next-term` and `locked`. Each is shown with a colour **and** a text or icon label.
- The persistent footer text is exactly: `Not official advising. Always confirm with the KSU catalog and your advisor.` It links to `https://catalog.kennesaw.edu/`.
- No runtime network requests, and no backend.
- **The deploy workflow is `workflow_dispatch` only.** A production build fails if the bundled dataset is the sample.

## Review Focus

1. **`localStorage` that throws or holds corrupt JSON.** The app must still load with every course not taken. Covered by a Task 6 test.
2. **Saved status for a course no longer in the dataset** (after a data update). It must be ignored, not crash anything. Covered by a Task 6 test.
3. **A course with no links at all**, for example CSE 4983 with notes only. It must still get a layout position and be visible. Covered by a Task 4 test.
4. **Searches written differently from the ID**, like `cs3305`, `CS3305` or ` cs 3305 `. They must find CS 3305. Covered by a Task 9 test.
5. **An OR whose alternatives are all external.** It must not create an orphan junction node, and the course must still show it is locked. Covered by a Task 3 test.

## File Structure

```
web/
  package.json  vite.config.ts  tsconfig.json  index.html
  scripts/check-data.mjs            production build guard
  src/
    main.tsx  App.tsx  styles.css
    data/types.ts                   Course/Logic (design schema) + normalized N* types
    data/normalize.ts               normalize(dataset)
    data/dataset.ts                 loadDataset(): real file if present, else sample
    data/sample.json                hand-written sample (Task 1)
    logic/eligibility.ts            evaluate, nodeState
    logic/graph.ts                  buildGraph
    logic/layout.ts                 layoutGraph
    logic/highlight.ts              highlightSets, concentrationSet
    logic/view.ts                   toFlow (graph + state -> React Flow props)
    logic/describe.ts               describeLogic (readable requirement text)
    logic/search.ts                 searchCourses
    state/status.ts                 loadStatus, saveStatus, useStatus
    components/GraphView.tsx  CourseNode.tsx  JunctionNode.tsx
    components/DetailPanel.tsx  Filters.tsx  CourseList.tsx  Footer.tsx
  src/**/*.test.ts                  colocated Vitest tests
.github/workflows/deploy.yml
```

---

### Task 1: Scaffold, types, sample data, normalize

**Files:**
- Create: the `web/` scaffold (Vite `react-ts` template), `web/src/data/{types.ts,normalize.ts,dataset.ts,sample.json}`
- Modify: `CLAUDE.md` (Commands section), `.gitignore` (add `web/node_modules/`, `web/dist/`)
- Test: `web/src/data/normalize.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: the design's `Grade`, `Leaf`, `Logic`, `Group`, `Course` and `Dataset`, plus:
    - `type NLeaf = { kind: "course" | "external"; id: string; minGrade: Grade }`
    - `type NExpr = NLeaf | { kind: "and" | "or"; children: NExpr[] }`
    - `type NCourse = Omit<Course, "prereqs" | "coreqs"> & { prereqs: NExpr | null; coreqs: NExpr | null }`
    - `type NDataset = { catalogYear: string; source: string; courses: NCourse[]; byId: Map<string, NCourse> }`
  - `normalize(dataset: Dataset): NDataset`
  - `pickDataset(real: Dataset | undefined, sample: Dataset): Dataset` returns `real` when it's defined, otherwise `sample`.
  - `loadDataset(): NDataset` returns `normalize(pickDataset(<glob result>, sample))`, where the glob result comes from `import.meta.glob("../../../data/2026-2027/courses.json", { eager: true })`.
  - `SAMPLE_SOURCE = "SAMPLE"`, the `source` value of `sample.json`

- [ ] **Step 1: Scaffold and install**

Run `npm create vite@latest web -- --template react-ts`, then in `web/` run `npm i @xyflow/react @dagrejs/dagre` and `npm i -D vitest jsdom @types/node`. Set `base` and `server.fs.allow` in `vite.config.ts`, and add `"test": "vitest run"` to the package scripts.
Expected: `npm run build` succeeds.

- [ ] **Step 2: Write `sample.json`**

Use `"source": "SAMPLE"` and `"catalogYear": "2026-2027"`, with these 10 courses. Each has a non-empty title, credits `"3"` (labs `"1"`), a one-line description, a `catalogUrl` and groups.

| id | groups | prereqs | coreqs | notes |
|---|---|---|---|---|
| CSE 1321 | core-field | null | `"CSE 1321L"` | |
| CSE 1321L | core-field | null | `"CSE 1321"` | |
| CSE 1322 | core-field | `{"and":[{"course":"CSE 1321","minGrade":"B"},{"course":"CSE 1321L","minGrade":"B"}]}` | `{"and":["CSE 1322L",{"or":["MATH 1113","MATH 1190",{"external":"MATH 1179"}]}]}` | |
| CSE 1322L | core-field | `{"and":[{"course":"CSE 1321","minGrade":"B"},{"course":"CSE 1321L","minGrade":"B"}]}` | `"CSE 1322"` | |
| MATH 1113 | gen-ed-math | null | null | |
| MATH 1190 | gen-ed-math | `"MATH 1113"` | null | `["By Placement"]` |
| MATH 2345 | core-field | `"MATH 1190"` | null | |
| CS 3305 | major-required | `{"and":[{"or":["MATH 2345",{"external":"CSE 2300"}]},{"or":[{"and":[{"course":"CSE 1322","minGrade":"B"},{"course":"CSE 1322L","minGrade":"B"}]},{"external":"MTRE 2610","minGrade":"B"},{"external":"CPE 3000","minGrade":"B"}]}]}` | null | |
| CS 3642 | conc-ai | `"CS 3305"` | null | |
| CSE 4983 | major-elective | `{"or":[{"external":"CSE 4900"},{"external":"CSE 4901"}]}` | null | `["Senior standing"]` |

CSE 4983's prerequisites are invented. They exist only to exercise an OR whose alternatives are all external.

- [ ] **Step 2b: Write the failing tests in `normalize.test.ts`**

```ts
test("string leaf becomes course with grade C", () => {
  expect(normalize(ds({ prereqs: "MATH 1113" })).courses[0].prereqs).toEqual({ kind: "course", id: "MATH 1113", minGrade: "C" });
});
test("object leaves keep grade; external keeps kind", () => {
  const p = normalize(ds({ prereqs: { or: [{ course: "CSE 1322", minGrade: "B" }, { external: "MTRE 2610" }] } })).courses[0].prereqs;
  expect(p).toEqual({ kind: "or", children: [{ kind: "course", id: "CSE 1322", minGrade: "B" }, { kind: "external", id: "MTRE 2610", minGrade: "C" }] });
});
test("null stays null and byId indexes every course", () => { /* sample: byId.size === 10, byId.get("CS 3305") defined */ });
test("pickDataset falls back to the sample, and prefers real data", () => {
  expect(pickDataset(undefined, sample).source).toBe("SAMPLE");
  expect(pickDataset({ ...sample, source: "catalog" }, sample).source).toBe("catalog");
});
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `npm test -- normalize`. Expected: FAIL (module not found).

- [ ] **Step 4: Implement `types.ts`, `normalize.ts` and `dataset.ts`**

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `npm test -- normalize`. Expected: 4 passed.

- [ ] **Step 6: Add web commands to `CLAUDE.md` and update `.gitignore`**

The commands are `cd web && npm ci`, `npm run dev`, `npm test`, `npm test -- <file-pattern>` for one test file, and `npm run build`.

- [ ] **Step 7: Commit**

```bash
git add web .gitignore CLAUDE.md
git commit -m "feat(web): scaffold app with schema types, sample data and normalize"
```

---

### Task 2: Eligibility

**Files:** Create `web/src/logic/eligibility.ts`. Test `web/src/logic/eligibility.test.ts`.

**Interfaces:**
- Consumes: `NExpr`, `NCourse`
- Produces:
  - `type Status = "not-taken" | "in-progress" | "complete"`
  - `type StatusMap = Record<string, Status>` (a missing key means `"not-taken"`)
  - `type NodeState = "complete" | "in-progress" | "eligible-now" | "eligible-next-term" | "locked"`
  - `evaluate(expr: NExpr | null, status: StatusMap, countInProgress: boolean): boolean`. `null` is true and an external leaf is false.
  - `nodeState(course: NCourse, status: StatusMap): NodeState`

- [ ] **Step 1: Write the failing tests** (they use the sample via `normalize`)

```ts
test("no prereqs -> eligible-now", () => expect(nodeState(c("CSE 1321"), {})).toBe("eligible-now"));
test("own status wins", () => expect(nodeState(c("CS 3305"), { "CS 3305": "complete" })).toBe("complete"));
test("AND needs all", () => expect(nodeState(c("CSE 1322"), { "CSE 1321": "complete" })).toBe("locked"));
test("in-progress prereqs -> eligible-next-term", () =>
  expect(nodeState(c("CSE 1322"), { "CSE 1321": "in-progress", "CSE 1321L": "complete" })).toBe("eligible-next-term"));
test("OR satisfied by one in-graph branch", () =>
  expect(nodeState(c("CS 3305"), { "MATH 2345": "complete", "CSE 1322": "complete", "CSE 1322L": "complete" })).toBe("eligible-now"));
test("external leaf never satisfies", () => expect(nodeState(c("CSE 4983"), {})).toBe("locked"));
test("coreqs do not block", () => expect(nodeState(c("CSE 1321"), {})).toBe("eligible-now"));
test("notes do not block", () => expect(nodeState(c("MATH 1190"), { "MATH 1113": "complete" })).toBe("eligible-now"));
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `npm test -- eligibility`. Expected: FAIL.

- [ ] **Step 3: Implement `evaluate` and `nodeState`**

`nodeState` checks in this order: the course's own status first; then `evaluate(prereqs, status, false)` for eligible-now; then `evaluate(prereqs, status, true)` for eligible-next-term; otherwise locked.

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `npm test -- eligibility`. Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/logic/eligibility*
git commit -m "feat(web): compute course eligibility"
```

---

### Task 3: Graph building

**Files:** Create `web/src/logic/graph.ts`. Test `web/src/logic/graph.test.ts`.

**Interfaces:**
- Consumes: `NCourse`, `NExpr`
- Produces:
  - `type GNode = { id: string; kind: "course"; courseId: string; externalOnlyGroups: number } | { id: string; kind: "junction"; op: "and" | "or"; target: string; externals: NLeaf[] }`
  - `type GEdge = { id: string; source: string; target: string; kind: "prereq" | "coreq"; minGrade?: Grade }`. `minGrade` is set only when it isn't C.
  - `type Graph = { nodes: GNode[]; edges: GEdge[] }`
  - `buildGraph(courses: NCourse[]): Graph`. A course node's id is its course id. A junction's id is `j:<courseId>:<path>`, where `path` is the dot-joined child indexes from the root, e.g. `j:CS 3305:1`.

Prerequisite rules:
- A top-level leaf or `and` becomes direct edges into the course.
- Each `or`, and each `and` nested under an `or`, becomes a junction. Its in-graph children link into it, and it links to its parent (a course or another junction).
- External leaves are not nodes. They are listed in their junction's `externals`.
- An `or` with no in-graph descendants creates no junction and no edges. Instead it adds 1 to the course node's `externalOnlyGroups`.

Corequisite rule: each in-graph course leaf anywhere in `coreqs` gets one `coreq` edge into the course, with no junctions.

- [ ] **Step 1: Write the failing tests** (they use the sample)

```ts
test("AND prereqs are direct edges with grade labels", () => {
  expect(prereqEdgesInto("CSE 1322")).toEqual([{ source: "CSE 1321", minGrade: "B" }, { source: "CSE 1321L", minGrade: "B" }]);
});
test("CS 3305 has two OR junctions and a nested AND junction", () => {
  const ids = junctionsFor("CS 3305").map(j => `${j.id}:${j.op}`);
  expect(ids).toEqual(["j:CS 3305:0:or", "j:CS 3305:1:or", "j:CS 3305:1.0:and"]);
});
test("externals are listed on the junction, never as nodes", () => {
  expect(junction("j:CS 3305:1").externals.map(e => e.id)).toEqual(["MTRE 2610", "CPE 3000"]);
  expect(g.nodes.find(n => n.id === "MTRE 2610")).toBeUndefined();
});
test("all-external OR creates no junction and counts on the course", () => {
  expect(junctionsFor("CSE 4983")).toEqual([]);
  expect(courseNode("CSE 4983").externalOnlyGroups).toBe(1);
});
test("coreq edges are flat and dashed-kind", () => {
  expect(coreqSourcesInto("CSE 1322").sort()).toEqual(["CSE 1322L", "MATH 1113", "MATH 1190"]);
});
test("grade C edges carry no minGrade", () => expect(edge("MATH 1113", "MATH 1190").minGrade).toBeUndefined());
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `npm test -- graph`. Expected: FAIL.

- [ ] **Step 3: Implement `buildGraph`**

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `npm test -- graph`. Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/logic/graph*
git commit -m "feat(web): build course graph with AND/OR junctions"
```

---

### Task 4: Layout

**Files:** Create `web/src/logic/layout.ts`. Test `web/src/logic/layout.test.ts`.

**Interfaces:**
- Consumes: `Graph`
- Produces:
  - `type Positions = Map<string, { x: number; y: number }>`
  - `layoutGraph(graph: Graph): Positions` uses dagre `rankdir: "LR"` with `prereq` edges only. Course nodes are 160×48 and junctions 16×16 (the builder may tune these).

- [ ] **Step 1: Write the failing tests**

```ts
test("every node gets a position", () => expect([...pos.keys()].sort()).toEqual(g.nodes.map(n => n.id).sort()));
test("prereq flows left to right", () => expect(pos.get("CSE 1321")!.x).toBeLessThan(pos.get("CS 3305")!.x));
test("mutual coreqs do not break layout", () => expect(() => layoutGraph(g)).not.toThrow());
test("isolated course is positioned", () => expect(pos.get("CSE 4983")).toBeDefined());
```

- [ ] **Step 2: Run, then implement, then run again**

Run: `npm test -- layout`. Expected: FAIL before, 4 passed after.

- [ ] **Step 3: Commit**

```bash
git add web/src/logic/layout*
git commit -m "feat(web): dagre left-to-right layout"
```

---

### Task 5: Highlight sets

**Files:** Create `web/src/logic/highlight.ts`. Test `web/src/logic/highlight.test.ts`.

**Interfaces:**
- Consumes: `Graph`, `NCourse`, `Group`
- Produces:
  - `type Highlight = { selected: string; ancestors: Set<string>; descendants: Set<string>; takeWith: Set<string> }`. The sets hold node ids, including junction ids.
  - `highlightSets(graph: Graph, selected: string): Highlight` follows `prereq` edges only. `takeWith` holds only the direct `coreq` neighbours, in both directions.
  - `concentrationSet(graph: Graph, courses: NCourse[], group: Group): Set<string>` returns the group's courses plus their ancestors.

- [ ] **Step 1: Write the failing tests**

```ts
test("ancestors of CS 3305 are its whole chain", () =>
  expect(courseIds(h("CS 3305").ancestors)).toEqual(["CSE 1321", "CSE 1321L", "CSE 1322", "CSE 1322L", "MATH 1113", "MATH 1190", "MATH 2345"]));
test("descendants of CSE 1321 go through junctions", () =>
  expect(courseIds(h("CSE 1321").descendants)).toEqual(["CS 3305", "CS 3642", "CSE 1322", "CSE 1322L"]));
test("coreqs are takeWith only, not traversed", () => {
  expect(courseIds(h("CSE 1321").takeWith)).toEqual(["CSE 1321L"]);
  expect(h("CSE 1321").ancestors.size).toBe(0);
});
test("concentration set includes prereq chain", () =>
  expect(courseIdsOf(concentrationSet(g, courses, "conc-ai"))).toContain("MATH 1113"));
```

- [ ] **Step 2: Run, then implement, then run again**

Run: `npm test -- highlight`. Expected: FAIL before, 4 passed after.

- [ ] **Step 3: Commit**

```bash
git add web/src/logic/highlight*
git commit -m "feat(web): prerequisite chain and unlock highlight sets"
```

---

### Task 6: Status store

**Files:** Create `web/src/state/status.ts`. Test `web/src/state/status.test.ts`.

**Interfaces:**
- Consumes: `Status`, `StatusMap`
- Produces:
  - `STATUS_KEY = "owlpath:v1:2026-2027:status"`
  - `loadStatus(storage: Storage | null, validIds: Set<string>): StatusMap` drops unknown ids and invalid values, and returns `{}` on any error.
  - `saveStatus(storage: Storage | null, status: StatusMap): void` never throws.
  - `useStatus(validIds: Set<string>): [StatusMap, (id: string, s: Status) => void]` uses `window.localStorage`, falling back to `null` when the access itself throws.

- [ ] **Step 1: Write the failing tests**

```ts
test("round-trips through storage", ...);                        // save then load returns same map
test("throwing storage -> empty map, save does not throw", ...); // getItem/setItem throw
test("corrupt JSON -> empty map", ...);
test("unknown course ids and bad values are dropped", ...);      // {"CS 9999":"complete","CS 3305":"done"} -> {}
test("null storage works", () => expect(loadStatus(null, ids)).toEqual({}));
```

- [ ] **Step 2: Run, then implement, then run again**

Run: `npm test -- status`. Expected: FAIL before, 5 passed after.

- [ ] **Step 3: Commit**

```bash
git add web/src/state
git commit -m "feat(web): browser-only course status store"
```

---

### Task 7: Graph view

**Files:**
- Create: `web/src/logic/view.ts`, `web/src/components/{GraphView,CourseNode,JunctionNode}.tsx`
- Modify: `web/src/App.tsx`, `web/src/styles.css`
- Test: `web/src/logic/view.test.ts`

**Interfaces:**
- Consumes: `Graph`, `Positions`, `Highlight`, `NodeState`, `nodeState`
- Produces:
  - `type ViewCtx = { highlight: Highlight | null; filter: Set<string> | null; states: Record<string, NodeState> }`
  - `toFlow(graph: Graph, positions: Positions, ctx: ViewCtx): { nodes: Node[]; edges: Edge[] }`, using React Flow's `Node`/`Edge` types
    - Course node `type: "course"`, `data: { courseId, state, externalOnlyGroups }`. Junction node `type: "junction"`, `data: { op, externalCount }`.
    - The `className` gets `dimmed`, `selected`, `ancestor`, `descendant` and `take-with` as they apply.
    - `coreq` edges get `style.strokeDasharray`. An edge with `minGrade` gets it as its `label`.
  - `GraphView` props: `{ graph, positions, ctx, onSelect: (courseId: string | null) => void }`

Dimming:
- When a course is selected, everything outside selected ∪ ancestors ∪ descendants ∪ takeWith is dimmed.
- Otherwise, when a filter is active, everything outside the filter set is dimmed.
- Selection takes precedence over the filter.

- [ ] **Step 1: Write the failing tests for `toFlow`**

```ts
test("selection dims unrelated nodes", () => expect(cls(flow({ selected: "CS 3305" }), "CSE 4983")).toContain("dimmed"));
test("ancestors and descendants are marked", () => {
  const f = flow({ selected: "CSE 1322" });
  expect(cls(f, "CSE 1321")).toContain("ancestor"); expect(cls(f, "CS 3305")).toContain("descendant");
});
test("selection beats filter", () => expect(cls(flow({ selected: "CS 3305", filter: "conc-ai" }), "CSE 1321")).not.toContain("dimmed"));
test("coreq edges are dashed and grade labels shown", ...);
test("node carries its eligibility state", () => expect(node(flow({}), "CSE 1321").data.state).toBe("eligible-now"));
```

- [ ] **Step 2: Run them to confirm they fail, implement `toFlow`, then run them again**

Run: `npm test -- view`. Expected: FAIL before, 5 passed after.

- [ ] **Step 3: Build the components and wire `App.tsx`**

Wire it in this order: `loadDataset`, then `buildGraph`, then `layoutGraph` (memoized once), then `useStatus`, the selection state and `toFlow`. Clicking a course node selects it and clicking the pane clears the selection. `CourseNode` shows the id, a short title and its state label and icon. `JunctionNode` shows `OR`/`AND` and `+N` when it has externals.

- [ ] **Step 4: Verify in the browser**

Run: `npm run dev` and open the printed URL. Use the webapp-testing skill or check by hand that:
- The sample graph renders left to right.
- Clicking CS 3305 highlights its chain and dims CSE 4983.
- Clicking the pane clears the selection.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): interactive React Flow graph with highlighting"
```

---

### Task 8: Detail panel and requirement text

**Files:**
- Create: `web/src/logic/describe.ts`, `web/src/components/DetailPanel.tsx`
- Modify: `web/src/App.tsx`
- Test: `web/src/logic/describe.test.ts`

**Interfaces:**
- Consumes: `NExpr`, `NCourse`, `useStatus`, `StatusMap`
- Produces:
  - `describeLogic(expr: NExpr | null): string`. `null` becomes `"None"`. A leaf becomes `ID`, plus ` (B)` for a grade other than C, plus `outside program` inside the parentheses for an external: `CSE 2300 (outside program)` or `MTRE 2610 (B, outside program)`. Nested groups are wrapped in parentheses; the top level isn't.
  - `DetailPanel` props: `{ course: NCourse; status: StatusMap; onStatus: (id: string, s: Status) => void; onClose: () => void }`

- [ ] **Step 1: Write the failing tests**

```ts
test("CS 3305 reads naturally", () => expect(describeLogic(prereqsOf("CS 3305"))).toBe(
  "(MATH 2345 or CSE 2300 (outside program)) and ((CSE 1322 (B) and CSE 1322L (B)) or MTRE 2610 (B, outside program) or CPE 3000 (B, outside program))"));
test("single leaf", () => expect(describeLogic(prereqsOf("MATH 1190"))).toBe("MATH 1113"));
test("null", () => expect(describeLogic(null)).toBe("None"));
```

- [ ] **Step 2: Run them to confirm they fail, implement, then run them again**

Run: `npm test -- describe`. Expected: FAIL before, 3 passed after.

- [ ] **Step 3: Build `DetailPanel`**

It shows:
- Title, credits and description
- `Prerequisites:` from `describeLogic`
- `Take with:` from `describeLogic(coreqs)`, with each in-graph corequisite marked met when it's complete or in progress
- The notes list
- A "View in catalog" link to `catalogUrl` (opens in a new tab, `rel="noopener"`)
- A three-way status control for not taken, in progress and complete

Open it when a course is selected.

- [ ] **Step 4: Verify in the browser**

Select CS 3305 and check the text matches the test. Set CSE 1321 and CSE 1321L to complete; CSE 1322 should change to eligible-now. Reload, and the statuses should still be there.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): course detail panel with status control"
```

---

### Task 9: Filter, search, small screens, footer

**Files:**
- Create: `web/src/logic/search.ts`, `web/src/components/{Filters,CourseList,Footer}.tsx`
- Modify: `web/src/App.tsx`
- Test: `web/src/logic/search.test.ts`

**Interfaces:**
- Consumes: `concentrationSet`, `NCourse`, `nodeState`
- Produces:
  - `searchCourses(courses: NCourse[], query: string): NCourse[]` matches the id ignoring case and spaces, and the title as a case-insensitive substring. Id matches come first, then the rest sorted by id. An empty query returns `[]`.
  - Filter options in order: `All` (null), `Data Science` → `conc-data-science`, `Cyber & Network Security` → `conc-cyber`, `AI` → `conc-ai`, `General electives` → `major-elective`

- [ ] **Step 1: Write the failing tests**

```ts
test.each(["cs3305", "CS3305", " cs 3305 "])("finds CS 3305 from %j", q => expect(searchCourses(cs, q)[0].id).toBe("CS 3305"));
test("title match", () => expect(searchCourses(cs, "data struct").map(c => c.id)).toContain("CS 3305"));  // sample title "Data Structures"
test("empty query -> []", () => expect(searchCourses(cs, "  ")).toEqual([]));
```

- [ ] **Step 2: Run them to confirm they fail, implement, then run them again**

Run: `npm test -- search`. Expected: FAIL before, 5 passed after.

- [ ] **Step 3: Build the UI**

- `Filters` holds the concentration selector and the search box. Choosing a search result selects that course.
- Under `max-width: 767px` (`matchMedia`), render `CourseList` instead of `GraphView`: a searchable list with each course's state label. Tapping a course opens `DetailPanel`.
- `Footer` carries the exact notice text and the catalog link from the Global Constraints.

- [ ] **Step 4: Verify in the browser**

On desktop, the AI filter should dim everything outside CS 3642's chain, and searching `cs3305` should select it. At 375px wide, the list view should appear with no horizontal scroll. The footer should be visible in both layouts.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): concentration filter, search, mobile list, notice"
```

---

### Task 10: Build guard and manual deploy

**Files:**
- Create: `web/scripts/check-data.mjs`, `.github/workflows/deploy.yml`
- Modify: `web/package.json` (`"build": "node scripts/check-data.mjs && tsc -b && vite build"`, plus `"build:sample": "tsc -b && vite build"` for local previews)

**Interfaces:**
- `check-data.mjs` exits with code 1 and a clear message if `../data/2026-2027/courses.json` is missing or its `source` is `"SAMPLE"`. Otherwise it exits with 0.

- [ ] **Step 1: Confirm the guard blocks the sample build**

With no real data file present, run `npm run build`. Expected: it exits with code 1 and prints `refusing to build: reviewed dataset data/2026-2027/courses.json not found`.

- [ ] **Step 2: Implement `check-data.mjs` and confirm the guard again**

Run `npm run build` again. Expected: the same failure. `npm run build:sample` should succeed.

- [ ] **Step 3: Write `deploy.yml`**

- Trigger: **`on: workflow_dispatch` only**, with a top comment: `# Switch to "push: branches: [main]" only after the reviewed dataset is committed (see design doc).`
- Jobs: checkout, `actions/setup-node` (Node 22, npm cache for `web/package-lock.json`), `npm ci`, `npm test` and `npm run build` in `web/`, then `actions/upload-pages-artifact` (`web/dist`) and `actions/deploy-pages`.
- Permissions: `pages: write`, `id-token: write`.

- [ ] **Step 4: Run the full suite**

Run: `npm test` in `web/`. Expected: every test passes.

- [ ] **Step 5: Commit**

```bash
git add web/scripts web/package.json .github/workflows/deploy.yml
git commit -m "ci(web): manual-only Pages deploy guarded against sample data"
```

The user enables GitHub Pages ("GitHub Actions" source) in the repo settings and starts the first deploy by hand, after pipeline Task 7 commits the reviewed data.
