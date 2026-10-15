import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Icon, Soul } from '../components/icons'
import { Card, ScreenTitle } from '../components/ui'
import { api, ApiError, type ShopItem, type ShopKind, type ShopOrder } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'

// Souls shop: real Dota 2 items. Souls are charged immediately, an admin gifts the item in Steam.

export const KIND: Record<ShopKind, { name: string; color: string; image: string }> = {
  crimson: { name: 'Crimson', color: '#E0313B', image: '/media/juggernaut.webp' },
  golden: { name: 'Golden', color: '#F5C542', image: '/media/juggernaut.webp' },
  arcana: { name: 'Аркана', color: '#ADE55C', image: '/media/nevermore.webp' },
  immortal: { name: 'Бессмертный', color: '#E4AE39', image: '/media/juggernaut.webp' },
  other: { name: 'Предмет', color: '#B0C3D9', image: '/media/pudge.png' },
}
const STATUS: Record<ShopOrder['status'], [string, string]> = {
  pending: ['ждёт выдачи', 'text-gold'],
  sent: ['выдан', 'text-ok'],
  cancelled: ['отменён, души возвращены', 'text-muted'],
}
const ERR: Record<string, string> = {
  not_enough_souls: 'Не хватает душ',
  note_required: 'Напишите, что именно хотите получить',
  out_of_stock: 'Закончилось — загляните позже',
  too_many_pending: 'Дождитесь выдачи прошлых заказов',
  steam_not_verified: 'Покупки — только с проверенным Steam',
}

