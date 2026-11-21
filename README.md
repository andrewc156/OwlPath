# OwlPath

An interactive prerequisite map for Kennesaw State University's College of Computing and Software Engineering.

Pick a course to see what it requires and what it unlocks. Mark courses as complete or in progress, and OwlPath shows what you can take now and what opens up next term.

**Live site:** https://andrewc156.github.io/OwlPath/

OwlPath is inspired by GradGT, Georgia Tech's prerequisite chart, but built independently. It is a student project and isn't affiliated with or endorsed by Kennesaw State University. Always confirm your plan with the official catalog and your advisor.

## Majors covered

Both use the 2026–27 catalog. Choose one from the dropdown.

| Major | Id |
| --- | --- |
| BS in Computer Science | `bs-cs` |
| BS in Data Science and Analytics | `bs-dsa` |

Each map covers the major's core field of study, major requirements, concentrations (CS only) and listed electives, plus every course needed to reach them, including MATH and other prefixes.

## How it works

- **Prerequisites** come from the KSU catalog and support `and`, `or` and minimum grades. Alternatives outside the program show as text, not nodes.
- **Corequisites and notes** (placement, standing, permission) are shown but never block eligibility.
- **Either/or requirements** ("take one of these") are labeled on the map.
- **Progress** is saved in your browser and shared across majors, so switching majors keeps what you've marked. The reset button clears it.

There is no backend. The course data is a static JSON file bundled into the app.

## Repository layout

```
owlpath_pipeline/   Python pipeline that builds the course data from the catalog
tests/              pipeline tests
data/
  schema/           courses.schema.json, the contract between pipeline and app
  2026-2027/
    catalog/        saved course listing PDFs, shared by every major
    bs-cs/ bs-dsa/  per major: program.json, overrides.json, courses.json, reports
web/                React + Vite + TypeScript app (React Flow + dagre)
docs/               spec, design docs and build plans
```

## Running the web app

Requires Node 22.12 or later.

```sh
cd web
npm ci
npm run dev          # start the dev server
npm test             # run the Vitest tests
npm run build        # typecheck and build for production
```

`npm run build` refuses to run unless every major folder has a reviewed, valid, non-sample `courses.json`. For a local preview against whatever data is present, use `npm run build:sample`.

## Building the course data

Requires Python 3.13. Run from the repo root.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                   # pipeline tests
.venv/bin/python -m owlpath_pipeline.build bs-cs --draft   # draft build with report
.venv/bin/python -m owlpath_pipeline.build bs-cs           # strict build
.venv/bin/python -m owlpath_pipeline.banner bs-cs          # Banner cross-check
```

The catalog site blocks automated clients, so course listings are saved by hand as PDFs: open the catalog's Courses listing, filter to one prefix, expand all courses and print to PDF as `data/<year>/catalog/<prefix>.pdf`. Each major's program page goes in `data/<year>/<major>/program-page.pdf`.

The catalog is the source of truth. Banner is only a cross-check, and every hand correction goes in the major's `overrides.json` with a reason. The Banner check fetches politely (it honors the site's crawl delay), so it runs slowly.

See `docs/` for the full spec and design, including how to add a major.

## Deployment

Every push to `main` runs the pipeline and web tests, then deploys `web/dist` to GitHub Pages. A deploy can also be started by hand from Actions → "Deploy web app to GitHub Pages".

## License

[MIT](LICENSE)
