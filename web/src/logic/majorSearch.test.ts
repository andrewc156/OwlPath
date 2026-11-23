import { expect, test } from 'vitest'
import type { MajorEntry } from '../data/dataset'
import { groupMajors } from './majorSearch'

const e = (id: string, name: string, level: MajorEntry['level'], checked: boolean): MajorEntry => ({ id, name, level, checked })
const entries = [
  e('ms-dsa', 'MS Data Science and Analytics', 'graduate', true),
  e('bs-cs', 'BS Computer Science', 'undergraduate', true),
  e('bba-accounting', 'BBA Accounting', 'undergraduate', false),
]

test('groups by level, A–Z, and filters by query', () => {
  const g = groupMajors(entries, '')
  expect(g.map((x) => [x.label, x.items.map((i) => i.id)])).toEqual([
    ['Undergraduate', ['bba-accounting', 'bs-cs']],
    ['Graduate', ['ms-dsa']],
  ])
  expect(groupMajors(entries, 'data')[0].items.map((i) => i.id)).toEqual(['ms-dsa'])
})

test('matches name or id case-insensitively and drops empty groups', () => {
  expect(groupMajors(entries, 'BS-CS').map((x) => x.label)).toEqual(['Undergraduate'])
  expect(groupMajors(entries, 'accounting')[0].items.map((i) => i.id)).toEqual(['bba-accounting'])
  expect(groupMajors(entries, 'zzz')).toEqual([])
})
