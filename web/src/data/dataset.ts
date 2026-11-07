import sampleJson from './sample.json'
import { normalize } from './normalize'
import type { Dataset, NDataset } from './types'

/** `source` value of the hand-written sample; production builds refuse it. */
export const SAMPLE_SOURCE = 'SAMPLE'

const sample = sampleJson as Dataset

// Resolves to {} until the reviewed dataset is committed at the repo root.
const real = import.meta.glob<Dataset>('../../../data/2026-2027/courses.json', { eager: true, import: 'default' })

export function pickDataset(realData: Dataset | undefined, sampleData: Dataset): Dataset {
  return realData ?? sampleData
}

export function loadDataset(): NDataset {
  return normalize(pickDataset(Object.values(real)[0], sample))
}
