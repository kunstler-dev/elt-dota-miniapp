import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { lazy, Suspense, useMemo, useRef, useState } from 'react'

import { api } from '../lib/api'
import { lookOf } from '../lib/arsenal'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'
import type { CharacterHandle } from './Character3D'
import { CANVAS_H, STAGE_SIZE as SIZE } from './pudgeLayout'

// three.js is a separate chunk: it loads in parallel with the splash and doesn't slow down the first screen
const Character3D = lazy(() => import('./Character3D').then((m) => ({ default: m.Character3D })))

type Float = { id: number; x: number; y: number; text: string }

/** Tap stage: the active hero in 3D with its own attacks and taunts. */
export function HeroStage() {
  const tap = useGame((s) => s.tap)
  const power = useGame((s) => s.snap?.tap_power ?? 1)
  const hero = useGame((s) => s.snap?.active_hero ?? 'pudge')
  const handle = useRef<CharacterHandle>(null)
  const { data: arsenal } = useQuery({ queryKey: ['arsenal', hero], queryFn: () => api.arsenal(hero) })
  const look = useMemo(() => (arsenal ? lookOf(arsenal) : undefined), [arsenal])
  const heroName = arsenal?.heroes.find((h) => h.id === hero)?.name ?? 'героя'
  const nextId = useRef(0)
  const [floats, setFloats] = useState<Float[]>([])
  const [bubble, setBubble] = useState('')
  const [flash, setFlash] = useState(0)

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    e.preventDefault()
    if (!tap()) {
      haptic('heavy')
      return
    }
    haptic('light')
    handle.current?.hit()
    const r = e.currentTarget.getBoundingClientRect()
    const id = ++nextId.current
    setFloats((f) => [...f.slice(-20), { id, x: e.clientX - r.left, y: e.clientY - r.top, text: `+${power}` }])
    setTimeout(() => setFloats((f) => f.filter((x) => x.id !== id)), 900)
    setFlash(id)
  }

  return (
    <button
      type="button"
      aria-label={`Тапнуть ${heroName}`}
      onPointerDown={onPointerDown}
      className="relative touch-none select-none"
      style={{ width: SIZE, height: SIZE }}
    >
      <span
        className="pointer-events-none absolute rounded-[50%] border-2 border-[#5A1A1F] bg-[#1C0A0C]"
        // ellipse center is under the hero's feet (feet at scene y=0 project ~22 px below the old center)
        style={{ left: 30, right: 30, bottom: -12, height: 62, boxShadow: '0 0 48px 6px rgba(212,37,47,.28)' }}
      />
      {flash > 0 && (
        <motion.span
          key={flash}
          className="pointer-events-none absolute rounded-full bg-red/40"
          style={{ left: 70, right: 70, top: 60, bottom: 50 }}
          initial={{ opacity: 1 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 0.28 }}
        />
      )}
      {/* the scene is wider and taller than the button: canvas center matches the stage center, edges don't clip animations */}
      <div
        className="pointer-events-none absolute left-1/2 -translate-x-1/2"
        style={{ width: 'min(100vw, 480px)', height: CANVAS_H, top: (SIZE - CANVAS_H) / 2 }}
      >
        {look && (
          <Suspense fallback={null}>
            <Character3D handle={handle} onMood={setBubble} look={look} />
          </Suspense>
        )}
      </div>
      <AnimatePresence>
        {bubble && (
          <motion.span
            key={bubble}
            className="pointer-events-none absolute right-0 top-[14px] rounded-[14px_14px_14px_4px] bg-ink px-3 py-1.5 text-[13px] font-extrabold text-bar"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
          >
            {bubble}
          </motion.span>
        )}
      </AnimatePresence>
      {floats.map((f) => (
        <motion.span
          key={f.id}
          className="pointer-events-none absolute font-display text-[30px] font-bold text-ink"
          style={{ left: f.x, top: f.y, x: '-50%', textShadow: '0 2px 12px rgba(108,196,255,.8)' }}
          initial={{ opacity: 1, y: '-50%' }}
          animate={{ opacity: 0, y: -110 }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
        >
          {f.text}
        </motion.span>
      ))}
    </button>
  )
}
