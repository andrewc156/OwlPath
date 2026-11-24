# OwlPath

An interactive prerequisite map for every degree program at Kennesaw State University.

Pick a course to see what it requires and what it unlocks. Mark courses as complete or in progress, and OwlPath shows what you can take now and what opens up next term.

**Live site:** https://andrewc156.github.io/OwlPath/

OwlPath is inspired by GradGT, Georgia Tech's prerequisite chart, but built independently. It is a student project and isn't affiliated with or endorsed by Kennesaw State University. Always confirm your plan with the official catalog and your advisor.

## Majors covered

Every degree program (bachelor's, master's, specialist and doctoral) in the 2026–27 undergraduate and graduate catalogs. Search for one in the dropdown. Minors, certificates and endorsements aren't included.

- **Checked** majors were reviewed by a person against the catalog: BS in Computer Science (`bs-cs`), BS in Data Science and Analytics (`bs-dsa`) and MS in Data Science and Analytics (`ms-dsa`).
- **Not yet checked** majors are built automatically from the catalog and nobody has reviewed them. They carry a "not yet checked" tag, and the map says so. Requirements can be missed or misread, so confirm with the catalog and your advisor. A program the automatic build can't read cleanly isn't published until someone fixes it.

Each map covers the program's requirements and listed electives (and concentrations where it has them), plus every course needed to reach them, including MATH and other prefixes.

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
    catalog/
      undergraduate/  crawled catalog snapshot (courses, programs) and the level's shared overrides.json
      graduate/       the same for the graduate catalog
    <major>/        per major: program.json, courses.json, reports
    majors.json     the dropdown list
    STATUS.md       which majors are checked, auto-built or held
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

`npm run build` ships checked majors and auto-built majors that built cleanly, and holds the rest. It refuses if a checked major is held, a `courses.json` is the sample or invalid, or `majors.json` is out of date. For a local preview against whatever data is present, use `npm run build:sample`.

## Building the course data

Requires Python 3.13. Run from the repo root.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                   # pipeline tests
.venv/bin/python -m owlpath_pipeline.publish       # draft, build and sort every major; writes majors.json and STATUS.md
.venv/bin/python -m owlpath_pipeline.build bs-cs --draft   # one major, draft build with report
.venv/bin/python -m owlpath_pipeline.banner bs-cs          # Banner cross-check
```

Course data comes from a snapshot of the whole catalog, committed under `data/<year>/catalog/<level>/`. To refresh it, install the optional browser extra and run the crawler:

```sh
.venv/bin/pip install -e '.[dev,crawl]' && .venv/bin/playwright install chromium
.venv/bin/python -m owlpath_pipeline.crawl undergraduate   # also: graduate; --refresh re-fetches, --from-cache rebuilds from cached pages
```

The crawler drives a real browser and honors robots.txt, including its 120-second crawl delay, so a full level takes hours. It stops and reports at the first sign of a block, and rerunning resumes from the cache. `publish --from-pdfs` still reads course listings saved by hand as PDFs instead of the snapshot.

The catalog is the source of truth. Banner is only a cross-check, and every hand correction goes in the level's shared `overrides.json` with a reason. The Banner check fetches politely (it honors the site's crawl delay), so it runs slowly.

See `docs/` for the full spec and design, including how to add a major.

## Deployment

Every push to `main` runs the pipeline and web tests, then deploys `web/dist` to GitHub Pages. The build ships checked majors and auto-built ones that built cleanly, and holds the rest. A deploy can also be started by hand from Actions → "Deploy web app to GitHub Pages".

## License

[MIT](LICENSE)
