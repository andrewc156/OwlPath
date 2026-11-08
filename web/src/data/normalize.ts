import type { Dataset, Logic, NCourse, NDataset, NExpr } from './types'

function normalizeLogic(logic: Logic): NExpr {
  if (typeof logic === 'string') return { kind: 'course', id: logic, minGrade: 'C' }
  if ('and' in logic) return { kind: 'and', children: logic.and.map(normalizeLogic) }
  if ('or' in logic) return { kind: 'or', children: logic.or.map(normalizeLogic) }
  if ('course' in logic) return { kind: 'course', id: logic.course, minGrade: logic.minGrade ?? 'C' }
  return { kind: 'external', id: logic.external, minGrade: logic.minGrade ?? 'C' }
}

export function normalize(dataset: Dataset): NDataset {
  const courses: NCourse[] = dataset.courses.map((c) => ({
    ...c,
    prereqs: c.prereqs === null ? null : normalizeLogic(c.prereqs),
    coreqs: c.coreqs === null ? null : normalizeLogic(c.coreqs),
  }))
  return {
    catalogYear: dataset.catalogYear,
    source: dataset.source,
    courses,
    byId: new Map(courses.map((c) => [c.id, c])),
  }
}
