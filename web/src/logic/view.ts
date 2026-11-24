import type { Edge, Node } from '@xyflow/react'
import type { NodeState } from './eligibility'
import type { Graph } from './graph'
import type { Highlight } from './highlight'
import { routeKey, type Layout } from './layout'
import { choicePartners } from './choices'

export type ViewCtx = {
  highlight: Highlight | null
  filter: Set<string> | null
  states: Record<string, NodeState>
  /** The major's either/or program requirements. */
  choices: string[][]
  /** Courses left off the map (less common either/or options); their edges go too. */
  hidden: Set<string>
  /** Course titles by id, for the node text. */
  titles: Record<string, string>
}

export type CourseNodeData = { courseId: string; title: string; state: NodeState; externalOnlyGroups: number; choiceWith: string[] }
export type JunctionNodeData = { op: 'and' | 'or'; externalCount: number }

/** Selection wins over the Show filter. */
function nodeClass(id: string, ctx: ViewCtx): string {
  const h = ctx.highlight
  if (h) {
    if (id === h.selected) return 'selected'
    if (h.ancestors.has(id)) return 'ancestor'
    if (h.descendants.has(id)) return 'descendant'
    if (h.takeWith.has(id)) return 'take-with'
    if (choicePartners(ctx.choices, h.selected).includes(id)) return 'alternative'
    return 'dimmed'
  }
  if (ctx.filter && !ctx.filter.has(id)) return 'dimmed'
  return ''
}

export function toFlow(graph: Graph, { positions, routes }: Layout, ctx: ViewCtx): { nodes: Node[]; edges: Edge[] } {
  const classes = new Map(graph.nodes.map((n) => [n.id, nodeClass(n.id, ctx)]))

  // A junction belongs to one course (its target), so it goes when that course is hidden.
  const gone = new Set(graph.nodes.filter((n) => ctx.hidden.has(n.kind === 'junction' ? n.target : n.id)).map((n) => n.id))
  const nodes: Node[] = graph.nodes.filter((n) => !gone.has(n.id)).map((n) => {
    const position = positions.get(n.id) ?? { x: 0, y: 0 }
    const className = classes.get(n.id)
    if (n.kind === 'course') {
      const data: CourseNodeData = {
        courseId: n.courseId,
        title: ctx.titles[n.courseId] ?? '',
        state: ctx.states[n.courseId] ?? 'locked',
        externalOnlyGroups: n.externalOnlyGroups,
        choiceWith: choicePartners(ctx.choices, n.courseId),
      }
      return { id: n.id, type: 'course', position, data, className }
    }
    const data: JunctionNodeData = { op: n.op, externalCount: n.externals.length }
    return { id: n.id, type: 'junction', position, data, className, selectable: false }
  })

  // Coreqs aren't in the layout, so their lines can cross unrelated courses. Show one only while one of its
  // courses is selected; the detail panel lists coreqs either way.
  const showCoreq = (e: Graph['edges'][number]) => !!ctx.highlight && [e.source, e.target].includes(ctx.highlight.selected)
  const edges: Edge[] = graph.edges
    .filter((e) => !gone.has(e.source) && !gone.has(e.target) && (e.kind === 'prereq' || showCoreq(e)))
    .map((e) => {
    const dimmed = classes.get(e.source) === 'dimmed' || classes.get(e.target) === 'dimmed'
    const edge: Edge = { id: e.id, source: e.source, target: e.target, className: dimmed ? 'dimmed' : '' }
    if (e.kind === 'coreq') edge.style = { strokeDasharray: '6 4' }
    else {
      edge.type = 'routed'
      edge.data = { points: routes.get(routeKey(e.source, e.target)) ?? [] }
    }
    if (e.minGrade) edge.label = e.minGrade
    return edge
  })

  return { nodes, edges }
}
