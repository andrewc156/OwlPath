import { BaseEdge, type Edge, type EdgeProps } from '@xyflow/react'
import { smoothPath, type Point } from '../logic/layout'

export type RoutedEdgeData = { points: Point[] }

/** A prereq edge drawn through dagre's bend points, so it runs in the gaps between courses, not across them. */
export function RoutedEdge({ sourceX, sourceY, targetX, targetY, data, label, style, markerEnd }:
  EdgeProps<Edge<RoutedEdgeData, 'routed'>>) {
  const points = [{ x: sourceX, y: sourceY }, ...(data?.points ?? []), { x: targetX, y: targetY }]
  const mid = points[Math.floor(points.length / 2)]
  return (
    <BaseEdge path={smoothPath(points)} label={label} labelX={mid.x} labelY={mid.y}
      style={style} markerEnd={markerEnd} />
  )
}
