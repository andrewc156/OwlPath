// Production build guard. A checked major needs a valid, current, checked courses.json; an unchecked one ships
// only when auto-built clean; one without courses.json is held; majors.json must list exactly what ships. Deploys are automatic on main, so this is the last gate.
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

  const shipped = []
  const refuse = (text) => {
    ok = false
    messages.push(`refusing to build: ${text}`)
  }
  for (const id of programs) {
    const rel = `${id}/courses.json`
    let spec
    try {
      spec = JSON.parse(readFileSync(new URL(`${id}/program.json`, dataRoot), 'utf8'))
    } catch (err) {
      refuse(`${id}/program.json is unreadable (${err.message})`)
      continue
    }
    const checked = spec.checked === true
    let data
    try {
      data = JSON.parse(readFileSync(new URL(rel, dataRoot), 'utf8'))
    } catch (err) {
      if (err.code !== 'ENOENT') refuse(`${rel} is not valid JSON (${err.message})`)
      else if (checked) refuse(`${id} is checked but has no reviewed courses.json`)
      else messages.push(`held: ${id}`)
      continue
    }
    if (data.source === 'SAMPLE') {
      refuse(`${rel} is the sample dataset`)
      continue
    }
    const errors = validateDataset(data)
    if (errors.length) {
      refuse(`${rel} has ${errors.length} problem(s):\n  ${errors.join('\n  ')}`)
      continue
    }
    if (data.program.id !== id) {
      refuse(`${rel} says program "${data.program.id}" but lives in folder ${id}`)
      continue
    }
    if (!isDeepStrictEqual(spec.program, data.program) || !isDeepStrictEqual(spec.choices, data.choices)
      || !isDeepStrictEqual(spec.lessCommon ?? [], data.lessCommon ?? [])) {
      refuse(`${id}/program.json changed since courses.json was built; rebuild with the pipeline`)
      continue
    }
    if (checked && data.checked !== true) {
      refuse(`${rel} must say "checked": true because ${id}/program.json is checked`)
      continue
    }
    if (!checked) {
      const problems = []
      if (data.checked === true) problems.push('says "checked": true but program.json is not checked')
      if ((spec.draftWarnings ?? []).length) problems.push(`${id}/program.json still has draftWarnings`)
      let report = ''
      try {
        report = readFileSync(new URL(`${id}/build-report.md`, dataRoot), 'utf8')
      } catch {
        problems.push('has no build-report.md')
      }
      if (report) {
        if (!report.includes('## Warnings needing review\n\nNone.')) problems.push('build-report.md has warnings needing review')
        if (report.includes('## Validation errors')) problems.push('build-report.md has validation errors')
      }
      if (problems.length) {
        refuse(`${id} is not checked and ${rel} cannot ship: ${problems.join('; ')}`)
        continue
      }
    }
    shipped.push({ checked, id, level: spec.level, name: data.program.name })
    messages.push(`dataset ok: ${id} (${data.courses.length} courses, source ${data.source}${checked ? '' : ', auto-built, unchecked'})`)
  }

  // majors.json drives the dropdown; it must list exactly the majors that ship.
  if (ok) {
    let listed = null
    try {
      listed = JSON.parse(readFileSync(new URL('majors.json', dataRoot), 'utf8'))
    } catch (err) {
      refuse(`majors.json is missing or unreadable (${err.message}); rebuild with the pipeline`)
    }
    if (listed) {
      const byId = (a, b) => (a.id < b.id ? -1 : 1)
      const want = [...shipped].sort(byId)
      // Each entry also names the picker's college group, which comes from the catalog snapshot.
      const named = Array.isArray(listed) && listed.every((m) => typeof m?.college === 'string' && m.college.trim() !== '')
      const got = named ? listed.map(({ college, ...rest }) => rest).sort(byId) : null
      if (!got || !isDeepStrictEqual(got, want)) refuse('majors.json is out of date; rebuild with the pipeline')
    }
  }
  return { ok, messages }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const { ok, messages } = checkPrograms(new URL('../../data/2026-2027/', import.meta.url))
  for (const m of messages) (ok ? console.log : console.error)(m)
  if (!ok) process.exit(1)
}
