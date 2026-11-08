// Final review #2: the deploy guard must reject structurally broken or dangling data.
import { expect, test } from 'vitest'
import sample from './sample.json'
// Plain JS so the Node build guard can use it without a TS step.
import { validateDataset } from '../../scripts/validate-dataset.mjs'

const clone = () => JSON.parse(JSON.stringify(sample))

test('sample structure is valid', () => expect(validateDataset(clone())).toEqual([]))

test('courses must be a non-empty array', () => {
  expect(validateDataset({ ...clone(), courses: [] }).join()).toContain('courses')
  expect(validateDataset({}).join()).toContain('courses')
})

test('duplicate ids are rejected', () => {
  const d = clone(); d.courses.push({ ...d.courses[0] })
  expect(validateDataset(d).join()).toContain('duplicate id CSE 1321')
})

test('unknown course references are rejected, including inside objects', () => {
  const d = clone()
  d.courses.find((c: { id: string }) => c.id === 'CS 3642').prereqs = { and: ['CS 3305', 'CSE 1322 '] }
  d.courses.find((c: { id: string }) => c.id === 'MATH 2345').coreqs = { course: 'MATH 9999', minGrade: 'B' }
  const errs = validateDataset(d).join('\n')
  expect(errs).toContain('CS 3642: unknown course "CSE 1322 "')
  expect(errs).toContain('MATH 2345: unknown course "MATH 9999"')
})

test('external references need not exist', () => expect(validateDataset(clone()).join()).not.toContain('MTRE 2610'))

test('invalid minGrade is rejected', () => {
  const d = clone()
  d.courses.find((c: { id: string }) => c.id === 'CS 3642').prereqs = { course: 'CS 3305', minGrade: 'E' }
  expect(validateDataset(d).join()).toContain('CS 3642: invalid minGrade "E"')
})
