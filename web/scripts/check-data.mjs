// Production build guard: refuse to build unless every major's reviewed dataset exists,
// isn't the sample and is valid. Deploys are automatic on main, so this is the last gate.
// See docs/superpowers/specs/2026-11-11-owlpath-multi-major-design.md ("Build guard").
import { isDeepStrictEqual } from 'node:util'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { validateDataset } from './validate-dataset.mjs'

/**
 * A program folder is any direct subfolder of dataRoot that holds program.json.
 * @param {URL} dataRoot folder URL ending in "/", e.g. data/2026-2027/
 * @returns {{ ok: boolean, messages: string[] }}
 */
export function checkPrograms(dataRoot) {
  const root = fileURLToPath(dataRoot)
  const has = (dir, file) => existsSync(new URL(`${dir}/${file}`, dataRoot))
  const dirs = readdirSync(root, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name).sort()
  const programs = dirs.filter((d) => has(d, 'program.json'))

  const messages = []
  let ok = true
  // The app bundles every */courses.json, so each one must belong to a checked program folder.
  for (const d of dirs.filter((d) => has(d, 'courses.json') && !has(d, 'program.json'))) {
    ok = false
    messages.push(`refusing to build: ${d}/courses.json has no program.json, so it would ship unchecked`)
  }
  if (programs.length === 0) return { ok: false, messages: [...messages, `refusing to build: no program folders in ${root}`] }

  for (const id of programs) {
    const rel = `${id}/courses.json`
    let data
    try {
      data = JSON.parse(readFileSync(new URL(rel, dataRoot), 'utf8'))
    } catch (err) {
      ok = false
      messages.push(err.code === 'ENOENT'
        ? `refusing to build: ${id} has no reviewed courses.json`
        : `refusing to build: ${rel} is not valid JSON (${err.message})`)
      continue
    }
    if (data.source === 'SAMPLE') {
      ok = false
      messages.push(`refusing to build: ${rel} is the sample dataset`)
      continue
    }
    const errors = validateDataset(data)
    if (errors.length) {
      ok = false
      messages.push(`refusing to build: ${rel} has ${errors.length} problem(s):\n  ${errors.join('\n  ')}`)
      continue
    }
    if (data.program.id !== id) {
      ok = false
      messages.push(`refusing to build: ${rel} says program "${data.program.id}" but lives in folder ${id}`)
      continue
    }
    const spec = JSON.parse(readFileSync(new URL(`${id}/program.json`, dataRoot), 'utf8'))
    if (!isDeepStrictEqual(spec.program, data.program) || !isDeepStrictEqual(spec.choices, data.choices)) {
      ok = false
      messages.push(`refusing to build: ${id}/program.json changed since courses.json was built; rebuild with the pipeline`)
      continue
    }
    messages.push(`dataset ok: ${id} (${data.courses.length} courses, source ${data.source})`)
  }
  return { ok, messages }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const { ok, messages } = checkPrograms(new URL('../../data/2026-2027/', import.meta.url))
  for (const m of messages) (ok ? console.log : console.error)(m)
  if (!ok) process.exit(1)
}
