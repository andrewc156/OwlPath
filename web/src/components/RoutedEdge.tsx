import { BaseEdge, type Edge, type EdgeProps } from '@xyflow/react'
import { smoothPath, type Point } from '../logic/layout'

export type RoutedEdgeData = { points: Point[] }

/** A prereq edge drawn through dagre's bend points, so it runs in the gaps between courses, not across them. */
export function RoutedEdge({ sourceX, sourceY, targetX, targetY, data, label, style, markerEnd }:
  EdgeProps<Edge<RoutedEdgeData, 'routed'>>) {
  const points = [{ x: sourceX, y: sourceY }, ...(data?.points ?? []), { x: targetX, y: targetY }]
  // Label the middle of the first gap the edge crosses (points 1 and 2 are the source column's edge and the
  // next column's edge); a level-ended curve passes exactly through that midpoint.
  const [a, b] = points.length >= 3 ? [points[1], points[2]] : [points[0], points[points.length - 1]]
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  return (
    <BaseEdge path={smoothPath(points)} label={label} labelX={mid.x} labelY={mid.y}
      style={style} markerEnd={markerEnd} />
  )
}
