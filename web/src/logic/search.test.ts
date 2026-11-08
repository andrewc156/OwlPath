import { expect, test } from 'vitest'
import { searchCourses } from './search'
import { sample } from './testSample'

const cs = sample.courses

test.each(['cs3305', 'CS3305', ' cs 3305 '])('finds CS 3305 from %j', (q) => expect(searchCourses(cs, q)[0].id).toBe('CS 3305'))
test('title match', () => expect(searchCourses(cs, 'data struct').map((c) => c.id)).toContain('CS 3305'))
test('empty query -> []', () => expect(searchCourses(cs, '  ')).toEqual([]))
