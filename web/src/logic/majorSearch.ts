import type { MajorEntry } from '../data/dataset'

export type CollegeGroup = { name: string; items: MajorEntry[] }
export type MajorGroup = { label: 'Undergraduate' | 'Graduate'; colleges: CollegeGroup[] }

/** One row of the open picker: a level or college header (opens and closes what's under it) or a major. */
export type PickerRow =
  | { kind: 'level'; key: string; name: string; count: number; open: boolean }
  | { kind: 'college'; key: string; name: string; count: number; open: boolean }
  | { kind: 'major'; key: string; major: MajorEntry }

const LEVELS: [MajorGroup['label'], MajorEntry['level']][] = [['Undergraduate', 'undergraduate'], ['Graduate', 'graduate']]

/** The key that names one college within one level (the same college has majors at both levels). */
export const collegeKey = (level: MajorEntry['level'], college: string) => `${level}|${college}`

/** The key that names one level's header. */
export const levelKey = (level: MajorEntry['level']) => `level|${level}`

/**
 * Undergraduate first, then Graduate; colleges A–Z within a level; majors A–Z within a college.
 * Case-insensitive match on the major's name, id or college. Empty colleges and levels are dropped.
 */
export function groupMajors(entries: MajorEntry[], query: string): MajorGroup[] {
  const q = query.trim().toLowerCase()
  const match = (m: MajorEntry) =>
    !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q) || m.college.toLowerCase().includes(q)
  return LEVELS.map(([label, level]) => {
    const byCollege = new Map<string, MajorEntry[]>()
    for (const m of entries) {
      if (m.level === level && match(m)) byCollege.set(m.college, [...(byCollege.get(m.college) ?? []), m])
    }
    const colleges = [...byCollege]
      .map(([name, items]) => ({ name, items: items.sort((a, b) => a.name.localeCompare(b.name)) }))
      .sort((a, b) => a.name.localeCompare(b.name))
    return { label, colleges }
  }).filter((g) => g.colleges.length > 0)
}

/**
 * The rows the picker shows, in order: each level, its colleges when the level is open, and each open college's
 * majors. While searching everything with a match is open; otherwise only the keys in `expanded` are.
 */
export function pickerRows(groups: MajorGroup[], expanded: ReadonlySet<string>, searching: boolean): PickerRow[] {
  const rows: PickerRow[] = []
  for (const g of groups) {
    const level = g.label === 'Undergraduate' ? 'undergraduate' : 'graduate'
    const lkey = levelKey(level)
    const levelOpen = searching || expanded.has(lkey)
    rows.push({ kind: 'level', key: lkey, name: g.label, count: g.colleges.reduce((n, c) => n + c.items.length, 0), open: levelOpen })
    if (!levelOpen) continue
    for (const c of g.colleges) {
      const key = collegeKey(level, c.name)
      const open = searching || expanded.has(key)
      rows.push({ kind: 'college', key, name: c.name, count: c.items.length, open })
      if (open) for (const m of c.items) rows.push({ kind: 'major', key: m.id, major: m })
    }
  }
  return rows
}
