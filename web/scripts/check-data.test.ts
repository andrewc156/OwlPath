// The deploy guard must refuse unless every program folder has a reviewed, valid dataset.
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { expect, test } from 'vitest'
import sample from '../src/data/sample.json'
import { checkPrograms } from './check-data.mjs'

const real = (id: string) => ({ ...sample, source: 'KSU catalog', program: { ...sample.program, id } })

function root(programs: Record<string, object | null>) {
  const dir = mkdtempSync(join(tmpdir(), 'owlpath-'))
  mkdirSync(join(dir, 'catalog'))
  for (const [id, data] of Object.entries(programs)) {
    mkdirSync(join(dir, id))
    writeFileSync(join(dir, id, 'program.json'), '{}')
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
