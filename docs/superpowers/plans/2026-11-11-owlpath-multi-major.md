# Multi-Major (BS CS + BSDSA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a major dropdown, a reviewed BS Data Science and Analytics map and a "Reset progress" button to OwlPath.

**Architecture:**
- **Data.** Each major gets its own folder under `data/2026-2027/<program>/`, holding `program.json`, `overrides.json`, `courses.json` and its reports. The saved catalog PDFs stay shared.
- **Pipeline.** It takes the program as a CLI argument and copies the program metadata (`program`, `choices`) into `courses.json`.
- **Web app.** It loads every major's dataset, builds each graph lazily and caches it, and switches majors from a header dropdown. Status stays shared across majors.

**Tech Stack:** Python 3.13 + pytest, jsonschema, pypdf. React + Vite + TypeScript, `@xyflow/react`, dagre, Vitest.

**Spec:**
- `docs/superpowers/specs/2026-11-11-owlpath-multi-major-design.md`, which builds on
- `docs/superpowers/specs/2026-11-06-owlpath-design.md`.

## Global Constraints

- Program ids are `bs-cs` and `bs-dsa`. The default major is `bs-cs`.
- Program names are "BS Computer Science" and "BS Data Science and Analytics".
- Status `localStorage` key stays `owlpath:v1:2026-2027:status`. The selected major's key is `owlpath:v1:major`, and the URL parameter is `?major=<id>`.
- The "Show" filter keeps its "All" option. CS filters: Data Science → `["conc-data-science"]`, Cyber & Network Security → `["conc-cyber"]`, AI → `["conc-ai"]`, General electives → `["major-elective"]`. BSDSA filters: "Required courses" → `["core-field","major-required"]`, "Electives" → `["major-elective"]`.
- BSDSA choices: `["CSE 2300","MATH 2345"]`, `["STAT 1401","STAT 2332"]`, `["STAT 3120","STAT 3125"]`, `["CSE 3153","CS 3410"]`, `["DATA 4030","DATA 4140"]`. CS has `[]`.
- Reset confirmation text, exactly: "Reset all progress? This marks every course as not taken in both majors."
- The `groups` enum does not change. MATH 1179 and MATH 1189 are never nodes (user ruling).
- Catalog rules are unchanged:
  - The catalog is the authority, and every hand fix goes in that program's `overrides.json` with a reason.
  - Never fetch catalog.kennesaw.edu. It blocks automated clients, so data comes from saved PDFs.
  - Banner is fetched politely, in the background, for `bs-dsa` only.
- Deploys are automatic on `main`, so the build guard must refuse any missing, sample or invalid dataset for **any** program.
- Commit and push only as the commit steps say. The branch is `feat/multi-major`, and nothing gets merged without asking.

## Review Focus

1. **Saved progress from before this change.** A student with CS progress under the old key opens the new version. Expected: their progress is all still there on the CS map. Test in Task 5.
2. **Progress for a course that exists only in the other major** (DATA 3010 marked complete, then the student switches to CS). Expected: it isn't dropped from storage, and it's back when they switch to BSDSA. Test in Task 5.
3. **An unknown or stale `?major=` value** (for example `?major=bs-ee`, or a removed major in `localStorage`). Expected: the CS map loads and nothing crashes. Test in Task 4.
4. **A major whose folder has `program.json` but no `courses.json`** (BSDSA mid-review). Expected: the production build refuses. Test in Task 3.
5. **Switching majors while a course that doesn't exist in the new major is selected or filtered.** Expected: the selection and filter clear, and no blank panel appears. Test in Task 7.

---

## File Structure

- `data/schema/courses.schema.json`: adds required top-level `program` and `choices`.
- `owlpath_pipeline/validate.py`: checks that every choice id is a course in the dataset.
- `owlpath_pipeline/config.py`: `PROGRAMS = ("bs-cs", "bs-dsa")`, `program_dir(program) -> Path`.
- `owlpath_pipeline/build.py`: `build_dataset(..., meta)`. The CLI takes a `program` argument.
- `owlpath_pipeline/banner.py`: the CLI takes a `program` argument.
- `data/2026-2027/bs-cs/`: the current CS files, moved. `data/2026-2027/bs-dsa/`: the new files.
- `web/src/data/types.ts`: adds `Program`, `FilterOption` and `Choice`; `Dataset` and `NDataset` gain `program` and `choices`.
- `web/src/data/dataset.ts`: `loadPrograms(): NDataset[]`.
- `web/src/data/sample.json`: gains a `program` block and `choices`.
- `web/src/state/major.ts` (new): `resolveMajor`, `saveMajor`.
- `web/src/state/status.ts`: union ids, plus `resetStatus` in the hook.
- `web/src/logic/highlight.ts`: `filterSet(graph, courses, groups: Group[])`, replacing `concentrationSet`.
- `web/src/logic/choices.ts` (new): `choicePartners(choices, id): string[]`.
- `web/src/components/Filters.tsx`, `CourseNode.tsx`, `DetailPanel.tsx`, and the new `MajorPicker.tsx` and `ResetButton.tsx`.
- `web/src/App.tsx`: per-major state and a graph cache.
- `web/scripts/check-data.mjs` and `validate-dataset.mjs`: handle every program.

