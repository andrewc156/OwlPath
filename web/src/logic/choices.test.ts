import { expect, test } from 'vitest'
import { choicePartners, hiddenCourses, shownPartners } from './choices'

test('choicePartners lists the other options', () => {
  expect(choicePartners([['CSE 2300', 'MATH 2345']], 'MATH 2345')).toEqual(['CSE 2300'])
  expect(choicePartners([['A', 'B'], ['A', 'C']], 'A')).toEqual(['B', 'C'])
  expect(choicePartners([['A', 'B', 'C'], ['C', 'B']], 'C')).toEqual(['A', 'B'])
  expect(choicePartners([], 'A')).toEqual([])
})

const choices = [['STAT 3120', 'STAT 3125'], ['DATA 4030', 'DATA 4140']]
const less = new Set(['STAT 3125', 'DATA 4140'])
const hidden = (status: Record<string, 'complete' | 'in-progress' | 'not-taken'>, selected: string | null) =>
  [...hiddenCourses(less, choices, status, selected)].sort()

test('less common options are hidden by default', () => expect(hidden({}, null)).toEqual(['DATA 4140', 'STAT 3125']))
test('selecting the usual option reveals the other', () => expect(hidden({}, 'STAT 3120')).toEqual(['DATA 4140']))
test('selecting a hidden option (from search) shows it', () => expect(hidden({}, 'STAT 3125')).toEqual(['DATA 4140']))
test('a marked hidden option stays visible', () => {
  expect(hidden({ 'STAT 3125': 'complete', 'DATA 4140': 'in-progress' }, null)).toEqual([])
  expect(hidden({ 'STAT 3125': 'not-taken' }, null)).toEqual(['DATA 4140', 'STAT 3125'])
})
test('shownPartners pairs each hidden option with a shown one', () =>
  expect(shownPartners(less, choices)).toEqual(new Map([['STAT 3125', 'STAT 3120'], ['DATA 4140', 'DATA 4030']])))
