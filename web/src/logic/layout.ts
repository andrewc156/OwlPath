import { graphlib, layout } from '@dagrejs/dagre'
import type { Graph } from './graph'

export type Point = { x: number; y: number }
export type Positions = Map<string, Point>
/**
 * Bend points for each prereq edge, keyed `source->target`, without the two end points: straight out of the
 * source's column, through dagre's points, and straight into the target's column.
 */
export type Routes = Map<string, Point[]>
export type Layout = { positions: Positions; routes: Routes }

export const COURSE_SIZE = { width: 160, height: 56 }
export const JUNCTION_SIZE = { width: 16, height: 16 }

export const routeKey = (source: string, target: string) => `${source}->${target}`

/**
 * Left-to-right dagre layout over prereq edges only; coreqs would add cycles. Positions are top-left corners.
 * Routes keep dagre's bend points, which pass through the gaps between courses, so an edge drawn through them
 * never crosses a course it doesn't connect to.
 * `rankLike` maps a course to one it should sit beside (a less common option to its usual one): it gets that
 * course's incoming edges too, so it lands in the same column instead of drifting to the far left.
 */
export function layoutGraph(graph: Graph, rankLike: Map<string, string> = new Map()): Layout {
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
  // Nodes in one rank share a centre x. A junction is narrower than the courses beside it, so an edge that
  // bent right at the junction could clip a course above or below it: leave and enter at the column's edge.
  const halfWidth = new Map<number, number>()
  for (const n of graph.nodes) {
    const { x, width } = g.node(n.id)
    halfWidth.set(Math.round(x), Math.max(halfWidth.get(Math.round(x)) ?? 0, width / 2))
  }
  const columnHalf = (x: number) => halfWidth.get(Math.round(x))
  const routes: Routes = new Map()
  for (const e of graph.edges) {
    if (e.kind !== 'prereq') continue
    const s = g.node(e.source), t = g.node(e.target)
    const bends: Point[] = (g.edge(e.source, e.target)?.points ?? []).slice(1, -1)
    // A bend inside a column of nodes (a dagre dummy node) becomes a straight run across that column at the
    // height dagre kept free, so the edge only changes height in the gaps between columns, where no node is.
    const across = bends.flatMap(({ x, y }) => {
      const half = columnHalf(x)
      return half === undefined ? [{ x, y }] : [{ x: x - half, y }, { x: x + half, y }]
    })
    routes.set(routeKey(e.source, e.target), [
      { x: s.x + (columnHalf(s.x) ?? s.width / 2), y: s.y },
      ...across,
      { x: t.x - (columnHalf(t.x) ?? t.width / 2), y: t.y },
    ])
  }
  return { positions, routes }
}

/**
 * SVG path through every point in order. Each step is a cubic that leaves and arrives level, so it stays
 * inside the box between its two points and never cuts a corner into a neighbouring node.
 */
export function smoothPath(points: Point[]): string {
  const f = (n: number) => Math.round(n * 100) / 100
  if (points.length === 0) return ''
  let [prev] = points
  let d = `M${f(prev.x)},${f(prev.y)}`
  for (const p of points.slice(1)) {
    if (p.x === prev.x && p.y === prev.y) continue
    const mid = (prev.x + p.x) / 2
    d += p.x === prev.x || p.y === prev.y
      ? `L${f(p.x)},${f(p.y)}`
      : `C${f(mid)},${f(prev.y)} ${f(mid)},${f(p.y)} ${f(p.x)},${f(p.y)}`
    prev = p
  }
  return d
}
