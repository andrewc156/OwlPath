// Per-major view data and the pure rules behind the header controls.
import type { FocusRequest } from '../components/GraphView'
import type { NDataset } from '../data/types'
import { shownPartners } from './choices'
import { buildGraph, type Graph } from './graph'
import { layoutGraph, type Layout } from './layout'

export type ProgramView = { graph: Graph; layout: Layout }

const cache = new Map<string, ProgramView>()

/** Graph and layout for one major, built the first time it's shown, then reused. */
export function programView(ds: NDataset): ProgramView {
  let view = cache.get(ds.program.id)
  if (!view) {
    const graph = buildGraph(ds.courses)
    view = { graph, layout: layoutGraph(graph, shownPartners(ds.lessCommon, ds.choices)) }
    cache.set(ds.program.id, view)
  }
  return view
}

export type MajorState = { major: string; selected: string | null; filter: number | null; focus: FocusRequest | null }

/** A course or filter from one major may not exist in another, so switching clears them. */
export function switchMajor(_state: MajorState, major: string): MajorState {
  return { major, selected: null, filter: null, focus: null }
}

export const RESET_TEXT = 'Reset all progress? This marks every course as not taken in every major.'

export function askAndReset(confirm: (text: string) => boolean, onReset: () => void): void {
  if (confirm(RESET_TEXT)) onReset()
}