export function ShopScreen() {
  const souls = useGame((s) => s.snap?.souls ?? 0)
  const verified = useGame((s) => s.me?.steam?.verified)
  const { data } = useQuery({ queryKey: ['shop'], queryFn: api.shop })
  const { data: fr } = useQuery({ queryKey: ['friends'], queryFn: api.friends })
  const setTab = useGame((s) => s.setTab)
  const [pick, setPick] = useState<ShopItem | null>(null)
  const perFriend = fr?.rules.bonus ?? 500
  /** How many friends to invite to have enough souls for an item */
  const friendsFor = (price: number) => Math.max(0, Math.ceil((price - souls) / perFriend))
  const cheapest = data?.items.filter((i) => i.kind === 'arcana').reduce((m, i) => (m && m.price < i.price ? m : i), undefined as ShopItem | undefined)

  return (
    <div className="flex flex-col gap-4 px-4 pt-3.5 pb-6">
      <ScreenTitle title="Магазин" subtitle="Арканы и предметы Dota 2 за души" back />
      <Card className="flex items-center justify-between px-3.5 py-3">
        <span className="text-[13px] text-muted">Ваши души</span>
        <span className="flex items-center gap-1.5 font-display text-lg font-bold">
          <Soul size={20} />
          {fmt(souls)}
        </span>
      </Card>
      {/* friends are the main path to prizes */}
      <button
        type="button"
        onClick={() => setTab('friends')}
        className="press flex items-center gap-3 rounded-2xl border border-[#8A6A22] p-3.5 text-left"
        style={{ background: 'linear-gradient(120deg, #3a2a0c, #1a1408)' }}
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gold text-black"><Icon name="friends" size={22} /></span>
        <span className="flex flex-col">
          <span className="text-sm font-extrabold text-[#F5D27A]">Быстрее всего — друзья</span>
          <span className="text-xs leading-snug text-[#e8d9b0]">
            +{fmt(perFriend)} душ за друга, +{fmt(fr?.rules.bonus_premium ?? 1200)} с Premium и {Math.round((fr?.rules.share_l1 ?? 0.1) * 100)}% с их душ навсегда.
            {cheapest ? ` До арканы «${cheapest.title}» — ≈ ${friendsFor(cheapest.price)} друзей.` : ''}
          </span>
        </span>
      </button>
      {!verified && (
        <Card className="border-[#5A4A1A] bg-[#1E180B] p-3.5 text-[13px] leading-relaxed text-[#E8C46A]">
          Покупки доступны после проверки Steam: открытый профиль, аккаунт старше 180 дней и опыт в Dota 2.
        </Card>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        {data?.items.map((it) => {
          const k = KIND[it.kind]
          const soldOut = (it.stock !== null && it.stock <= 0) || it.listings === 0
          return (
            <button
              key={it.id}
              type="button"
              disabled={soldOut}
              onClick={() => setPick(it)}
              className="press flex flex-col overflow-hidden rounded-2xl border bg-surface text-left disabled:opacity-50"
              style={{ borderColor: `${k.color}55` }}
            >
              <div className="relative flex h-[104px] items-center justify-center" style={{ background: `radial-gradient(circle at 50% 70%, ${k.color}33, transparent 70%)` }}>
                <img src={it.image ?? k.image} alt="" className="h-full w-full object-contain p-1.5" />
                <span className="absolute top-2 left-2 rounded-md px-1.5 py-0.5 text-[10px] font-extrabold text-black" style={{ background: k.color }}>
                  {k.name}
                </span>
                {(it.stock !== null || soldOut) && (
                  <span className="absolute top-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-bold">
                    {soldOut ? 'нет в наличии' : `осталось ${it.stock}`}
                  </span>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-1 p-2.5">
                <span className="text-[13px] leading-tight font-extrabold">{it.title}</span>
                <span className="mt-auto flex items-center gap-1 text-sm font-extrabold">
                  <Soul size={14} />
                  {fmt(it.price)}
                </span>
                {souls < it.price && <span className="text-[10px] font-bold text-gold">≈ {friendsFor(it.price)} друзей</span>}
              </div>
            </button>
          )
        })}
      </div>

      {data && data.orders.length > 0 && (
        <div>
          <h3 className="mb-2 text-[13px] font-extrabold tracking-wide text-muted uppercase">Мои заказы</h3>
          <div className="flex flex-col gap-1.5">
            {data.orders.map((o) => (
              <Card key={o.id} className="flex flex-col gap-0.5 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-bold">{o.title}</span>
                  <span className="flex shrink-0 items-center gap-1 text-xs font-extrabold">
                    <Soul size={12} />
                    {fmt(o.price)}
                  </span>
                </div>
                {o.note && <span className="truncate text-xs text-muted">«{o.note}»</span>}
                <span className={`text-xs font-bold ${STATUS[o.status][1]}`}>
                  {STATUS[o.status][0]}
                  {o.admin_note ? ` · ${o.admin_note}` : ''}
                </span>
              </Card>
            ))}
          </div>
        </div>
      )}

      <p className="m-0 text-xs leading-relaxed text-muted">
        После покупки администратор добавит вас в друзья в Steam и отправит предмет подарком (обычно в течение 3 дней).
        Если выдать не получится — заказ отменяется, и души возвращаются.
      </p>

      {pick && <BuySheet item={pick} souls={souls} canBuy={!!verified} onClose={() => setPick(null)} />}
    </div>
  )
}

function BuySheet({ item, souls, canBuy, onClose }: { item: ShopItem; souls: number; canBuy: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const [note, setNote] = useState('')
  const buy = useMutation({
    mutationFn: () => api.shopBuy(item.id, note),
    onSuccess: (r) => {
      haptic('heavy')
      applyState(r.state)
      void qc.invalidateQueries({ queryKey: ['shop'] })
      onClose()
    },
  })
  const k = KIND[item.kind]
  const enough = souls >= item.price
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/60" onClick={onClose}>
      <div
        className="flex w-full flex-col gap-3 rounded-t-3xl border-t border-line bg-ground p-4 pb-[max(16px,env(safe-area-inset-bottom))]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3">
          <img src={item.image ?? k.image} alt="" className="h-16 w-16 rounded-xl object-contain" style={{ background: `${k.color}22` }} />
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] font-extrabold" style={{ color: k.color }}>
              {k.name}
            </span>
            <span className="font-display text-lg leading-tight font-bold">{item.title}</span>
          </div>
        </div>
        {item.about && <p className="m-0 text-[13px] leading-relaxed text-muted">{item.about}</p>}
        {item.need_note && (
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={280}
            rows={2}
            placeholder="Что именно хотите получить (герой, название предмета)"
            className="resize-none rounded-xl border border-line-2 bg-surface px-3 py-2.5 text-sm outline-none focus:border-ice-line"
          />
        )}
        <button
          type="button"
          disabled={!canBuy || !enough || buy.isPending || (item.need_note && note.trim().length < 3)}
          onClick={() => buy.mutate()}
          className="press flex items-center justify-center gap-1.5 rounded-[14px] bg-gold py-3.5 text-[15px] font-extrabold text-black disabled:opacity-40"
        >
          {enough ? 'Купить за' : 'Не хватает душ:'} <Soul size={16} /> {fmt(item.price)}
        </button>
        {buy.error && (
          <span className="text-center text-xs font-bold text-[#FF8A90]">
            {buy.error instanceof ApiError ? (ERR[buy.error.message] ?? 'Ошибка') : 'Ошибка'}
          </span>
        )}
      </div>
    </div>
  )
}
