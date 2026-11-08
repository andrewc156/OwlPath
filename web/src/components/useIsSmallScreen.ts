import { useEffect, useState } from 'react'

const QUERY = '(max-width: 767px)'

export function useIsSmallScreen(): boolean {
  const [small, setSmall] = useState(() => window.matchMedia(QUERY).matches)
  useEffect(() => {
    const mq = window.matchMedia(QUERY)
    const onChange = () => setSmall(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return small
}
