import { expect, test } from 'vitest'
import { buildGraph } from './graph'
import { COURSE_SIZE, JUNCTION_SIZE, layoutGraph, routeKey, smoothPath } from './layout'
import { sample } from './testSample'

const g = buildGraph(sample.courses)
const { positions: pos, routes } = layoutGraph(g)

test('every node gets a position', () => expect([...pos.keys()].sort()).toEqual(g.nodes.map((n) => n.id).sort()))
test('prereq flows left to right', () => expect(pos.get('CSE 1321')!.x).toBeLessThan(pos.get('CS 3305')!.x))
test('mutual coreqs do not break layout', () => expect(() => layoutGraph(g)).not.toThrow())
test('isolated course is positioned', () => expect(pos.get('CSE 4983')).toBeDefined())

test('rankLike puts a course in the same column as its partner', () => {
  // CSE 4983 has no in-graph prereqs, so on its own it sits in the first column.
  const moved = layoutGraph(g, new Map([['CSE 4983', 'CS 3305']])).positions
  expect(moved.get('CSE 4983')!.x).toBe(moved.get('CS 3305')!.x)
})

test('every prereq edge has a route', () => {
  for (const e of g.edges.filter((e) => e.kind === 'prereq')) expect(routes.get(routeKey(e.source, e.target))).toBeDefined()
})

test('smoothPath passes through every point and leaves each one level', () => {
  expect(smoothPath([{ x: 0, y: 0 }, { x: 40, y: 0 }, { x: 80, y: 30 }])).toBe('M0,0L40,0C60,0 60,30 80,30')
  expect(smoothPath([{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 10, y: 0 }])).toBe('M0,0L10,0')
  expect(smoothPath([])).toBe('')
})

test('routes change height only between columns', () => {
  const half = new Map<number, number>()
  for (const [id, p] of pos) {
    const h = (id.startsWith('j:') ? JUNCTION_SIZE : COURSE_SIZE).width / 2
    half.set(p.x + h, Math.max(half.get(p.x + h) ?? 0, h))
  }
  const inColumn = (x: number) => [...half].some(([c, h]) => Math.abs(x - c) < h - 0.5)
  for (const e of g.edges.filter((e) => e.kind === 'prereq')) {
    const pts = routes.get(routeKey(e.source, e.target))!
    for (let i = 1; i < pts.length; i++) {
      if (pts[i].y !== pts[i - 1].y) expect(inColumn((pts[i].x + pts[i - 1].x) / 2)).toBe(false)
    }
  }
})
