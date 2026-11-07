# OwlPath MVP Spec

OwlPath is an interactive prerequisite map for Kennesaw State University's College of Computing and Software Engineering (CCSE). It is inspired by [GradGT](https://grad-gt.vercel.app/), but OwlPath is a separate, independent project. The MVP covers only the **BS in Computer Science, 2026–27 catalog**.

These decisions were settled in a design interview on 2026-11-06. When a later change contradicts this file, update the file.

## Users and core job

- **Primary user:** KSU CS students planning their own path. Advisors and prospective students are secondary.
- **Core job:** show the prerequisite graph. Selecting a course highlights what it **requires** and what it **unlocks**, and dims everything else.

## Personal tracking

- Each course has one of three statuses: **not taken**, **in progress** or **complete**.
- Statuses are saved **only in the browser** (localStorage). There are no accounts and no server.
- A course is **eligible** when its prerequisite AND/OR logic is satisfied by completed courses.
- **In-progress** courses also count toward eligibility, and the courses they unlock are labeled "eligible next term." In-progress courses also satisfy corequisites.
- Marking a course complete means the student passed it with the required grade. Minimum grades are **displayed, never enforced**.

## Scope of courses

Included:
- Core field of study, major requirements, all three concentrations (Data Science, Cyber & Network Security, AI) and the major-elective list
- Every course needed to reach those courses, including non-CS courses such as MATH 1113 and MATH 1190

Excluded: general education courses that are not a prerequisite for anything in the graph, such as lab science pairs and humanities.

Every course record is tagged with its catalog year (`2026-2027`), so adding more years later does not require changing existing records.

## Data source and pipeline

- **Authority:** the official KSU undergraduate catalog. It runs on Modern Campus Catalog (formerly Acalog): https://catalog.kennesaw.edu/. The 2026–27 catalog is `catoid=84`.
- **Fetching:** a one-time, polite fetch of only the BS CS program page and the relevant course pages.
  - Honor `robots.txt`: `crawl-delay: 120` (one request every 120 seconds), and never request `/search_advanced.php`, `/ajax/` or `/portfolio*.php`.
  - Use an honest, generic User-Agent. Do not spoof a browser.
  - Cache raw HTML locally so pages are never fetched twice.
- **Cross-check:** compare parsed prerequisites against Banner's public course detail pages and flag every disagreement for a human to resolve. URL pattern: `https://owlexpress.kennesaw.edu/prodban/bwckctlg.p_disp_course_detail?cat_term_in=<term>&subj_code_in=<SUBJ>&crse_numb_in=<NUM>`. The catalog wins unless a human decides otherwise.
  - Known example: the catalog requires a **B** in CSE 1321 for CSE 1322, but Banner shows **C**.
- **Pipeline:** a Python script parses the pages into JSON, which is **committed to the repo** and reviewed and fixed by hand. The app reads only this file and never contacts the catalog at runtime.

### Prerequisite text in the catalog

The text has labeled lines, but the logic inside them is semi-structured prose. Expect a parser to produce a first draft that needs hand fixes. These examples come from the 2024–25 catalog:

- `CSE 1322 — Prerequisite: A grade of "B" or higher in CSE 1321 and CSE 1321L` / `Concurrent: CSE 1322L and (MATH 1113 or MATH 1190 or MATH 1179 or MATH 2202)`
- `CS 3305 — Prerequisite: (MATH 2345 or CSE 2300) and [(CSE 1322 and CSE 1322L each with a "B" or better), or MTRE 2610 with a "B" or better, or CPE 3000 with a "B" or better]`
- `CS 3626 — Prerequisite: MATH 2345 or CSE 2300` / `Concurrent: CS 3305`
- `MATH 1190 — Prerequisite: MATH 1113, or By Placement`
- `CSE 4983 — Prerequisite: Senior standing`

Known quirks:
- Both `()` and `[]` are used for nesting.
- Wording varies ("B or better" and "B or higher").
- There are typos (for example "inCSE").
- Some requirements are free text: placement, standing, permission.

## Representation

