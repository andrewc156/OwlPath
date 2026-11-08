import { useState } from 'react'
import type { NCourse } from '../data/types'
import type { NodeState } from '../logic/eligibility'
import { searchCourses } from '../logic/search'
import { STATE_LABEL } from './stateLabels'

type Props = { courses: NCourse[]; states: Record<string, NodeState>; visible: Set<string> | null; onSelect: (id: string) => void }

/** Small-screen replacement for the graph. */
export function CourseList({ courses, states, visible, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const base = query.trim() ? searchCourses(courses, query) : [...courses].sort((a, b) => a.id.localeCompare(b.id))
  const shown = visible ? base.filter((c) => visible.has(c.id)) : base
  return (
    <div className="course-list">
      <input type="search" placeholder="Search courses" aria-label="Search courses" value={query} onChange={(e) => setQuery(e.target.value)} />
      <ul>
        {shown.map((c) => {
          const label = STATE_LABEL[states[c.id] ?? 'locked']
          return (
            <li key={c.id}>
              <button className={`state-${states[c.id]}`} onClick={() => onSelect(c.id)}>
                <span className="cl-id">{c.id}</span>
                <span className="cl-title">{c.title}</span>
                <span className="cl-state"><span aria-hidden="true">{label.symbol}</span> {label.text}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
