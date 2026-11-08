import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import type { JunctionNodeData } from '../logic/view'

export function JunctionNode({ data }: NodeProps<Node<JunctionNodeData>>) {
  const label = data.op === 'or' ? 'OR' : 'AND'
  const extra = data.externalCount > 0 ? ` (+${data.externalCount} other)` : ''
  return (
    <div className={`junction-node junction-${data.op}`} title={`${label}${extra}`}>
      <Handle type="target" position={Position.Left} />
      <span>{data.op === 'or' ? 'OR' : '&'}</span>
      {data.externalCount > 0 && <span className="junction-ext">+{data.externalCount}</span>}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
