import { expect, test } from 'vitest'
import { nodeState } from './eligibility'
import { c } from './testSample'

test('no prereqs -> eligible-now', () => expect(nodeState(c('CSE 1321'), {})).toBe('eligible-now'))
test('own status wins', () => expect(nodeState(c('CS 3305'), { 'CS 3305': 'complete' })).toBe('complete'))
test('AND needs all', () => expect(nodeState(c('CSE 1322'), { 'CSE 1321': 'complete' })).toBe('locked'))
test('in-progress prereqs -> eligible-next-term', () =>
  expect(nodeState(c('CSE 1322'), { 'CSE 1321': 'in-progress', 'CSE 1321L': 'complete' })).toBe('eligible-next-term'))
test('OR satisfied by one in-graph branch', () =>
  expect(nodeState(c('CS 3305'), { 'MATH 2345': 'complete', 'CSE 1322': 'complete', 'CSE 1322L': 'complete' })).toBe('eligible-now'))
test('external leaf never satisfies', () => expect(nodeState(c('CSE 4983'), {})).toBe('locked'))
test('coreqs do not block', () => expect(nodeState(c('CSE 1321'), {})).toBe('eligible-now'))
test('notes do not block', () => expect(nodeState(c('MATH 1190'), { 'MATH 1113': 'complete' })).toBe('eligible-now'))
