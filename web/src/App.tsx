import { useEffect, useMemo, useState } from 'react'
import { AutoBuiltNote } from './components/AutoBuiltNote'
import { CourseList } from './components/CourseList'
import { DetailPanel } from './components/DetailPanel'
import { Filters } from './components/Filters'
import { Footer } from './components/Footer'
import { GraphView } from './components/GraphView'
import { MajorPicker } from './components/MajorPicker'
import { ResetButton } from './components/ResetButton'
import { useIsSmallScreen } from './components/useIsSmallScreen'
import { loadIndex } from './data/dataset'
import type { NDataset } from './data/types'
import { choicePartners, hiddenCourses } from './logic/choices'
import { nodeState, type Status, type StatusMap } from './logic/eligibility'
import { filterSet, highlightSets } from './logic/highlight'
import { fetchMajor, type LoadState } from './logic/majorLoad'
import { programView, switchMajor, type MajorState } from './logic/programView'
import type { ViewCtx } from './logic/view'
import { majorUrl, reloadToMajor, resolveMajor, saveMajor } from './state/major'
import { useStatus } from './state/status'

// The first load carries only the list of majors; a major's data loads when it's picked, and each
// graph and layout is built the first time it's shown.
const majors = loadIndex()
const majorIds = majors.map((m) => m.id)

function browserStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export default function App() {
  const [status, setStatus, resetStatus] = useStatus()
  const [view, setView] = useState<MajorState>(() => ({
    major: resolveMajor(window.location.search, browserStorage(), majorIds),
    selected: null, filter: null, focus: null,
  }))
  const entry = majors.find((m) => m.id === view.major) ?? majors[0]
  // The result is tagged with the major it answers, so a stale or pending one reads as loading.
  const [result, setResult] = useState<{ key: string; state: LoadState } | null>(null)
  const load: LoadState = result?.key === entry.id ? result.state : { status: 'loading' }

  useEffect(() => {
    let current = true
    fetchMajor(entry.id).then((state) => { if (current) setResult({ key: entry.id, state }) })
    return () => { current = false }
  }, [entry.id])

  const changeMajor = (id: string) => {
    saveMajor(browserStorage(), id)
    window.history.replaceState(null, '', majorUrl(window.location.href, id))
    setView((v) => switchMajor(v, id))
  }
  const setSelected = (id: string | null) => setView((v) => ({ ...v, selected: id }))
  const setFilter = (i: number | null) => setView((v) => ({ ...v, filter: i }))
  const selectFromSearch = (id: string) =>
    setView((v) => ({ ...v, selected: id, focus: { id, seq: (v.focus?.seq ?? 0) + 1 } }))

  const dataset = load.status === 'ready' && load.data.program.id === entry.id ? load.data : null

  return (
    <div className="app">
      <header className="app-header">
        <h1>OwlPath</h1>
        <MajorPicker majors={majors} value={entry.id} onChange={changeMajor} />
        {dataset && (
          <>
            <span className="subtitle">{dataset.program.name} · {dataset.catalogYear} catalog</span>
            <Filters options={dataset.program.filters} courses={dataset.courses} filter={view.filter}
              onFilter={setFilter} onSelect={selectFromSearch} />
          </>
        )}
        <ResetButton disabled={Object.keys(status).length === 0} onReset={resetStatus} />
      </header>
      <AutoBuiltNote checked={entry.checked} />
      {dataset ? (
        <LoadedMajor dataset={dataset} view={view} status={status} setStatus={setStatus}
          setSelected={setSelected} selectFromSearch={selectFromSearch} />
      ) : (
        <main className="app-main load-state" role="status">
          {load.status === 'error' ? (
            <p>Couldn't load this major.{' '}
              <button type="button" onClick={() => reloadToMajor(entry.id, window, browserStorage())}>Retry</button></p>
          ) : <p>Loading {entry.name}…</p>}
        </main>
      )}
      <Footer />
    </div>
  )
}

type LoadedProps = {
  dataset: NDataset
  view: MajorState
  status: StatusMap
  setStatus: (id: string, s: Status) => void
  setSelected: (id: string | null) => void
  selectFromSearch: (id: string) => void
}

function LoadedMajor({ dataset, view, status, setStatus, setSelected, selectFromSearch }: LoadedProps) {
  const { graph, layout } = programView(dataset)
  const small = useIsSmallScreen()
  const titles = useMemo(() => Object.fromEntries(dataset.courses.map((c) => [c.id, c.title])), [dataset])

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
  const hidden = useMemo(
    () => hiddenCourses(dataset.lessCommon, dataset.choices, status, selectedCourse?.id ?? null),
    [dataset, status, selectedCourse],
  )
  const ctx: ViewCtx = useMemo(
    () => ({
      highlight: selectedCourse ? highlightSets(graph, selectedCourse.id) : null,
      filter: visible, states, choices: dataset.choices, hidden, titles,
    }),
    [graph, selectedCourse, visible, states, dataset, hidden, titles],
  )

  const panel = selectedCourse && (
    <DetailPanel course={selectedCourse} choiceWith={choicePartners(dataset.choices, selectedCourse.id)}
      lessCommon={dataset.lessCommon} onSelectCourse={selectFromSearch}
      status={status} onStatus={setStatus} onClose={() => setSelected(null)} />
  )

  return (
    <main className="app-main">
      {small ? (
        panel ?? <CourseList courses={dataset.courses.filter((c) => !hidden.has(c.id))} states={states} visible={visible}
          onSelect={setSelected} />
      ) : (
        <>
          <GraphView key={dataset.program.id} graph={graph} layout={layout} ctx={ctx} focus={view.focus}
            onSelect={setSelected} />
          {panel}
        </>
      )}
    </main>
  )
}
