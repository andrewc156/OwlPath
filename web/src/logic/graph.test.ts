import { expect, test } from 'vitest'
import { buildGraph, type GNode } from './graph'
import { sample } from './testSample'

const g = buildGraph(sample.courses)
type Junction = Extract<GNode, { kind: 'junction' }>
type CourseN = Extract<GNode, { kind: 'course' }>

const prereqEdgesInto = (id: string) =>
  g.edges.filter((e) => e.kind === 'prereq' && e.target === id).map((e) => ({ source: e.source, minGrade: e.minGrade }))
const junctionsFor = (id: string) => g.nodes.filter((n): n is Junction => n.kind === 'junction' && n.target === id)
const junction = (id: string) => g.nodes.find((n): n is Junction => n.kind === 'junction' && n.id === id)!
const courseNode = (id: string) => g.nodes.find((n): n is CourseN => n.kind === 'course' && n.id === id)!
const coreqSourcesInto = (id: string) => g.edges.filter((e) => e.kind === 'coreq' && e.target === id).map((e) => e.source)
const edge = (source: string, target: string) => g.edges.find((e) => e.source === source && e.target === target)!

test('AND prereqs are direct edges with grade labels', () => {
  expect(prereqEdgesInto('CSE 1322')).toEqual([{ source: 'CSE 1321', minGrade: 'B' }, { source: 'CSE 1321L', minGrade: 'B' }])
})

test('CS 3305 has two OR junctions and a nested AND junction', () => {
  const ids = junctionsFor('CS 3305').map((j) => `${j.id}:${j.op}`)
  expect(ids).toEqual(['j:CS 3305:0:or', 'j:CS 3305:1:or', 'j:CS 3305:1.0:and'])
})

test('externals are listed on the junction, never as nodes', () => {
  expect(junction('j:CS 3305:1').externals.map((e) => e.id)).toEqual(['MTRE 2610', 'CPE 3000'])
  expect(g.nodes.find((n) => n.id === 'MTRE 2610')).toBeUndefined()
})

test('all-external OR creates no junction and counts on the course', () => {
  expect(junctionsFor('CSE 4983')).toEqual([])
  expect(courseNode('CSE 4983').externalOnlyGroups).toBe(1)
})

test('coreq edges are flat and dashed-kind', () => {
  expect(coreqSourcesInto('CSE 1322').sort()).toEqual(['CSE 1322L', 'MATH 1113', 'MATH 1190'])
})

test('grade C edges carry no minGrade', () => expect(edge('MATH 1113', 'MATH 1190').minGrade).toBeUndefined())

// Final review #1: an all-external group nested under an OR is an alternative, not a requirement.
import { normalize } from '../data/normalize'
import type { Course, Logic } from '../data/types'

function tiny(prereqs: Logic) {
  const base = { title: 't', credits: '3', description: '', catalogYear: '2026-2027', catalogUrl: '', groups: ['major-required'], coreqs: null, notes: [] } as const
  const courses = [
    { ...base, id: 'CS 1000', prereqs: null },
    { ...base, id: 'CS 1100', prereqs: null },
    { ...base, id: 'CS 2000', prereqs },
  ] as unknown as Course[]
  return buildGraph(normalize({ catalogYear: '2026-2027', source: 'test', courses }).courses)
}
const target = (gr: ReturnType<typeof tiny>) => gr.nodes.find((n): n is CourseN => n.kind === 'course' && n.id === 'CS 2000')!
const junctionIn = (gr: ReturnType<typeof tiny>, id: string) => gr.nodes.find((n): n is Junction => n.kind === 'junction' && n.id === id)!

test('all-external AND inside an OR is listed on the OR junction, not flagged on the course', () => {
  const gr = tiny({ or: [{ and: [{ external: 'MTRE 2610' }, { external: 'MTRE 2610L' }] }, 'CS 1000'] })
  expect(target(gr).externalOnlyGroups).toBe(0)
  expect(junctionIn(gr, 'j:CS 2000:r').externals.map((e) => e.id)).toEqual(['MTRE 2610', 'MTRE 2610L'])
})

test('all-external OR inside an AND junction is listed on that junction', () => {
  const gr = tiny({ or: [{ and: ['CS 1000', { or: [{ external: 'E 1000' }, { external: 'E 2000' }] }] }, 'CS 1100'] })
  expect(target(gr).externalOnlyGroups).toBe(0)
  expect(junctionIn(gr, 'j:CS 2000:0').externals.map((e) => e.id)).toEqual(['E 1000', 'E 2000'])
})
