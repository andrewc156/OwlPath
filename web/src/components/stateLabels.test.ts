import { expect, test } from 'vitest'
import { autoBuiltText } from './stateLabels'

test('auto-built text only for unchecked majors', () => {
  expect(autoBuiltText(false)).toBe('Auto-built from the catalog and not yet checked by a person. Confirm with the catalog and your advisor.')
  expect(autoBuiltText(true)).toBeNull()
})
