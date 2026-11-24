# Graduate catalog snapshot

`catalog-courses.json` and `programs.json` hold the 2026-27 **Graduate** Catalog (catoid 83), written by
`.venv/bin/python -m owlpath_pipeline.crawl graduate`. `overrides.json` holds the hand fixes shared by every
graduate major, each with a reason. Majors with `"level": "graduate"` in their `program.json` read this folder.

Graduate listings have no "Description" label, so the reader takes each field as one line and the text after it as the description.
