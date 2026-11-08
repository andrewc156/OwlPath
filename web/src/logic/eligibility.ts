import type { NCourse, NExpr } from '../data/types'

export type Status = 'not-taken' | 'in-progress' | 'complete'
/** A missing key means "not-taken". */
export type StatusMap = Record<string, Status>
export type NodeState = 'complete' | 'in-progress' | 'eligible-now' | 'eligible-next-term' | 'locked'

/** null is satisfied; external leaves never are. Coreqs and notes are not inputs here. */
export function evaluate(expr: NExpr | null, status: StatusMap, countInProgress: boolean): boolean {
  if (expr === null) return true
  switch (expr.kind) {
    case 'and':
      return expr.children.every((e) => evaluate(e, status, countInProgress))
    case 'or':
      return expr.children.some((e) => evaluate(e, status, countInProgress))
    case 'external':
      return false
    case 'course': {
      const s = status[expr.id]
      return s === 'complete' || (countInProgress && s === 'in-progress')
    }
  }
}

export function nodeState(course: NCourse, status: StatusMap): NodeState {
  const own = status[course.id]
  if (own === 'complete' || own === 'in-progress') return own
  if (evaluate(course.prereqs, status, false)) return 'eligible-now'
  if (evaluate(course.prereqs, status, true)) return 'eligible-next-term'
  return 'locked'
}
