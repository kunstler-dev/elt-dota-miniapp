import { useMutation, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'

import { Coin, Icon } from '../components/icons'
import { Progress } from '../components/ui'
import { api, type GuessQuestion } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'

const SilhouetteScene = lazy(() => import('./SilhouetteScene').then((m) => ({ default: m.SilhouetteScene })))

type Reveal = { correct: boolean; timeout: boolean; name: string; answerId: string; picked: string | null; reward: number }

const VIEW_HINT: Record<GuessQuestion['view'], string> = {
  front: '',
  back: 'Со спины',
  high: 'Вид сверху',
  close: 'Крупный план',
  odd: 'Неудобный ракурс',
}

/** Streak: guess in a row until the first mistake; each next hero is harder. */
export function GuessGame({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const [session, setSession] = useState<string | null>(null)
  const [playsLeft, setPlaysLeft] = useState(0)
  const [q, setQ] = useState<GuessQuestion | null>(null)
  const [left, setLeft] = useState(0)
  const [reveal, setReveal] = useState<Reveal | null>(null)
  const [over, setOver] = useState<{ streak: number; total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const total = useRef(0)
  const pendingNext = useRef<GuessQuestion | null>(null)

  const start = useMutation({
    mutationFn: api.guessStart,
    onSuccess: (r) => {
      total.current = 0
      setOver(null)
      setReveal(null)
      setSession(r.session)
      setPlaysLeft(r.plays_left)
      setQ(r.question)
      setLeft(r.question.seconds)
    },
    onError: (e) => setError(e instanceof Error && e.message === 'no_plays_left' ? 'Серии на сегодня закончились' : 'Не удалось начать'),
  })
  const send = useMutation({
    mutationFn: (hero: string | null) => api.guessAnswer(session!, hero ?? ''),
    onSuccess: (r, hero) => {
      haptic(r.correct ? 'heavy' : 'medium')
      applyState(r.state)
      total.current += r.reward
      setReveal({ correct: r.correct, timeout: r.timeout, name: r.answer.name, answerId: r.answer.id, picked: hero, reward: r.reward })
      pendingNext.current = r.next
      if (!r.next) {
        setOver({ streak: r.streak, total: total.current })
        void qc.invalidateQueries({ queryKey: ['games'] })
      }
    },
  })

  useEffect(() => {
    start.mutate()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // question timer
  useEffect(() => {
    if (!q || reveal) return
    const startedAt = performance.now()
    const id = setInterval(() => {
      const l = Math.max(0, q.seconds - (performance.now() - startedAt) / 1000)
      setLeft(l)
      if (l <= 0) {
        clearInterval(id)
        send.mutate(null)
      }
    }, 100)
    return () => clearInterval(id)
  }, [q, reveal]) // eslint-disable-line react-hooks/exhaustive-deps

  // after a correct answer: a short pause for the reveal, then the next hero
  useEffect(() => {
    if (!reveal?.correct || !pendingNext.current) return
    const t = setTimeout(() => {
      const next = pendingNext.current!
      pendingNext.current = null
      setReveal(null)
      setQ(next)
      setLeft(next.seconds)
    }, 1400)
    return () => clearTimeout(t)
  }, [reveal])

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ground">
      <div className="flex items-center justify-between px-4 pt-3 pb-2">
        <button type="button" aria-label="Закрыть" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface">
          <Icon name="back" size={20} />
        </button>
        <div className="flex flex-col items-center">
          <div className="font-display text-lg font-bold">Угадай героя</div>
          {q && (
            <div className="text-[11px] text-muted">
              серия {q.streak} · {VIEW_HINT[q.view] || 'спереди'}
              {q.model.items.length === 0 && ' · без предметов'}
            </div>
          )}
        </div>
        <div className="flex w-10 flex-col items-end text-[11px] font-bold">
          {q && (
            <span className="flex items-center gap-0.5 text-ice">
              <Coin size={11} />
              {fmt(q.reward)}
            </span>
          )}
        </div>
      </div>

      <div className="px-4">
        <Progress value={q && !reveal ? left / q.seconds : 0} color={left < 4 ? 'bg-red' : 'bg-gold'} height={6} />
      </div>

      <div className="relative min-h-0 flex-1">
        <span
          className="pointer-events-none absolute rounded-[50%]"
          style={{ left: '15%', right: '15%', top: '12%', bottom: '18%', background: 'radial-gradient(closest-side, rgba(212,37,47,.35), transparent)' }}
        />
        {q && (
          <Suspense fallback={null}>
            <SilhouetteScene body={q.model.body} items={q.model.items} hidden={!reveal} spin={q.spin} view={q.view} round={q.round} urgency={1 - left / q.seconds} />
          </Suspense>
        )}
        {reveal && (
          <div className="absolute inset-x-0 bottom-3 text-center">
            <div className={`font-display text-xl font-bold ${reveal.correct ? 'text-ok' : 'text-[#FF8A90]'}`}>
              {reveal.correct ? 'Верно!' : reveal.timeout || !reveal.picked ? 'Время вышло' : 'Мимо'} — {reveal.name}
            </div>
            {reveal.reward > 0 && (
              <div className="mt-1 flex items-center justify-center gap-1.5 font-bold">
                <Coin size={16} />+{fmt(reveal.reward)}
              </div>
            )}
          </div>
        )}
        {over && (
          <div className="absolute inset-x-4 top-4 rounded-2xl border border-line bg-surface/95 p-4 text-center">
            <div className="font-display text-lg font-bold">Серия: {over.streak}</div>
            <div className="mt-1 flex items-center justify-center gap-1.5 text-sm font-bold">
              Заработано <Coin size={14} /> {fmt(over.total)}
            </div>
            <div className="mt-1 text-xs text-muted">Очки рейтинга считаются по лучшей серии дня</div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 px-4 pt-2 pb-[max(16px,env(safe-area-inset-bottom))]">
        {error && <div className="col-span-2 text-center text-sm font-bold">{error}</div>}
        {q?.options.map((o) => {
          const right = reveal && o.id === reveal.answerId
          const wrongPick = reveal && o.id === reveal.picked && !reveal.correct
          return (
            <button
              key={o.id}
              type="button"
              disabled={!!reveal || send.isPending}
              onClick={() => send.mutate(o.id)}
              className={`press rounded-xl border py-3.5 text-sm font-extrabold ${
                right ? 'border-ok bg-[#12301F] text-ok' : wrongPick ? 'border-red bg-red-deep text-[#FF8A90]' : 'border-line-2 bg-surface'
              }`}
            >
              {o.name}
            </button>
          )
        })}
        {over && (
          <button
            type="button"
            disabled={start.isPending}
            onClick={() => (playsLeft > 0 ? start.mutate() : onClose())}
            className="press col-span-2 rounded-xl bg-red py-3.5 text-[15px] font-extrabold text-white"
          >
            {playsLeft > 0 ? `Новая серия (осталось ${playsLeft})` : 'Готово'}
          </button>
        )}
      </div>
    </div>
  )
}
