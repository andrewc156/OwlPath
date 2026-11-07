import { useMemo, useState } from 'react'
import { DetailPanel } from './components/DetailPanel'
import { GraphView } from './components/GraphView'
import { loadDataset } from './data/dataset'
import { nodeState } from './logic/eligibility'
import { buildGraph } from './logic/graph'
import { highlightSets } from './logic/highlight'
import { layoutGraph } from './logic/layout'
import type { ViewCtx } from './logic/view'
import { useStatus } from './state/status'

// Data, graph and layout are fixed for the session; compute once.
const dataset = loadDataset()
const graph = buildGraph(dataset.courses)
const positions = layoutGraph(graph)
const validIds = new Set(dataset.courses.map((c) => c.id))

export default function App() {
  const [status, setStatus] = useStatus(validIds)
  const [selected, setSelected] = useState<string | null>(null)

  const ctx: ViewCtx = useMemo(
    () => ({
      highlight: selected ? highlightSets(graph, selected) : null,
      filter: null,
      states: Object.fromEntries(dataset.courses.map((c) => [c.id, nodeState(c, status)])),
    }),
    [selected, status],
  )

  const selectedCourse = selected ? dataset.byId.get(selected) : undefined

  return (
    <div className="app">
      <header className="app-header">
        <h1>OwlPath</h1>
        <span className="subtitle">BS Computer Science · {dataset.catalogYear} catalog</span>
      </header>
      <main className="app-main">
        <GraphView graph={graph} positions={positions} ctx={ctx} onSelect={setSelected} />
        {selectedCourse && (
          <DetailPanel course={selectedCourse} status={status} onStatus={setStatus} onClose={() => setSelected(null)} />
        )}
      </main>
    </div>
  )
}
