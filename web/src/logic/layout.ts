import { graphlib, layout } from '@dagrejs/dagre'
import type { Graph } from './graph'

export type Positions = Map<string, { x: number; y: number }>

export const COURSE_SIZE = { width: 160, height: 56 }
export const JUNCTION_SIZE = { width: 16, height: 16 }

/** Left-to-right dagre layout over prereq edges only; coreqs would add cycles. Returns top-left corners. */
export function layoutGraph(graph: Graph): Positions {
  const g = new graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 24, ranksep: 80 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const n of graph.nodes) g.setNode(n.id, n.kind === 'course' ? { ...COURSE_SIZE } : { ...JUNCTION_SIZE })
  for (const e of graph.edges) if (e.kind === 'prereq') g.setEdge(e.source, e.target)
  layout(g)

  const positions: Positions = new Map()
  for (const n of graph.nodes) {
    const { x, y, width, height } = g.node(n.id)
    positions.set(n.id, { x: x - width / 2, y: y - height / 2 })
  }
  return positions
}
