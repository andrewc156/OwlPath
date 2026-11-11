// Which major's map is shown: ?major= in the URL, then the remembered choice, then the first major.
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
  return ids[0]
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
