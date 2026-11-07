import { expect, test } from 'vitest'
import { STATUS_KEY, loadStatus, saveStatus } from './status'

const ids = new Set(['CS 3305', 'CSE 1321'])

class MemoryStorage implements Storage {
  private m = new Map<string, string>()
  get length() { return this.m.size }
  clear() { this.m.clear() }
  getItem(k: string) { return this.m.get(k) ?? null }
  key(i: number) { return [...this.m.keys()][i] ?? null }
  removeItem(k: string) { this.m.delete(k) }
  setItem(k: string, v: string) { this.m.set(k, v) }
}

const throwing = {
  getItem() { throw new Error('denied') },
  setItem() { throw new Error('denied') },
} as unknown as Storage

test('round-trips through storage', () => {
  const s = new MemoryStorage()
  saveStatus(s, { 'CS 3305': 'complete', 'CSE 1321': 'in-progress' })
  expect(loadStatus(s, ids)).toEqual({ 'CS 3305': 'complete', 'CSE 1321': 'in-progress' })
})

test('throwing storage -> empty map, save does not throw', () => {
  expect(loadStatus(throwing, ids)).toEqual({})
  expect(() => saveStatus(throwing, { 'CS 3305': 'complete' })).not.toThrow()
})

test('corrupt JSON -> empty map', () => {
  const s = new MemoryStorage()
  s.setItem(STATUS_KEY, '{not json')
  expect(loadStatus(s, ids)).toEqual({})
})

test('unknown course ids and bad values are dropped', () => {
  const s = new MemoryStorage()
  s.setItem(STATUS_KEY, JSON.stringify({ 'CS 9999': 'complete', 'CS 3305': 'done' }))
  expect(loadStatus(s, ids)).toEqual({})
})

test('null storage works', () => expect(loadStatus(null, ids)).toEqual({}))
