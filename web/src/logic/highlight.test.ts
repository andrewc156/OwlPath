import { expect, test } from 'vitest'
import { buildGraph } from './graph'
import { concentrationSet, highlightSets } from './highlight'
import { sample } from './testSample'

const g = buildGraph(sample.courses)
const h = (id: string) => highlightSets(g, id)
const courseIds = (s: Set<string>) => [...s].filter((id) => !id.startsWith('j:')).sort()

test('ancestors of CS 3305 are its whole chain', () =>
  expect(courseIds(h('CS 3305').ancestors)).toEqual(['CSE 1321', 'CSE 1321L', 'CSE 1322', 'CSE 1322L', 'MATH 1113', 'MATH 1190', 'MATH 2345']))

test('descendants of CSE 1321 go through junctions', () =>
  expect(courseIds(h('CSE 1321').descendants)).toEqual(['CS 3305', 'CS 3642', 'CSE 1322', 'CSE 1322L']))

test('coreqs are takeWith only, not traversed', () => {
  expect(courseIds(h('CSE 1321').takeWith)).toEqual(['CSE 1321L'])
  expect(h('CSE 1321').ancestors.size).toBe(0)
})

test('concentration set includes prereq chain', () =>
  expect(courseIds(concentrationSet(g, sample.courses, 'conc-ai'))).toContain('MATH 1113'))
