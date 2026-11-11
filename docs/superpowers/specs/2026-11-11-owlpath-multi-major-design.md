# OwlPath Multi-Major Design (BS CS + BS Data Science and Analytics)

Builds on `2026-11-06-owlpath-design.md`. Anything not changed here stays as it is there.

## Intent

Students in KSU's **BS Data Science and Analytics (BSDSA)** get the same prerequisite map that BS CS students have. A **major dropdown** switches between the two maps. A **reset button** clears a student's progress in one step.

This widens the MVP scope from "BS CS only" to "BS CS and BSDSA" (2026–27 catalog). The spec and `CLAUDE.md` get updated to match.

## Goals, non-goals, anti-goals

- **Goals**
  - The BSDSA map is built from the catalog with the same pipeline, the same review steps and the same rules (the catalog is the authority, hand fixes go in overrides with a reason).
  - A dropdown chooses the major. The choice is remembered and shows in the address bar, so links can be shared.
  - Completed courses carry over between majors.
  - A reset button sets every course back to "not taken".
- **Non-goals**
  - Other majors, minors or catalog years.
  - Degree auditing ("am I done?"), or treating the "any DATA/STAT 4000-level" and "any CS 3000–4000" elective rules as nodes. Only the listed courses are shown.
- **Anti-goals**
  - An unreviewed or invalid dataset for either major reaching the live site.
  - Losing a student's saved progress when they switch majors or when this version deploys.

## Decisions (user answered yes to all, 2026-11-11)

1. **One dataset per major.** Whether a leaf is a `course` or an `external`, and whether a course is `prereq-only`, depends on the major's graph. CSE 2300 is external on the CS map but a listed course on BSDSA. *Rejected:* one merged `courses.json` with per-major groups. It can't express the same course being a node in one major and text in the other.
2. **Either/or program requirements** (for example "CSE 2300 or MATH 2345") show **both courses as nodes**. Each is marked "choose one" and names the other options.
3. **Status is shared across majors**, keyed by course id. It stays under the same `localStorage` key, so existing progress survives.
4. **Each major supplies its own filter options.** The control is labelled "Show".
5. **The selected major persists** (`localStorage`) and appears in the URL as `?major=<id>`. Switching majors clears the selected course, the filter and search focus.
6. **The build guard covers every major.** The build refuses to run unless every major's dataset exists, isn't the sample and is valid.
7. **Reset button** (user request): clears every course's status in both majors after an "Are you sure?" confirmation.

## Data

**Layout.** The saved catalog listings stay shared. Everything else moves into a folder per major.

```
data/2026-2027/
  catalog/*.pdf                shared course listings (+ new data.pdf)
  bs-cs/                       program-page.pdf, program.json, overrides.json, courses.json, build-report.md, banner-diff.md
  bs-dsa/                      same files for BSDSA
```

The current CS files move into `bs-cs/` unchanged. The CS dataset's courses stay exactly as reviewed. Only the new top-level fields below are added.

**`program.json` gains program metadata:**

```json
{
  "catalogYear": "2026-2027",
  "program": { "id": "bs-dsa", "name": "BS Data Science and Analytics",
               "filters": [ { "label": "Required courses", "groups": ["core-field", "major-required"] },
                            { "label": "Electives", "groups": ["major-elective"] } ] },
  "choices": [ ["CSE 2300", "MATH 2345"], ["STAT 1401", "STAT 2332"], ["STAT 3120", "STAT 3125"],
               ["CSE 3153", "CS 3410"], ["DATA 4030", "DATA 4140"] ],
  "courses": { "<id>": ["<group>", ...] }
}
```

- The CS filters keep their current four options: Data Science, Cyber & Network Security, AI, General electives. CS has `"choices": []`.
- **My call:** a filter option lists several `groups` so "Required courses" can cover the core field and the major requirements together.

**`courses.json` adds `program` and `choices`** at the top level, copied from `program.json`. This becomes `{ catalogYear, source, program, choices, courses }`. The schema makes both required.
- Every id in `choices` must be a course in the dataset; the validators check this.
- The `groups` enum doesn't change. BSDSA uses `core-field`, `major-required`, `major-elective`, `gen-ed-math` and `prereq-only`.

