import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import type { JunctionNodeData } from '../logic/view'

/** Where prerequisite lines meet: OR means any one of them, AND means all of them. */
export function JunctionNode({ data }: NodeProps<Node<JunctionNodeData>>) {
  const label = data.op === 'or' ? 'OR' : 'AND'
  const meaning = data.op === 'or' ? 'Any one of these' : 'All of these'
  const n = data.externalCount
  const extra = n > 0 ? ` (or ${n} course${n > 1 ? 's' : ''} outside this program; see the course's details)` : ''
  return (
    <div className={`junction-node junction-${data.op}`} title={`${meaning}${extra}`}>
      <Handle type="target" position={Position.Left} />
      <span>{label}</span>
      {n > 0 && <span className="junction-ext">+{n}</span>}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
