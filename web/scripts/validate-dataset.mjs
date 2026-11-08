// Structural checks for data/<year>/courses.json, used by the production build guard.
// Mirrors the pipeline's validator so hand edits can't ship a silently wrong graph.

const GRADES = new Set(['A', 'B', 'C', 'D'])

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
  return errors
}
