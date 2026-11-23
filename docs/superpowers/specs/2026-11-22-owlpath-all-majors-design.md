# OwlPath All-Majors Design

Builds on `2026-11-06-owlpath-design.md` and `2026-11-11-owlpath-multi-major-design.md`. Anything not changed here stays as it is there.

## Intent

OwlPath is for a KSU student who wants to see which classes they should take and which ones clear the most prerequisite blockers. Today it covers three majors (BS CS, BS DSA, MS DSA). This design makes it cover **every KSU degree program, undergraduate and graduate**, so any student can find their own major.

The "which course clears the most blockers" ranking is a separate project. It gets its own design after this one ships (see "Later").

## Goals, non-goals, anti-goals

- **Goals**
  - Every degree program in the 2026–27 undergraduate and graduate catalogs appears on the site, built from the catalog by the pipeline.
  - Catalog data is collected by an honest scraper instead of PDFs saved by hand.
  - Each major's program page is drafted into `program.json` automatically instead of written by hand.
  - Majors that build cleanly go live automatically, labeled as not yet checked. Majors with problems wait for a person (user decision, option 3).
  - The site stays fast: the first load doesn't grow as majors are added.
- **Non-goals**
  - The "take this next" ranking (next design).
  - Minors, certificates, endorsements and other non-degree programs.
  - General education planning, requirement-count rules ("15 hours of electives"), arranging courses into semesters, live sections, transfer credit, other catalog years.
  - Running the crawl in CI.
- **Anti-goals**
  - Disguising the scraper, or trying harder to get around KSU's bot check after it blocks us.
  - An unchecked map that looks checked.
  - A checked major silently changing or disappearing.
  - Students losing saved progress.

## Constraints

- **Catalog rules** (see `docs/mvp-spec.md`): honor robots.txt, with `crawl-delay: 120` and no requests to `/ajax/`, `/search_advanced.php`, `/portfolio.php` or `/portfolio_nopop.php`. Identify honestly with `config.USER_AGENT` and cache every page.
- **Authority:** the catalog is the authority. Banner is only a cross-check. Every hand fix has a written reason.
- **Site:** static site with no backend, on GitHub Pages. Every push to `main` runs the tests, the build guard and the deploy.
- **Progress:** stored under `owlpath:v1:2026-2027:status` and keyed by course id. Never rename that key, and never drop other majors' ids when loading.

## What the spike showed (2026-11-22)

A throwaway test loaded two pages with headless Chromium under our honest User-Agent, 2 minutes apart, after reading robots.txt.

- **The bot check passes.** The catalog sits behind AWS WAF.
  - The first request returns HTTP 202 with a JavaScript check served from `*.token.awswaf.com`.
  - A real browser passes it automatically in about 3 seconds. The page then reloads with a 200 and an `aws-waf-token` cookie.
  - We used no disguise.
- **Expanded course listings come in the page itself.** The expanded print listing for a prefix holds every course's full text, with no `/ajax/` requests. The URL is `content.php?filter%5B27%5D=<PREFIX>&filter%5B29%5D=&filter%5Bcourse_type%5D=-1&filter%5Bkeyword%5D=&filter%5B32%5D=1&filter%5Bcpage%5D=1&cur_cat_oid=<catoid>&expand=1&navoid=<courses navoid>&print=1`.
- **The data matches the PDFs exactly.** The page text of the STAT listing, run through the existing `catalog_pdf.parse_listing`, gave the same 10 courses as the saved PDF. Prerequisites and descriptions were identical, with zero warnings.
- **Program pages are structured.** The print view (`preview_program.php?catoid=<c>&poid=<p>&print`) has one `div.acalog-core` block per section.
  - Each block has a heading and `li.acalog-course` items.
  - For BS CS that gives Core Field of Study (7 courses), Major Requirements (13), Major Electives (5), and each concentration with "Required Courses" and "Elective Courses" blocks.
  - Course links go to `preview_course_nopop.php?catoid=<c>&coid=<id>`.