**BSDSA program list** (from `bs-dsa/program-page.pdf`; the credit totals check out at 18 + 37 + 6):
- core-field: MATH 2202, CSE 2300, MATH 2345, STAT 1401, STAT 2332, CSE 1321, CSE 1321L, CSE 1322, CSE 1322L
- major-required: DATA 3010, STAT 3120, STAT 3125, STAT 3130, DATA 3230, MATH 3260, DATA 3300, CSE 3153, CS 3410, DATA 4000, DATA 4030, DATA 4140, STAT 4210, DATA 4310, DATA 4990
- major-elective: DATA 3396, DATA 3398, CSE 4983 (the page also allows any DATA or STAT 4000-level course, which isn't listed)
- gen-ed-math: MATH 1113, MATH 1190. The user's earlier ruling stands: MATH 1179 and MATH 1189 stay as text, never nodes.

**Catalog input.** BSDSA needs `catalog/data.pdf`, the DATA listing saved the same way as the others. If the DATA prerequisites name another missing prefix, the build reports it and the user saves that listing too.

## Pipeline

- **Every CLI takes the program as an argument:** `python -m owlpath_pipeline.build <program> [--draft]` and `python -m owlpath_pipeline.banner <program>`. Each reads and writes `data/<year>/<program>/`.
- **Overrides belong to their program.** The existing check (an override for a course not in that graph is an error) stays as it is.
- **`build_dataset` gains a `meta` argument**, so it can copy `program` and `choices` into the output. It checks that every choice id is in the program list.
- **Review for BSDSA follows the CS process:**
  - a draft build, then overrides with reasons, then a strict build with no warnings;
  - the Banner check, run only for `bs-dsa`, in the background;
  - a spot-check of about 10 courses, shown to the user before the data is committed.
- The CS dataset is regenerated with the new top-level fields. A test confirms its `courses` array is identical to the reviewed one.

## Web app

- **Loading.**
  - `import.meta.glob('../../../data/2026-2027/*/courses.json')` loads every major. The default is `bs-cs`.
  - The graph and layout are built once per major, the first time it's shown, then cached.
  - When no real dataset exists, the sample still loads, as before; it gets its own `program` block.
- **Header.**
  - A **Major** dropdown with the program names; the subtitle shows the chosen program's name.
  - The **Show** filter, with options from `program.filters` plus "All".
  - Search, which covers only the current major.
  - **Reset progress.**
- **Major selection.**
  - Read order: `?major=` in the URL, then `localStorage` (`owlpath:v1:major`), then `bs-cs`. An unknown id falls back to `bs-cs`.
  - Switching updates both with `history.replaceState` and clears the selection, filter and focus.
- **Status.**
  - It stays under `owlpath:v1:2026-2027:status`. `loadStatus` accepts ids from **any** major (the union), so switching majors never drops saved progress.
  - Eligibility only looks up the current major's ids, so extra ids are harmless.
- **Either/or courses.**
  - A node in a choice gets a short "or MATH 2345" line, the other ids joined by "/".
  - The detail panel says "Program requirement: take one of CSE 2300 or MATH 2345."
  - Choices don't change eligibility.
- **Reset progress.**
  - The button asks "Reset all progress? This marks every course as not taken in both majors." with `window.confirm`.
  - On confirm it clears the status map and saves the empty map. It's disabled when nothing is marked.
  - It also appears on small screens.
- **Build guard.** `check-data.mjs` finds every `data/2026-2027/*/program.json` and refuses to build when any of these holds:
  - no program folders are found;
  - a folder has no `courses.json`;
  - a dataset is the sample;
  - a dataset fails `validateDataset`, which now also checks `program` and `choices`.

## Testing

- **Pipeline:** program-argument paths, metadata pass-through, choice ids that aren't courses are errors, and the CS courses are unchanged after the move.
- **Web (Vitest):**
  - the major resolution order and fallback;
  - status loading keeps ids from other majors;
  - reset clears everything;
  - multi-group filter sets;
  - the choice text;
  - the guard with two programs, including one missing `courses.json`.
- **Browser check:** a screenshot of both majors, the dropdown, a choice node and the reset confirmation.

## Left to the builder

- Exact visual styling of the choice line and the reset button, using the existing tokens, with readable contrast in both themes.
- Order of majors in the dropdown: CS first, then by name.
