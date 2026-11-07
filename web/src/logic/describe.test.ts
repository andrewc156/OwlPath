import { expect, test } from 'vitest'
import { describeLogic } from './describe'
import { c } from './testSample'

const prereqsOf = (id: string) => c(id).prereqs

test('CS 3305 reads naturally', () =>
  expect(describeLogic(prereqsOf('CS 3305'))).toBe(
    '(MATH 2345 or CSE 2300 (outside program)) and ((CSE 1322 (B) and CSE 1322L (B)) or MTRE 2610 (B, outside program) or CPE 3000 (B, outside program))',
  ))
test('single leaf', () => expect(describeLogic(prereqsOf('MATH 1190'))).toBe('MATH 1113'))
test('null', () => expect(describeLogic(null)).toBe('None'))
