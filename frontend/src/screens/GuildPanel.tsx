import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { useState } from 'react'

import { Avatar } from '../components/Avatar'
import { Coin, Icon, Soul } from '../components/icons'
import { ChatView } from '../components/ChatView'
import { PlayerSheet } from '../components/PlayerSheet'
import { Card, Progress } from '../components/ui'
import { api, ApiError, type GuildDetail, type GuildHome, type GuildShort } from '../lib/api'
import { fmt, short } from '../lib/format'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'

const ERR: Record<string, string> = {
  not_enough_coins: 'Не хватает ELT COIN',
  name_taken: 'Это название уже занято',
  bad_name: 'Название: 3–20 символов, буквы, цифры, пробел, - _ .',
  already_in_guild: 'Вы уже в гильдии',
  guild_full: 'В гильдии нет мест',
  rejoin_cooldown: 'Вступить в новую гильдию можно через сутки после выхода',
  steam_not_verified: 'Награды гильдии — только для проверенных Steam-аккаунтов',
  not_ready: 'Ступень ещё не выполнена',
}
const errText = (e: unknown) => (e instanceof ApiError ? (ERR[e.message] ?? 'Ошибка') : 'Ошибка')

/** Guild picture; old guilds without a custom picture show the first letter of the name */
function GuildPic({ g, className }: { g: GuildShort; className: string }) {
  return g.emblem_url ? (
    <img src={g.emblem_url} alt="" className={`${className} object-cover`} />
  ) : (
    <span className={`${className} flex items-center justify-center bg-red-deep font-display text-lg font-bold text-[#FF8A90]`}>
      {g.name.slice(0, 1).toUpperCase()}
    </span>
  )
}

/** A 256x256 square from the chosen file (center crop), JPEG; the server accepts up to 300 KB */
async function squareImage(file: File): Promise<string> {
  const bmp = await createImageBitmap(file)
  const side = Math.min(bmp.width, bmp.height)
  const c = document.createElement('canvas')
  c.width = c.height = 256
  c.getContext('2d')!.drawImage(bmp, (bmp.width - side) / 2, (bmp.height - side) / 2, side, side, 0, 0, 256, 256)
  return c.toDataURL('image/jpeg', 0.85)
}

function left(ms: number) {
  const d = Math.max(0, ms - Date.now())
  const days = Math.floor(d / 86_400_000)
  const h = Math.floor((d % 86_400_000) / 3_600_000)
  return days > 0 ? `${days} д ${h} ч` : `${h} ч`
}

export function GuildPanel() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['guild'], queryFn: api.guild })
  const [view, setView] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const set = (d: GuildDetail) => qc.setQueryData<GuildHome>(['guild'], (o) => (o ? { ...o, guild: d } : o))

  if (!data) return null
  if (data.guild) return <MyGuild g={data.guild} minContrib={data.rules.min_contrib} warPrizes={data.rules.war_prizes} onChange={set} />

  return (
    <div className="flex flex-col gap-4 px-4 pt-3.5 pb-6">
      <div className="flex flex-col items-center gap-1 pt-1 text-center">
        <h1 className="m-0 font-display text-2xl font-bold">Гильдии</h1>
        <div className="max-w-[320px] text-[13px] text-muted">
          Играйте командой: очки активности участников идут в гильдию, а за недельные задания каждый получает души
        </div>
      </div>
      <button
        type="button"
        onClick={() => setCreating(true)}
        className="press flex items-center justify-center gap-2 rounded-[14px] bg-red py-3.5 text-[15px] font-extrabold text-white"
      >
        Создать гильдию · <Coin size={14} /> {short(data.rules.create_cost)}
      </button>
      {data.rejoin_in_ms > 0 && (
        <div className="text-center text-xs text-gold">Вступить в гильдию можно через {left(Date.now() + data.rejoin_in_ms)}</div>
      )}
      <div className="text-[13px] font-extrabold tracking-wide text-muted uppercase">Топ гильдий недели</div>
      {data.top.length === 0 && <Card className="p-4 text-center text-[13px] text-muted">Гильдий пока нет — создайте первую</Card>}
      <div className="flex flex-col gap-2">
        {data.top.map((g, i) => (
          <GuildRow key={g.id} g={g} rank={i + 1} onClick={() => setView(g.id)} />
        ))}
      </div>
      <AnimatePresence>
        {view !== null && <GuildSheet id={view} canJoin={data.rejoin_in_ms <= 0} onClose={() => setView(null)} />}
        {creating && <CreateSheet home={data} onClose={() => setCreating(false)} />}
      </AnimatePresence>
    </div>
  )
}

