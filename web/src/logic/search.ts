import type { NCourse } from '../data/types'

const compact = (s: string) => s.replace(/\s+/g, '').toLowerCase()

/** Id matches (ignoring case and spaces) first, then title matches; each sorted by id. */
export function searchCourses(courses: NCourse[], query: string): NCourse[] {
  const q = query.trim()
  if (!q) return []
  const idKey = compact(q)
  const titleKey = q.toLowerCase()
  const byId = (a: NCourse, b: NCourse) => a.id.localeCompare(b.id)
  const idHits = courses.filter((c) => compact(c.id).includes(idKey)).sort(byId)
  const seen = new Set(idHits.map((c) => c.id))
  const titleHits = courses.filter((c) => !seen.has(c.id) && c.title.toLowerCase().includes(titleKey)).sort(byId)
  return [...idHits, ...titleHits]
}
