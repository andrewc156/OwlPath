import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { loadDataset } from '../data/dataset'
import type { CourseNodeData } from '../logic/view'
import { STATE_LABEL } from './stateLabels'

const dataset = loadDataset()

export function CourseNode({ data }: NodeProps<Node<CourseNodeData>>) {
  const course = dataset.byId.get(data.courseId)
  const label = STATE_LABEL[data.state]
  return (
    <div className={`course-node state-${data.state}`} title={course?.title}>
      <Handle type="target" position={Position.Left} />
      <div className="course-id">{data.courseId}</div>
      <div className="course-title">{course?.title}</div>
      <div className="course-state">
        <span aria-hidden="true">{label.symbol}</span> {label.text}
        {data.externalOnlyGroups > 0 && <span className="ext-only"> · needs outside course</span>}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