- Prerequisites are stored as a **nested AND/OR expression tree**, never a flat list.
- Each course requirement carries a **minimum grade**. The default is C (KSU policy), and exceptions such as B are recorded where the catalog states them.
- **Corequisites** ("Concurrent:" or "Corequisite:") are a **separate requirement type** from prerequisites and are drawn differently, for example as dashed links.
- **Requirements that are not courses** (placement, class standing, permission of instructor or department) are stored as **notes** on the course. Notes are displayed but never block eligibility. In "X or By Placement", course X still counts as a normal alternative.
- **Alternatives outside the program**, for example CS 3305's MTRE 2610 or CPE 3000, appear as **text inside the OR**, not as graph nodes. Any course that is required within the program gets its own node.
- Program membership (required, core field, which concentration, elective pool) is stored as **group tags** on courses. There are no count rules.

The final schema is in `docs/superpowers/specs/2026-11-06-owlpath-design.md` (fields `prereqs`/`coreqs`/`description`, with plain-string leaves for grade-C in-graph courses). Example:

```json
{
  "id": "CS 3305",
  "title": "Data Structures",
  "credits": "3",
  "description": "...",
  "catalogYear": "2026-2027",
  "catalogUrl": "https://catalog.kennesaw.edu/preview_course_nopop.php?catoid=84&coid=...",
  "groups": ["major-required"],
  "prereqs": {
    "and": [
      { "or": ["MATH 2345", { "external": "CSE 2300" }] },
      { "or": [
        { "and": [{ "course": "CSE 1322", "minGrade": "B" }, { "course": "CSE 1322L", "minGrade": "B" }] },
        { "external": "MTRE 2610", "minGrade": "B" },
        { "external": "CPE 3000", "minGrade": "B" }
      ]}
    ]
  },
  "coreqs": null,
  "notes": []
}
```

## Display

- The default view is a **layered graph ordered by prerequisite depth**, which reads roughly freshman to senior.
- An **OR group** is drawn as a small junction node. The alternative courses link into the junction, and the junction links to the course that needs it. Courses with only AND requirements get direct links.
- **Concentrations** work as a colour-coded filter and highlight on one shared graph: Data Science, Cyber, AI or general electives.
- **Desktop first.** On phones it must still work through a course list and course detail view; a full mobile graph is not required.
- Each course **links to its official catalog page**.
- A visible notice says the map is **not official advising**.
- All data is **checked by hand against the catalog** before launch.

## Architecture

- A **static site with no backend**. Python builds the data, a JavaScript frontend reads the committed JSON, and the site is hosted on a static host such as GitHub Pages. The frontend framework is not decided yet.
- **Built from scratch**, not forked from GradGT. GradGT ([repo](https://github.com/VineethSendilraj/GradGT)) is MIT licensed, so specific pieces may be reused with credit.

## Out of scope for the MVP

- Accounts, logins and plans saved to a server
- Degree audit and transcript import (no DegreeWorks or Banner integration)
- Arranging courses into semesters
- Live offerings, sections, seat availability, and typical-term offerings (the CS advising "Course Forecast")
- Requirement-count rules, such as "15 elective hours, at least 9 of them CS"
- Majors other than the BS in CS, and minors
- Catalog years other than 2026–27
- Transfer credit and AP/placement equivalencies

## BS CS structure (verify against the 2026–27 catalog)

This comes from the unofficial **2025–26** curriculum sheet (https://campus.kennesaw.edu/colleges-departments/ccse/advising/resources/docs/curriculum-sheets/bscs-2025.pdf). Confirm it against the 2026–27 catalog before relying on it.

- **Core field of study:** CSE 1321/L, CSE 1322/L (B or better), MATH 2202, MATH 2345, TCOM 2010
- **Major requirements (C or better):** CS 3305, 3410, 3502, 3503, 3622, 4306, 4308, 4504, 4850; SWE 3313; CSE 3801; STAT 2332; MATH 3260
- **Concentrations (15 hours):**
  - Data Science: CS 4265, 4412, 4422, 4522, plus CS 4524 or 4722
  - Cyber & Network Security: CS 3626, 4612, 4622, 4626, plus one of IT 4823, 4833, 4843, 4853 or 4883
  - Artificial Intelligence: CS 3642, 4267, 4732, 4742, 4277
- **Electives instead of a concentration:** 15 hours with at least 9 CS. Up to 6 hours may come from SWE 3633, 3643, 3683, 4633 or CSE 4983.
- **Gen-ed math that feeds the major:** MATH 1113, MATH 1190