---

### Task 1: Schema and pipeline validator carry program metadata

**Files:**
- Modify: `data/schema/courses.schema.json`, `owlpath_pipeline/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Produces:
  - The dataset shape is `{catalogYear, source, program: {id, name, filters: [{label, groups: Group[]}]}, choices: string[][], courses}`.
  - `validate_dataset` returns `"choices: unknown course X"` for a choice id that isn't a course.

- [ ] **Step 1: Write failing tests**

Update the existing valid-dataset helper in `test_validate.py` so that it includes `"program": {"id": "bs-cs", "name": "BS Computer Science", "filters": [{"label": "AI", "groups": ["conc-ai"]}]}` and `"choices": []`. Then add:

```python
def test_missing_program_block_is_error():
    d = valid(); del d["program"]
    assert validate_dataset(d)            # schema error

def test_choice_with_unknown_course_is_error():
    d = valid(); d["choices"] = [["CSE 1321", "ZZZ 9999"]]
    assert "choices: unknown course ZZZ 9999" in validate_dataset(d)

def test_choice_needs_two_courses():
    d = valid(); d["choices"] = [["CSE 1321"]]
    assert validate_dataset(d)            # schema: minItems 2
```

- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_validate.py -v`. Expected: the 3 new tests FAIL.
- [ ] **Step 3: Implement.**
  - Schema:
    - `program` requires `id` (pattern `^[a-z0-9-]+$`), `name` (string) and `filters`. `filters` is an array of `{label: string, groups: [group enum], minItems 1}`.
    - `choices` is an array of arrays of `courseId`, each with `minItems` 2. Both are added to `required`.
  - In `validate_dataset`, after the schema check, add the unknown-choice check.
- [ ] **Step 4:** Run `.venv/bin/pytest`. Expected: every test passes except those that build a dataset without `program`, which Task 2 fixes. List any such failures by name in the ledger; don't change them here.
- [ ] **Step 5: Commit:** `git commit -m "feat: schema carries program metadata and either/or choices"`.

---

### Task 2: Pipeline runs per program; move the CS data

**Files:**
- Modify: `owlpath_pipeline/config.py`, `build.py`, `banner.py`
- Move: `git mv data/2026-2027/{program.json,overrides.json,courses.json,build-report.md,banner-diff.md,program-page.pdf} data/2026-2027/bs-cs/`
- Test: `tests/test_build.py`, `tests/test_banner.py`

**Interfaces:**
- Consumes: the Task 1 schema.
- Produces:
  - `config.PROGRAMS: tuple[str, ...] = ("bs-cs", "bs-dsa")` and `config.program_dir(program: str) -> Path` (= `DATA_DIR / program`).
  - `build_dataset(program: dict[str, list[str]], get_raw, overrides: dict, meta: dict) -> tuple[dict, list[str]]`. `meta` is `{"program": {...}, "choices": [...]}`, copied to the output as-is. A choice id missing from `program` raises `ValueError("choices: X is not in program.json")`.
  - The CLIs are `python -m owlpath_pipeline.build <program> [--draft]` and `python -m owlpath_pipeline.banner <program>`. An unknown program exits with argparse's error.

- [ ] **Step 1: Write failing tests.**
  - Update the existing `build_dataset` calls in `test_build.py` and `test_catalog_pdf.py` to pass `meta=META`, where `META = {"program": {"id": "bs-cs", "name": "BS Computer Science", "filters": [{"label": "AI", "groups": ["conc-ai"]}]}, "choices": []}`.
  - Change `test_cli_keeps_reviewed_dataset_when_warnings_remain` to monkeypatch `config.DATA_DIR`. Write the files under `tmp_path / "bs-cs"`, with `program.json` carrying `program` and `choices`, and call `build.main(["bs-cs"])`.
  - Add:

