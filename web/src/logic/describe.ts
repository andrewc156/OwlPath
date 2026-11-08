import type { NExpr } from '../data/types'

function leafText(id: string, grade: string, external: boolean): string {
  const parts = [...(grade !== 'C' ? [grade] : []), ...(external ? ['outside program'] : [])]
  return parts.length ? `${id} (${parts.join(', ')})` : id
}

function describe(expr: NExpr, nested: boolean): string {
  if (expr.kind === 'course' || expr.kind === 'external') return leafText(expr.id, expr.minGrade, expr.kind === 'external')
  const text = expr.children.map((e) => describe(e, true)).join(` ${expr.kind} `)
  return nested ? `(${text})` : text
}

/** Readable requirement text; nested groups get parentheses, the top level doesn't. */
export function describeLogic(expr: NExpr | null): string {
  return expr === null ? 'None' : describe(expr, false)
}
