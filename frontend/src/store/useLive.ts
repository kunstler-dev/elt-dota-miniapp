import { useEffect, useState } from 'react'

import { useGame, view } from './game'

/** Live coins and energy, recomputed ~10 times per second. */
export function useLive() {
  const snap = useGame((s) => s.snap)
  const snapAt = useGame((s) => s.snapAt)
  const unconfirmed = useGame((s) => s.pending + s.inflight)
  const [now, setNow] = useState(() => performance.now())

  useEffect(() => {
    const id = setInterval(() => setNow(performance.now()), 100)
    return () => clearInterval(id)
  }, [])

  if (!snap) return null
  return { ...view(snap, snapAt, unconfirmed, Math.max(now, snapAt)), snap }
}