- **The catalogs are discoverable from their own pages.**
  - The Courses page has a prefix dropdown (`select[name='filter[27]']`) with 154 prefixes in the undergraduate catalog.
  - Undergraduate navoids: Courses is 9372 and Academic Programs is 9371.
  - The graduate Academic Programs page is probably navoid 9027 (from the MS DSA page's `returnto`). Confirm it from the graduate catalog's own navigation.
- **One thing to change.** Each page also pulled about 9 small scripts from the catalog host. The real crawler shouldn't (see below).

## Approaches

- **A. Copy the whole catalog, then build every major from it (chosen).**
  - One crawl collects both catalogs. The pipeline drafts and builds every major from that copy, and publishing follows option 3.
  - It's the biggest change up front, and the first run will turn up many warnings to sort through. It's the only approach where "every major" happens without a manual step per major.
- **B. Add majors one at a time with a scrape command.**
  - Smaller change, but 150+ runs to reach every major, and finding each page's URL by hand.
  - The site changes in A are needed anyway past about 10 majors, and B works against option 3's goal of most majors appearing quickly.
- **Ruled out.**
  - Saving PDFs by hand: more than 150 program pages and roughly 250 listings.
  - Banner as the main source: it has no program pages and still lists retired course numbers, such as STAT 8210.

The user chose honest scraping, option 3 publishing and approach A on 2026-11-22. They also decided that fixes may put held majors live, except fixes that change a checked major (section 5).

## Design

### 1. Crawler

A new pipeline command crawls one catalog level, or both.

**Request rules.** These replace today's "stop and ask if blocked" rule:
- **Browser:** a real headless Chromium through Playwright, with the User-Agent set to `config.USER_AGENT`. No stealth plugins, no fingerprint changes, no proxies, no CAPTCHA services.
- **robots.txt:** read it first and honor it.
  - Requests to disallowed paths are aborted, never sent.
  - Wait the crawl delay (120 s) between page loads on the catalog host. The bot check's automatic reload belongs to the same page visit, and the next page waits 120 s from it.
  - Share `.cache/http/.last-request.json` with `PoliteFetcher`, so every tool honors the same delay.
- **Requests allowed through:**
  - catalog-host documents;
  - requests to the AWS bot-check host;
  - nothing else. Abort catalog scripts, styles, images and third-party trackers.
  - Verify on the first page that the bot check still passes under these rules. If it needs more, allow only the minimum, never more than the spike loaded.
- **Cache and resume:** every page is cached and never fetched twice, so the crawl resumes where it stopped. A refresh option may clear one catalog's cache, for mid-year catalog edits.
- **Stopping:** stop the whole crawl and report if any of these happen:
  - robots.txt can't be read;
  - the bot check doesn't pass within about 60 seconds;
  - a page ends on a non-200 status;
  - a page lacks its expected content.

  Never retry in a loop, and never escalate. Rerunning later resumes from the cache.
- **Where it runs:** locally, not in CI. A full run is long: roughly 450–550 pages, about 15–18 hours.

**What it fetches, per level:**
1. The Courses page, for the prefix list and the Courses navoid.
2. Each prefix's expanded print listing, plus any further pages if a listing is paginated.
3. The Academic Programs page, for every program's name and `poid`.
4. Each in-scope program's print page.

**Scope filter.** Degree programs only: bachelor's, master's, specialist and doctoral. Use the index's own grouping if it has one, otherwise the degree suffix in the name. Every program left out is listed in the status report (section 5), so nothing disappears silently.

### 2. Catalog snapshot (committed)

Raw HTML stays in `.cache/` and isn't committed. The crawler writes a compact snapshot under `data/2026-2027/catalog/<level>/`, which is committed:
- **Courses:** the raw course records (id, title, credits, description, prerequisite text, corequisite text, course URL).
- **Programs:** each program's structure (name, URL, sections with headings, course ids in order, "or" markers and free-text lines).

Builds read the snapshot, so anyone can rebuild without crawling, and diffs show what changed in the catalog.

The saved PDFs are superseded. Keep the PDF reader as a fallback input in case the crawler is ever blocked. Once the regression check (section 7) passes, remove the PDFs from the repo; git history keeps them.

### 3. Drafting `program.json`

The drafter turns each program's snapshot into a `program.json` (`level`, `program`, `choices`, `courses`). The map's scope stays as today: core field of study, major requirements, concentrations, listed electives and project courses, plus every course needed to reach them.

- **Sections to groups:**

  | Section | Group |
  | --- | --- |
  | Core field of study | `core-field` |
  | Major requirements and required courses | `major-required` |
  | Listed major electives | `major-elective` |
  | Project or capstone | `major-project` |
  | Each concentration, track, option or emphasis | its own `conc-<slug>`, holding both its required and its elective courses (as BS CS does today) |
  | General education core, university or free electives, minors, program totals | left out |

  A section with courses that the drafter doesn't recognize is a drafting warning.
- **Filters:**
  - "Required courses" (`core-field` and `major-required`);
  - one filter per concentration, labeled with its name;
  - "Electives" (`major-elective`);
  - "Project" (`major-project`).

  Each is included only if non-empty.
- **Either/or:** alternatives joined by "or" within a list become a `choices` entry. All options appear as nodes marked "choose one", as today. `lessCommon` is set only by a person.
- **Left out on purpose:** internships, co-ops, undergraduate or graduate research, thesis and dissertation research hours, directed or independent study, and special or selected topics. These are the permission-run courses today's maps leave out. Each major's report lists them.
- **Text-only elective rules** ("any CS 3000–4000 course") aren't nodes, as today. They're listed in the report.
- **Ids and names:**
  - Existing ids `bs-cs`, `bs-dsa` and `ms-dsa` stay, because links and saved choices use them.
  - New ids are the degree plus a slug, such as `bba-accounting`. They must be unique and stay the same when the same catalog is crawled again.
  - Names follow today's style: degree, then field, as in "BBA Accounting".
- **The drafter never overwrites a program a person has edited or checked.** For those, it reports any difference between a fresh draft and the file, for example a course the catalog added.

### 4. Building

- **Shared course overrides.**
  - Course fixes move from each major's `overrides.json` to one file per level, `catalog/<level>/overrides.json`, each with a reason. A fix is written once and applies to every major.
  - Overrides are written in catalog terms: course leaves with grades, never `external`. Each major's build still decides which leaves are nodes and which are text, because CSE 2300 is a node in one major and text in another.
  - Overrides are applied **before** the closure, so a course an override requires is pulled into the map.
  - An override is stale if its course isn't in the snapshot.
  - Today's nine overrides move over: CS 3622, CSE 3801, CSE 2300, STAT 3125, DS 7020, STAT 7100, DS 7900, STAT 7010 and STAT 8220. Each `external` leaf becomes a plain course leaf.
- **The parser turns common non-course phrases into notes:** admission to a program, class standing, and permission, consent or approval of an instructor, department or program director. That removes the need for overrides like the ones for DS 7020 and STAT 7100.
- **When an OR has no option on the map** in an **auto-built** major, the first-listed option is pulled in as a `prereq-only` node and the others stay text. The course stays reachable, and the report notes it.
  - "Or permission" and "or placement" options are notes, not options on the map, so the rule still applies to them.
  - In **checked** majors the case stays a warning for a person to settle, as today. So BS DSA's STAT 3125 (BIOL 1107, BIOL 1108 or CHEM 1212, all text) keeps its current form, and the regression gate holds.
- **Courses from the other catalog level.** If a course isn't in the major's own snapshot, the build looks it up in the other level's snapshot and uses that level's overrides. An example would be a graduate course that requires an undergraduate course. Only a course missing from both is a "course page not found" warning.
- **Course links** go to each course's own catalog page whenever its coid appears on any crawled page. Coids appear in prerequisite links in listings and in course items on program pages. A course with no known coid keeps the prefix listing link.

### 5. Status and publishing (option 3)

Every major is in one of three states:

| State | Meaning | On the site |
| --- | --- | --- |
| **checked** | A person reviewed it. Marked in `program.json`. | Yes, no label |
| **auto-built** | Clean build, not yet reviewed | Yes, labeled "not yet checked" |
| **held** | Has unresolved build or drafting warnings, or validation errors | No, listed in the status report |

- **What holds a major:** any unresolved build or drafting warning, or any validation error. Banner differences don't hold a major. They need a person's judgment and are part of checking it.
- **Held majors ship nothing.** If an auto-built major picks up a warning on a rebuild, its old `courses.json` is removed, so it leaves the site until fixed.
- **A checked major that fails to build blocks the deploy,** as today. It is never dropped silently.
- **A checked major whose data changes in a clean rebuild stays checked, but the change is never silent.** Causes include a re-crawl, a shared override or a parser rule. The status report lists every changed checked major with each course's before and after, and the commit or PR that carries the change says so.
- **Who may unblock held majors** (user decision, 2026-11-22):
  - Fixes written while clearing held majors may put those majors live without the user reviewing each fix. These fixes are shared course overrides and parser rules, each with a written reason. The majors go live as "not yet checked".
  - Every fix and its reason is listed in the status report and in the PR that adds it.
  - **Exception:** a fix that would change any checked major waits for the user's OK before it's committed. The build reports which checked majors a change would alter, so this is visible before committing.
- **Status report** (`data/2026-2027/STATUS.md`, generated and committed):
  - counts per level and state;
  - each held major with its warnings;
  - the shared courses ranked by how many majors they hold, since one fix there unblocks many;
  - checked majors whose fresh draft differs from their file;
  - programs left out of scope.
- **Build guard:**
  - Checked majors must be valid and current, as today.
  - Auto-built majors that ship must be valid, current and clean.
  - Held majors must not ship.
  - Each shipped dataset's state must match its `program.json`.
- **Checking a major** (auto-built to checked) uses today's review:
  1. Run the Banner check for that major.
  2. Look over the map and the report.
  3. Set choices, `lessCommon` and any fixes.
  4. Mark it checked.

### 6. Web app

- **First load:** carries only the list of majors (id, name, level, state). A major's course data loads when it's picked, with a short loading state. Today the bundle holds every major's data (536 KB in all). It must not grow as majors are added.
- **Major picker:** 150+ majors means a searchable picker, grouped Undergraduate and Graduate, A–Z, with auto-built majors marked.

  ```
  Major  [ search majors…                    ]
         UNDERGRADUATE
           BBA Accounting               not yet checked
           BS Computer Science
           …
         GRADUATE
           MS Data Science and Analytics
  ```
- **Label on auto-built majors,** under the header while one is open:

  ```
  BBA Accounting · 2026-2027 catalog
  ⚠ Auto-built from the catalog and not yet checked by a person. Confirm with the catalog and your advisor.
  ```
- **Groups become program-defined:** the standard ids plus `conc-<slug>`. Today they're a fixed list in `courses.schema.json` and `web/src/data/types.ts`. Filters still come from each program.
- **Saved progress:** once majors load lazily, the app can no longer check saved progress against every major's course ids. Loading keeps any well-formed course id, so no major's progress is dropped.
- **Unchanged:**
  - `?major=<id>` links and the remembered major;
  - shared progress (never drop other majors' ids);
  - the reset button;
  - the line-routing rules.
- **Fallback:** a link or saved choice naming an unknown or held major falls back to the default major (`bs-cs`).

### 7. Migration of the three current majors

- All three become **checked** and keep their hand-tuned `program.json` (choices, `lessCommon`, exclusions, comments). Their group ids stay valid.
- **Regression gate.** Rebuilt from the crawl snapshot, their `courses.json` must match today's, except for course links. Any other difference is a catalog change since the PDFs were saved (Nov 8–20). It must be explained, and either accepted or fixed, before merging.

### 8. Docs and rules

- **`CLAUDE.md`:**
  - the honest-browser crawl rules and stop rules, replacing "stop and ask if blocked";
  - the new layout;
  - the scope (all degree programs);
  - adding majors (automatic, plus checking);
  - shared overrides.
- **`README.md`:** majors section (what "not yet checked" means) and the crawl command.
- **`docs/mvp-spec.md`:** stays as history. This design wins where they differ.

## Testing

- **Crawler,** with a fake browser and clock:
  - disallowed paths are aborted;
  - the 120 s delay holds across pages and runs (shared last-request file);
  - cached pages are skipped;
  - a failed bot check, a non-200 status or missing content stops the crawl;
  - only allowed requests go through.
- **Snapshot readers:**
  - the saved STAT listing page gives the same records as `stat.pdf`;
  - pagination is followed;
  - the prefix list and the program index are read correctly.
- **Drafter,** with fixtures:
  - BS CS, BS DSA and MS DSA give the expected groups, filters and choices;
  - at least three differently structured majors (for example a business, a nursing and an engineering program) give sensible drafts or clear warnings;
  - edited and checked programs are never overwritten.
- **Build:**
  - one shared override gives a node in one major and text in another;
  - overrides apply before the closure;
  - the non-course phrase notes work;
  - the OR-with-no-option rule works;
  - the three states, including removing a newly held major's `courses.json`.
- **Guard:**
  - a broken checked major refuses;
  - a clean auto-built major ships;
  - a held major can't ship;
  - a state mismatch refuses.
- **Web:**
  - the first load excludes course data;
  - picker search and grouping;
  - the label shows only on auto-built majors;
  - unknown or held `?major=` falls back;
  - progress for every major survives.
- **End to end:** the regression gate in section 7. Spot-check line routing on a few of the largest auto-built majors.

## Calls I made (check these)

1. **Degree programs only.** No minors, certificates or endorsements.
2. **When an OR has no option on the map, the first-listed option becomes a node,** in auto-built majors only. Checked majors keep a person's decision.
3. **Banner differences don't hold an auto-built major.**
4. **Held majors don't appear in the picker at all.**
5. **The saved PDFs are removed once the regression gate passes.** The PDF reader stays as a fallback.
6. **The label wording and the "BBA Accounting" name style.**
7. **The crawl runs locally, not in GitHub Actions.**
8. **The build looks up a course in the other catalog level** before calling it missing.
9. **A checked major whose data changes in a clean rebuild stays checked,** with the change listed in the status report and the PR.
10. **This plan ends once the full crawl has run, the clean majors are live and the status report shows what's held.** Clearing held majors continues afterward, a batch at a time.

## Left to the builder

- Module and file names, and the snapshot's exact format.
- Parsing HTML directly or reusing the text parser.
- How section headings are matched to groups.
- The slug rules (within section 3's constraints).
- How the first load leaves out course data.
- The picker component.
- The report layout.
- How pagination is detected.
- The final list of allowed requests, after verifying the bot check.

## Later

**The "take this next" ranking.** Among the courses a student can take, show which ones clear the most prerequisite blockers. It works on any major once this ships. It gets its own design, starting with what counts as "clears the most".
