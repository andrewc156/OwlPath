import { useMemo, useState } from 'react'
import { CourseList } from './components/CourseList'
import { DetailPanel } from './components/DetailPanel'
import { Filters } from './components/Filters'
import { Footer } from './components/Footer'
import { GraphView } from './components/GraphView'
import { MajorPicker } from './components/MajorPicker'
import { ResetButton } from './components/ResetButton'
import { useIsSmallScreen } from './components/useIsSmallScreen'
import { loadPrograms } from './data/dataset'
import { choicePartners } from './logic/choices'
import { nodeState } from './logic/eligibility'
import { filterSet, highlightSets } from './logic/highlight'
import { allCourseIds, programView, switchMajor, type MajorState } from './logic/programView'
import type { ViewCtx } from './logic/view'
import { majorUrl, resolveMajor, saveMajor } from './state/major'
import { useStatus } from './state/status'

// Every major's data is bundled; each graph and layout is built the first time it's shown.
const programs = loadPrograms()
const byProgram = new Map(programs.map((p) => [p.program.id, p]))
const programIds = programs.map((p) => p.program.id)
const statusIds = allCourseIds(programs)

function browserStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export default function App() {
  const [status, setStatus, resetStatus] = useStatus(statusIds)
  const [view, setView] = useState<MajorState>(() => ({
    major: resolveMajor(window.location.search, browserStorage(), programIds),
    selected: null, filter: null, focus: null,
  }))
  const dataset = byProgram.get(view.major) ?? programs[0]
  const { graph, positions } = programView(dataset)
  const small = useIsSmallScreen()

  const changeMajor = (id: string) => {
    saveMajor(browserStorage(), id)
    window.history.replaceState(null, '', majorUrl(window.location.href, id))
    setView((v) => switchMajor(v, id))
  }
  const setSelected = (id: string | null) => setView((v) => ({ ...v, selected: id }))
  const setFilter = (i: number | null) => setView((v) => ({ ...v, filter: i }))
  const selectFromSearch = (id: string) =>
    setView((v) => ({ ...v, selected: id, focus: { id, seq: (v.focus?.seq ?? 0) + 1 } }))

  const filterOption = view.filter === null ? undefined : dataset.program.filters[view.filter]
  const visible = useMemo(
    () => (filterOption ? filterSet(graph, dataset.courses, filterOption.groups) : null),
    [graph, dataset, filterOption],
  )
  const states = useMemo(
    () => Object.fromEntries(dataset.courses.map((c) => [c.id, nodeState(c, status)])),
    [dataset, status],
  )
  const selectedCourse = view.selected ? dataset.byId.get(view.selected) : undefined
  const ctx: ViewCtx = useMemo(
    () => ({
      highlight: selectedCourse ? highlightSets(graph, selectedCourse.id) : null,
      filter: visible, states, choices: dataset.choices,
    }),
    [graph, selectedCourse, visible, states, dataset],
  )

  const panel = selectedCourse && (
    <DetailPanel course={selectedCourse} choiceWith={choicePartners(dataset.choices, selectedCourse.id)}
      status={status} onStatus={setStatus} onClose={() => setSelected(null)} />
  )

  return (
    <div className="app">
      <header className="app-header">
        <h1>OwlPath</h1>
        <MajorPicker programs={programs.map((p) => p.program)} value={dataset.program.id} onChange={changeMajor} />
        <span className="subtitle">{dataset.program.name} · {dataset.catalogYear} catalog</span>
        <Filters options={dataset.program.filters} courses={dataset.courses} filter={view.filter}
          onFilter={setFilter} onSelect={selectFromSearch} />
        <ResetButton disabled={Object.keys(status).length === 0} onReset={resetStatus} />
      </header>
      <main className="app-main">
        {small ? (
          panel ?? <CourseList courses={dataset.courses} states={states} visible={visible} onSelect={setSelected} />
        ) : (
          <>
            <GraphView key={dataset.program.id} graph={graph} positions={positions} ctx={ctx} focus={view.focus}
              onSelect={setSelected} />
            {panel}
          </>
        )}
      </main>
      <Footer />
    </div>
  )
}