```python
def test_meta_is_copied_to_output(): ...          # dataset["program"] == META["program"]; dataset["choices"] == META["choices"]
def test_choice_not_in_program_is_error(): ...    # meta choices [["CS 3305","ZZZ 9999"]] -> ValueError mentioning ZZZ 9999
def test_cli_rejects_unknown_program(capsys): ... # build.main(["bs-ee"]) raises SystemExit(2)
def test_cs_dataset_courses_unchanged_after_move():
    # Pins the reviewed CS courses: rebuild in memory from bs-cs/ and compare to the committed file.
    d = config.program_dir("bs-cs")
    prog = json.loads((d / "program.json").read_text())
    built, warnings = build_dataset(prog["courses"], catalog_get_raw(), json.loads((d / "overrides.json").read_text()),
                                    {"program": prog["program"], "choices": prog["choices"]})
    assert warnings == [] and built == json.loads((d / "courses.json").read_text())
```

  - In `test_banner.py`, add `test_banner_cli_reads_program_folder`: monkeypatch `DATA_DIR` and pass a fake fetcher, the same way the existing CLI test injects one. If none exists, monkeypatch `PoliteFetcher.default` to return an object whose `fetch` returns the CSE 1322 fixture. Assert that `banner-diff.md` is written under `tmp_path / "bs-cs"`.

- [ ] **Step 2:** Run `.venv/bin/pytest -q`. Expected: the new tests fail; `test_cs_dataset_courses_unchanged_after_move` fails because `bs-cs/` doesn't exist yet.
- [ ] **Step 3: Implement.**
  - Do the `git mv`.
  - Add `program` and `choices` to `bs-cs/program.json` using the CS values from Global Constraints. Rename its `_comment` paths to the `bs-cs/` folder.
  - Add `meta` to `build_dataset` and both CLIs.
  - Regenerate the CS dataset with `.venv/bin/python -m owlpath_pipeline.build bs-cs`, then run `git diff --stat data/2026-2027/bs-cs/courses.json`.
  - Expected: the only diff is the added `program` and `choices` keys. Check with `git diff data/2026-2027/bs-cs/courses.json | grep '^[-+] ' | grep -v '"program"\|"choices"\|"filters"\|"label"\|"groups"\|"name"\|"id": "bs-cs"'`, which should print nothing about courses.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit:** `git commit -m "feat: run the pipeline per program; move CS data to bs-cs/"`.

---

### Task 3: Web types, validator and build guard handle every program

**Files:**
- Modify: `web/src/data/types.ts`, `web/src/data/sample.json`, `web/src/data/normalize.ts`, `web/scripts/validate-dataset.mjs`, `web/scripts/validate-dataset.d.mts`, `web/scripts/check-data.mjs`
- Test: `web/src/data/validateDataset.test.ts`, `web/src/data/normalize.test.ts`, new `web/scripts/check-data.test.ts`

**Interfaces:**
- Produces:
  - `type FilterOption = { label: string; groups: Group[] }`.
  - `type Program = { id: string; name: string; filters: FilterOption[] }`.
  - `Dataset` and `NDataset` gain `program: Program; choices: string[][]`; `normalize` copies both.
  - `validateDataset(data)` adds `"program: missing id/name/filters"` and `"choices: unknown course X"`.
  - `check-data.mjs` exports `checkPrograms(dataRoot: URL): { ok: boolean; messages: string[] }`. The script's main runs it on `data/2026-2027/` and exits 1 if not ok.
  - The sample gets `program: {"id": "bs-cs", "name": "BS Computer Science (sample)", "filters": [...CS filters]}` and `choices: []`.

- [ ] **Step 1: Write failing tests.**
  - `validateDataset.test.ts`: a dataset without `program` gives an error containing "program". `choices: [["CSE 1321", "ZZZ 9999"]]` gives "choices: unknown course ZZZ 9999".
  - `normalize.test.ts`: `normalize(sample).program.id === 'bs-cs'` and `choices` equals `[]`.
  - `check-data.test.ts`: write temp folders with `fs.mkdtempSync` and call `checkPrograms(pathToFileURL(dir + '/'))`. Expected results:
    - two valid programs → `ok` true;
    - `bs-dsa/` with `program.json` but no `courses.json` → `ok` false, and a message contains "bs-dsa" and "courses.json";
    - a `courses.json` whose `source` is "SAMPLE" → `ok` false;
    - no program folders → `ok` false.
