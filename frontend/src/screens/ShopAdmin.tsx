import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Soul } from '../components/icons'
import { Card, Segmented } from '../components/ui'
import { api, type AdminShop, type ShopItem } from '../lib/api'
import { fmt } from '../lib/format'
import { openExternal } from '../lib/telegram'
import { KIND } from './ShopScreen'

type View = 'orders' | 'items'

const usd = (cents: number | null) => (cents == null ? '—' : `$${(cents / 100).toFixed(2)}`)

/** Shop admin: orders (delivered / cancel with a souls refund), souls-per-dollar rate, prices from the Steam market. */
export function ShopAdmin() {
  const [view, setView] = useState<View>('orders')
  const { data } = useQuery({
    queryKey: ['admin', 'shop'],
    queryFn: api.adminShop,
    refetchInterval: (q) => (q.state.data?.refreshing ? 5000 : false),
  })
  if (!data) return null
  const pending = data.orders.filter((o) => o.status === 'pending').length
  return (
    <div className="flex flex-col gap-2.5 pt-1">
      <Segmented<View>
        value={view}
        onChange={setView}
        options={[
          ['orders', `Заказы${pending ? ` (${pending})` : ''}`],
          ['items', 'Витрина'],
        ]}
      />
      {view === 'orders' ? (
        <Orders orders={data.orders} />
      ) : (
        <>
          <Pricing data={data} />
          {data.items.map((it) => (
            <ItemRow key={it.id} item={it} />
          ))}
        </>
      )}
    </div>
  )
}

function Pricing({ data }: { data: AdminShop }) {
  const qc = useQueryClient()
  const [rate, setRate] = useState('')
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['admin', 'shop'] })
    void qc.invalidateQueries({ queryKey: ['shop'] })
  }
  const saveRate = useMutation({ mutationFn: api.adminShopRate, onSuccess: () => (setRate(''), refresh()) })
  const pull = useMutation({ mutationFn: api.adminShopRefresh, onSuccess: refresh })
  return (
    <Card className="flex flex-col gap-2 p-3 text-xs">
      <div className="flex items-center gap-2">
        <span className="flex-1 text-sm font-extrabold">
          Курс: 1 $ = {fmt(data.souls_per_usd)} <Soul size={12} className="inline" />
        </span>
        <input
          value={rate}
          onChange={(e) => setRate(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder={String(data.souls_per_usd)}
          className="w-20 rounded-lg border border-line-2 bg-surface-2 px-2 py-1.5 text-sm outline-none"
        />
        <button
          type="button"
          disabled={!rate || saveRate.isPending}
          onClick={() => saveRate.mutate(Number(rate))}
          className="press rounded-lg bg-red px-3 py-1.5 font-extrabold text-white disabled:opacity-40"
        >
          OK
        </button>
      </div>
      <span className="text-muted">Цена в душах = цена на торговой площадке Steam × курс. Цены обновляются раз в сутки.</span>
      <button
        type="button"
        disabled={data.refreshing || pull.isPending}
        onClick={() => pull.mutate()}
        className="press rounded-lg border border-line-2 py-2 font-bold disabled:opacity-50"
      >
        {data.refreshing ? 'Обновляем цены с площадки… (~2 мин)' : 'Обновить цены с площадки сейчас'}
      </button>
    </Card>
  )
}

function Orders({ orders }: { orders: AdminShop['orders'] }) {
  const qc = useQueryClient()
  const close = useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: 'sent' | 'cancelled'; note?: string }) => api.adminShopOrder(id, status, note),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin', 'shop'] }),
  })
  if (orders.length === 0) return <Card className="p-4 text-center text-sm text-muted">Заказов пока нет</Card>
  return (
    <>
      {orders.map((o) => (
        <Card key={o.id} className="flex flex-col gap-1.5 p-3 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-extrabold">
              #{o.id} {o.title}
            </span>
            <span className="flex items-center gap-1 font-extrabold">
              <Soul size={12} />
              {fmt(o.price)}
            </span>
          </div>
          {o.note && <span className="text-ink">«{o.note}»</span>}
          <span className="text-muted">
            {o.user} · Steam: {o.persona ?? '—'} · {new Date(o.created_ms).toLocaleString('ru-RU')}
          </span>
          <div className="flex gap-3">
            {o.steam_id && (
              <button type="button" onClick={() => openExternal(`https://steamcommunity.com/profiles/${o.steam_id}`)} className="font-bold text-ice">
                Профиль Steam
              </button>
            )}
            <button
              type="button"
              onClick={() => openExternal(`https://steamcommunity.com/market/listings/570/${encodeURIComponent(o.title)}`)}
              className="font-bold text-ice"
            >
              На площадке
            </button>
          </div>
          {o.status === 'pending' ? (
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => close.mutate({ id: o.id, status: 'sent' })}
                className="press flex-1 rounded-lg bg-[#12301F] py-2 font-bold text-ok"
              >
                Выдан
              </button>
              <button
                type="button"
                onClick={() => {
                  const note = prompt('Причина отмены (увидит игрок)', 'Не получилось выдать')
                  if (note !== null) close.mutate({ id: o.id, status: 'cancelled', note })
                }}
                className="press flex-1 rounded-lg bg-red-deep py-2 font-bold text-[#FF8A90]"
              >
                Отменить и вернуть души
              </button>
            </div>
          ) : (
            <span className={`font-bold ${o.status === 'sent' ? 'text-ok' : 'text-muted'}`}>
              {o.status === 'sent' ? 'выдан' : 'отменён'}
              {o.admin_note ? ` · ${o.admin_note}` : ''}
            </span>
          )}
        </Card>
      ))}
    </>
  )
}

