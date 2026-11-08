import type { NCourse, NExpr } from '../data/types'
import type { Status, StatusMap } from '../logic/eligibility'
import { describeLogic } from '../logic/describe'

type Props = { course: NCourse; status: StatusMap; onStatus: (id: string, s: Status) => void; onClose: () => void }

const STATUS_OPTIONS: { value: Status; label: string }[] = [
  { value: 'not-taken', label: 'Not taken' },
  { value: 'in-progress', label: 'In progress' },
  { value: 'complete', label: 'Complete' },
]

function courseLeaves(expr: NExpr | null, out: string[] = []): string[] {
  if (!expr) return out
  if (expr.kind === 'course') out.push(expr.id)
  else if (expr.kind === 'and' || expr.kind === 'or') expr.children.forEach((e) => courseLeaves(e, out))
  return out
}

export function DetailPanel({ course, status, onStatus, onClose }: Props) {
  const current = status[course.id] ?? 'not-taken'
  const coreqIds = [...new Set(courseLeaves(course.coreqs))]
  return (
    <aside className="detail-panel" aria-label={`${course.id} details`}>
      <button className="close" onClick={onClose} aria-label="Close details">×</button>
      <h2>{course.id}</h2>
      <p className="detail-title">{course.title}</p>
      <p className="muted">{course.credits} credit hours</p>
      <p>{course.description}</p>

      <h3>Prerequisites</h3>
      <p>{describeLogic(course.prereqs)}</p>

      {course.coreqs && (
        <>
          <h3>Take with</h3>
          <p>{describeLogic(course.coreqs)}</p>
          <ul className="coreq-list">
            {coreqIds.map((id) => {
              const s = status[id]
              const met = s === 'complete' || s === 'in-progress'
              return <li key={id}>{met ? '✓' : '○'} {id} {met ? '(met)' : '(take with)'}</li>
            })}
          </ul>
        </>
      )}

      {course.notes.length > 0 && (
        <>
          <h3>Notes</h3>
          <ul>{course.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}

      <h3>My status</h3>
      <div className="status-control" role="radiogroup" aria-label="My status">
        {STATUS_OPTIONS.map((o) => (
          <label key={o.value} className={current === o.value ? 'active' : ''}>
            <input type="radio" name={`status-${course.id}`} value={o.value} checked={current === o.value}
              onChange={() => onStatus(course.id, o.value)} />
            {o.label}
          </label>
        ))}
      </div>

      <p><a href={course.catalogUrl} target="_blank" rel="noopener">View in catalog ↗</a></p>
    </aside>
  )
}
