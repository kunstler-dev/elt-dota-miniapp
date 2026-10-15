import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Card } from '../components/ui'
import { api } from '../lib/api'

/** Chat moderation: reports (restore / delete / mute / ban) and the list of punished players (lift). */
export function ChatAdmin() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['admin', 'chat'], queryFn: api.chatAdmin, refetchInterval: 15_000 })
  const done = () => void qc.invalidateQueries({ queryKey: ['admin', 'chat'] })
  const restore = useMutation({ mutationFn: api.chatRestore, onSuccess: done })
  const del = useMutation({ mutationFn: api.chatDelete, onSuccess: done })
  const ban = useMutation({
    mutationFn: ({ uid, minutes, purge }: { uid: number; minutes: number; purge: boolean }) => api.chatBan(uid, minutes, 'нарушение правил чата', purge),
    onSuccess: done,
  })
  const unban = useMutation({ mutationFn: api.chatUnban, onSuccess: done })
  if (!data) return null
  return (
    <div className="flex flex-col gap-2.5 pt-1">
      <h3 className="text-[13px] font-extrabold tracking-wide text-muted uppercase">Жалобы ({data.reports.length})</h3>
      {data.reports.length === 0 && <Card className="p-4 text-center text-sm text-muted">Жалоб нет</Card>}
      {data.reports.map((r) => (
        <Card key={r.id} className="flex flex-col gap-1.5 p-3 text-xs">
          <div className="flex justify-between">
            <span className="font-extrabold">{r.name}</span>
            <span className={r.hidden ? 'font-bold text-[#FF8A90]' : 'text-muted'}>
              {r.reports} жалоб{r.hidden ? ' · скрыто' : ''} · {r.channel === 'world' ? 'мировой' : 'гильдия'}
            </span>
          </div>
          <div className="text-sm">«{r.text}»</div>
          <div className="grid grid-cols-2 gap-1.5">
            <button type="button" onClick={() => restore.mutate(r.id)} className="press rounded-lg bg-[#12301F] py-2 font-bold text-ok">
              Всё в порядке
            </button>
            <button type="button" onClick={() => del.mutate(r.id)} className="press rounded-lg border border-line-2 py-2 font-bold">
              Удалить
            </button>
            <button type="button" onClick={() => ban.mutate({ uid: r.user_id, minutes: 1440, purge: false })} className="press rounded-lg bg-red-deep py-2 font-bold text-[#FF8A90]">
              Мут 24 ч
            </button>
            <button
              type="button"
              onClick={() => confirm(`Бан ${r.name} навсегда и удалить все сообщения?`) && ban.mutate({ uid: r.user_id, minutes: 0, purge: true })}
              className="press rounded-lg bg-red-deep py-2 font-bold text-[#FF8A90]"
            >
              Бан навсегда
            </button>
          </div>
        </Card>
      ))}

      <h3 className="mt-2 text-[13px] font-extrabold tracking-wide text-muted uppercase">Наказанные ({data.bans.length})</h3>
      {data.bans.length === 0 && <Card className="p-4 text-center text-sm text-muted">Никого</Card>}
      {data.bans.map((b) => (
        <Card key={b.user_id} className="flex items-center gap-2 p-3 text-xs">
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-sm font-extrabold">{b.name}</span>
            <span className="text-muted">
              {b.permanent ? 'бан навсегда' : `мут до ${new Date(b.until_ms).toLocaleString('ru-RU')}`}
              {b.reason ? ` · ${b.reason}` : ''}
            </span>
          </span>
          <button type="button" onClick={() => unban.mutate(b.user_id)} className="press rounded-lg border border-line-2 px-3 py-2 font-bold">
            Снять
          </button>
        </Card>
      ))}
    </div>
  )
}