function ItemRow({ item }: { item: ShopItem }) {
  const qc = useQueryClient()
  const [stock, setStock] = useState(item.stock === null ? '' : String(item.stock))
  const save = useMutation({
    mutationFn: (patch: { stock?: number; unlimited?: boolean; active?: boolean }) => api.adminShopItem(item.id, patch),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'shop'] })
      void qc.invalidateQueries({ queryKey: ['shop'] })
    },
  })
  const dirty = stock !== (item.stock === null ? '' : String(item.stock))
  const k = KIND[item.kind] ?? KIND.other
  return (
    <Card className={`flex flex-col gap-2 p-3 text-xs ${item.active ? '' : 'opacity-50'}`}>
      <div className="flex items-center gap-2.5">
        <img src={item.image ?? k.image} alt="" className="h-10 w-10 rounded-lg object-contain" style={{ background: `${k.color}22` }} />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-extrabold">{item.title}</span>
          <span className="text-muted">
            <span style={{ color: k.color }}>{k.name}</span> · {usd(item.usd_cents)} ·{' '}
            {item.listings === 0 ? <span className="text-[#FF8A90]">нет лотов</span> : `лотов: ${item.listings ?? '?'}`}
          </span>
        </div>
        <span className="flex items-center gap-1 font-extrabold">
          <Soul size={12} />
          {fmt(item.price)}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <input
          value={stock}
          onChange={(e) => setStock(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder="наличие: без лимита"
          className="min-w-0 flex-1 rounded-lg border border-line-2 bg-surface-2 px-2 py-1.5 outline-none"
        />
        <button
          type="button"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate(stock === '' ? { unlimited: true } : { stock: Number(stock) })}
          className="press rounded-lg bg-red px-3 py-1.5 font-extrabold text-white disabled:opacity-40"
        >
          OK
        </button>
        <button
          type="button"
          onClick={() => save.mutate({ active: !item.active })}
          className="press rounded-lg border border-line-2 px-2.5 py-1.5 font-bold"
        >
          {item.active ? 'Скрыть' : 'Показать'}
        </button>
      </div>
    </Card>
  )
}
