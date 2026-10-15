import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'

import { Bolt, Coin, Icon } from '../components/icons'
import { Card } from '../components/ui'
import { api, type Arsenal, type ArsenalChange, type GameState } from '../lib/api'
import { lookOf, rarity } from '../lib/arsenal'
import { fmt, short } from '../lib/format'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'
import { useLive } from '../store/useLive'

const Character3D = lazy(() => import('../components/Character3D').then((m) => ({ default: m.Character3D })))

/** Heroes (buy / tap with this one) and the selected hero's Arsenal with a 3D fitting room. */
export function ArsenalPanel() {
  const qc = useQueryClient()
  const live = useLive()
  const applyState = useGame((s) => s.applyState)
  const flush = useGame((s) => s.flush)
  const active = useGame((s) => s.snap?.active_hero ?? 'pudge')
  const [hero, setHero] = useState(active)
  const { data } = useQuery({ queryKey: ['arsenal', hero], queryFn: () => api.arsenal(hero) })
  const [slot, setSlot] = useState<string | null>(null)
  const [tryOn, setTryOn] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  function show(text: string) {
    setToast(text)
    setTimeout(() => setToast(null), 2600)
  }

  const onDone = (r: { arsenal: Arsenal; state: GameState }) => {
    applyState(r.state)
    qc.setQueryData(['arsenal', r.arsenal.hero], r.arsenal)
    setTryOn(null)
  }
  const onItem = (r: ArsenalChange) => {
    onDone(r)
  }
  const buyItem = useMutation({
    mutationFn: async (id: string) => {
      await flush()
      return api.buyItem(id)
    },
    onSuccess: (r) => {
      haptic('heavy')
      onItem(r)
    },
    onError: () => haptic('heavy'),
  })
  const equip = useMutation({
    mutationFn: api.equipItem,
    onSuccess: (r) => {
      haptic('medium')
      onItem(r)
    },
  })
  const buyHero = useMutation({
    mutationFn: async (id: string) => {
      await flush()
      return api.buyHero(id)
    },
    onSuccess: (r) => {
      haptic('heavy')
      onDone(r)
      show(`${r.arsenal.heroes.find((h) => h.active)?.name} теперь ваш!`)
    },
    onError: () => haptic('heavy'),
  })
  const select = useMutation({
    mutationFn: api.selectHero,
    onSuccess: (r) => {
      haptic('medium')
      onDone(r)
    },
  })

  if (!data || !live) return null
  const info = data.heroes.find((h) => h.id === data.hero)!
  const setById = new Map(data.sets.map((g) => [g.id, g]))
  const curSlot = slot && data.slots.some((s) => s.id === slot) ? slot : data.slots[0].id
  const slotItems = data.items.filter((i) => i.slot === curSlot).sort((a, b) => a.power - b.power)
  const full = data.full_set ? setById.get(data.full_set) : null
  const busy = buyItem.isPending || equip.isPending || buyHero.isPending || select.isPending

  return (
    <div className="flex flex-col gap-3">
      {toast && (
        <div className="fixed inset-x-4 top-3 z-50 mx-auto max-w-[440px] rounded-2xl border border-ice-line bg-[#0E1A24] px-4 py-3 text-center text-sm font-extrabold shadow-lg">
          {toast}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        {data.heroes.map((h) => (
          <button
            key={h.id}
            type="button"
            onClick={() => {
              setHero(h.id)
              setSlot(null)
              setTryOn(null)
            }}
            className={`relative flex min-w-0 flex-col overflow-hidden rounded-xl border ${
              h.id === data.hero ? 'border-ice' : 'border-line'
            } bg-surface`}
          >
            <img src={`/media/heroes/${h.id}.png`} alt="" className={`aspect-[16/9] w-full object-cover ${h.owned ? '' : 'opacity-50 grayscale'}`} />
            {h.active && <span className="absolute top-1 left-1 rounded bg-red px-1 text-[9px] font-extrabold">ТАПАЕТ</span>}
            <span className="truncate px-1.5 pt-1 text-[11px] font-bold">{h.name}</span>
            <span className="flex items-center gap-0.5 px-1.5 pb-1.5 text-[10px] text-muted">
              {h.owned ? (
                <>
                  <Bolt size={10} /> {h.tap_power}
                </>
              ) : (
                <>
                  <Coin size={10} /> {short(h.price)}
                </>
              )}
            </span>
          </button>
        ))}
      </div>

      <div className="relative -mx-4 h-[330px] overflow-hidden">
        <span
          className="pointer-events-none absolute rounded-[50%] border-2 border-[#5A1A1F] bg-[#1C0A0C]"
          style={{ left: '22%', right: '22%', bottom: 26, height: 56, boxShadow: '0 0 48px 6px rgba(212,37,47,.25)' }}
        />
        <Suspense fallback={null}>
          <Character3D mode="preview" look={lookOf(data, tryOn)} cameraDist={5.6} />
        </Suspense>
        <div className="pointer-events-none absolute top-2 left-4 flex flex-col gap-1">
          <span className="flex items-center gap-1.5 rounded-lg bg-black/60 px-2 py-1 text-[13px] font-extrabold">
            <Bolt size={14} />
            Сила тапа {data.tap_power}
          </span>
          {info.income > 0 && (
            <span className="rounded-lg bg-black/60 px-2 py-1 text-xs font-bold text-muted">+{short(info.income)} / час</span>
          )}
          {full && (
            <span className="rounded-lg bg-black/60 px-2 py-1 text-xs font-bold" style={{ color: rarity(full.tier).color }}>
              Сет «{full.name}» ×{full.bonus}
            </span>
          )}
        </div>
        <span className="pointer-events-none absolute right-4 bottom-2 text-[11px] text-muted">крутите пальцем</span>
      </div>

      {!info.owned ? (
        <Card className="flex flex-col gap-2 p-3.5">
          <div className="text-sm">
            <span className="font-extrabold">{info.name}</span>
            <span className="text-muted"> · сила тапа {info.power}, +{short(info.income)} в час</span>
          </div>
          <button
            type="button"
            disabled={busy || live.coins < info.price}
            onClick={() => buyHero.mutate(info.id)}
            className="press flex items-center justify-center gap-2 rounded-[12px] bg-red py-3 text-[15px] font-extrabold text-white disabled:bg-surface-2 disabled:text-muted"
          >
            Купить героя за <Coin size={16} /> {fmt(info.price)}
          </button>
        </Card>
      ) : (
        !info.active && (
          <button
            type="button"
            disabled={busy}
            onClick={() => select.mutate(info.id)}
            className="press rounded-[12px] border border-ice-line bg-[#0E1A24] py-3 text-sm font-extrabold text-ice"
          >
            Тапать за {info.name}
          </button>
        )
      )}

      <div className="grid grid-cols-4 gap-2">
        {data.slots.map((s) => {
          const worn = data.items.find((i) => i.id === data.equipped[s.id])
          const tier = worn ? (setById.get(worn.set)?.tier ?? 0) : 0
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => {
                setSlot(s.id)
                setTryOn(null)
              }}
              className={`flex flex-col items-center gap-1 rounded-xl border px-1 py-2 ${
                s.id === curSlot ? 'border-ice-line bg-[#0E1A24]' : 'border-line bg-surface'
              }`}
            >
              <span className="text-[12px] font-bold">{s.name}</span>
              <span className="h-1 w-6 rounded-full" style={{ background: rarity(tier).color }} />
            </button>
          )
        })}
      </div>

      <div className="flex flex-col gap-2">
        {slotItems.map((it) => {
          const g = setById.get(it.set)!
          const r = rarity(g.tier)
          const previewing = tryOn === it.id
          return (
            <Card key={it.id} className={`flex items-center gap-3 p-3 ${previewing ? 'border-ice-line' : ''}`}>
              <button
                type="button"
                onClick={() => setTryOn(previewing ? null : it.id)}
                className="flex min-w-0 flex-1 items-center gap-3 text-left"
              >
                <span className="h-10 w-1.5 shrink-0 rounded-full" style={{ background: r.color }} />
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="truncate text-sm font-bold">{g.name}</span>
                  <span className="text-xs" style={{ color: r.color }}>
                    {r.name}
                    {it.power > 0 && <span className="text-muted"> · +{it.power} к тапу</span>}
                  </span>
                </span>
                {!it.equipped && (
                  <Icon name={previewing ? 'done' : 'user'} size={16} className={previewing ? 'text-ice' : 'text-muted'} />
                )}
              </button>
              {it.equipped ? (
                <span className="rounded-[10px] bg-[#12301F] px-3 py-2 text-xs font-extrabold text-ok">Надето</span>
              ) : it.owned ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => equip.mutate(it.id)}
                  className="press rounded-[10px] border border-line-2 bg-surface-2 px-3 py-2 text-xs font-extrabold"
                >
                  Надеть
                </button>
              ) : (
                <button
                  type="button"
                  disabled={busy || !info.owned || live.coins < it.price}
                  onClick={() => buyItem.mutate(it.id)}
                  className="press flex items-center gap-1 rounded-[10px] bg-red px-3 py-2 text-xs font-extrabold text-white disabled:bg-surface-2 disabled:text-muted"
                >
                  <Coin size={12} />
                  {short(it.price)}
                </button>
              )}
            </Card>
          )
        })}
      </div>
      <p className="m-0 text-xs leading-relaxed text-muted">
        {info.owned
          ? 'Нажмите на предмет, чтобы примерить. Соберите сет целиком — получите множитель к силе тапа.'
          : 'Предметы можно примерить уже сейчас, а покупать — после покупки героя.'}
      </p>
    </div>
  )
}
