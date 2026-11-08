import type { Edge, Node } from '@xyflow/react'
import type { NodeState } from './eligibility'
import type { Graph } from './graph'
import type { Highlight } from './highlight'
import type { Positions } from './layout'

export type ViewCtx = { highlight: Highlight | null; filter: Set<string> | null; states: Record<string, NodeState> }

export type CourseNodeData = { courseId: string; state: NodeState; externalOnlyGroups: number }
export type JunctionNodeData = { op: 'and' | 'or'; externalCount: number }

/** Selection wins over the concentration filter. */
function nodeClass(id: string, ctx: ViewCtx): string {
  const h = ctx.highlight
  if (h) {
    if (id === h.selected) return 'selected'
    if (h.ancestors.has(id)) return 'ancestor'
    if (h.descendants.has(id)) return 'descendant'
    if (h.takeWith.has(id)) return 'take-with'
    return 'dimmed'
  }
  if (ctx.filter && !ctx.filter.has(id)) return 'dimmed'
  return ''
}

export function toFlow(graph: Graph, positions: Positions, ctx: ViewCtx): { nodes: Node[]; edges: Edge[] } {
  const classes = new Map(graph.nodes.map((n) => [n.id, nodeClass(n.id, ctx)]))

  const nodes: Node[] = graph.nodes.map((n) => {
    const position = positions.get(n.id) ?? { x: 0, y: 0 }
    const className = classes.get(n.id)
    if (n.kind === 'course') {
      const data: CourseNodeData = { courseId: n.courseId, state: ctx.states[n.courseId] ?? 'locked', externalOnlyGroups: n.externalOnlyGroups }
      return { id: n.id, type: 'course', position, data, className }
    }
    const data: JunctionNodeData = { op: n.op, externalCount: n.externals.length }
    return { id: n.id, type: 'junction', position, data, className, selectable: false }
  })

  const edges: Edge[] = graph.edges.map((e) => {
    const dimmed = classes.get(e.source) === 'dimmed' || classes.get(e.target) === 'dimmed'
    const edge: Edge = { id: e.id, source: e.source, target: e.target, className: dimmed ? 'dimmed' : '' }
    if (e.kind === 'coreq') edge.style = { strokeDasharray: '6 4' }
    if (e.minGrade) edge.label = e.minGrade
    return edge
  })

  return { nodes, edges }
}
