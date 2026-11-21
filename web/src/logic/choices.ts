import type { StatusMap } from './eligibility'

/** The other courses in every either/or requirement that includes `id`, without duplicates, in order. */
export function choicePartners(choices: string[][], id: string): string[] {
  const out: string[] = []
  for (const choice of choices) {
    if (!choice.includes(id)) continue
    for (const other of choice) if (other !== id && !out.includes(other)) out.push(other)
  }
  return out
}

/**
 * Less common either/or options to leave off the map right now. One shows again when it or a course it
 * pairs with is selected, or when the student has marked it, so their progress is never hidden.
 */
export function hiddenCourses(lessCommon: Set<string>, choices: string[][], status: StatusMap,
  selected: string | null): Set<string> {
  const revealed = new Set(selected ? [selected, ...choicePartners(choices, selected)] : [])
  return new Set([...lessCommon].filter((id) => !revealed.has(id) && (status[id] ?? 'not-taken') === 'not-taken'))
}

/** Each less common option mapped to the first shown option it pairs with, so layout can place them together. */
export function shownPartners(lessCommon: Set<string>, choices: string[][]): Map<string, string> {
  const out = new Map<string, string>()
  for (const id of lessCommon) {
    const partner = choicePartners(choices, id).find((p) => !lessCommon.has(p))
    if (partner) out.set(id, partner)
  }
  return out
}

/** Which option most students take, when the major marks the others as less common. */
export function usualNote(id: string, partners: string[], lessCommon: Set<string>): string {
  if (lessCommon.has(id)) {
    const usual = partners.filter((p) => !lessCommon.has(p))
    return usual.length ? `Most students take ${usual.join(' or ')} instead.` : ''
  }
  return partners.some((p) => lessCommon.has(p)) ? `Most students take ${id}.` : ''
}
