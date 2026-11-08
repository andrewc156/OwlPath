import type { NodeState } from '../logic/eligibility'

/** Every state has a text label and symbol, never colour alone. */
export const STATE_LABEL: Record<NodeState, { symbol: string; text: string }> = {
  complete: { symbol: '✓', text: 'Complete' },
  'in-progress': { symbol: '◐', text: 'In progress' },
  'eligible-now': { symbol: '●', text: 'Eligible' },
  'eligible-next-term': { symbol: '◔', text: 'Next term' },
  locked: { symbol: '🔒', text: 'Locked' },
}