function GuildRow({ g, rank, onClick }: { g: GuildShort; rank: number; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="press flex items-center gap-3 rounded-[14px] border border-line bg-surface p-2.5 text-left">
      <span className={`w-6 text-center font-display text-sm font-bold ${rank === 1 ? 'text-gold' : 'text-muted'}`}>{rank}</span>
      <GuildPic g={g} className="h-10 w-10 rounded-xl" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-extrabold">{g.name}</span>
        <span className="text-[11px] text-muted">
          {g.members}/{g.max_members} участников
        </span>
      </div>
      <span className="text-[13px] font-extrabold">{fmt(g.points)}</span>
    </button>
  )
}

function Sheet({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/60" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full overflow-y-auto rounded-t-3xl border-t border-line bg-ground p-4 pb-[max(16px,env(safe-area-inset-bottom))]"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

function GuildSheet({ id, canJoin, onClose }: { id: number; canJoin: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const { data: g } = useQuery({ queryKey: ['guild', id], queryFn: () => api.guildInfo(id) })
  const join = useMutation({
    mutationFn: () => api.guildJoin(id),
    onSuccess: () => {
      haptic('medium')
      void qc.invalidateQueries({ queryKey: ['guild'] })
      onClose()
    },
  })
  return (
    <Sheet onClose={onClose}>
      {g && (
        <div className="flex flex-col gap-3">
          <Header g={g} />
          <Members g={g} />
          <button
            type="button"
            disabled={!canJoin || join.isPending || g.members >= g.max_members}
            onClick={() => join.mutate()}
            className="press rounded-[14px] bg-red py-3.5 text-[15px] font-extrabold text-white disabled:bg-surface-2 disabled:text-muted"
          >
            {g.members >= g.max_members ? 'Мест нет' : 'Вступить'}
          </button>
          {join.error && <div className="text-center text-xs font-bold text-[#FF8A90]">{errText(join.error)}</div>}
        </div>
      )}
    </Sheet>
  )
}

function CreateSheet({ home, onClose }: { home: GuildHome; onClose: () => void }) {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const [name, setName] = useState('')
  const [about, setAbout] = useState('')
  const [pic, setPic] = useState<string | null>(null)
  const create = useMutation({
    mutationFn: () => api.guildCreate(name, pic!, about),
    onSuccess: (r) => {
      haptic('heavy')
      applyState(r.state)
      qc.setQueryData<GuildHome>(['guild'], { ...home, guild: r.guild })
      onClose()
    },
  })
  return (
    <Sheet onClose={onClose}>
      <div className="flex flex-col gap-3">
        <div className="font-display text-xl font-bold">Новая гильдия</div>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={20}
          placeholder="Название"
          className="rounded-xl border border-line-2 bg-surface px-3 py-3 text-[15px] font-bold outline-none focus:border-ice-line"
        />
        <input
          value={about}
          onChange={(e) => setAbout(e.target.value)}
          maxLength={140}
          placeholder="Девиз (необязательно)"
          className="rounded-xl border border-line-2 bg-surface px-3 py-3 text-sm outline-none focus:border-ice-line"
        />
        <label className="press flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-line-2 bg-surface p-3">
          {pic ? (
            <img src={pic} alt="" className="h-16 w-16 rounded-2xl object-cover" />
          ) : (
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-2 text-2xl text-muted">+</span>
          )}
          <span className="flex flex-col">
            <span className="text-sm font-extrabold">{pic ? 'Сменить картинку' : 'Картинка гильдии'}</span>
            <span className="text-xs text-muted">Своё фото или арт — будет гербом гильдии</span>
          </span>
          <input type="file" accept="image/*" className="hidden" onChange={async (e) => {
            const f = e.target.files?.[0]
            if (f) setPic(await squareImage(f))
          }} />
        </label>
        <button
          type="button"
          disabled={name.trim().length < 3 || !pic || create.isPending}
          onClick={() => create.mutate()}
          className="press flex items-center justify-center gap-1.5 rounded-[14px] bg-red py-3.5 text-[15px] font-extrabold text-white disabled:opacity-50"
        >
          Создать за <Coin size={14} /> {fmt(home.rules.create_cost)}
        </button>
        {create.error && <div className="text-center text-xs font-bold text-[#FF8A90]">{errText(create.error)}</div>}
      </div>
    </Sheet>
  )
}

function Header({ g, onPicture }: { g: GuildDetail; onPicture?: (dataUrl: string) => void }) {
  return (
    <div className="flex items-center gap-3">
      {onPicture ? (
        <label className="relative cursor-pointer" title="Сменить картинку">
          <GuildPic g={g} className="h-16 w-16 rounded-2xl" />
          <span className="absolute -right-1 -bottom-1 rounded-md bg-black/80 px-1 text-[10px] font-bold">✎</span>
          <input type="file" accept="image/*" className="hidden" onChange={async (e) => {
            const f = e.target.files?.[0]
            if (f) onPicture(await squareImage(f))
          }} />
        </label>
      ) : (
        <GuildPic g={g} className="h-16 w-16 rounded-2xl" />
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="truncate font-display text-xl font-bold">{g.name}</div>
        {g.about && <div className="truncate text-xs text-muted">{g.about}</div>}
        <div className="text-xs text-muted">
          {g.members}/{g.max_members} участников · {fmt(g.points)} очков{g.rank ? ` · #${g.rank} недели` : ''}
        </div>
      </div>
    </div>
  )
}

function Members({ g, onPlayer, onKick }: { g: GuildDetail; onPlayer?: (id: number) => void; onKick?: (id: number) => void }) {
  return (
    <div className="flex flex-col gap-1.5">
      {g.members_list.map((m, i) => (
        <div key={m.id} className={`flex items-center gap-2.5 rounded-[14px] border bg-surface p-2 ${m.me ? 'border-ice-line' : 'border-line'}`}>
          <span className="w-5 text-center text-xs font-bold text-muted">{i + 1}</span>
          <button type="button" onClick={() => onPlayer?.(m.id)} className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
            <Avatar name={m.name} photo={m.photo_url} size={30} />
            <span className="truncate text-sm font-bold">{m.name}</span>
            {m.role === 'owner' && <Icon name="star" size={13} className="shrink-0 text-gold" />}
          </button>
          <span className="text-[13px] font-extrabold">{fmt(m.points)}</span>
          {onKick && !m.me && (
            <button type="button" aria-label="Исключить" onClick={() => onKick(m.id)} className="press px-1 text-lg leading-none text-muted">
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

function MyGuild({ g, minContrib, warPrizes, onChange }: { g: GuildDetail; minContrib: number; warPrizes: number[]; onChange: (g: GuildDetail) => void }) {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const [player, setPlayer] = useState<number | null>(null)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const [chat, setChat] = useState(false)
  const claim = useMutation({
    mutationFn: ({ quest, tier }: { quest: string; tier: number }) => api.guildClaim(quest, tier),
    onSuccess: (r) => {
      haptic('heavy')
      applyState(r.state)
      onChange(r.guild)
    },
  })
  const leave = useMutation({
    mutationFn: api.guildLeave,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['guild'] }),
  })
  const kick = useMutation({ mutationFn: api.guildKick, onSuccess: (r) => onChange(r.guild) })
  const picture = useMutation({ mutationFn: api.guildEmblem, onSuccess: (r) => onChange(r.guild) })
  const eligible = g.my_points >= minContrib

  return (
    <div className="flex flex-col gap-4 px-4 pt-3.5 pb-6">
      <Header g={g} onPicture={g.my_role === 'owner' ? (img) => picture.mutate(img) : undefined} />

      <Card className="flex items-center justify-between p-3">
        <div className="flex flex-col">
          <span className="text-xs text-muted">Ваш вклад за неделю</span>
          <span className="font-display text-lg font-bold">{fmt(g.my_points)}</span>
        </div>
        <span className="text-right text-[11px] text-muted">
          до конца недели
          <br />
          <span className="font-bold text-ink">{left(g.ends_ms)}</span>
        </span>
      </Card>
      {!eligible && (
        <div className="-mt-2 text-xs text-gold">Наберите {minContrib} очков активности за неделю, чтобы забирать награды гильдии</div>
      )}

      <button
        type="button"
        onClick={() => setChat(true)}
        className="press flex items-center justify-between rounded-xl border border-ice-line bg-[#0e1a26] px-3 py-3 text-sm font-extrabold"
      >
        Чат гильдии
        <span className="text-xs font-bold text-ice">открыть →</span>
      </button>
      {chat && (
        <div className="fixed inset-0 z-50 flex flex-col bg-ground px-4 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]">
          <div className="mb-2 flex items-center gap-3">
            <button type="button" onClick={() => setChat(false)} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface">
              <Icon name="back" size={20} />
            </button>
            <div className="font-display text-lg font-bold">Чат «{g.name}»</div>
          </div>
          <ChatView channel={`g:${g.id}`} canModerate={g.my_role === 'owner'} height="h-[calc(100vh-150px)]" />
        </div>
      )}
      <Card className="flex items-center gap-3 border-[#5a1d22] p-3" >
        <span className="font-display text-2xl font-bold text-[#FF8A90]">{g.rank ? `#${g.rank}` : '—'}</span>
        <span className="flex flex-col text-xs leading-snug text-muted">
          <span className="text-sm font-extrabold text-ink">Война гильдий — место недели</span>
          Топ-3 гильдии в конце недели: каждому участнику с {minContrib}+ очками {warPrizes.join(' / ')} душ
        </span>
      </Card>
      <div className="text-[13px] font-extrabold tracking-wide text-muted uppercase">Задания гильдии</div>
      {g.quests.map((q) => {
        const next = q.tiers.find((t) => !t.done) ?? q.tiers[q.tiers.length - 1]
        return (
          <Card key={q.id} className="flex flex-col gap-2.5 p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-extrabold">{q.title}</span>
              <span className="text-xs font-bold text-muted">
                {fmt(q.progress)} / {fmt(next.goal)}
              </span>
            </div>
            <Progress value={Math.min(1, q.progress / next.goal)} color="bg-gold" height={6} />
            <div className="grid grid-cols-3 gap-2">
              {q.tiers.map((t) => (
                <button
                  key={t.tier}
                  type="button"
                  disabled={!t.can_claim || claim.isPending}
                  onClick={() => claim.mutate({ quest: q.id, tier: t.tier })}
                  className={`press flex flex-col items-center gap-0.5 rounded-xl border py-2 text-xs ${
                    t.claimed
                      ? 'border-ok/40 bg-[#12301F] text-ok'
                      : t.can_claim
                        ? 'border-gold bg-[#2A2210] text-gold'
                        : 'border-line-2 bg-surface-2 text-muted'
                  }`}
                >
                  <span className="font-bold">{short(t.goal)}</span>
                  <span className="flex items-center gap-1 font-extrabold">
                    {t.claimed ? 'забрано' : <><Soul size={12} />+{t.souls}</>}
                  </span>
                </button>
              ))}
            </div>
          </Card>
        )
      })}
      {claim.error && <div className="text-center text-xs font-bold text-[#FF8A90]">{errText(claim.error)}</div>}

      <div className="text-[13px] font-extrabold tracking-wide text-muted uppercase">Участники</div>
      <Members
        g={g}
        onPlayer={setPlayer}
        onKick={g.my_role === 'owner' ? (id) => kick.mutate(id) : undefined}
      />

      {confirmLeave ? (
        <div className="flex gap-2">
          <button type="button" onClick={() => setConfirmLeave(false)} className="press flex-1 rounded-xl border border-line-2 bg-surface py-3 text-sm font-bold">
            Остаться
          </button>
          <button
            type="button"
            disabled={leave.isPending}
            onClick={() => leave.mutate()}
            className="press flex-1 rounded-xl bg-red-deep py-3 text-sm font-extrabold text-[#FF8A90]"
          >
            Выйти
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirmLeave(true)}
          className="press rounded-xl border border-[#5a1d22] bg-red-deep py-3 text-sm font-extrabold text-[#FF8A90]"
        >
          Выйти из гильдии
        </button>
      )}
      <div className="-mt-2 text-center text-[11px] text-muted">Вступить в другую гильдию можно через сутки после выхода</div>
      <AnimatePresence>{player !== null && <PlayerSheet id={player} onClose={() => setPlayer(null)} />}</AnimatePresence>
    </div>
  )
}
