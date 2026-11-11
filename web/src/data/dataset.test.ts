import { expect, test } from 'vitest'
import sampleJson from './sample.json'
import { pickPrograms } from './dataset'
import type { Dataset } from './types'

const sample = sampleJson as Dataset
const prog = (id: string, name: string): Dataset => ({ ...sample, source: 'catalog', program: { ...sample.program, id, name } })

test('bs-cs comes first, then by name', () => {
  const out = pickPrograms([prog('zz', 'Zoology'), prog('bs-dsa', 'BS Data Science and Analytics'), prog('bs-cs', 'BS Computer Science')], sample)
  expect(out.map((d) => d.program.id)).toEqual(['bs-cs', 'bs-dsa', 'zz'])
})

test('falls back to the sample when there is no real data', () => {
  expect(pickPrograms([], sample).map((d) => d.source)).toEqual(['SAMPLE'])
})
