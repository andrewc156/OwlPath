import { expect, test, vi } from 'vitest'
import sampleJson from '../data/sample.json'
import { normalize } from '../data/normalize'
import type { Dataset } from '../data/types'
import { RESET_TEXT, allCourseIds, askAndReset, programView, switchMajor } from './programView'

const sample = sampleJson as Dataset
const a = normalize(sample)
const b = normalize({ ...sample, program: { ...sample.program, id: 'bs-dsa', name: 'DSA' },
  courses: [...sample.courses, { ...sample.courses[0], id: 'DATA 3010' }] })

test('programView builds once per program and caches', () => {
  expect(programView(a)).toBe(programView(a))
  expect(programView(b)).not.toBe(programView(a))
  expect(programView(b).validIds.has('DATA 3010')).toBe(true)
})

test('allCourseIds is the union of every major', () => {
  const ids = allCourseIds([a, b])
  expect(ids.has('DATA 3010') && ids.has('CS 3305')).toBe(true)
})

test('switching major clears selection, filter and focus', () => {
  expect(switchMajor({ major: 'bs-cs', selected: 'CS 3305', filter: 2, focus: { id: 'CS 3305', seq: 3 } }, 'bs-dsa'))
    .toEqual({ major: 'bs-dsa', selected: null, filter: null, focus: null })
})

test('reset asks first and respects cancel', () => {
  const onReset = vi.fn()
  const no = vi.fn(() => false)
  askAndReset(no, onReset)
  expect(no).toHaveBeenCalledWith(RESET_TEXT)
  expect(onReset).not.toHaveBeenCalled()
  askAndReset(() => true, onReset)
  expect(onReset).toHaveBeenCalledTimes(1)
  expect(RESET_TEXT).toBe('Reset all progress? This marks every course as not taken in both majors.')
})
