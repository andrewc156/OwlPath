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

/** Each folder gets a program.json matching its courses.json (or `programJson` when given). */
function root(programs: Record<string, Data | null>, opts: { programJson?: Record<string, object | null> } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'owlpath-'))
  mkdirSync(join(dir, 'catalog'))
  for (const [id, data] of Object.entries(programs)) {
    mkdirSync(join(dir, id))
    const pj = id in (opts.programJson ?? {}) ? opts.programJson![id]
      : { program: data?.program ?? real(id).program, choices: data?.choices ?? [], courses: {} }
    if (pj) writeFileSync(join(dir, id, 'program.json'), JSON.stringify(pj))
    if (data) writeFileSync(join(dir, id, 'courses.json'), JSON.stringify(data))
  }
  return pathToFileURL(dir + '/')
}

test('two valid programs pass', () => {
  expect(checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': real('bs-dsa') })).ok).toBe(true)
})

test('a program without courses.json is refused', () => {
  const r = checkPrograms(root({ 'bs-cs': real('bs-cs'), 'bs-dsa': null }))
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

test('the app bundles the same data folder the guard checks', () => {
  const year = (file: string) => readFileSync(new URL(file, import.meta.url), 'utf8').match(/data\/(\d{4}-\d{4})\//g)
  const app = year('../src/data/dataset.ts')
  const guard = year('./check-data.mjs')
  expect(app).not.toBeNull()
  expect(new Set(app)).toEqual(new Set(guard))
})
