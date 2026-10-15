import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { api, ApiError, type ChatMsg } from '../lib/api'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'
import { Avatar } from './Avatar'

// Channel chat (world or g:<id>): polls for new messages every 3 s, composer at the bottom.
// Tapping a message opens a menu: report, delete, and for admins mute/ban.

const ERR: Record<string, string> = {
  too_fast: 'Не так быстро — одно сообщение в 3 секунды',
  no_links: 'Ссылки и упоминания каналов в чате запрещены',
  steam_required: 'Писать могут только игроки с привязанным Steam',
  muted: 'Вы не можете писать в чат — мут',
}

const time = (ms: number) => new Date(ms).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
const PERMANENT_FROM = 2 ** 60

export function ChatView({ channel, canModerate, height = 'h-[calc(100vh-260px)]' }: { channel: string; canModerate?: boolean; height?: string }) {
  const isAdmin = useGame((s) => !!s.me?.user.is_admin)
  const [msgs, setMsgs] = useState<ChatMsg[]>([])
  const [text, setText] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [muted, setMuted] = useState<{ until: number; reason: string | null } | null>(null)
  const [menu, setMenu] = useState<ChatMsg | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const last = useRef(0)
  const box = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  useEffect(() => {
    let alive = true
    setMsgs([])
    last.current = 0
    const pull = async () => {
      const r = await api.chat(channel, last.current).catch(() => null)
      if (!alive || !r) return
      setMuted(r.muted_until ? { until: r.muted_until, reason: r.muted_reason } : null)
      if (r.messages.length === 0) return
      last.current = r.messages[r.messages.length - 1].id
      setMsgs((m) => [...m, ...r.messages].slice(-200))
    }
    void pull()
    const id = setInterval(pull, 3000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [channel])

  useEffect(() => {
    if (stick.current && box.current) box.current.scrollTop = box.current.scrollHeight
  }, [msgs])

  const send = useMutation({
    mutationFn: () => api.chatSend(channel, text),
    onSuccess: (r) => {
      haptic('light')
      setText('')
      setErr(null)
      stick.current = true
      last.current = Math.max(last.current, r.message.id)
      setMsgs((m) => [...m, r.message])
    },
    onError: (e) => setErr(e instanceof ApiError ? (ERR[e.message] ?? 'Не отправилось') : 'Не отправилось'),
  })
  const hide = (id: number) => setMsgs((m) => m.filter((x) => x.id !== id))
  const act = useMutation({
    mutationFn: async ({ kind, m }: { kind: 'report' | 'delete' | 'mute1h' | 'mute24h' | 'ban'; m: ChatMsg }) => {
      if (kind === 'report') return api.chatReport(m.id).then((r) => (r.hidden ? 'Сообщение скрыто — на проверке у модератора' : 'Жалоба отправлена'))
      if (kind === 'delete') return api.chatDelete(m.id).then(() => 'Удалено')
      const minutes = kind === 'mute1h' ? 60 : kind === 'mute24h' ? 1440 : 0
      return api.chatBan(m.user_id, minutes, 'нарушение правил чата', kind === 'ban').then(() => (minutes ? 'Мут выдан' : 'Бан навсегда, сообщения удалены'))
    },
    onSuccess: (msg, { kind, m }) => {
      if (kind === 'delete' || kind === 'ban') hide(m.id)
      if (kind === 'ban') setMsgs((all) => all.filter((x) => x.user_id !== m.user_id))
      setNote(msg)
      setTimeout(() => setNote(null), 2500)
      setMenu(null)
    },
    onError: () => {
      setNote('Не получилось')
      setMenu(null)
    },
  })

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
        }}
        className={`${height} flex flex-col gap-2 overflow-y-auto rounded-2xl border border-line bg-surface p-2.5`}
      >
        {msgs.length === 0 && <div className="m-auto text-sm text-muted">Пока тихо — напишите первым</div>}
        {msgs.map((m) => (
          <div key={m.id} className={`flex gap-2 ${m.me ? 'flex-row-reverse' : ''}`}>
            {!m.me && <Avatar name={m.name} photo={m.photo_url} size={28} />}
            <button
              type="button"
              onClick={() => setMenu(m)}
              className={`max-w-[78%] rounded-2xl px-3 py-1.5 text-left ${m.me ? 'bg-[#1d3550]' : 'bg-surface-2'}`}
            >
              {!m.me && (
                <div className="flex items-center gap-1 text-[11px] font-extrabold text-ice">
                  {m.name}
                  {m.guild && <span className="rounded bg-red-deep px-1 text-[9px] text-[#FF8A90]">{m.guild}</span>}
                  {m.league && <span className="text-[9px] font-bold text-muted">{m.league}</span>}
                </div>
              )}
              <div className="text-sm leading-snug break-words">{m.text}</div>
              <div className="text-right text-[9px] text-muted">{time(m.created_ms)}</div>
            </button>
          </div>
        ))}
      </div>
      {note && <div className="text-center text-xs font-bold text-ok">{note}</div>}
      {err && <div className="text-center text-xs font-bold text-[#FF8A90]">{err}</div>}
      {muted ? (
        <div className="rounded-xl border border-[#5a1d22] bg-red-deep px-3 py-2.5 text-center text-xs font-bold text-[#FF8A90]">
          {muted.until >= PERMANENT_FROM ? 'Вы заблокированы в чате' : `Мут до ${new Date(muted.until).toLocaleString('ru-RU')}`}
          {muted.reason ? ` · ${muted.reason}` : ''}
        </div>
      ) : (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (text.trim()) send.mutate()
          }}
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={300}
            placeholder="Сообщение…"
            className="min-w-0 flex-1 rounded-xl border border-line-2 bg-surface px-3 py-2.5 text-sm outline-none focus:border-ice-line"
          />
          <button type="submit" disabled={!text.trim() || send.isPending} className="press rounded-xl bg-red px-4 text-sm font-extrabold text-white disabled:opacity-40">
            ➤
          </button>
        </form>
      )}

      {menu && (
        <div className="fixed inset-0 z-[60] flex items-end bg-black/60" onClick={() => setMenu(null)}>
          <div
            className="flex w-full flex-col gap-2 rounded-t-3xl border-t border-line bg-ground p-4 pb-[max(16px,env(safe-area-inset-bottom))]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="truncate text-xs text-muted">
              {menu.name}: «{menu.text}»
            </div>
            {!menu.me && <Action onClick={() => act.mutate({ kind: 'report', m: menu })}>Пожаловаться</Action>}
            {(menu.me || canModerate || isAdmin) && <Action onClick={() => act.mutate({ kind: 'delete', m: menu })}>Удалить сообщение</Action>}
            {isAdmin && !menu.me && (
              <>
                <Action danger onClick={() => act.mutate({ kind: 'mute1h', m: menu })}>Мут на 1 час</Action>
                <Action danger onClick={() => act.mutate({ kind: 'mute24h', m: menu })}>Мут на 24 часа</Action>
                <Action danger onClick={() => confirm(`Забанить ${menu.name} навсегда и удалить все его сообщения?`) && act.mutate({ kind: 'ban', m: menu })}>
                  Бан навсегда и удалить всё
                </Action>
              </>
            )}
            <Action onClick={() => setMenu(null)}>Отмена</Action>
          </div>
        </div>
      )}
    </div>
  )
}

function Action({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`press rounded-xl border py-3 text-sm font-extrabold ${danger ? 'border-[#5a1d22] bg-red-deep text-[#FF8A90]' : 'border-line-2 bg-surface'}`}
    >
      {children}
    </button>
  )
}
