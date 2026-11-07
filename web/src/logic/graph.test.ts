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
