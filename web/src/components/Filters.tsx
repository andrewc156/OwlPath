import { useState } from 'react'
import type { FilterOption, NCourse } from '../data/types'
import { searchCourses } from '../logic/search'

/** `filter` is an index into `options` (the major's own filter list); null means All. */
type Props = {
  options: FilterOption[]
  courses: NCourse[]
  filter: number | null
  onFilter: (i: number | null) => void
  onSelect: (id: string) => void
}

export function Filters({ options, courses, filter, onFilter, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const results = searchCourses(courses, query).slice(0, 8)
  return (
    <div className="filters">
      <label>
        Show{' '}
        <select value={filter ?? ''} onChange={(e) => onFilter(e.target.value === '' ? null : Number(e.target.value))}>
          <option value="">All</option>
          {options.map((o, i) => <option key={o.label} value={i}>{o.label}</option>)}
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
