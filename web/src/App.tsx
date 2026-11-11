import { useMemo, useState } from 'react'
import { CourseList } from './components/CourseList'
import { DetailPanel } from './components/DetailPanel'
import { Filters } from './components/Filters'
import { Footer } from './components/Footer'
import { GraphView, type FocusRequest } from './components/GraphView'
import { useIsSmallScreen } from './components/useIsSmallScreen'
import { loadPrograms } from './data/dataset'
import type { Group } from './data/types'
import { nodeState } from './logic/eligibility'
import { buildGraph } from './logic/graph'
import { concentrationSet, highlightSets } from './logic/highlight'
import { layoutGraph } from './logic/layout'
import type { ViewCtx } from './logic/view'
import { useStatus } from './state/status'

// Data, graph and layout are fixed for the session; compute once.
// Task 7 wires the major dropdown; until then show the first major.
const dataset = loadPrograms()[0]
const graph = buildGraph(dataset.courses)
const positions = layoutGraph(graph)
const validIds = new Set(dataset.courses.map((c) => c.id))

export default function App() {
  const [status, setStatus] = useStatus(validIds)
  const [selected, setSelected] = useState<string | null>(null)
  const [filter, setFilter] = useState<Group | null>(null)
  const [focus, setFocus] = useState<FocusRequest | null>(null)
  const selectFromSearch = (id: string) => {
    setSelected(id)
    setFocus((f) => ({ id, seq: (f?.seq ?? 0) + 1 }))
  }
  const small = useIsSmallScreen()

  const filterSet = useMemo(() => (filter ? concentrationSet(graph, dataset.courses, filter) : null), [filter])
  const states = useMemo(() => Object.fromEntries(dataset.courses.map((c) => [c.id, nodeState(c, status)])), [status])
  const ctx: ViewCtx = useMemo(
    () => ({ highlight: selected ? highlightSets(graph, selected) : null, filter: filterSet, states }),
    [selected, filterSet, states],
  )

  const selectedCourse = selected ? dataset.byId.get(selected) : undefined
  const panel = selectedCourse && (
    <DetailPanel course={selectedCourse} status={status} onStatus={setStatus} onClose={() => setSelected(null)} />
  )

  return (
    <div className="app">
      <header className="app-header">
        <h1>OwlPath</h1>
        <span className="subtitle">BS Computer Science · {dataset.catalogYear} catalog</span>
        <Filters courses={dataset.courses} filter={filter} onFilter={setFilter} onSelect={selectFromSearch} />
      </header>
      <main className="app-main">
        {small ? (
          panel ?? <CourseList courses={dataset.courses} states={states} visible={filterSet} onSelect={setSelected} />
        ) : (
          <>
            <GraphView graph={graph} positions={positions} ctx={ctx} focus={focus} onSelect={setSelected} />
            {panel}
          </>
        )}
      </main>
      <Footer />
    </div>
  )
}
