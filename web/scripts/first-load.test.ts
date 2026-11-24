// All-majors design §6: the first load carries only the list of majors, and a major's course data loads when it's
// picked, so the first load doesn't grow as majors are added. These checks read the app's source: no browser.
import { readdirSync, readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const src = new URL('../src/', import.meta.url)
const read = (file: string) => readFileSync(new URL(file, src), 'utf8')

test('the one courses.json glob is lazy, so each major is its own chunk', () => {
  const globs = [...read('data/dataset.ts').matchAll(
    /import\.meta\.glob(?:<[^>]*>)?\(\s*(['"])([^'"]+)\1\s*(?:,\s*(\{[^}]*\}))?\s*\)/g)]
  const courses = globs.filter((m) => m[2].endsWith('/courses.json'))
  expect(courses.map((m) => m[2])).toEqual(['../../../data/2026-2027/*/courses.json'])
  expect(courses[0][3] ?? '').not.toMatch(/eager/)
})

test('no app module imports a courses.json directly', () => {
  const files = (readdirSync(src, { recursive: true }) as string[])
    .filter((f) => /\.tsx?$/.test(f) && !/\.test\.tsx?$/.test(f))
  expect(files).toContain('data/dataset.ts')
  for (const f of files) {
    expect(read(f), f).not.toMatch(/(?:from\s*|import\s*\(\s*)['"][^'"]*courses\.json['"]/)
  }
})