- [ ] **Step 2:** Run `cd web && npm test`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - A program folder is any direct subfolder of the data root that contains `program.json`; ignore `catalog/`.
  - Keep the success log line, one per program: `dataset ok: <program> (<n> courses, source <source>)`.
- [ ] **Step 4:** Run `npm test && npm run build`. Expected: all pass, and the build prints `dataset ok: bs-cs …`. `bs-dsa/` doesn't exist yet, so only one program is checked.
- [ ] **Step 5: Commit:** `git commit -m "feat: web validator and build guard check every program"`.

---

### Task 4: Load every major and resolve the selected one

**Files:**
- Modify: `web/src/data/dataset.ts`
- Create: `web/src/state/major.ts`
- Test: `web/src/data/dataset.test.ts` (new), `web/src/state/major.test.ts` (new)

**Interfaces:**
- Consumes: Task 3 types.
- Produces:
  - `pickPrograms(real: Dataset[], sample: Dataset): Dataset[]` returns `real` sorted with `bs-cs` first and the rest by `program.name`, or `[sample]` when `real` is empty.
  - `loadPrograms(): NDataset[]` uses `import.meta.glob('../../../data/2026-2027/*/courses.json', {eager: true, import: 'default'})`.
  - `MAJOR_KEY = 'owlpath:v1:major'`.
  - `resolveMajor(search: string, storage: Storage | null, ids: string[]): string` returns the `?major=` value if it's in `ids`, else the stored value if it's in `ids`, else `ids[0]`. It never throws.
  - `saveMajor(storage: Storage | null, id: string): void` never throws.
  - `majorUrl(href: string, id: string): string` returns the href with the `major` parameter set.

- [ ] **Step 1: Write failing tests.**

```ts
test('url beats storage', () => expect(resolveMajor('?major=bs-dsa', store({ 'owlpath:v1:major': 'bs-cs' }), IDS)).toBe('bs-dsa'))
test('storage used when url absent', ...)              // '' + stored bs-dsa -> 'bs-dsa'
test('unknown url and stored ids fall back to first', ...)   // '?major=bs-ee', stored 'gone' -> 'bs-cs'
test('throwing storage falls back', ...)               // storage whose getItem throws -> 'bs-cs'
test('majorUrl keeps other params', () => expect(majorUrl('https://x/OwlPath/?a=1', 'bs-dsa')).toBe('https://x/OwlPath/?a=1&major=bs-dsa'))
test('pickPrograms puts bs-cs first and falls back to sample', ...)
```

- [ ] **Step 2:** Run `npm test -- major dataset`. Expected: FAIL.
- [ ] **Step 3:** Implement both modules. Remove the old `pickDataset` and `loadDataset` and update their imports. App wiring happens in Task 7; until then, `App.tsx` uses `loadPrograms()[0]` so it compiles.
- [ ] **Step 4:** Run `npm test && npx tsc -b`. Expected: pass.
- [ ] **Step 5: Commit:** `git commit -m "feat: load every major and resolve the selected one"`.

---

### Task 5: Status is shared across majors and can be reset

**Files:**
- Modify: `web/src/state/status.ts`
- Test: `web/src/state/status.test.ts`

**Interfaces:**
- Produces: `useStatus(validIds: Set<string>): [StatusMap, (id: string, s: Status) => void, () => void]`. The third element is `resetStatus`, which sets `{}` and saves it. Callers pass the **union** of every major's ids.

- [ ] **Step 1: Write failing tests.**

```ts
test('keeps ids from another major', () => {
  const s = store({ [STATUS_KEY]: JSON.stringify({ 'DATA 3010': 'complete', 'CS 3305': 'complete' }) })
  expect(loadStatus(s, new Set(['CS 3305', 'DATA 3010']))).toEqual({ 'DATA 3010': 'complete', 'CS 3305': 'complete' })
})
test('pre-existing CS progress under the old key still loads', ...)   // same key, CS ids -> unchanged map
test('reset clears and persists', ...)  // renderHook(useStatus); act(set CS 3305 complete); act(reset); status {} and storage holds "{}"
```

  The reset test uses `@testing-library/react`'s `renderHook` if it's installed (check `web/package.json`). If not, test a pure `resetStatus(storage)` helper that saves `{}`, and have the hook call it.
