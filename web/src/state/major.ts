import { defaultMajor } from '../logic/majorLoad'

// Which major's map is shown: ?major= in the URL, then the remembered choice, then bs-cs (or the first major).
export const MAJOR_KEY = 'owlpath:v1:major'

/** Never throws; unknown ids fall through to the next source. */
export function resolveMajor(search: string, storage: Storage | null, ids: string[]): string {
  const fromUrl = new URLSearchParams(search).get('major')
  if (fromUrl && ids.includes(fromUrl)) return fromUrl
  try {
    const stored = storage?.getItem(MAJOR_KEY)
    if (stored && ids.includes(stored)) return stored
  } catch {
    // Storage blocked: fall back.
  }
  return defaultMajor(ids)
}

/** Never throws. */
export function saveMajor(storage: Storage | null, id: string): void {
  try {
    storage?.setItem(MAJOR_KEY, id)
  } catch {
    // Storage full or blocked: the choice just won't persist.
  }
}

export function majorUrl(href: string, id: string): string {
  const url = new URL(href)
  url.searchParams.set('major', id)
  return url.toString()
}

/** The parts of `window` a reload needs. */
export type PageControls = {
  location: { readonly href: string; reload(): void }
  history: { replaceState(data: unknown, unused: string, url?: string | URL | null): void }
}

/**
 * Retry after a major failed to load. Each major's data file is hashed, so after a deploy an old tab's file is
 * gone: only a reload brings the new index and file names. The major goes into the URL and the saved choice
 * first, so the reload reopens it. Progress is untouched (it lives under its own key). Never throws.
 */
export function reloadToMajor(id: string, page: PageControls, storage: Storage | null): void {
  saveMajor(storage, id)
  page.history.replaceState(null, '', majorUrl(page.location.href, id))
  page.location.reload()
}
