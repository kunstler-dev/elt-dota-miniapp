import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Avatar } from '../components/Avatar'
import { Card, ScreenTitle } from '../components/ui'
import { api, ApiError, type ContestEntry } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic, openExternal } from '../lib/telegram'

// Video contest: ELT videos on TikTok / YouTube Shorts / YouTube, the top 10 by views share 100,000 RUB
// (as Steam top-up codes or Dota 2 items, not cash).

const ERR: Record<string, string> = {
  bad_url: 'Нужна ссылка на ролик TikTok, YouTube Shorts или YouTube',
  already_submitted: 'Этот ролик уже добавлен',
  too_many_entries: 'Максимум роликов уже добавлен',
  contest_closed: 'Приём роликов закрыт',
  steam_not_verified: 'Участвовать могут только игроки с проверенным Steam',
}
const STATUS: Record<ContestEntry['status'], [string, string]> = {
  pending: ['на проверке', 'text-gold'],
  approved: ['засчитан', 'text-ok'],
  rejected: ['отклонён', 'text-[#FF8A90]'],
}
const PLATFORM: Record<ContestEntry['platform'], string> = { youtube: 'YouTube', tiktok: 'TikTok' }

const RULES = [
  'Снимите ролик про ELT: геймплей бота, Хук Пуджа, Угадай героя, свой Арсенал или реакцию на выигрыш. Подойдут TikTok, YouTube Shorts и обычные видео на YouTube.',
  'В ролике или описании — ссылка на бота или канал @ELT_TG и хэштег #ELTdota. Видео должно быть публичным и опубликованным во время конкурса.',
  'Только свой оригинальный контент: перезаливы чужих роликов не засчитываются.',
  'В зачёт идёт сумма просмотров всех ваших роликов (до {max} штук). Просмотры обновляются автоматически каждые 2 часа.',
  'Накрутка просмотров, боты и покупные просмотры — дисквалификация без права повторного участия.',
  'Участвовать могут игроки с привязанным и проверенным Steam-аккаунтом. Перед выдачей призов администрация вручную проверяет ролики победителей.',
  'Призы выдаются кодами пополнения кошелька Steam или предметами Dota 2 на эквивалентную сумму — не деньгами. Выдача — в течение 7 дней после конца конкурса.',
]

function useCountdown(to: number | null) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])
  if (!to) return ''
  const d = Math.max(0, to - now)
  const days = Math.floor(d / 86_400_000)
  const h = Math.floor((d % 86_400_000) / 3_600_000)
  const m = Math.floor((d % 3_600_000) / 60_000)
  return days > 0 ? `${days} д ${h} ч` : `${h} ч ${m} мин`
}

