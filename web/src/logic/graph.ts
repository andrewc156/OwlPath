import type { Grade, NCourse, NExpr, NLeaf } from '../data/types'

export type GNode =
  | { id: string; kind: 'course'; courseId: string; externalOnlyGroups: number }
  | { id: string; kind: 'junction'; op: 'and' | 'or'; target: string; externals: NLeaf[] }

/** minGrade is set only when it isn't C. */
export type GEdge = { id: string; source: string; target: string; kind: 'prereq' | 'coreq'; minGrade?: Grade }

export type Graph = { nodes: GNode[]; edges: GEdge[] }

const ROOT_PATH = 'r'

function hasInGraphCourse(expr: NExpr, known: Set<string>): boolean {
  if (expr.kind === 'course') return known.has(expr.id)
  if (expr.kind === 'external') return false
  return expr.children.some((e) => hasInGraphCourse(e, known))
}

function collectCourses(expr: NExpr, out: Set<string>): void {
  if (expr.kind === 'course') out.add(expr.id)
  else if (expr.kind === 'and' || expr.kind === 'or') expr.children.forEach((e) => collectCourses(e, out))
}

export function buildGraph(courses: NCourse[]): Graph {
  const known = new Set(courses.map((c) => c.id))
  const nodes: GNode[] = []
  const edges: GEdge[] = []

  for (const course of courses) {
    const courseNode: Extract<GNode, { kind: 'course' }> = {
      id: course.id, kind: 'course', courseId: course.id, externalOnlyGroups: 0,
    }
    nodes.push(courseNode)

    const link = (source: string, target: string, path: string, minGrade: Grade) => {
      const e: GEdge = { id: `prereq:${source}->${target}:${path}`, source, target, kind: 'prereq' }
      if (minGrade !== 'C') e.minGrade = minGrade
      edges.push(e)
    }

    // parent: the node this expression feeds into (the course or a junction).
    const attach = (expr: NExpr, parent: Extract<GNode, { kind: 'junction' }> | null, path: string, underOr: boolean): void => {
      const parentId = parent?.id ?? course.id
      if (expr.kind === 'course') {
        if (known.has(expr.id)) link(expr.id, parentId, path, expr.minGrade)
        return
      }
      if (expr.kind === 'external') {
        if (parent) parent.externals.push(expr)
        else courseNode.externalOnlyGroups += 1
        return
      }
      const needsJunction = expr.kind === 'or' || underOr
      if (!needsJunction) {
        expr.children.forEach((child, i) => attach(child, parent, path === ROOT_PATH ? `${i}` : `${path}.${i}`, false))
        return
      }
      if (!hasInGraphCourse(expr, known)) {
        courseNode.externalOnlyGroups += 1
        return
      }
      const junction: Extract<GNode, { kind: 'junction' }> = {
        id: `j:${course.id}:${path}`, kind: 'junction', op: expr.kind, target: course.id, externals: [],
      }
      nodes.push(junction)
      edges.push({ id: `prereq:${junction.id}->${parentId}`, source: junction.id, target: parentId, kind: 'prereq' })
      expr.children.forEach((child, i) =>
        attach(child, junction, path === ROOT_PATH ? `${i}` : `${path}.${i}`, expr.kind === 'or'))
    }

    if (course.prereqs) attach(course.prereqs, null, ROOT_PATH, false)

    if (course.coreqs) {
      const sources = new Set<string>()
      collectCourses(course.coreqs, sources)
      for (const s of sources) {
        if (known.has(s)) edges.push({ id: `coreq:${s}->${course.id}`, source: s, target: course.id, kind: 'coreq' })
      }
    }
  }
  return { nodes, edges }
}
