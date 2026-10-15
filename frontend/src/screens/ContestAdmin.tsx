import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Card } from '../components/ui'
import { api, type AdminContest } from '../lib/api'
import { fmt } from '../lib/format'
import { openExternal } from '../lib/telegram'

type Entry = AdminContest['entries'][number]

/** Contest admin: start, video review, manual views (if TikTok/YouTube didn't return them), rejection. */
export function ContestAdmin() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['admin', 'contest'], queryFn: api.adminContest })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['admin', 'contest'] })
  const start = useMutation({ mutationFn: api.adminContestStart, onSuccess: refresh })
  const pull = useMutation({ mutationFn: api.adminContestRefresh, onSuccess: refresh })
  if (!data) return null
  return (
    <div className="flex flex-col gap-2.5 pt-1">
      <Card className="flex items-center gap-3 p-3">
        <div className="flex flex-1 flex-col text-sm">
          <span className="font-extrabold">
            {data.phase === 'soon' ? 'Конкурс не запущен' : data.phase === 'active' ? 'Конкурс идёт' : 'Конкурс завершён'}
          </span>
          {data.end_ms && <span className="text-xs text-muted">до {new Date(data.end_ms).toLocaleString('ru-RU')}</span>}
        </div>
        {data.phase === 'soon' ? (
          <button
            type="button"
            onClick={() => confirm('Запустить конкурс на 30 дней с этой минуты?') && start.mutate()}
            className="press rounded-lg bg-red px-3 py-2 text-xs font-extrabold text-white"
          >
            Запустить
          </button>
        ) : (
          <button type="button" disabled={pull.isPending} onClick={() => pull.mutate()} className="press rounded-lg border border-line-2 px-3 py-2 text-xs font-bold">
            {pull.isPending ? '…' : 'Обновить просмотры'}
          </button>
        )}
      </Card>
      {pull.data && (
        <div className="text-xs text-muted">
          Обновлено: {pull.data.updated}, не удалось: {pull.data.failed}
        </div>
      )}
      {data.entries.length === 0 && <Card className="p-4 text-center text-sm text-muted">Роликов пока нет</Card>}
      {data.entries.map((e) => (
        <EntryCard key={e.id} e={e} onChange={refresh} />
      ))}
    </div>
  )
}

function EntryCard({ e, onChange }: { e: Entry; onChange: () => void }) {
  const [views, setViews] = useState('')
  const review = useMutation({
    mutationFn: (body: { status?: string; views?: number; note?: string }) => api.adminContestReview(e.id, body),
    onSuccess: () => {
      setViews('')
      onChange()
    },
  })
  const tone = e.status === 'approved' ? 'text-ok' : e.status === 'rejected' ? 'text-[#FF8A90]' : 'text-gold'
  return (
    <Card className="flex flex-col gap-2 p-3 text-xs">
      <div className="flex items-start gap-2">
        <button type="button" onClick={() => openExternal(e.url)} className="flex min-w-0 flex-1 flex-col text-left">
          <span className="truncate text-sm font-bold">{e.title || e.url}</span>
          <span className="truncate text-muted">
            {e.platform} · {e.author ?? '—'} · игрок {e.user}
            {e.published_ms ? ` · опубл. ${new Date(e.published_ms).toLocaleDateString('ru-RU')}` : ''}
          </span>
        </button>
        <span className="text-right font-extrabold">
          {fmt(e.views)}
          <span className={`block text-[10px] ${tone}`}>{e.status}</span>
        </span>
      </div>
      {(e.fetch_error || e.manual) && (
        <div className="text-muted">{e.manual ? 'просмотры вписаны вручную' : `не удалось получить просмотры: ${e.fetch_error}`}</div>
      )}
      <div className="flex gap-1.5">
        <button type="button" onClick={() => review.mutate({ status: 'approved', note: '' })} className="press rounded-lg bg-[#12301F] px-2.5 py-1.5 font-bold text-ok">
          Засчитать
        </button>
        <button
          type="button"
          onClick={() => {
            const note = prompt('Причина отклонения (увидит игрок)', 'Не соответствует правилам')
            if (note !== null) review.mutate({ status: 'rejected', note })
          }}
          className="press rounded-lg bg-red-deep px-2.5 py-1.5 font-bold text-[#FF8A90]"
        >
          Отклонить
        </button>
        <input
          value={views}
          onChange={(ev) => setViews(ev.target.value.replace(/\D/g, ''))}
          placeholder="просмотры"
          inputMode="numeric"
          className="min-w-0 flex-1 rounded-lg border border-line-2 bg-surface-2 px-2 py-1.5 outline-none"
        />
        <button
          type="button"
          disabled={!views}
          onClick={() => review.mutate({ views: Number(views) })}
          className="press rounded-lg border border-line-2 px-2.5 py-1.5 font-bold disabled:opacity-40"
        >
          OK
        </button>
      </div>
    </Card>
  )
}
