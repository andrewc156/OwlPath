import sampleJson from './sample.json'
import { normalize } from './normalize'
import type { Dataset, NDataset } from './types'

/** `source` value of the hand-written sample; production builds refuse it. */
export const SAMPLE_SOURCE = 'SAMPLE'

const sample = sampleJson as Dataset

// One reviewed dataset per major, data/2026-2027/<program>/courses.json. The build guard
// (scripts/check-data.mjs) checks the same folders.
const real = import.meta.glob<Dataset>('../../../data/2026-2027/*/courses.json', { eager: true, import: 'default' })

/** bs-cs first, then by name; the sample only when no real dataset exists. */
export function pickPrograms(realData: Dataset[], sampleData: Dataset): Dataset[] {
  if (realData.length === 0) return [sampleData]
  return [...realData].sort((a, b) =>
    a.program.id === 'bs-cs' ? -1 : b.program.id === 'bs-cs' ? 1 : a.program.name.localeCompare(b.program.name))
}

export function loadPrograms(): NDataset[] {
  return pickPrograms(Object.values(real), sample).map(normalize)
}
