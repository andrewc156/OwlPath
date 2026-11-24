// The deploy guard must refuse unless every program folder has a reviewed, valid dataset.
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { expect, test } from 'vitest'
import sample from '../src/data/sample.json'
import { checkPrograms } from './check-data.mjs'

type Data = { program: { id: string }; choices: string[][] }
const real = (id: string) => ({ ...sample, source: 'KSU catalog', program: { ...sample.program, id } })
const CLEAN = '# Build report\n\n## Warnings needing review\n\nNone.\n'

type Opts = {
  programJson?: Record<string, object | null>
  checked?: string[] // ids whose program.json says "checked": true (courses.json gets the same flag unless overridden)
  coursesChecked?: Record<string, boolean>
  draftWarnings?: Record<string, string[]>
  report?: Record<string, string>
  majors?: object[] | null // null = no majors.json
}

/** Each folder gets a program.json matching its courses.json (or `programJson` when given). majors.json defaults to the shipped majors. */
function root(programs: Record<string, Data | null>, opts: Opts = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'owlpath-'))
  mkdirSync(join(dir, 'catalog'))
  const majors: object[] = []
  for (const [id, data] of Object.entries(programs)) {
    mkdirSync(join(dir, id))
    const checked = (opts.checked ?? []).includes(id)
    const pj = id in (opts.programJson ?? {}) ? opts.programJson![id]
      : { level: 'undergraduate', program: data?.program ?? real(id).program, choices: data?.choices ?? [], courses: {},
        ...(checked ? { checked: true } : {}), ...(opts.draftWarnings?.[id] ? { draftWarnings: opts.draftWarnings[id] } : {}) }
    if (pj) writeFileSync(join(dir, id, 'program.json'), JSON.stringify(pj))
    if (data) {
      const flag = opts.coursesChecked?.[id] ?? checked
      writeFileSync(join(dir, id, 'courses.json'), JSON.stringify({ ...data, checked: flag }))
      writeFileSync(join(dir, id, 'build-report.md'), opts.report?.[id] ?? CLEAN)
      if (pj) majors.push({ checked, id, level: 'undergraduate', name: (pj as { program: { name: string } }).program.name })
    }
  }
  if (opts.majors !== null) writeFileSync(join(dir, 'majors.json'), JSON.stringify(opts.majors ?? majors))
  return pathToFileURL(dir + '/')
}

const msgs = (r: { messages: string[] }) => r.messages.join('\n')

test('two valid programs pass', () => {
  expect(checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': real('bs-dsa') })).ok).toBe(true)
})

test('a checked major without courses.json refuses', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': null }, { checked: ['bs-dsa'] }))
  expect(r.ok).toBe(false)
  expect(r.messages.join('\n')).toMatch(/bs-dsa.*courses\.json/)
})

test('sample data is refused', () => {
  expect(checkPrograms(root({ 'bs-cs': { ...sample } })).ok).toBe(false)
})

test('no program folders is refused', () => {
  expect(checkPrograms(root({})).ok).toBe(false)
})

test('a courses.json without program.json is refused, since the app would bundle it unchecked', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs'), tmp: real('tmp') }, { programJson: { tmp: null } }))
  expect(r.ok).toBe(false)
  expect(r.messages.join('\n')).toMatch(/tmp.*program\.json/)
})

test('program id must match its folder', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': real('bs-cs') }))
  expect(r.ok).toBe(false)
  expect(r.messages.join('\n')).toContain('bs-dsa')
})

test('courses.json must be rebuilt after program.json changes', () => {
  const stale = { program: { ...real('bs-cs').program, name: 'Renamed' }, choices: [], courses: {} }
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { programJson: { 'bs-cs': stale } }))
  expect(r.ok).toBe(false)
  expect(r.messages.join('\n')).toMatch(/bs-cs.*rebuild/)
})

test('courses.json must be rebuilt after lessCommon changes', () => {
  const stale = { program: real('bs-cs').program, choices: [], lessCommon: ['CSE 1321'], courses: {} }
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { programJson: { 'bs-cs': stale } }))
  expect(r.ok).toBe(false)
  expect(r.messages.join('\n')).toMatch(/bs-cs.*rebuild/)
})

test('the app bundles the same data folder the guard checks', () => {
  const year = (file: string) => readFileSync(new URL(file, import.meta.url), 'utf8').match(/data\/(\d{4}-\d{4})\//g)
  const app = year('../src/data/dataset.ts')
  const guard = year('./check-data.mjs')
  expect(app).not.toBeNull()
  expect(new Set(app)).toEqual(new Set(guard))
})

test('a clean auto-built major ships', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': real('bs-dsa') }, { checked: ['bs-cs'] }))
  expect(r.ok, msgs(r)).toBe(true)
})

test('a held major with courses.json refuses', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { draftWarnings: { 'bs-cs': ['unparsed prerequisite'] } }))
  expect(r.ok).toBe(false)
  expect(msgs(r)).toMatch(/bs-cs.*draftWarnings/)
})

test('an auto-built major whose report has warnings refuses', () => {
  const bad = '## Warnings needing review\n\n- CS 1 has an odd prerequisite\n'
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { report: { 'bs-cs': bad } }))
  expect(r.ok).toBe(false)
  expect(msgs(r)).toMatch(/bs-cs.*build-report/)
})

test('an auto-built major whose report has validation errors refuses', () => {
  const bad = `${CLEAN}\n## Validation errors\n\n- boom\n`
  expect(checkPrograms(root({ 'bs-cs': real('bs-cs') }, { report: { 'bs-cs': bad } })).ok).toBe(false)
})

test('checked flag mismatch refuses', () => {
  const a = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { checked: ['bs-cs'], coursesChecked: { 'bs-cs': false } }))
  expect(a.ok).toBe(false)
  expect(msgs(a)).toMatch(/bs-cs.*checked/)
  const b = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { coursesChecked: { 'bs-cs': true } }))
  expect(b.ok).toBe(false)
  expect(msgs(b)).toMatch(/bs-cs.*checked/)
})

test('majors.json out of date refuses', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs') }, { majors: [] }))
  expect(r.ok).toBe(false)
  expect(msgs(r)).toContain('majors.json')
  const wrong = [{ checked: true, id: 'bs-cs', level: 'undergraduate', name: sample.program.name }]
  expect(checkPrograms(root({ 'bs-cs': real('bs-cs') }, { majors: wrong })).ok).toBe(false)
  expect(checkPrograms(root({ 'bs-cs': real('bs-cs') }, { majors: null })).ok).toBe(false)
})

test('a held major without courses.json is skipped and the build passes', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': null }))
  expect(r.ok, msgs(r)).toBe(true)
  expect(msgs(r)).toContain('held: bs-dsa')
})

test('a courses.json beside an unreadable program.json refuses', () => {
  const dir = root({ 'bs-cs': real('bs-cs') })
  writeFileSync(new URL('bs-cs/program.json', dir), '{ nope')
  const r = checkPrograms(dir)
  expect(r.ok).toBe(false)
  expect(msgs(r)).toMatch(/bs-cs.*program\.json/)
})
