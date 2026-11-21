import { Background, Controls, ReactFlow, useReactFlow, type EdgeTypes, type NodeTypes } from '@xyflow/react'
import { useEffect, useMemo } from 'react'
import type { Graph } from '../logic/graph'
import type { Layout } from '../logic/layout'
import { toFlow, type ViewCtx } from '../logic/view'
import { CourseNode } from './CourseNode'
import { JunctionNode } from './JunctionNode'
import { RoutedEdge } from './RoutedEdge'

const nodeTypes: NodeTypes = { course: CourseNode, junction: JunctionNode }
const edgeTypes: EdgeTypes = { routed: RoutedEdge }

/** A request to bring a course into view; seq changes on every request, even for the same course. */
export type FocusRequest = { id: string; seq: number }

type Props = {
  graph: Graph; layout: Layout; ctx: ViewCtx; focus: FocusRequest | null
  onSelect: (courseId: string | null) => void
}

function FocusOn({ focus }: { focus: FocusRequest | null }) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    if (focus) void fitView({ nodes: [{ id: focus.id }], maxZoom: 1.2, duration: 300 })
  }, [focus, fitView])
  return null
}

export function GraphView({ graph, layout, ctx, focus, onSelect }: Props) {
  const { nodes, edges } = useMemo(() => toFlow(graph, layout, ctx), [graph, layout, ctx])
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
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
      <FocusOn focus={focus} />
    </ReactFlow>
  )
}
