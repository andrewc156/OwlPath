import { normalize } from './normalize'
import type { Dataset, NDataset } from './types'

/** `source` value of the hand-written sample; production builds refuse it. */
export const SAMPLE_SOURCE = 'SAMPLE'

export type MajorEntry = { id: string; name: string; level: 'undergraduate' | 'graduate'; checked: boolean }

// The first load carries only this list. The build guard (scripts/check-data.mjs) checks it against the
// shipped courses.json files.
const indexFiles = import.meta.glob<MajorEntry[]>('../../../data/2026-2027/majors.json', { eager: true, import: 'default' })

// One chunk per major, fetched when it's picked.
const majorFiles = import.meta.glob<Dataset>('../../../data/2026-2027/*/courses.json', { import: 'default' })

// Local previews only (npm run dev, build:sample). The sample is loaded lazily and the branch folds away in a
// production build, so it never reaches the shipped bundle.
const SAMPLE_ENTRY: MajorEntry = { id: 'bs-cs', name: 'BS Computer Science (sample)', level: 'undergraduate', checked: true }

/**
 * The sample is only for local previews: a production build with no index throws, so a glob that
 * stops matching can't quietly ship the sample.
 */
export function indexOrSample(index: MajorEntry[], production = false): MajorEntry[] {
  if (index.length > 0) return index
  if (production) throw new Error('OwlPath: no reviewed dataset was bundled; refusing to show sample data')
  return [SAMPLE_ENTRY]
}

export function loadIndex(): MajorEntry[] {
  return indexOrSample(Object.values(indexFiles)[0] ?? [], import.meta.env.PROD && !import.meta.env.VITE_ALLOW_SAMPLE)
}

/** Loads one major's data. Rejects for an unknown id. */
export async function loadMajor(id: string): Promise<NDataset> {
  const load = Object.entries(majorFiles).find(([path]) => path.endsWith(`/${id}/courses.json`))?.[1]
  if (load) return normalize(await load())
  if (!(import.meta.env.PROD && !import.meta.env.VITE_ALLOW_SAMPLE) && Object.keys(majorFiles).length === 0 && id === SAMPLE_ENTRY.id) {
    return normalize((await import('./sample.json')).default as Dataset)
  }
  throw new Error(`OwlPath: unknown major ${id}`)
}
