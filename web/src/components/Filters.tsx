import { useState } from 'react'
import type { Group, NCourse } from '../data/types'
import { searchCourses } from '../logic/search'

export const FILTER_OPTIONS: { label: string; group: Group | null }[] = [
  { label: 'All', group: null },
  { label: 'Data Science', group: 'conc-data-science' },
  { label: 'Cyber & Network Security', group: 'conc-cyber' },
  { label: 'AI', group: 'conc-ai' },
  { label: 'General electives', group: 'major-elective' },
]

type Props = { courses: NCourse[]; filter: Group | null; onFilter: (g: Group | null) => void; onSelect: (id: string) => void }

export function Filters({ courses, filter, onFilter, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const results = searchCourses(courses, query).slice(0, 8)
  return (
    <div className="filters">
      <label>
        Concentration{' '}
        <select value={filter ?? ''} onChange={(e) => onFilter((e.target.value || null) as Group | null)}>
          {FILTER_OPTIONS.map((o) => <option key={o.label} value={o.group ?? ''}>{o.label}</option>)}
        </select>
      </label>
      <div className="search">
        <input type="search" placeholder="Find a course (e.g. CS 3305)" aria-label="Find a course"
          value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && results[0]) { onSelect(results[0].id); setQuery('') } }} />
        {results.length > 0 && (
          <ul className="search-results" role="listbox">
            {results.map((c) => (
              <li key={c.id}>
                <button onClick={() => { onSelect(c.id); setQuery('') }}><strong>{c.id}</strong> {c.title}</button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
