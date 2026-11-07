// Data schema: docs/superpowers/specs/2026-11-06-owlpath-design.md

export type Grade = 'A' | 'B' | 'C' | 'D'

/** A plain string is an in-graph course with minimum grade C. */
export type Leaf =
  | string
  | { course: string; minGrade?: Grade }
  | { external: string; minGrade?: Grade }

export type Logic = Leaf | { and: Logic[] } | { or: Logic[] }

export type Group =
  | 'core-field'
  | 'major-required'
  | 'conc-data-science'
  | 'conc-cyber'
  | 'conc-ai'
  | 'major-elective'
  | 'gen-ed-math'
  | 'prereq-only'

export interface Course {
  id: string
  title: string
  credits: string
  description: string
  catalogYear: string
  catalogUrl: string
  groups: Group[]
  prereqs: Logic | null
  coreqs: Logic | null
  notes: string[]
}

export interface Dataset {
  catalogYear: string
  source: string
  courses: Course[]
}

// Normalized forms: every leaf is an object with an explicit grade.

export type NLeaf = { kind: 'course' | 'external'; id: string; minGrade: Grade }
export type NExpr = NLeaf | { kind: 'and' | 'or'; children: NExpr[] }
export type NCourse = Omit<Course, 'prereqs' | 'coreqs'> & { prereqs: NExpr | null; coreqs: NExpr | null }
export type NDataset = { catalogYear: string; source: string; courses: NCourse[]; byId: Map<string, NCourse> }
