import { expect, test } from 'vitest'
import { usualNote } from './choices'

const less = new Set(['STAT 3125'])
test('the usual option says most students take it', () =>
  expect(usualNote('STAT 3120', ['STAT 3125'], less)).toBe('Most students take STAT 3120.'))
test('the less common option points to the usual one', () =>
  expect(usualNote('STAT 3125', ['STAT 3120'], less)).toBe('Most students take STAT 3120 instead.'))
test('pairs with no less common option say nothing', () =>
  expect(usualNote('STAT 1401', ['STAT 2332'], less)).toBe(''))
