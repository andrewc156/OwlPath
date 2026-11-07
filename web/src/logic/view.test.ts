import { expect, test } from 'vitest'
import type { Group } from '../data/types'
import { nodeState, type NodeState } from './eligibility'
import { buildGraph } from './graph'
import { concentrationSet, highlightSets } from './highlight'
import { layoutGraph } from './layout'
import { sample } from './testSample'
import { toFlow } from './view'

const g = buildGraph(sample.courses)
const pos = layoutGraph(g)
const states: Record<string, NodeState> = Object.fromEntries(sample.courses.map((c) => [c.id, nodeState(c, {})]))

function flow(opts: { selected?: string; filter?: Group }) {
  return toFlow(g, pos, {
    highlight: opts.selected ? highlightSets(g, opts.selected) : null,
    filter: opts.filter ? concentrationSet(g, sample.courses, opts.filter) : null,
    states,
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

test('coreq edges are dashed and grade labels shown', () => {
  const f = flow({})
  const coreq = f.edges.find((e) => e.id.startsWith('coreq:'))!
  expect(coreq.style?.strokeDasharray).toBeDefined()
  const graded = f.edges.find((e) => e.source === 'CSE 1321' && e.target === 'CSE 1322')!
  expect(graded.label).toBe('B')
})

test('node carries its eligibility state', () => expect(node(flow({}), 'CSE 1321').data.state).toBe('eligible-now'))
