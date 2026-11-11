import { expect, test } from 'vitest'
import sampleJson from './sample.json'
import { normalize } from './normalize'
import type { Course, Dataset } from './types'

const sample = sampleJson as Dataset

function ds(over: Partial<Course>): Dataset {
  return { ...sample, courses: [{ ...sample.courses[0], ...over }] }
}

test('string leaf becomes course with grade C', () => {
  expect(normalize(ds({ prereqs: 'MATH 1113' })).courses[0].prereqs).toEqual({ kind: 'course', id: 'MATH 1113', minGrade: 'C' })
})

test('object leaves keep grade; external keeps kind', () => {
  const p = normalize(ds({ prereqs: { or: [{ course: 'CSE 1322', minGrade: 'B' }, { external: 'MTRE 2610' }] } })).courses[0].prereqs
  expect(p).toEqual({ kind: 'or', children: [{ kind: 'course', id: 'CSE 1322', minGrade: 'B' }, { kind: 'external', id: 'MTRE 2610', minGrade: 'C' }] })
})

test('null stays null and byId indexes every course', () => {
  const n = normalize(sample)
  expect(n.byId.get('CSE 1321')!.prereqs).toBeNull()
  expect(n.byId.size).toBe(10)
  expect(n.byId.get('CS 3305')).toBeDefined()
})


test('program and choices are carried through', () => {
  const n = normalize(sample)
  expect(n.program.id).toBe('bs-cs')
  expect(n.choices).toEqual([])
})
