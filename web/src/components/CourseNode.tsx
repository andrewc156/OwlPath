import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { loadPrograms } from '../data/dataset'
import type { CourseNodeData } from '../logic/view'
import { STATE_LABEL } from './stateLabels'

// Titles are the same in every major, so look them up across all of them.
const titles = new Map(loadPrograms().flatMap((p) => p.courses.map((c) => [c.id, c.title] as const)))

export function CourseNode({ data }: NodeProps<Node<CourseNodeData>>) {
  const title = titles.get(data.courseId)
  const label = STATE_LABEL[data.state]
  return (
    <div className={`course-node state-${data.state}`} title={title}>
      <Handle type="target" position={Position.Left} />
      <div className="course-id">
        {data.courseId}
        {data.choiceWith.length > 0 && <span className="choice-with"> or {data.choiceWith.join(' / ')}</span>}
      </div>
      <div className="course-title">{title}</div>
      <div className="course-state">
        <span aria-hidden="true">{label.symbol}</span> {label.text}
        {data.externalOnlyGroups > 0 && <span className="ext-only"> · needs outside course</span>}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
