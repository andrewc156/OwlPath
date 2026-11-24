import { expect, test } from 'vitest'
import { indexOrSample, loadIndex, loadMajor, type MajorEntry } from './dataset'

const entry = (id: string): MajorEntry => ({ id, name: id, level: 'undergraduate', checked: true })

test('falls back to the sample when there is no index', () => {
  expect(indexOrSample([]).map((m) => m.id)).toEqual(['bs-cs'])
})

test('a production build never falls back to the sample', () => {
  expect(() => indexOrSample([], true)).toThrow(/no reviewed dataset/)
  expect(indexOrSample([entry('bs-cs')], true)).toHaveLength(1)
})

test('loadIndex lists the shipped majors with their flags', () => {
  const ids = loadIndex().map((m) => m.id)
  expect(ids).toContain('bs-cs')
  expect(loadIndex().every((m) => typeof m.checked === 'boolean')).toBe(true)
})

test('loadMajor loads one major and rejects an unknown id', async () => {
  expect((await loadMajor('bs-cs')).program.id).toBe('bs-cs')
  await expect(loadMajor('nope')).rejects.toThrow()
})
