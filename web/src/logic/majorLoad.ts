import { loadMajor } from '../data/dataset'
import type { NDataset } from '../data/types'

export type LoadState = { status: 'loading' } | { status: 'ready'; data: NDataset } | { status: 'error' }

/** Never rejects: a failed chunk fetch becomes an error state the app can retry. */
export async function fetchMajor(id: string, load: (id: string) => Promise<NDataset> = loadMajor): Promise<LoadState> {
  try {
    return { status: 'ready', data: await load(id) }
  } catch {
    return { status: 'error' }
  }
}

/** bs-cs when it ships, else the first major. */
export function defaultMajor(ids: string[]): string {
  return ids.includes('bs-cs') ? 'bs-cs' : ids[0]
}
