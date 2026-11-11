/** The other courses in every either/or requirement that includes `id`, without duplicates, in order. */
export function choicePartners(choices: string[][], id: string): string[] {
  const out: string[] = []
  for (const choice of choices) {
    if (!choice.includes(id)) continue
    for (const other of choice) if (other !== id && !out.includes(other)) out.push(other)
  }
  return out
}
