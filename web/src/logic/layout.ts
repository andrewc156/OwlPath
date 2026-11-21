import { graphlib, layout } from '@dagrejs/dagre'
import type { Graph } from './graph'

export type Positions = Map<string, { x: number; y: number }>

export const COURSE_SIZE = { width: 160, height: 56 }
export const JUNCTION_SIZE = { width: 16, height: 16 }

/**
 * Left-to-right dagre layout over prereq edges only; coreqs would add cycles. Returns top-left corners.
 * `rankLike` maps a course to one it should sit beside (a less common option to its usual one): it gets that
 * course's incoming edges too, so it lands in the same column instead of drifting to the far left.
 */
export function layoutGraph(graph: Graph, rankLike: Map<string, string> = new Map()): Positions {
  const g = new graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 24, ranksep: 80 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const n of graph.nodes) g.setNode(n.id, n.kind === 'course' ? { ...COURSE_SIZE } : { ...JUNCTION_SIZE })
  for (const e of graph.edges) if (e.kind === 'prereq') g.setEdge(e.source, e.target)
  for (const [id, partner] of rankLike) {
    for (const e of graph.edges) {
      if (e.kind === 'prereq' && e.target === partner && e.source !== id && !g.hasEdge(e.source, id)) g.setEdge(e.source, id)
    }
  }
  layout(g)

  const positions: Positions = new Map()
  for (const n of graph.nodes) {
    const { x, y, width, height } = g.node(n.id)
    positions.set(n.id, { x: x - width / 2, y: y - height / 2 })
  }
  return positions
}
