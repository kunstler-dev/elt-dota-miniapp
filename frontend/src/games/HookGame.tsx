import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'

import { Coin, Icon } from '../components/icons'
import { Progress } from '../components/ui'
import { api } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'
import type { HitKind } from './HookScene'

const HookScene = lazy(() => import('./HookScene').then((m) => ({ default: m.HookScene })))

type Round = Awaited<ReturnType<typeof api.hookStart>>
type Pop = { id: number; text: string; tone: 'gold' | 'red' | 'ice' }

const BASE: Record<HitKind, number> = { enemy: 1, mega: 3, ally: -1 }
/** Combo multiplier: 1-2 hits x1, 3-5 x2, 6+ x3 */
const mult = (combo: number) => (combo >= 6 ? 3 : combo >= 3 ? 2 : 1)

/** Full-screen Pudge Hook round: start on the server -> 30 s of play -> result validated by the server. */
export function HookGame({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const [round, setRound] = useState<Round | null>(null)
  const [left, setLeft] = useState(0)
  const [score, setScore] = useState(0)
  const [combo, setCombo] = useState(0)
  const [pops, setPops] = useState<Pop[]>([])
  const [flash, setFlash] = useState(0)
  const stats = useRef({ score: 0, combo: 0, hits: 0, mega: 0, ally: 0, throws: 0, maxCombo: 0 })
  const lastThrow = useRef(0)
  const popId = useRef(0)
  const [result, setResult] = useState<{ reward: number; best: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const start = useMutation({
    mutationFn: api.hookStart,
    onSuccess: (r) => {
      stats.current = { score: 0, combo: 0, hits: 0, mega: 0, ally: 0, throws: 0, maxCombo: 0 }
      setScore(0)
      setCombo(0)
      setResult(null)
      setRound(r)
      setLeft(r.duration)
    },
    onError: (e) => setError(e instanceof Error && e.message === 'no_plays_left' ? 'Попытки на сегодня закончились' : 'Не удалось начать'),
  })
  const finish = useMutation({
    mutationFn: (r: Round) => api.hookFinish(r.session, stats.current.hits + stats.current.mega, stats.current.score),
    onSuccess: (r) => {
      applyState(r.state)
      setResult({ reward: r.reward, best: r.best })
      void qc.invalidateQueries({ queryKey: ['games'] })
    },
    onError: () => setResult({ reward: 0, best: 0 }),
  })

  useEffect(() => {
    start.mutate()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!round || result) return
    const startedAt = performance.now()
    const id = setInterval(() => {
      const l = Math.max(0, round.duration - (performance.now() - startedAt) / 1000)
      setLeft(l)
      if (l <= 0) {
        clearInterval(id)
        finish.mutate(round)
      }
    }, 100)
    return () => clearInterval(id)
  }, [round]) // eslint-disable-line react-hooks/exhaustive-deps

  function pop(text: string, tone: Pop['tone']) {
    const id = ++popId.current
    setPops((p) => [...p.slice(-3), { id, text, tone }])
    setTimeout(() => setPops((p) => p.filter((x) => x.id !== id)), 900)
  }

  const events = useMemo(
    () => ({
      onThrow: () => {
        const now = performance.now()
        if (!round || now - lastThrow.current < round.cooldown_ms) return false
        lastThrow.current = now
        stats.current.throws += 1
        haptic('light')
        return true
      },
      onHit: (kind: HitKind) => {
        const s = stats.current
        if (kind === 'ally') {
          s.ally += 1
          s.combo = 0
          s.score += BASE.ally
          setFlash((f) => f + 1)
          pop('Свой! −1', 'red')
          haptic('medium')
        } else {
          s.combo += 1
          s.maxCombo = Math.max(s.maxCombo, s.combo)
          if (kind === 'mega') s.mega += 1
          else s.hits += 1
          const m = mult(s.combo)
          const pts = BASE[kind] * m
          s.score += pts
          pop(`+${pts}${m > 1 ? ` ×${m}` : ''}${kind === 'mega' ? ' ЗОЛОТО' : ''}`, kind === 'mega' ? 'gold' : 'ice')
          haptic('heavy')
        }
        setScore(s.score)
        setCombo(s.combo)
      },
      onMiss: () => {
        if (stats.current.combo >= 3) pop('Комбо сорвано', 'red')
        stats.current.combo = 0
        setCombo(0)
      },
    }),
    [round],
  )

  const running = !!round && !result && left > 0
  const m = mult(combo)
  const st = stats.current
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ground">
      <div className="flex items-center justify-between gap-2 px-4 pt-3 pb-2">
        <button type="button" aria-label="Закрыть" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface">
          <Icon name="back" size={20} />
        </button>
        <div className="flex flex-col items-center">
          <div className="font-display text-3xl leading-none font-bold tabular-nums">{score}</div>
          <div className="text-[10px] font-bold tracking-wider text-muted uppercase">очков</div>
        </div>
        <div
          className={`flex w-[72px] flex-col items-center rounded-xl border px-2 py-1 transition ${
            m === 3 ? 'border-gold bg-[#2A2210] text-gold' : m === 2 ? 'border-ice-line bg-surface text-ice' : 'border-line bg-surface text-muted'
          }`}
        >
          <span className="font-display text-lg leading-none font-bold">×{m}</span>
          <span className="text-[10px] font-bold">комбо {combo}</span>
        </div>
      </div>
      <div className="px-4">
        <Progress value={round ? left / round.duration : 1} color={left < 8 ? 'bg-red' : 'bg-gold'} height={6} />
      </div>

      <div className="relative flex-1 overflow-hidden">
        {round && (
          <Suspense fallback={<div className="p-6 text-center text-sm text-muted">Загружаем линию…</div>}>
            <HookScene seed={round.seed} running={running} duration={round.duration} events={events} />
          </Suspense>
        )}
        {/* red flash: hooked your own creep */}
        <AnimatePresence>
          {flash > 0 && running && (
            <motion.div
              key={flash}
              className="pointer-events-none absolute inset-0 border-4 border-red"
              style={{ background: 'radial-gradient(circle, transparent 50%, rgba(212,37,47,.35))' }}
              initial={{ opacity: 1 }}
              animate={{ opacity: 0 }}
              transition={{ duration: 0.6 }}
            />
          )}
        </AnimatePresence>
        <div className="pointer-events-none absolute inset-x-0 top-[28%] flex flex-col items-center gap-1">
          <AnimatePresence>
            {pops.map((p) => (
              <motion.div
                key={p.id}
                className={`font-display text-2xl font-bold drop-shadow ${p.tone === 'gold' ? 'text-gold' : p.tone === 'red' ? 'text-[#FF6B73]' : 'text-ice'}`}
                initial={{ opacity: 0, y: 10, scale: 0.8 }}
                animate={{ opacity: 1, y: -20, scale: 1 }}
                exit={{ opacity: 0, y: -50 }}
                transition={{ duration: 0.35 }}
              >
                {p.text}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
        {running && left > (round?.duration ?? 30) - 4 && (
          <div className="pointer-events-none absolute inset-x-4 bottom-5 rounded-2xl bg-black/60 p-3 text-center text-xs leading-relaxed font-bold">
            Тап по реке — бросок хука. <span className="text-[#FF6B73]">Красные</span> — враги +1,{' '}
            <span className="text-gold">золотой</span> мегакрип +3, <span className="text-ok">зелёных</span> не трогать (−1).
            Попадай подряд — комбо до ×3. К концу крипы быстрее.
          </div>
        )}
        {(result || error) && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-6">
            <div className="flex w-full max-w-[320px] flex-col items-center gap-3 rounded-3xl border border-line bg-surface p-5 text-center">
              {error ? (
                <div className="text-sm font-bold">{error}</div>
              ) : (
                <>
                  <div className="font-display text-xl font-bold">Раунд окончен</div>
                  <div className="font-display text-4xl font-bold">{st.score}</div>
                  <div className="grid w-full grid-cols-2 gap-1.5 text-xs">
                    <Stat label="Враги" value={st.hits} />
                    <Stat label="Золотые" value={st.mega} />
                    <Stat label="Свои (штраф)" value={st.ally} />
                    <Stat label="Лучшее комбо" value={st.maxCombo} />
                    <Stat label="Точность" value={`${st.throws ? Math.round(((st.hits + st.mega) / st.throws) * 100) : 0}%`} />
                    <Stat label="Рекорд" value={result!.best} />
                  </div>
                  <div className="flex items-center gap-2 font-display text-2xl font-bold">
                    <Coin size={24} />+{fmt(result!.reward)}
                  </div>
                </>
              )}
              <div className="flex w-full gap-2">
                <button type="button" onClick={onClose} className="press flex-1 rounded-xl border border-line-2 bg-surface-2 py-3 text-sm font-extrabold">
                  Выйти
                </button>
                {!error && (round?.plays_left ?? 0) > 0 && (
                  <button type="button" onClick={() => start.mutate()} className="press flex-1 rounded-xl bg-red py-3 text-sm font-extrabold text-white">
                    Ещё раз ({round?.plays_left})
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col rounded-lg bg-surface-2 py-1.5">
      <span className="text-[10px] text-muted">{label}</span>
      <span className="text-sm font-extrabold">{value}</span>
    </div>
  )
}
