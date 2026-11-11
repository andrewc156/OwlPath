// Per-major view data and the pure rules behind the header controls.
import type { FocusRequest } from '../components/GraphView'
import type { NDataset } from '../data/types'
import { buildGraph, type Graph } from './graph'
import { layoutGraph, type Positions } from './layout'

export type ProgramView = { graph: Graph; positions: Positions; validIds: Set<string> }

const cache = new Map<string, ProgramView>()

/** Graph and layout for one major, built the first time it's shown, then reused. */
export function programView(ds: NDataset): ProgramView {
  let view = cache.get(ds.program.id)
  if (!view) {
    const graph = buildGraph(ds.courses)
    view = { graph, positions: layoutGraph(graph), validIds: new Set(ds.courses.map((c) => c.id)) }
    cache.set(ds.program.id, view)
  }
  return view
}

/** Every major's course ids: status is shared, so none may be dropped on load. */
export function allCourseIds(programs: NDataset[]): Set<string> {
  return new Set(programs.flatMap((p) => p.courses.map((c) => c.id)))
}

export type MajorState = { major: string; selected: string | null; filter: number | null; focus: FocusRequest | null }

/** A course or filter from one major may not exist in another, so switching clears them. */
export function switchMajor(_state: MajorState, major: string): MajorState {
  return { major, selected: null, filter: null, focus: null }
}

export const RESET_TEXT = 'Reset all progress? This marks every course as not taken in both majors.'

export function askAndReset(confirm: (text: string) => boolean, onReset: () => void): void {
  if (confirm(RESET_TEXT)) onReset()
}
