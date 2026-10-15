import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { Icon } from '../components/icons'
import { Card, Segmented } from '../components/ui'
import { ContestAdmin } from './ContestAdmin'
import { ShopAdmin } from './ShopAdmin'
import { ChatAdmin } from './ChatAdmin'
import { api } from '../lib/api'
import { fmt, short } from '../lib/format'

// Admin panel: ADMIN_IDS only (the server checks every request; the button in the profile is just an entry point).

type Tab = 'stats' | 'shop' | 'chat' | 'prizes' | 'analysis' | 'contest'

const PRIZE: Record<string, string> = { arcana: 'Аркана', immortal: 'Immortal', dota_plus: 'Dota Plus' }

export function AdminScreen({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('stats')
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ground">
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <button type="button" aria-label="Закрыть" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface">
          <Icon name="back" size={20} />
        </button>
        <div className="font-display text-lg font-bold">Админка</div>
      </div>
      <div className="px-4 pb-2">
        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            ['stats', 'Обзор'],
            ['shop', 'Магазин'],
            ['chat', 'Чат'],
            ['prizes', 'Призы'],
            ['analysis', 'Анализ'],
            ['contest', 'Конкурс'],
          ]}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-[max(20px,env(safe-area-inset-bottom))]">
        {tab === 'stats' && <Stats />}
        {tab === 'prizes' && <Prizes />}
        {tab === 'analysis' && <Analysis />}
        {tab === 'contest' && <ContestAdmin />}
        {tab === 'shop' && <ShopAdmin />}
        {tab === 'chat' && <ChatAdmin />}
      </div>
    </div>
  )
}

function Tile({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <span className="text-[11px] font-bold text-muted">{label}</span>
      <span className={`font-display text-xl font-bold ${accent ?? ''}`}>{typeof value === 'number' ? fmt(value) : value}</span>
    </Card>
  )
}

function H({ children }: { children: ReactNode }) {
  return <h3 className="mt-4 mb-2 text-[13px] font-extrabold tracking-wide text-muted uppercase">{children}</h3>
}

function Stats() {
  const { data: s, dataUpdatedAt } = useQuery({ queryKey: ['admin', 'stats'], queryFn: api.adminStats, refetchInterval: 30_000 })
  if (!s) return <div className="p-8 text-center text-sm text-muted">Загружаем…</div>
  const u = s.users
  return (
    <div>
      <div className="grid grid-cols-2 gap-2">
        <Tile label="Онлайн (5 мин)" value={u.online} accent="text-ok" />
        <Tile label="Всего игроков" value={u.total} />
        <Tile label="Заходили сегодня" value={u.today} />
        <Tile label="За 7 дней" value={u.week} />
        <Tile label="Новых сегодня" value={u.new_today} />
        <Tile label="Новых за 7 дней" value={u.new_week} />
        <Tile label="Подписаны на канал" value={u.subscribed} />
        <Tile label="Steam привязан / проверен" value={`${fmt(u.steam_linked)} / ${fmt(u.steam_verified)}`} />
        <Tile label="Засчитанных рефералов" value={u.referred} />
        <Tile label="Гильдий" value={s.guilds} />
      </div>

      <H>Задания</H>
      <Card className="divide-y divide-line">
        <div className="flex px-3 py-2 text-[11px] font-bold text-muted">
          <span className="flex-1">Задание</span>
          <span className="w-16 text-right">всего</span>
          <span className="w-16 text-right">сегодня</span>
        </div>
        <Row title="Награда дня" total={null} today={s.daily_claims_today} />
        {s.tasks.map((t) => (
          <Row key={t.id} title={t.title} total={t.done} today={t.today} />
        ))}
      </Card>

      <H>Мини-игры сегодня</H>
      <div className="grid grid-cols-2 gap-2">
        <Tile label="Хук: игроков / игр" value={`${s.games.hook.players_today} / ${s.games.hook.plays_today}`} />
        <Tile label="Угадай: игроков / серий" value={`${s.games.guess.players_today} / ${s.games.guess.plays_today}`} />
      </div>

      <H>Экономика</H>
      <div className="grid grid-cols-3 gap-2">
        <Tile label="ELT на руках" value={short(s.economy.coins)} />
        <Tile label="Заработано" value={short(s.economy.earned_total)} />
        <Tile label="Душ" value={short(s.economy.souls)} />
        <Tile label="Подписок анализа" value={s.analysis.active_subs} />
        <Tile label="Звёзд получено" value={s.analysis.stars_total} />
      </div>
      <div className="mt-3 text-center text-[11px] text-muted">Обновлено {new Date(dataUpdatedAt).toLocaleTimeString('ru-RU')} · каждые 30 с</div>
    </div>
  )
}

function Row({ title, total, today }: { title: string; total: number | null; today: number }) {
  return (
    <div className="flex items-center px-3 py-2.5 text-sm">
      <span className="flex-1 truncate font-bold">{title}</span>
      <span className="w-16 text-right font-extrabold">{total === null ? '—' : fmt(total)}</span>
      <span className="w-16 text-right text-muted">{fmt(today)}</span>
    </div>
  )
}

