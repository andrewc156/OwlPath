import { expect, test } from 'vitest'
import type { Group } from '../data/types'
import { nodeState, type NodeState } from './eligibility'
import { buildGraph } from './graph'
import { filterSet, highlightSets } from './highlight'
import { layoutGraph } from './layout'
import { sample } from './testSample'
import { toFlow } from './view'

const g = buildGraph(sample.courses)
const pos = layoutGraph(g)
const states: Record<string, NodeState> = Object.fromEntries(sample.courses.map((c) => [c.id, nodeState(c, {})]))

function flow(opts: { selected?: string; filter?: Group; choices?: string[][]; hidden?: string[] }) {
  return toFlow(g, pos, {
    highlight: opts.selected ? highlightSets(g, opts.selected) : null,
    filter: opts.filter ? filterSet(g, sample.courses, [opts.filter]) : null,
    states,
    choices: opts.choices ?? [],
    hidden: new Set(opts.hidden ?? []),
  })
}
const node = (f: ReturnType<typeof flow>, id: string) => f.nodes.find((n) => n.id === id)!
const cls = (f: ReturnType<typeof flow>, id: string) => node(f, id).className ?? ''

test('selection dims unrelated nodes', () => expect(cls(flow({ selected: 'CS 3305' }), 'CSE 4983')).toContain('dimmed'))

test('ancestors and descendants are marked', () => {
  const f = flow({ selected: 'CSE 1322' })
  expect(cls(f, 'CSE 1321')).toContain('ancestor')
  expect(cls(f, 'CS 3305')).toContain('descendant')
})

test('selection beats filter', () =>
  expect(cls(flow({ selected: 'CS 3305', filter: 'conc-ai' }), 'CSE 1321')).not.toContain('dimmed'))

const firstCoreq = g.edges.find((e) => e.kind === 'coreq')!

test('coreq edges show only while one of their courses is selected', () => {
  expect(flow({}).edges.some((e) => e.id.startsWith('coreq:'))).toBe(false)
  expect(flow({ selected: firstCoreq.target }).edges.some((e) => e.id === firstCoreq.id)).toBe(true)
  expect(flow({ selected: firstCoreq.source }).edges.some((e) => e.id === firstCoreq.id)).toBe(true)
})

test('prereq edges follow layout routes', () => {
  const e = flow({}).edges.find((e) => e.id.startsWith('prereq:'))!
  expect(e.type).toBe('routed')
  expect((e.data as { points: unknown[] }).points.length).toBeGreaterThanOrEqual(2)
})

test('coreq edges are dashed and grade labels shown', () => {
  const coreq = flow({ selected: firstCoreq.target }).edges.find((e) => e.id === firstCoreq.id)!
  expect(coreq.style?.strokeDasharray).toBeDefined()
  const f = flow({})
  const graded = f.edges.find((e) => e.source === 'CSE 1321' && e.target === 'CSE 1322')!
  expect(graded.label).toBe('B')
})

test('node carries its eligibility state', () => expect(node(flow({}), 'CSE 1321').data.state).toBe('eligible-now'))

test('course nodes carry their either/or partners', () => {
  const f = flow({ choices: [['CSE 1321', 'MATH 2345']] })
  expect(node(f, 'CSE 1321').data.choiceWith).toEqual(['MATH 2345'])
  expect(node(f, 'MATH 2345').data.choiceWith).toEqual(['CSE 1321'])
  expect(node(f, 'CS 3305').data.choiceWith).toEqual([])
})

test('hidden courses and their edges are left out', () => {
  const f = flow({ hidden: ['CSE 1321'] })
  expect(f.nodes.find((n) => n.id === 'CSE 1321')).toBeUndefined()
  expect(f.edges.some((e) => e.source === 'CSE 1321' || e.target === 'CSE 1321')).toBe(false)
})

test('the other option of a selected course is marked, not dimmed', () => {
  const f = flow({ selected: 'CS 3305', choices: [['CS 3305', 'CSE 4983']] })
  expect(cls(f, 'CSE 4983')).toBe('alternative')
})
