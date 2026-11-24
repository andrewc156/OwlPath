import { expect, test } from 'vitest'
import sampleJson from '../data/sample.json'
import { normalize } from '../data/normalize'
import type { Dataset } from '../data/types'
import { defaultMajor, fetchMajor } from './majorLoad'

const data = normalize(sampleJson as Dataset)

test('fetchMajor returns an error state when loading fails', async () => {
  expect(await fetchMajor('x', () => Promise.reject(new Error('chunk')))).toEqual({ status: 'error' })
})

test('fetchMajor returns the data when loading works', async () => {
  expect(await fetchMajor('x', () => Promise.resolve(data))).toEqual({ status: 'ready', data })
})

test('defaultMajor prefers bs-cs, else the first id', () => {
  expect(defaultMajor(['ms-dsa', 'bs-cs'])).toBe('bs-cs')
  expect(defaultMajor(['ms-dsa', 'bs-dsa'])).toBe('ms-dsa')
})
