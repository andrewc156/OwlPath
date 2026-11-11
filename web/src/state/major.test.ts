import { expect, test } from 'vitest'
import { MAJOR_KEY, majorUrl, resolveMajor, saveMajor } from './major'

const IDS = ['bs-cs', 'bs-dsa']

function store(init: Record<string, string> = {}): Storage {
  const m = new Map(Object.entries(init))
  return {
    get length() { return m.size },
    clear: () => m.clear(),
    getItem: (k: string) => m.get(k) ?? null,
    key: (i: number) => [...m.keys()][i] ?? null,
    removeItem: (k: string) => { m.delete(k) },
    setItem: (k: string, v: string) => { m.set(k, v) },
  }
}
const throwing = { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') } } as unknown as Storage

test('url beats storage', () => expect(resolveMajor('?major=bs-dsa', store({ [MAJOR_KEY]: 'bs-cs' }), IDS)).toBe('bs-dsa'))
test('storage used when url absent', () => expect(resolveMajor('', store({ [MAJOR_KEY]: 'bs-dsa' }), IDS)).toBe('bs-dsa'))
test('unknown url and stored ids fall back to first', () =>
  expect(resolveMajor('?major=bs-ee', store({ [MAJOR_KEY]: 'gone' }), IDS)).toBe('bs-cs'))
test('throwing or missing storage falls back', () => {
  expect(resolveMajor('', throwing, IDS)).toBe('bs-cs')
  expect(resolveMajor('', null, IDS)).toBe('bs-cs')
})
test('saveMajor persists and never throws', () => {
  const s = store()
  saveMajor(s, 'bs-dsa')
  expect(s.getItem(MAJOR_KEY)).toBe('bs-dsa')
  expect(() => saveMajor(throwing, 'bs-dsa')).not.toThrow()
})
test('majorUrl keeps other params', () =>
  expect(majorUrl('https://x/OwlPath/?a=1', 'bs-dsa')).toBe('https://x/OwlPath/?a=1&major=bs-dsa'))
