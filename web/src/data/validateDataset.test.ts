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

test('program block is required', () => {
  const d = clone(); delete d.program
  expect(validateDataset(d).join()).toContain('program')
})

test('choices must name courses in the dataset', () => {
  const d = clone(); d.choices = [['CSE 1321', 'ZZZ 9999']]
  expect(validateDataset(d)).toContain('choices: unknown course ZZZ 9999')
})

test('lessCommon must name a course with a shown either/or partner', () => {
  const d = clone(); d.choices = [['CSE 1321', 'CSE 1322']]; d.lessCommon = ['CSE 1322']
  expect(validateDataset(d)).toEqual([])
  d.lessCommon = ['CSE 1321', 'CSE 1322']
  expect(validateDataset(d)).toContain('lessCommon: CSE 1322 needs an either/or requirement with a shown option')
  d.lessCommon = ['ZZZ 9999']
  expect(validateDataset(d)).toContain('lessCommon: unknown course ZZZ 9999')
})

test('every course group must match the group pattern', () => {
  const d = clone(); d.courses[0].groups = ['Conc AI']
  expect(validateDataset(d).join()).toContain('invalid group "Conc AI"')
  const ok = clone(); ok.courses[0].groups = ['conc-cyber-and-network-security']
  expect(validateDataset(ok).join()).not.toContain('invalid group')
})

test('a filter group no course uses is rejected', () => {
  const d = clone(); d.program.filters[0].groups = ['conc-nobody-has-this']
  expect(validateDataset(d).join()).toContain('filter group "conc-nobody-has-this" is used by no course')
})

test('catalogUrl must be a KSU catalog link, since it feeds the "View in catalog" href', () => {
  for (const url of ['javascript:alert(1)', 'https://evil.example/', 'http://catalog.kennesaw.edu/x',
    'https://catalog.kennesaw.edu.evil.example/', undefined]) {
    const d = clone(); d.courses[0].catalogUrl = url
    expect(validateDataset(d).join('\n'), String(url)).toContain('CSE 1321: catalogUrl must start with https://catalog.kennesaw.edu/')
  }
})
