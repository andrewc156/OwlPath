import { Background, Controls, ReactFlow, type NodeTypes } from '@xyflow/react'
import { useMemo } from 'react'
import type { Graph } from '../logic/graph'
import type { Positions } from '../logic/layout'
import { toFlow, type ViewCtx } from '../logic/view'
import { CourseNode } from './CourseNode'
import { JunctionNode } from './JunctionNode'

const nodeTypes: NodeTypes = { course: CourseNode, junction: JunctionNode }

type Props = { graph: Graph; positions: Positions; ctx: ViewCtx; onSelect: (courseId: string | null) => void }

export function GraphView({ graph, positions, ctx, onSelect }: Props) {
  const { nodes, edges } = useMemo(() => toFlow(graph, positions, ctx), [graph, positions, ctx])
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      onNodeClick={(_, node) => node.type === 'course' && onSelect(node.id)}
      onPaneClick={() => onSelect(null)}
      fitView
      minZoom={0.2}
      proOptions={{ hideAttribution: false }}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
