// Test helper: the normalized sample dataset.
import sampleJson from '../data/sample.json'
import { normalize } from '../data/normalize'
import type { Dataset, NCourse } from '../data/types'

export const sample = normalize(sampleJson as Dataset)
export const c = (id: string): NCourse => {
  const course = sample.byId.get(id)
  if (!course) throw new Error(`no sample course ${id}`)
  return course
}