- [ ] **Step 2:** Run `npm test -- status`. Expected: the reset test FAILs. The two load tests already pass, because `loadStatus` filters by whatever set it's given; the Review Focus lines depend on Task 7 passing the union. Record that in the ledger.
- [ ] **Step 3:** Implement the reset.
- [ ] **Step 4:** Run `npm test`. Expected: pass.
- [ ] **Step 5: Commit:** `git commit -m "feat: reset progress; status shared across majors"`.

---

### Task 6: Per-major filters and either/or labels

**Files:**
- Modify: `web/src/logic/highlight.ts`, `web/src/components/Filters.tsx`, `CourseNode.tsx`, `DetailPanel.tsx`, `web/src/logic/view.ts`
- Create: `web/src/logic/choices.ts`
- Test: `web/src/logic/highlight.test.ts`, new `web/src/logic/choices.test.ts`, `web/src/logic/view.test.ts`

**Interfaces:**
- Produces:
  - `filterSet(graph: Graph, courses: NCourse[], groups: Group[]): Set<string>` returns the courses in any of `groups`, plus their prerequisite chains (same traversal as before). It replaces `concentrationSet`.
  - `choicePartners(choices: string[][], id: string): string[]` returns the other ids in every choice containing `id`, deduplicated, in order.
  - `CourseNodeData` gains `choiceWith: string[]`. `ViewCtx` gains `choices: string[][]`.
  - `Filters` props become `{ options: FilterOption[]; filter: number | null; onFilter: (i: number | null) => void; courses; onSelect }`. The filter is the option index, and the label is "Show".
  - `DetailPanel` gets a `choiceWith: string[]` prop.

- [ ] **Step 1: Write failing tests.**

```ts
test('filterSet unions several groups', ...)  // core-field + major-required members both included, with their prereq chains
test('choicePartners', () => {
  expect(choicePartners([['CSE 2300', 'MATH 2345']], 'MATH 2345')).toEqual(['CSE 2300'])
  expect(choicePartners([['A', 'B'], ['A', 'C']], 'A')).toEqual(['B', 'C'])
  expect(choicePartners([], 'A')).toEqual([])
})
test('toFlow puts choiceWith on course nodes', ...)  // ctx.choices [['CSE 1321','CSE 1322']] -> node CSE 1321 data.choiceWith ['CSE 1322']
```

- [ ] **Step 2:** Run `npm test`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - `CourseNode` renders `or <ids joined by " / ">` as one short line when `choiceWith` is non-empty. Fit it inside the existing 160×56 node: shorten the state line if needed, without overflow.
  - `DetailPanel` renders "Program requirement: take one of {id} or {partners joined by ' or '}."
  - Delete `FILTER_OPTIONS`.
- [ ] **Step 4:** Run `npm test && npx tsc -b`. Expected: pass.
- [ ] **Step 5: Commit:** `git commit -m "feat: per-major filter options and either/or labels"`.

---

### Task 7: App wiring: major dropdown, reset button, graph cache

**Files:**
- Modify: `web/src/App.tsx`, `web/src/styles.css`, `web/src/components/CourseList.tsx` (reset on small screens)
- Create: `web/src/components/MajorPicker.tsx`, `web/src/components/ResetButton.tsx`, `web/src/logic/programView.ts`
- Test: new `web/src/logic/programView.test.ts`, new `web/src/components/ResetButton.test.tsx` (if testing-library is available; otherwise test the pure handler)

**Interfaces:**
- Consumes: Tasks 3–6.
- Produces:
  - `programView(ds: NDataset): { graph; positions; validIds: Set<string> }`, memoized per `ds.program.id` in a module-level `Map`.
  - `allCourseIds(programs: NDataset[]): Set<string>`, the union.
  - `ResetButton({ disabled, onReset, confirm = window.confirm })` calls `onReset` only when `confirm(RESET_TEXT)` returns true.

- [ ] **Step 1: Write failing tests.**

```ts
test('programView caches per program', () => expect(programView(a)).toBe(programView(a)))
test('allCourseIds is the union', ...)
test('reset asks first and respects cancel', ...)  // confirm -> false: onReset not called; true: called once; the confirm text equals RESET_TEXT
test('switching major clears selection and filter', ...)  // pure reducer: switchMajor(state, 'bs-dsa') -> { major: 'bs-dsa', selected: null, filter: null, focus: null }
```

  Put `switchMajor` in `programView.ts` so it's testable without rendering.