function Prizes() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['admin', 'prizes'], queryFn: api.adminPrizes })
  const sent = useMutation({ mutationFn: api.adminPrizeSent, onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin', 'prizes'] }) })
  if (!data) return null
  if (data.prizes.length === 0)
    return <Card className="mt-2 p-4 text-center text-sm text-muted">Призов месяца пока нет — появятся после конца первого месяца</Card>
  return (
    <div className="flex flex-col gap-2 pt-1">
      {data.prizes.map((p) => (
        <Card key={p.id} className="flex items-center gap-3 p-3">
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="text-sm font-extrabold">
              {p.place} место · {PRIZE[p.prize] ?? p.prize}
              <span className="ml-1 text-xs font-bold text-muted">{p.period.slice(2)}</span>
            </span>
            <span className="truncate text-xs text-muted">
              {p.name} · Steam: {p.persona ?? '—'}
            </span>
            {p.steam_id && (
              <a href={`https://steamcommunity.com/profiles/${p.steam_id}`} target="_blank" rel="noreferrer" className="text-xs font-bold text-ice">
                Профиль Steam
              </a>
            )}
          </div>
          {p.status === 'sent' ? (
            <span className="text-xs font-extrabold text-ok">выдан</span>
          ) : (
            <button type="button" onClick={() => sent.mutate(p.id)} className="press rounded-lg bg-red px-3 py-2 text-xs font-extrabold text-white">
              Выдан
            </button>
          )}
        </Card>
      ))}
    </div>
  )
}

function Analysis() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['admin', 'analysis'], queryFn: api.adminAnalysis })
  const [price, setPrice] = useState('')
  const save = useMutation({
    mutationFn: api.adminAnalysisSettings,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin', 'analysis'] }),
  })
  const refund = useMutation({ mutationFn: api.adminRefund, onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin', 'analysis'] }) })
  if (!data) return null
  const st = data.settings
  return (
    <div className="flex flex-col gap-3 pt-1">
      <Card className="flex items-center justify-between p-3">
        <div className="flex flex-col">
          <span className="text-sm font-extrabold">Бета: анализ бесплатно всем</span>
          <span className="text-xs text-muted">Выключите — заработают лимит {st.free_per_week}/неделю и подписка</span>
        </div>
        <button
          type="button"
          onClick={() => save.mutate({ beta_free: !st.beta_free })}
          className={`press h-8 w-14 rounded-full p-1 transition ${st.beta_free ? 'bg-ok' : 'bg-surface-2'}`}
        >
          <span className={`block h-6 w-6 rounded-full bg-white transition ${st.beta_free ? 'translate-x-6' : ''}`} />
        </button>
      </Card>
      <Card className="flex items-center gap-2 p-3">
        <span className="flex-1 text-sm font-extrabold">Цена подписки: {st.price} ⭐ / 30 дней</span>
        <input
          value={price}
          onChange={(e) => setPrice(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          placeholder={String(st.price)}
          className="w-20 rounded-lg border border-line-2 bg-surface px-2 py-1.5 text-sm outline-none"
        />
        <button
          type="button"
          disabled={!price}
          onClick={() => save.mutate({ price: Number(price) }, { onSuccess: () => setPrice('') })}
          className="press rounded-lg bg-red px-3 py-1.5 text-xs font-extrabold text-white disabled:opacity-40"
        >
          OK
        </button>
      </Card>
      {save.error && <div className="text-xs font-bold text-[#FF8A90]">Цена: от 1 до 10000 ⭐</div>}

      <H>Подписчики ({data.subscribers.filter((s) => s.active).length} активных)</H>
      {data.subscribers.length === 0 && <Card className="p-3 text-center text-sm text-muted">Пока нет</Card>}
      {data.subscribers.map((s) => (
        <Card key={s.user_id} className="flex items-center gap-2 p-3 text-sm">
          <span className="flex-1 truncate font-bold">{s.name}</span>
          <span className={`text-xs ${s.active ? 'text-ok' : 'text-muted'}`}>до {new Date(s.expires_ms).toLocaleDateString('ru-RU')}</span>
          <span className="w-14 text-right text-xs font-extrabold">{s.paid} ⭐</span>
        </Card>
      ))}

      <H>Платежи</H>
      {data.payments.map((p) => (
        <Card key={p.charge_id} className="flex items-center gap-2 p-3 text-xs">
          <span className="flex-1 truncate">
            {p.user_id} · {new Date(p.created_ms).toLocaleDateString('ru-RU')} · {p.amount} ⭐
          </span>
          {p.refunded_ms ? (
            <span className="font-bold text-muted">возвращён</span>
          ) : (
            <button
              type="button"
              onClick={() => confirm(`Вернуть ${p.amount} ⭐ пользователю ${p.user_id}?`) && refund.mutate(p.charge_id)}
              className="press rounded-lg border border-line-2 px-2 py-1 font-bold"
            >
              Возврат
            </button>
          )}
        </Card>
      ))}
    </div>
  )
}
