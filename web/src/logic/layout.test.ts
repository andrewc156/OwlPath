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
