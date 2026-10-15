import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'

import { Coin } from '../components/icons'
import { api } from '../lib/api'

const HookGame = lazy(() => import('../games/HookGame').then((m) => ({ default: m.HookGame })))
const GuessGame = lazy(() => import('../games/GuessGame').then((m) => ({ default: m.GuessGame })))
const SilhouetteScene = lazy(() => import('../games/SilhouetteScene').then((m) => ({ default: m.SilhouetteScene })))
const DraftScreen = lazy(() => import('./DraftScreen').then((m) => ({ default: m.DraftScreen })))
const AncientScene = lazy(() => import('../games/AncientScene').then((m) => ({ default: m.AncientScene })))
const INVOKER = '/models/heroes/invoker/'
const INVOKER_ITEMS = ['bracer', 'cape', 'dress', 'hair', 'head', 'shoulder'].map((n) => `${INVOKER}items/invoker_${n}.glb`)
const AnalysisScreen = lazy(() => import('./AnalysisScreen').then((m) => ({ default: m.AnalysisScreen })))

type Open = null | 'hook' | 'guess' | 'analysis' | 'draft'
type Stats = { plays_left: number; plays_per_day: number; best: number }

/** Time until midnight Moscow time (UTC+3), when attempts reset */
function useResetIn() {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])
  const msk = now + 3 * 3600_000
  const left = 86_400_000 - (msk % 86_400_000)
  return `${Math.floor(left / 3_600_000)} ч ${Math.floor((left % 3_600_000) / 60_000)} мин`
}

const enter = (i: number) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.05 + i * 0.07, duration: 0.35 },
})

export function GamesScreen() {
  const [open, setOpen] = useState<Open>(null)
  const { data } = useQuery({ queryKey: ['games'], queryFn: api.games })
  const resetIn = useResetIn()
  const left = data ? data.hook.plays_left + data.guess.plays_left : 0
  const total = data ? data.hook.plays_per_day + data.guess.plays_per_day : 0

  return (
    <div className="flex flex-col gap-3.5 px-4 pt-3.5 pb-6">
      <motion.div {...enter(0)} className="flex items-end justify-between">
        <div>
          <h1 className="m-0 font-display text-[28px] leading-none font-bold">Арена</h1>
          <div className="mt-1.5 text-[13px] text-muted">Мини-игры за ELT и рейтинг</div>
        </div>
        <div className="flex flex-col items-end">
          <span className="font-display text-xl leading-none font-bold">
            {left}
            <span className="text-sm text-muted">/{total}</span>
          </span>
          <span className="mt-1 text-[10px] font-bold text-muted">обновление через {resetIn}</span>
        </div>
      </motion.div>

      <motion.div {...enter(1)}>
        <HookCard stats={data?.hook} onPlay={() => setOpen('hook')} />
      </motion.div>
      <motion.div {...enter(2)}>
        <GuessCard stats={data?.guess} onPlay={() => setOpen('guess')} />
      </motion.div>

      <motion.div {...enter(3)} className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => setOpen('analysis')}
          className="press relative flex h-[150px] flex-col justify-end overflow-hidden rounded-[20px] border border-[#2B3E56] p-3 text-left"
          style={{ background: 'linear-gradient(160deg, #142235 0%, #0B1119 70%)' }}
        >
          <img src="/media/ranks/rank_7.png" alt="" className="absolute -top-1 -right-2 h-[96px] w-[96px] object-contain opacity-95 drop-shadow-[0_0_14px_rgba(108,196,255,.45)]" />
          <span className="relative mb-1 w-fit rounded-md bg-ice/15 px-1.5 py-0.5 text-[10px] font-extrabold text-ice">DOTA 2</span>
          <span className="relative text-[15px] leading-tight font-extrabold">Разбор матча</span>
          <span className="relative mt-0.5 text-[11px] leading-snug text-muted">Ошибки и советы по MMR</span>
        </button>
        <button
          type="button"
          onClick={() => setOpen('draft')}
          className="press relative flex h-[150px] flex-col justify-end overflow-hidden rounded-[20px] border border-[#5a4a1a] p-3 text-left"
          style={{ background: 'linear-gradient(160deg, #2a2210 0%, #0d0c09 75%)' }}
        >
          <div className="absolute top-2.5 right-2.5 grid grid-cols-3 gap-1 opacity-80">
            {["axe", "lina", "sniper", "zeus", "phantom_assassin", "crystal_maiden"].map((h, i) => (
              <img key={h} src={`/media/heroes/${h}.png`} alt="" className={`h-[26px] w-[44px] rounded-[5px] object-cover ${i % 2 ? "grayscale" : ""}`} />
            ))}
          </div>
          <span className="relative mb-1 flex w-fit items-center gap-1 rounded-md bg-gold/15 px-1.5 py-0.5 text-[10px] font-extrabold text-gold">
            ELO
          </span>
          <span className="relative text-[15px] leading-tight font-extrabold">Драфт-дуэль</span>
          <span className="relative mt-0.5 text-[11px] leading-snug text-muted">Captains Mode 5×5, ладдер месяца</span>
        </button>
      </motion.div>

      <Suspense fallback={null}>
        {open === 'hook' && <HookGame onClose={() => setOpen(null)} />}
        {open === 'guess' && <GuessGame onClose={() => setOpen(null)} />}
        {open === 'analysis' && <AnalysisScreen onClose={() => setOpen(null)} />}
        {open === 'draft' && <DraftScreen onClose={() => setOpen(null)} />}
      </Suspense>
    </div>
  )
}

