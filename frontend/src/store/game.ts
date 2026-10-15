import { create } from 'zustand'

import { api, type GameState, type Me } from '../lib/api'

export type Tab = 'tap' | 'mine' | 'games' | 'friends' | 'season' | 'tasks' | 'daily' | 'shop' | 'profile' | 'contest'

const FLUSH_MS = 1000

type Store = {
  tab: Tab
  me: Me | null
  error: string | null
  /** Server snapshot and when it was received: energy regen and passive income are computed from these on the client */
  snap: GameState | null
  snapAt: number
  pending: number
  inflight: number
  setTab: (t: Tab) => void
  load: () => Promise<void>
  applyState: (s: GameState) => void
  tap: () => boolean
  flush: () => Promise<void>
}

let flushTimer: ReturnType<typeof setTimeout> | null = null

export const useGame = create<Store>((set, get) => ({
  tab: 'tap',
  me: null,
  error: null,
  snap: null,
  snapAt: 0,
  pending: 0,
  inflight: 0,

  setTab: (tab) => set({ tab }),

  load: async () => {
    try {
      const me = await api.me()
      set({ me, snap: me.state, snapAt: performance.now(), error: null })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'network' })
    }
  },

  applyState: (s) => set({ snap: s, snapAt: performance.now() }),

  tap: () => {
    const { snap, snapAt, pending, inflight } = get()
    if (!snap) return false
    const v = view(snap, snapAt, pending + inflight, performance.now())
    if (v.energy < snap.tap_power) return false
    set({ pending: pending + 1 })
    if (!flushTimer) flushTimer = setTimeout(() => void get().flush(), FLUSH_MS)
    return true
  },

  flush: async () => {
    flushTimer = null
    const { pending, inflight } = get()
    if (!pending || inflight) {
      if (pending) flushTimer = setTimeout(() => void get().flush(), FLUSH_MS)
      return
    }
    set({ pending: 0, inflight: pending })
    try {
      const r = await api.tap(pending)
      set({ snap: r.state, snapAt: performance.now(), inflight: 0 })
    } catch {
      set({ inflight: 0 }) // rejected taps simply disappear: the server is the source of truth
    }
    if (get().pending && !flushTimer) flushTimer = setTimeout(() => void get().flush(), FLUSH_MS)
  },
}))

/** What to show right now: server snapshot + regen + passive income + taps not yet confirmed. */
export function view(snap: GameState, snapAt: number, unconfirmed: number, now: number) {
  const elapsed = Math.max(0, now - snapAt)
  const regen = Math.floor((elapsed / 1000) * snap.energy_regen)
  const passive = Math.floor((snap.profit_per_hour * elapsed) / 3_600_000)
  return {
    coins: snap.coins + passive + unconfirmed * snap.tap_power,
    energy: Math.max(0, Math.min(snap.max_energy, snap.energy + regen) - unconfirmed * snap.tap_power),
  }
}
