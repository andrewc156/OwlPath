// Structural checks for data/<year>/courses.json, used by the production build guard.
// Mirrors the pipeline's validator so hand edits can't ship a silently wrong graph.

const GRADES = new Set(['A', 'B', 'C', 'D'])
// Same patterns as data/schema/courses.schema.json.
const GROUP = /^(core-field|major-required|major-elective|major-project|gen-ed-math|prereq-only|conc-[a-z0-9]+(-[a-z0-9]+)*)$/
// catalogUrl feeds the "View in catalog" link's href, so only KSU catalog pages may ship.
const CATALOG_URL = /^https:\/\/catalog\.kennesaw\.edu\//

/** @returns {string[]} error messages; empty means valid. */
export function validateDataset(data) {
  const errors = []
  if (!data || !Array.isArray(data.courses) || data.courses.length === 0) {
    return ['courses must be a non-empty array']
  }
  const ids = new Set()
  for (const c of data.courses) {
    if (!c || typeof c.id !== 'string') {
      errors.push('every course needs a string id')
      continue
    }
    if (ids.has(c.id)) errors.push(`duplicate id ${c.id}`)
    ids.add(c.id)
    if (typeof c.catalogUrl !== 'string' || !CATALOG_URL.test(c.catalogUrl)) {
      errors.push(`${c.id}: catalogUrl must start with https://catalog.kennesaw.edu/`)
    }
  }

  const check = (owner, logic) => {
    if (logic === null || logic === undefined) return
    if (typeof logic === 'string') {
      if (!ids.has(logic)) errors.push(`${owner}: unknown course "${logic}"`)
      return
    }
    if (typeof logic !== 'object') {
      errors.push(`${owner}: invalid requirement ${JSON.stringify(logic)}`)
      return
    }
    if (Array.isArray(logic.and) || Array.isArray(logic.or)) {
      const children = logic.and ?? logic.or
      if (children.length === 0) errors.push(`${owner}: empty and/or group`)
      children.forEach((child) => check(owner, child))
      return
    }
    if ('minGrade' in logic && !GRADES.has(logic.minGrade)) {
      errors.push(`${owner}: invalid minGrade "${logic.minGrade}"`)
    }
    if (typeof logic.course === 'string') {
      if (!ids.has(logic.course)) errors.push(`${owner}: unknown course "${logic.course}"`)
    } else if (typeof logic.external !== 'string') {
      errors.push(`${owner}: invalid requirement ${JSON.stringify(logic)}`)
    }
  }

  for (const c of data.courses) {
    if (!c || typeof c.id !== 'string') continue
    check(c.id, c.prereqs)
    check(c.id, c.coreqs)
  }

  const p = data.program
  if (!p || typeof p.id !== 'string' || typeof p.name !== 'string' || !Array.isArray(p.filters)) {
    errors.push('program: missing id/name/filters')
  }
  const used = new Set()
  for (const c of data.courses) {
    if (!c || !Array.isArray(c.groups)) continue
    for (const g of c.groups) {
      if (typeof g === 'string' && GROUP.test(g)) used.add(g)
      else errors.push(`${c.id}: invalid group ${JSON.stringify(g)}`)
    }
  }
  if (p && Array.isArray(p.filters)) {
    for (const f of p.filters) {
      for (const g of f?.groups ?? []) if (!used.has(g)) errors.push(`program: filter group "${g}" is used by no course`)
    }
  }
  if (!Array.isArray(data.choices)) {
    errors.push('choices must be an array')
  } else {
    for (const choice of data.choices) {
      if (!Array.isArray(choice) || choice.length < 2) {
        errors.push(`choices: ${JSON.stringify(choice)} needs at least two courses`)
        continue
      }
      for (const id of choice) if (!ids.has(id)) errors.push(`choices: unknown course ${id}`)
    }
  }
  const hidden = data.lessCommon ?? []
  if (!Array.isArray(hidden)) {
    errors.push('lessCommon must be an array')
  } else {
    for (const id of hidden) {
      if (!ids.has(id)) errors.push(`lessCommon: unknown course ${id}`)
      const shown = Array.isArray(data.choices) && data.choices.some(
        (ch) => Array.isArray(ch) && ch.includes(id) && ch.some((o) => !hidden.includes(o)))
      if (!shown) errors.push(`lessCommon: ${id} needs an either/or requirement with a shown option`)
    }
  }
  return errors
}
