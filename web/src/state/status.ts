import { useCallback, useState } from 'react'
import type { Status, StatusMap } from '../logic/eligibility'

export const STATUS_KEY = 'owlpath:v1:2026-2027:status'

const VALID: ReadonlySet<string> = new Set<Status>(['not-taken', 'in-progress', 'complete'])

// Progress is shared across majors and a major's data may not be loaded, so any well-formed course id is kept.
const COURSE_ID = /^[A-Z]{2,4} \d{4}[A-Z]?$/

/** Never throws; malformed ids and invalid values are dropped. */
export function loadStatus(storage: Storage | null): StatusMap {
  try {
    const raw = storage?.getItem(STATUS_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {}
    const out: StatusMap = {}
    for (const [id, value] of Object.entries(parsed)) {
      if (COURSE_ID.test(id) && typeof value === 'string' && VALID.has(value)) out[id] = value as Status
    }
    return out
  } catch {
    return {}
  }
}

/** Never throws. */
export function saveStatus(storage: Storage | null, status: StatusMap): void {
  try {
    storage?.setItem(STATUS_KEY, JSON.stringify(status))
  } catch {
    // Storage full or blocked: status just won't persist.
  }
}

/** Marks every course not taken, in every major. Never throws. */
export function resetStatus(storage: Storage | null): StatusMap {
  const empty: StatusMap = {}
  saveStatus(storage, empty)
  return empty
}

function browserStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function useStatus(): [StatusMap, (id: string, s: Status) => void, () => void] {
  const [status, setStatusMap] = useState<StatusMap>(() => loadStatus(browserStorage()))
  const setStatus = useCallback((id: string, s: Status) => {
    setStatusMap((prev) => {
      const next = { ...prev }
      if (s === 'not-taken') delete next[id]
      else next[id] = s
      saveStatus(browserStorage(), next)
      return next
    })
  }, [])
  const reset = useCallback(() => setStatusMap(resetStatus(browserStorage())), [])
  return [status, setStatus, reset]
}
