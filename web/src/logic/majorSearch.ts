import type { MajorEntry } from '../data/dataset'

export type MajorGroup = { label: 'Undergraduate' | 'Graduate'; items: MajorEntry[] }

/** Undergraduate first, then Graduate; A–Z by name; case-insensitive match on name or id; empty groups dropped. */
export function groupMajors(entries: MajorEntry[], query: string): MajorGroup[] {
  const q = query.trim().toLowerCase()
  const match = (m: MajorEntry) => !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q)
  const levels: [MajorGroup['label'], MajorEntry['level']][] = [['Undergraduate', 'undergraduate'], ['Graduate', 'graduate']]
  return levels
    .map(([label, level]) => ({
      label,
      items: entries.filter((m) => m.level === level && match(m)).sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .filter((g) => g.items.length > 0)
}