export function ContestScreen() {
  const qc = useQueryClient()
  const { data: c } = useQuery({ queryKey: ['contest'], queryFn: api.contest, refetchInterval: 60_000 })
  const [url, setUrl] = useState('')
  const [rules, setRules] = useState(false)
  const left = useCountdown(c?.end_ms ?? null)
  const submit = useMutation({
    mutationFn: () => api.contestSubmit(url),
    onSuccess: () => {
      haptic('medium')
      setUrl('')
      void qc.invalidateQueries({ queryKey: ['contest'] })
    },
  })
  const remove = useMutation({ mutationFn: api.contestRemove, onSuccess: () => void qc.invalidateQueries({ queryKey: ['contest'] }) })

  const active = c?.phase === 'active'
  const canAdd = active && c.me.entries.filter((e) => e.status !== 'rejected').length < c.max_entries

  return (
    <div className="flex flex-col gap-4 px-4 pt-3.5 pb-6">
      <ScreenTitle title="Видеоконкурс" subtitle="Снимай ролики про ELT — топ-10 по просмотрам" back />

      <div className="relative overflow-hidden rounded-[20px] border border-line">
        <img src="/media/contest.jpg" alt="Конкурс на 100 000 ₽" className="block w-full" />
        {c && (
          <span className="absolute top-3 right-3 rounded-lg bg-black/75 px-2.5 py-1 text-[11px] font-extrabold">
            {c.phase === 'soon' ? 'старт скоро' : c.phase === 'active' ? `до конца ${left}` : 'конкурс завершён'}
          </span>
        )}
      </div>

      <Card className="p-3">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-sm font-extrabold">Призы — 100 000 ₽</span>
          <span className="text-[11px] text-muted">кодами Steam / предметами</span>
        </div>
        <div className="grid grid-cols-5 gap-1.5">
          {c?.prizes.map((p, i) => (
            <div key={i} className={`flex flex-col items-center rounded-lg py-1.5 ${i === 0 ? 'bg-[#2A2210] text-gold' : 'bg-surface-2'}`}>
              <span className="text-[10px] font-bold opacity-70">{i + 1} место</span>
              <span className="text-[13px] font-extrabold">{p / 1000}к ₽</span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="flex flex-col gap-2.5 p-3">
        <span className="text-sm font-extrabold">Добавить ролик</span>
        {c?.phase === 'soon' && <span className="text-xs text-muted">Приём роликов откроется со стартом конкурса — следите за каналом @ELT_TG</span>}
        {c?.phase === 'finished' && <span className="text-xs text-muted">Конкурс завершён, идёт проверка победителей</span>}
        {active && (
          <>
            <div className="flex gap-2">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Ссылка на TikTok или YouTube"
                inputMode="url"
                className="min-w-0 flex-1 rounded-xl border border-line-2 bg-surface-2 px-3 py-2.5 text-sm outline-none focus:border-ice-line"
              />
              <button
                type="button"
                disabled={!canAdd || url.trim().length < 8 || submit.isPending}
                onClick={() => submit.mutate()}
                className="press rounded-xl bg-red px-4 text-sm font-extrabold text-white disabled:opacity-40"
              >
                Отправить
              </button>
            </div>
            <span className="text-[11px] text-muted">
              Не забудьте {c.hashtag} и ссылку на бота в описании · до {c.max_entries} роликов
            </span>
          </>
        )}
        {submit.error && (
          <span className="text-xs font-bold text-[#FF8A90]">{submit.error instanceof ApiError ? (ERR[submit.error.message] ?? 'Ошибка') : 'Ошибка'}</span>
        )}
        {c?.me.entries.map((e) => (
          <div key={e.id} className="flex items-center gap-2 rounded-xl bg-surface-2 p-2.5">
            <button type="button" onClick={() => openExternal(e.url)} className="flex min-w-0 flex-1 flex-col text-left">
              <span className="truncate text-[13px] font-bold">{e.title || e.url}</span>
              <span className="text-[11px] text-muted">
                {PLATFORM[e.platform]} · <span className={STATUS[e.status][1]}>{STATUS[e.status][0]}</span>
                {e.note ? ` · ${e.note}` : ''}
              </span>
            </button>
            <span className="text-right text-xs font-extrabold">
              {e.views_ms ? fmt(e.views) : '—'}
              <span className="block text-[10px] font-semibold text-muted">просм.</span>
            </span>
            {e.status === 'pending' && active && (
              <button type="button" aria-label="Удалить" onClick={() => remove.mutate(e.id)} className="press px-1 text-lg leading-none text-muted">
                ×
              </button>
            )}
          </div>
        ))}
      </Card>

      <div>
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-[13px] font-extrabold tracking-wide text-muted uppercase">Топ-10 по просмотрам</h3>
          {c?.me.rank && <span className="text-xs font-bold">вы на {c.me.rank} месте</span>}
        </div>
        {c && c.top.length === 0 && <Card className="p-4 text-center text-[13px] text-muted">Пока пусто — станьте первым</Card>}
        <div className="flex flex-col gap-1.5">
          {c?.top.map((r) => (
            <div key={r.id} className={`flex items-center gap-2.5 rounded-[14px] border bg-surface p-2.5 ${r.me ? 'border-ice-line' : 'border-line'}`}>
              <span className={`w-6 text-center font-display text-sm font-bold ${r.rank === 1 ? 'text-gold' : 'text-muted'}`}>{r.rank}</span>
              <Avatar name={r.name} photo={r.photo_url} size={32} />
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-bold">{r.name}</span>
                <span className="text-[11px] text-muted">
                  {r.videos} {r.videos === 1 ? 'ролик' : 'ролика'} · {r.prize_rub / 1000}к ₽
                </span>
              </div>
              <span className="text-[13px] font-extrabold">{fmt(r.views)}</span>
            </div>
          ))}
        </div>
      </div>

      <Card className="p-3">
        <button type="button" onClick={() => setRules((v) => !v)} className="flex w-full items-center justify-between text-sm font-extrabold">
          Правила конкурса
          <span className="text-muted">{rules ? '−' : '+'}</span>
        </button>
        {rules && (
          <ol className="mt-2.5 flex list-decimal flex-col gap-2 pl-5 text-xs leading-relaxed text-muted">
            {RULES.map((r) => (
              <li key={r}>{r.replace('{max}', String(c?.max_entries ?? 5))}</li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  )
}