- [ ] **Step 2:** Run `npm test`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
  - **Header order:** h1, MajorPicker (labelled "Major"), subtitle `{program.name} · {catalogYear} catalog`, Filters, ResetButton ("Reset progress", disabled when the status map is empty).
  - **On switch:** call `saveMajor`, then `history.replaceState(null, '', majorUrl(location.href, id))`, then apply `switchMajor`.
  - Pass `allCourseIds(programs)` to `useStatus`.
  - Style both new controls with the existing tokens, with readable contrast in light and dark.
- [ ] **Step 4:** Run `npm test && npm run build`. Expected: pass.
- [ ] **Step 5: Browser check.**
  - Run `npm run build:sample` only if `bs-dsa` data isn't ready yet; otherwise `npm run build`. Then serve with `npx vite preview --port 4173 --strictPort` in the background.
  - Use the Python Playwright in `.venv` to screenshot, in dark and light mode:
    - the header;
    - the switch to BSDSA, once its data exists (otherwise the CS-only dropdown);
    - the reset button disabled, then enabled after marking a course;
    - the confirm dialog being accepted (`page.on('dialog')`).
  - Look at every screenshot. Stop the server.
- [ ] **Step 6: Commit:** `git commit -m "feat: major dropdown and reset progress button"`.

---

### Task 8: BSDSA dataset (human in the loop)

**Files:**
- Create: `data/2026-2027/bs-dsa/{program-page.pdf (moved from the user's file), program.json, overrides.json, courses.json, build-report.md, banner-diff.md}`
- Needs from the user: `data/2026-2027/catalog/data.pdf`. If it isn't present, ask once and work on Task 9 meanwhile.

- [ ] **Step 1:** Run `git mv "data/2026-2027/Program_ Data Science and Analytics, B.S. - Kennesaw State University.pdf" data/2026-2027/bs-dsa/program-page.pdf`. Write `program.json` with exactly the lists in the design's "BSDSA program list", plus the `program` and `choices` values from Global Constraints. Add a `_comment` noting the unlisted "any DATA/STAT 4000-level" rule. Write `overrides.json` as `{}`.
- [ ] **Step 2:** Run `.venv/bin/python -m owlpath_pipeline.build bs-dsa --draft`. For every "course page not found", name the prefix and ask the user for that listing; don't guess. When it runs, add a coverage line to `test_catalog_pdf.py`: `"DATA 3010" in catalog`.
- [ ] **Step 3:** Resolve every warning in `bs-dsa/overrides.json`, each with a reason. Change only what the catalog text supports. Then run `.venv/bin/python -m owlpath_pipeline.build bs-dsa`. Expected: `0 unresolved warnings, 0 validation errors`.
- [ ] **Step 4:** Run `.venv/bin/python -m owlpath_pipeline.banner bs-dsa` with `run_in_background` (about 1 hour). Fill in the Resolution column. A real grade disagreement goes to the user; it isn't resolved silently.
- [ ] **Step 5:** Spot-check about 10 BSDSA courses, including every course in a choice pair and three DATA courses. Show them to the user as a catalog-versus-dataset table and wait for their OK.
- [ ] **Step 6:** Run `.venv/bin/pytest && cd web && npm test && npm run build`. Expected: all pass, and the guard prints `dataset ok` for both `bs-cs` and `bs-dsa`.
- [ ] **Step 7: Commit:** `git add data/2026-2027/bs-dsa data/2026-2027/catalog/data.pdf tests/test_catalog_pdf.py && git commit -m "data: add reviewed 2026-27 BSDSA dataset"`.

---

### Task 9: Docs follow the new scope

**Files:**
- Modify: `CLAUDE.md`, `docs/mvp-spec.md`

- [ ] **Step 1:** Make these edits:
  - In `CLAUDE.md`:
    - MVP scope becomes "BS Computer Science and BS Data Science and Analytics".
    - The folder tree shows `catalog/`, `bs-cs/` and `bs-dsa/`.
    - The schema block adds `program` and `choices`.
    - The pipeline commands take a `<program>` argument.
    - Add a line: "Adding a major: new `data/<year>/<id>/program.json` (+ `program`, `choices`), save any missing listing PDFs, then the same review."
  - In `docs/mvp-spec.md`, add a dated scope note pointing to the multi-major design.
- [ ] **Step 2:** Run `.venv/bin/pytest -q && (cd web && npm test)`. Expected: pass. This is a docs-only change; the run confirms nothing broke.
- [ ] **Step 3: Commit:** `git commit -m "docs: scope and commands for multiple majors"`.
