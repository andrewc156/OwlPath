import { expect, test } from 'vitest'
import { choicePartners } from './choices'

test('choicePartners lists the other options', () => {
  expect(choicePartners([['CSE 2300', 'MATH 2345']], 'MATH 2345')).toEqual(['CSE 2300'])
  expect(choicePartners([['A', 'B'], ['A', 'C']], 'A')).toEqual(['B', 'C'])
  expect(choicePartners([['A', 'B', 'C'], ['C', 'B']], 'C')).toEqual(['A', 'B'])
  expect(choicePartners([], 'A')).toEqual([])
})
