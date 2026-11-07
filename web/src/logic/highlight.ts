import type { Group, NCourse } from '../data/types'
import type { Graph } from './graph'

/** Node ids, including junction ids. */
export type Highlight = { selected: string; ancestors: Set<string>; descendants: Set<string>; takeWith: Set<string> }

function reach(starts: string[], next: Map<string, string[]>): Set<string> {
  const seen = new Set<string>()
  const stack = [...starts]
  while (stack.length) {
    for (const n of next.get(stack.pop()!) ?? []) {
      if (!seen.has(n)) {
        seen.add(n)
        stack.push(n)
      }
    }
  }
  return seen
}

function adjacency(graph: Graph) {
  const back = new Map<string, string[]>()
  const fwd = new Map<string, string[]>()
  const add = (m: Map<string, string[]>, k: string, v: string) => m.set(k, [...(m.get(k) ?? []), v])
  for (const e of graph.edges) {
    if (e.kind !== 'prereq') continue
    add(back, e.target, e.source)
    add(fwd, e.source, e.target)
  }
  return { back, fwd }
}

/** Follows prereq edges only; takeWith is just the direct coreq neighbours, either direction. */
export function highlightSets(graph: Graph, selected: string): Highlight {
  const { back, fwd } = adjacency(graph)
  const takeWith = new Set<string>()
  for (const e of graph.edges) {
    if (e.kind !== 'coreq') continue
    if (e.target === selected) takeWith.add(e.source)
    if (e.source === selected) takeWith.add(e.target)
  }
  takeWith.delete(selected)
  return { selected, ancestors: reach([selected], back), descendants: reach([selected], fwd), takeWith }
}

/** The group's courses plus everything needed to reach them. */
export function concentrationSet(graph: Graph, courses: NCourse[], group: Group): Set<string> {
  const members = courses.filter((c) => c.groups.includes(group)).map((c) => c.id)
  const { back } = adjacency(graph)
  return new Set([...members, ...reach(members, back)])
}
