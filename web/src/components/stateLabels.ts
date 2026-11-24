import type { NodeState } from '../logic/eligibility'

/** Every state has a text label and symbol, never colour alone. */
export const STATE_LABEL: Record<NodeState, { symbol: string; text: string }> = {
  complete: { symbol: '✓', text: 'Complete' },
  'in-progress': { symbol: '◐', text: 'In progress' },
  'eligible-now': { symbol: '●', text: 'Eligible' },
  'eligible-next-term': { symbol: '◔', text: 'Next term' },
  locked: { symbol: '🔒', text: 'Locked' },
}

export const AUTO_BUILT_TEXT = 'Auto-built from the catalog and not yet checked by a person. Confirm with the catalog and your advisor.'

export function autoBuiltText(checked: boolean): string | null {
  return checked ? null : AUTO_BUILT_TEXT
}
