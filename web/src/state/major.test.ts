import { expect, test } from 'vitest'
import { MAJOR_KEY, majorUrl, reloadToMajor, resolveMajor, saveMajor } from './major'

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
test('an unknown or held major falls back to bs-cs, wherever it is in the list', () => {
  expect(resolveMajor('?major=held-x', null, ['ms-dsa', 'bs-cs'])).toBe('bs-cs')
  expect(resolveMajor('', store({ [MAJOR_KEY]: 'gone' }), ['ms-dsa', 'bs-cs'])).toBe('bs-cs')
  expect(resolveMajor('', null, ['ms-dsa', 'bs-dsa'])).toBe('ms-dsa')
})

// Retry after a failed load reloads the page (a deploy may have replaced the major's chunk), so the major must be
// in the URL and the saved choice first: the reload then reopens it.
function fakePage(start: string, onReload: (href: string) => void) {
  let href = start
  const calls: string[] = []
  return {
    calls,
    page: {
      location: { get href() { return href }, reload: () => { calls.push('reload'); onReload(href) } },
      history: { replaceState: (_d: unknown, _u: string, url?: string | URL | null) => { calls.push('replaceState'); href = String(url) } },
    },
  }
}

test('reloadToMajor saves the major in the URL and storage, then reloads into it', () => {
  const s = store({ [MAJOR_KEY]: 'bs-cs' })
  let reopened = ''
  const { page, calls } = fakePage('https://x/OwlPath/?a=1', (href) => {
    reopened = resolveMajor(new URL(href).search, s, ['bs-cs', 'ms-dsa'])
  })
  reloadToMajor('ms-dsa', page, s)
  expect(calls).toEqual(['replaceState', 'reload'])
  expect(page.location.href).toBe('https://x/OwlPath/?a=1&major=ms-dsa')
  expect(s.getItem(MAJOR_KEY)).toBe('ms-dsa')
  expect(reopened).toBe('ms-dsa')
})

test('reloadToMajor still reloads when storage is blocked', () => {
  const { page, calls } = fakePage('https://x/OwlPath/', () => {})
  expect(() => reloadToMajor('bs-dsa', page, throwing)).not.toThrow()
  expect(calls).toEqual(['replaceState', 'reload'])
})