/** Attempts as dots: filled ones are left */
function Tries({ s, color }: { s?: Stats; color: string }) {
  if (!s) return null
  return (
    <span className="flex items-center gap-1">
      {Array.from({ length: s.plays_per_day }, (_, i) => (
        <span key={i} className="h-2 w-2 rounded-full" style={{ background: i < s.plays_left ? color : '#ffffff22' }} />
      ))}
    </span>
  )
}

function Chip({ children, tone }: { children: ReactNode; tone: string }) {
  return (
    <span className="rounded-lg border px-2 py-1 text-[11px] font-extrabold" style={{ borderColor: `${tone}55`, color: tone, background: `${tone}14` }}>
      {children}
    </span>
  )
}

function PlayButton({ s, onPlay, tone, text }: { s?: Stats; onPlay: () => void; tone: string; text: string }) {
  const can = !s || s.plays_left > 0
  return (
    <button
      type="button"
      disabled={!can}
      onClick={onPlay}
      className="press flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-extrabold disabled:!bg-surface-2 disabled:!text-muted disabled:shadow-none"
      style={{ background: tone, color: '#0b0d12', boxShadow: `0 6px 24px ${tone}55` }}
    >
      {can ? (
        <>
          {text} <Coin size={14} />
        </>
      ) : (
        'Попытки закончились — завтра снова'
      )}
    </button>
  )
}

function HookCard({ stats, onPlay }: { stats?: Stats; onPlay: () => void }) {
  const tone = '#FF4D55'
  return (
    <div
      className="relative overflow-hidden rounded-[22px] border border-[#5a1d22]"
      style={{ background: 'radial-gradient(circle at 85% 30%, #7a1a20 0%, #2a0c10 45%, #110709 100%)' }}
    >
      {/* Radiant Ancient in the back, Pudge in front of it */}
      <div className="pointer-events-none absolute -top-4 -right-6 h-[200px] w-[200px]">
        <Suspense fallback={null}>
          <AncientScene />
        </Suspense>
      </div>
      <img src="/media/pudge.png" alt="" className="pointer-events-none absolute top-6 -right-12 h-[190px] w-[190px] object-contain drop-shadow-[0_10px_30px_rgba(0,0,0,.6)]" />
      <div className="relative flex flex-col gap-3 p-4">
        <div className="max-w-[58%]">
          <div className="flex items-center gap-2">
            <Tries s={stats} color={tone} />
          </div>
          <div className="mt-2 font-display text-[26px] leading-none font-bold">Хук Пуджа</div>
          <div className="mt-2 text-xs leading-relaxed text-[#e6c2c4]">
            Тащи вражеских крипов, ищи золотого, не трогай своих. Комбо до ×3, к концу — быстрее.
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Chip tone="#F5C542">Рекорд {stats?.best ?? 0}</Chip>
          <Chip tone={tone}>30 секунд</Chip>
          <Chip tone="#8FD9A8">комбо ×3</Chip>
        </div>
        <PlayButton s={stats} onPlay={onPlay} tone={tone} text="Бросить хук" />
      </div>
    </div>
  )
}

function GuessCard({ stats, onPlay }: { stats?: Stats; onPlay: () => void }) {
  const tone = '#6CC4FF'
  return (
    <div
      className="relative overflow-hidden rounded-[22px] border border-[#1f3d57]"
      style={{ background: 'radial-gradient(circle at 80% 35%, #173a5a 0%, #0c1a28 45%, #080d13 100%)' }}
    >
      {/* live 3D silhouette of Invoker, like in the game itself */}
      <div className="pointer-events-none absolute top-0 -right-4 h-[230px] w-[190px]">
        <Suspense fallback={null}>
          <SilhouetteScene body={INVOKER + 'body.glb'} items={INVOKER_ITEMS} hidden spin={0.7} view="front" round={0} urgency={0} />
        </Suspense>
        <span className="absolute top-[36%] left-1/2 -translate-x-1/2 font-display text-5xl font-bold text-ice drop-shadow-[0_0_12px_#6cc4ff]">?</span>
      </div>
      <div className="relative flex flex-col gap-3 p-4">
        <div className="max-w-[58%]">
          <Tries s={stats} color={tone} />
          <div className="mt-2 font-display text-[26px] leading-none font-bold">Угадай героя</div>
          <div className="mt-2 text-xs leading-relaxed text-[#bcd6ea]">
            41 герой по 3D-силуэту. Серия до первой ошибки — дальше хитрее ракурс и без предметов.
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Chip tone="#F5C542">Лучшая серия {stats?.best ?? 0}</Chip>
          <Chip tone={tone}>до 6 вариантов</Chip>
          <Chip tone="#C8A2FF">5 ракурсов</Chip>
        </div>
        <PlayButton s={stats} onPlay={onPlay} tone={tone} text="Начать серию" />
      </div>
    </div>
  )
}
