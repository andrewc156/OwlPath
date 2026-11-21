import { expect, test } from 'vitest'
import { buildGraph } from './graph'
import { layoutGraph } from './layout'
import { sample } from './testSample'

const g = buildGraph(sample.courses)
const pos = layoutGraph(g)

test('every node gets a position', () => expect([...pos.keys()].sort()).toEqual(g.nodes.map((n) => n.id).sort()))
test('prereq flows left to right', () => expect(pos.get('CSE 1321')!.x).toBeLessThan(pos.get('CS 3305')!.x))
test('mutual coreqs do not break layout', () => expect(() => layoutGraph(g)).not.toThrow())
test('isolated course is positioned', () => expect(pos.get('CSE 4983')).toBeDefined())

test('rankLike puts a course in the same column as its partner', () => {
  // CSE 4983 has no in-graph prereqs, so on its own it sits in the first column.
  const moved = layoutGraph(g, new Map([['CSE 4983', 'CS 3305']]))
  expect(moved.get('CSE 4983')!.x).toBe(moved.get('CS 3305')!.x)
})
