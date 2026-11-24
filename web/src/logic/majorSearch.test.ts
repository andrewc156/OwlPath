import { expect, test } from 'vitest'
import type { MajorEntry } from '../data/dataset'
import { collegeKey, groupMajors, levelKey, pickerRows } from './majorSearch'

const CCSE = 'College of Computing and Software Engineering'
const COLES = 'Coles College of Business'
const e = (id: string, name: string, level: MajorEntry['level'], college: string, checked = false): MajorEntry =>
  ({ id, name, level, checked, college })
const entries = [
  e('ms-dsa', 'MS Data Science and Analytics', 'graduate', CCSE, true),
  e('bs-cs', 'BS Computer Science', 'undergraduate', CCSE, true),
  e('bsswe', 'BSSWE Software Engineering', 'undergraduate', CCSE),
  e('bba-accounting', 'BBA Accounting', 'undergraduate', COLES),
]

test('groups by level, then college A–Z, then major A–Z', () => {
  const g = groupMajors(entries, '')
  expect(g.map((x) => [x.label, x.colleges.map((c) => [c.name, c.items.map((i) => i.id)])])).toEqual([
    ['Undergraduate', [[COLES, ['bba-accounting']], [CCSE, ['bs-cs', 'bsswe']]]], // "Coles" sorts before "College"
    ['Graduate', [[CCSE, ['ms-dsa']]]],
  ])
})

test('matches name, id or college case-insensitively and drops empty groups', () => {
  expect(groupMajors(entries, 'BS-CS').map((x) => x.label)).toEqual(['Undergraduate'])
  expect(groupMajors(entries, 'accounting')[0].colleges.map((c) => c.name)).toEqual([COLES])
  expect(groupMajors(entries, 'coles')[0].colleges[0].items.map((i) => i.id)).toEqual(['bba-accounting'])
  expect(groupMajors(entries, 'zzz')).toEqual([])
})

test('levels and colleges open only when expanded, unless searching', () => {
  const groups = groupMajors(entries, '')
  const kinds = (rows: { kind: string }[]) => rows.map((r) => r.kind)
  expect(kinds(pickerRows(groups, new Set(), false))).toEqual(['level', 'level'])
  const ug = levelKey('undergraduate')
  expect(pickerRows(groups, new Set([ug]), false).map((r) => r.key))
    .toEqual([ug, collegeKey('undergraduate', COLES), collegeKey('undergraduate', CCSE), levelKey('graduate')])
  const both = pickerRows(groups, new Set([ug, collegeKey('undergraduate', CCSE)]), false)
  expect(both.map((r) => r.key)).toEqual([ug, collegeKey('undergraduate', COLES), collegeKey('undergraduate', CCSE),
    'bs-cs', 'bsswe', levelKey('graduate')])
  // a college key alone shows nothing while its level is closed
  expect(kinds(pickerRows(groups, new Set([collegeKey('graduate', CCSE)]), false))).toEqual(['level', 'level'])
  const searching = pickerRows(groupMajors(entries, 'b'), new Set(), true)
  expect(searching.filter((r) => r.kind === 'major').length).toBe(3)
  expect(searching[0]).toMatchObject({ kind: 'level', name: 'Undergraduate', count: 3, open: true })
})
