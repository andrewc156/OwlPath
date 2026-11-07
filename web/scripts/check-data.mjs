// Production build guard: refuse to build unless the reviewed dataset exists and isn't the sample.
// See docs/superpowers/specs/2026-11-06-owlpath-design.md ("Deploy").
import { readFileSync } from 'node:fs'

const REL = 'data/2026-2027/courses.json'
const url = new URL(`../../${REL}`, import.meta.url)

let data
try {
  data = JSON.parse(readFileSync(url, 'utf8'))
} catch (err) {
  if (err.code === 'ENOENT') {
    console.error(`refusing to build: reviewed dataset ${REL} not found`)
  } else {
    console.error(`refusing to build: ${REL} is not valid JSON (${err.message})`)
  }
  process.exit(1)
}

if (data.source === 'SAMPLE') {
  console.error(`refusing to build: ${REL} is the sample dataset`)
  process.exit(1)
}
console.log(`dataset ok: ${REL} (${data.courses?.length ?? 0} courses, source ${data.source})`)
