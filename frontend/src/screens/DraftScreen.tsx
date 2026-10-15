import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { Avatar } from '../components/Avatar'
import { Coin, Icon, Soul } from '../components/icons'
import { Card, Segmented } from '../components/ui'
import { api, ApiError, type DraftHero, type DraftMatchState, type DraftPart } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic } from '../lib/telegram'

// Draft duel: lobby (ELO, ladder, 30 s matchmaking -> bot), Captains Mode, position placement, outcome breakdown.

const POS = ['Керри', 'Мид', 'Оффлейн', 'Роумер', 'Саппорт']
const ATTR: [string, string][] = [['all-heroes', 'Все'], ['str', 'Сила'], ['agi', 'Ловк.'], ['int', 'Инт.'], ['all', 'Унив.']]

function useNow(ms = 250) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

export function DraftScreen({ onClose }: { onClose: () => void }) {
  const [matchId, setMatchId] = useState<string | null>(null)
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ground">
      <div className="flex items-center gap-3 px-4 pt-3 pb-2">
        <button type="button" aria-label="Закрыть" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface">
          <Icon name="back" size={20} />
        </button>
        <div className="font-display text-lg font-bold">Драфт-дуэль</div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-[max(20px,env(safe-area-inset-bottom))]">
        {matchId ? <Match id={matchId} onExit={() => setMatchId(null)} /> : <Lobby onMatch={setMatchId} />}
      </div>
    </div>
  )
}

// ---------------- lobby ----------------
function Lobby({ onMatch }: { onMatch: (id: string) => void }) {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['draft'], queryFn: api.draftLobby, refetchInterval: 15_000 })
  const [since, setSince] = useState<number | null>(null)
  const now = useNow(250)
  const join = useMutation({
    mutationFn: api.draftQueue,
    onSuccess: (r) => (r.match_id ? onMatch(r.match_id) : setSince(Date.now())),
  })
  const leave = useMutation({ mutationFn: api.draftLeave, onSuccess: () => setSince(null) })

  useEffect(() => {
    if (data?.queue && since === null) setSince(data.queue.since_ms)
  }, [data, since])

  // poll matchmaking once per second
  useEffect(() => {
    if (since === null) return
    const id = setInterval(async () => {
      const r = await api.draftPoll().catch(() => null)
      if (r?.match_id) {
        haptic('heavy')
        setSince(null)
        void qc.invalidateQueries({ queryKey: ['draft'] })
        onMatch(r.match_id)
      }
    }, 1000)
    return () => clearInterval(id)
  }, [since]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return <div className="p-8 text-center text-sm text-muted">Загружаем…</div>
  const r = data.rating
  const wr = r.games ? Math.round((r.wins / r.games) * 100) : 0
  const left = since ? Math.max(0, 30 - (now - since) / 1000) : 0
  const err = join.error instanceof ApiError ? join.error.message : null

  return (
    <div className="flex flex-col gap-3 pt-1">
      <div
        className="relative overflow-hidden rounded-[22px] border border-[#5a4a1a] p-4"
        style={{ background: 'radial-gradient(circle at 85% 20%, #4a3a12 0%, #1a150a 55%, #0d0b07 100%)' }}
      >
        <div className="text-[11px] font-extrabold tracking-wider text-gold">РЕЙТИНГ ELO</div>
        <div className="font-display text-[44px] leading-none font-bold">{r.elo}</div>
        <div className="mt-1 text-xs text-[#e8d9b0]">
          {r.games} рейтинговых игр · {wr}% побед
        </div>
        <div className="mt-3 text-xs leading-relaxed text-[#cdbf98]">
          Captains Mode 5×5: баны и пики по очереди, потом расставляете героев по позициям. Побеждает состав с большим
          числом очков — мета, контрпики, позиции, состав и синергия, с подробным разбором.
        </div>
      </div>

      {data.active ? (
        <button type="button" onClick={() => onMatch(data.active!)} className="press rounded-[14px] bg-gold py-3.5 text-[15px] font-extrabold text-black">
          Вернуться в матч
        </button>
      ) : since !== null ? (
        <Card className="flex flex-col items-center gap-2 p-4">
          <div className="font-display text-3xl font-bold tabular-nums">{Math.ceil(left)}</div>
          <div className="text-sm font-bold">Ищем соперника…</div>
          <div className="text-xs text-muted">Если за 30 секунд никого не найдём — сыграете с ботом</div>
          <button type="button" onClick={() => leave.mutate()} className="press mt-1 rounded-xl border border-line-2 px-4 py-2 text-xs font-bold">
            Отменить поиск
          </button>
        </Card>
      ) : (
        <button
          type="button"
          disabled={!data.ready || join.isPending}
          onClick={() => join.mutate()}
          className="press rounded-[14px] bg-gold py-3.5 text-[15px] font-extrabold text-black disabled:opacity-50"
        >
          {data.ready ? 'Найти соперника' : 'Загружаем данные героев…'}
        </button>
      )}
      {err && <div className="text-center text-xs font-bold text-[#FF8A90]">{err === 'draft_data_loading' ? 'Данные героев ещё загружаются, попробуйте через минуту' : 'Ошибка'}</div>}
      <div className="text-center text-[11px] text-muted">
        Игры с ботом в рейтинг не идут. Награда за них — первые 3 в день: <Coin size={10} className="inline" /> {fmt(data.bot_coins.win)} за
        победу, {fmt(data.bot_coins.loss)} за поражение (осталось {data.bot_rewards_left}).
      </div>

      <h3 className="mt-2 text-[13px] font-extrabold tracking-wide text-muted uppercase">Ладдер месяца</h3>
      <Card className="flex items-center justify-between p-3 text-sm">
        <span>
          Ваши очки: <b>{data.month.points > 0 ? '+' : ''}{data.month.points}</b> · игр {data.month.games}/{data.month.min_games}
        </span>
        <span className="flex items-center gap-1 text-xs font-bold text-gold">
          1 место <Soul size={12} /> {fmt(data.month.prizes[0])}
        </span>
      </Card>
      <div className="text-[11px] text-muted">Очки — сумма изменений ELO за месяц, в ладдер попадают игроки от {data.month.min_games} игр против людей. Призы — души для магазина, топ-10.</div>
      {data.ladder.length === 0 && <Card className="p-4 text-center text-sm text-muted">Ладдер пуст — сыграйте первые рейтинговые игры</Card>}
      {data.ladder.map((p) => (
        <div key={p.id} className={`flex items-center gap-2.5 rounded-[14px] border bg-surface p-2.5 ${p.me ? 'border-ice-line' : 'border-line'}`}>
          <span className={`w-6 text-center font-display text-sm font-bold ${p.rank === 1 ? 'text-gold' : 'text-muted'}`}>{p.rank}</span>
          <Avatar name={p.name} photo={p.photo_url} size={30} />
          <span className="flex-1 truncate text-sm font-bold">{p.name}</span>
          <span className="text-xs text-muted">{p.wins}/{p.games}</span>
          <span className="w-12 text-right text-sm font-extrabold">{p.points > 0 ? '+' : ''}{p.points}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------- match ----------------
function Match({ id, onExit }: { id: string; onExit: () => void }) {
  const qc = useQueryClient()
  const { data: hd } = useQuery({ queryKey: ['draft-heroes'], queryFn: api.draftHeroes, staleTime: Infinity })
  const { data: m } = useQuery({
    queryKey: ['draft-match', id],
    queryFn: () => api.draftMatch(id),
    refetchInterval: (q) => (q.state.data?.status === 'done' ? false : 1000),
  })
  const heroes = useMemo(() => new Map((hd?.heroes ?? []).map((h) => [h.id, h])), [hd])
  const set = (s: DraftMatchState) => qc.setQueryData(['draft-match', id], s)

  if (!m || !hd) return <div className="p-8 text-center text-sm text-muted">Загружаем матч…</div>
  return (
    <div className="flex flex-col gap-3 pt-1">
      <Teams m={m} heroes={heroes} />
      {m.status === 'draft' && <DraftBoard m={m} heroes={hd.heroes} onState={set} />}
      {m.status === 'place' && <Placement m={m} heroes={heroes} onState={set} />}
      {m.status === 'done' && (
        <Result
          m={m}
          heroes={heroes}
          onExit={() => {
            void qc.invalidateQueries({ queryKey: ['draft'] })
            onExit()
          }}
        />
      )}
    </div>
  )
}

function Portrait({ h, size = 'h-9 w-16', dim }: { h?: DraftHero; size?: string; dim?: boolean }) {
  return h ? (
    <img src={h.img} alt={h.name} className={`${size} rounded-md object-cover ${dim ? 'opacity-40 grayscale' : ''}`} />
  ) : (
    <span className={`${size} rounded-md border border-dashed border-line-2 bg-surface-2`} />
  )
}

function Teams({ m, heroes }: { m: DraftMatchState; heroes: Map<number, DraftHero> }) {
  const now = useNow(250)
  const row = (side: 'A' | 'B') => {
    const picks = m.actions.filter((a) => a.kind === 'pick' && a.side === side).map((a) => heroes.get(a.hero))
    const bans = m.actions.filter((a) => a.kind === 'ban' && a.side === side).map((a) => heroes.get(a.hero))
    const mine = side === m.me
    return (
      <div className={`rounded-xl border p-2 ${mine ? 'border-ice-line bg-[#0e1a26]' : 'border-[#5a1d22] bg-[#1a0d10]'}`}>
        <div className="mb-1.5 flex items-center justify-between text-[11px] font-extrabold">
          <span className={mine ? 'text-ice' : 'text-[#FF8A90]'}>{mine ? 'Вы' : m.players[side].name}</span>
          {m.turn?.side === side && (
            <span className="text-ink">
              {m.turn.kind === 'pick' ? 'пикает' : 'банит'} · {Math.max(0, Math.ceil((m.deadline_ms - now) / 1000))} с
            </span>
          )}
        </div>
        <div className="grid grid-cols-5 gap-1">
          {Array.from({ length: 5 }, (_, i) => (
            <Portrait key={i} h={picks[i]} size="h-8 w-full" />
          ))}
        </div>
        <div className="mt-1 grid grid-cols-7 gap-1">
          {Array.from({ length: 7 }, (_, i) => (
            <Portrait key={i} h={bans[i]} size="h-5 w-full" dim />
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-1.5">
      {row(m.me)}
      {row(m.me === 'A' ? 'B' : 'A')}
    </div>
  )
}

function DraftBoard({ m, heroes, onState }: { m: DraftMatchState; heroes: DraftHero[]; onState: (s: DraftMatchState) => void }) {
  const [attr, setAttr] = useState('all-heroes')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  const act = useMutation({
    mutationFn: (hero: number) => api.draftAct(m.id, hero),
    onSuccess: (s) => {
      haptic('medium')
      setSel(null)
      onState(s)
    },
  })
  const taken = new Set(m.actions.map((a) => a.hero))
  const myTurn = m.turn?.side === m.me
  const list = heroes.filter((h) => (attr === 'all-heroes' || h.attr === attr) && h.name.toLowerCase().includes(q.toLowerCase()))
  const selHero = heroes.find((h) => h.id === sel)
  return (
    <>
      <div className={`rounded-xl px-3 py-2 text-center text-sm font-extrabold ${myTurn ? (m.turn?.kind === 'pick' ? 'bg-[#12301F] text-ok' : 'bg-red-deep text-[#FF8A90]') : 'bg-surface-2 text-muted'}`}>
        {myTurn ? (m.turn?.kind === 'pick' ? 'Ваш пик' : 'Ваш бан') : 'Ход соперника…'} · ход {(m.turn?.step ?? 0) + 1}/24
      </div>
      <Segmented<string> value={attr} onChange={setAttr} options={ATTR} />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Поиск героя"
        className="rounded-xl border border-line-2 bg-surface px-3 py-2 text-sm outline-none focus:border-ice-line"
      />
      <div className="grid grid-cols-4 gap-1.5">
        {list.map((h) => {
          const used = taken.has(h.id)
          return (
            <button
              key={h.id}
              type="button"
              disabled={used}
              onClick={() => setSel(h.id)}
              className={`relative overflow-hidden rounded-lg border-2 ${sel === h.id ? 'border-gold' : 'border-transparent'} disabled:opacity-25`}
            >
              <img src={h.img} alt="" className="aspect-[16/9] w-full object-cover" loading="lazy" />
              <span className="absolute inset-x-0 bottom-0 truncate bg-black/70 px-1 text-[9px] font-bold">{h.name}</span>
            </button>
          )
        })}
      </div>
      {selHero && (
        <div className="sticky bottom-0 flex items-center gap-2 rounded-xl border border-line bg-surface p-2">
          <Portrait h={selHero} size="h-10 w-[72px]" />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-sm font-extrabold">{selHero.name}</span>
            <span className="truncate text-[10px] text-muted">
              {selHero.roles.join(', ')} · винрейт {(selHero.winrate * 100).toFixed(1)}%
            </span>
          </div>
          <button
            type="button"
            disabled={!myTurn || act.isPending}
            onClick={() => act.mutate(selHero.id)}
            className={`press rounded-lg px-3 py-2 text-xs font-extrabold disabled:opacity-40 ${m.turn?.kind === 'pick' ? 'bg-ok text-black' : 'bg-red text-white'}`}
          >
            {m.turn?.kind === 'pick' ? 'Пикнуть' : 'Забанить'}
          </button>
        </div>
      )}
    </>
  )
}

function Placement({ m, heroes, onState }: { m: DraftMatchState; heroes: Map<number, DraftHero>; onState: (s: DraftMatchState) => void }) {
  const now = useNow(250)
  const mine = m.actions.filter((a) => a.kind === 'pick' && a.side === m.me).map((a) => a.hero)
  const [order, setOrder] = useState<number[]>(mine)
  const [pick, setPick] = useState<number | null>(null)
  const place = useMutation({ mutationFn: () => api.draftPlace(m.id, order), onSuccess: onState })
  const done = !!m.orders[m.me]
  function tap(i: number) {
    if (pick === null) return setPick(i)
    const next = [...order]
    ;[next[pick], next[i]] = [next[i], next[pick]]
    setOrder(next)
    setPick(null)
  }
  return (
    <Card className="flex flex-col gap-2 p-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-extrabold">Расставьте героев по позициям</span>
        <span className="text-xs text-muted">{Math.max(0, Math.ceil((m.deadline_ms - now) / 1000))} с</span>
      </div>
      <span className="text-[11px] text-muted">Нажмите на двух героев, чтобы поменять их местами. Не успеете — поставим лучшую расстановку сами.</span>
      {order.map((h, i) => {
        const hero = heroes.get(h)
        return (
          <button
            key={i}
            type="button"
            disabled={done}
            onClick={() => tap(i)}
            className={`press flex items-center gap-2.5 rounded-xl border p-2 text-left ${pick === i ? 'border-gold bg-[#2A2210]' : 'border-line bg-surface-2'}`}
          >
            <span className="w-16 text-[11px] font-extrabold text-muted">
              Pos {i + 1}
              <br />
              {POS[i]}
            </span>
            <Portrait h={hero} size="h-9 w-16" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-bold">{hero?.name}</span>
              <span className="truncate text-[10px] text-muted">{hero?.roles.join(', ')}</span>
            </span>
          </button>
        )
      })}
      <button
        type="button"
        disabled={done || place.isPending}
        onClick={() => place.mutate()}
        className="press rounded-xl bg-gold py-3 text-sm font-extrabold text-black disabled:opacity-50"
      >
        {done ? 'Ждём соперника…' : 'Готово'}
      </button>
    </Card>
  )
}

function Result({ m, heroes, onExit }: { m: DraftMatchState; heroes: Map<number, DraftHero>; onExit: () => void }) {
  const r = m.result!
  const other = m.me === 'A' ? 'B' : 'A'
  const won = m.winner === m.me
  const [view, setView] = useState<'me' | 'them'>('me')
  const side = view === 'me' ? m.me : other
  return (
    <div className="flex flex-col gap-3">
      <div className={`rounded-[20px] border p-4 text-center ${won ? 'border-ok/50 bg-[#0f2418]' : 'border-red/50 bg-red-deep'}`}>
        <div className={`font-display text-3xl font-bold ${won ? 'text-ok' : 'text-[#FF8A90]'}`}>{won ? 'Победа' : 'Поражение'}</div>
        <div className="mt-1 font-display text-xl font-bold">
          {r[m.me].score} : {r[other].score}
        </div>
        {r.coin && <div className="mt-1 text-xs text-muted">Очки равны — победителя определил жребий</div>}
        <div className="mt-2 flex items-center justify-center gap-1.5 text-sm font-extrabold">
          {m.ranked ? (
            <>ELO {m.delta![m.me] > 0 ? '+' : ''}{m.delta![m.me]}</>
          ) : m.reward ? (
            <>
              <Coin size={14} /> +{fmt(m.reward)}
            </>
          ) : (
            <span className="text-muted">игра с ботом — без рейтинга</span>
          )}
        </div>
      </div>
      {r.decisive.length > 0 && (
        <Card className="p-3">
          <div className="mb-1.5 text-xs font-extrabold text-muted uppercase">Что решило игру</div>
          {r.decisive.map(([title, d]) => {
            const forMe = (m.me === 'A' ? d : -d) > 0
            return (
              <div key={title} className="flex justify-between text-sm">
                <span>{title}</span>
                <span className={`font-extrabold ${forMe ? 'text-ok' : 'text-[#FF8A90]'}`}>
                  {forMe ? 'в вашу пользу' : 'у соперника'} {Math.abs(d).toFixed(1)}
                </span>
              </div>
            )
          })}
        </Card>
      )}
      <Segmented<'me' | 'them'> value={view} onChange={setView} options={[['me', 'Ваш состав'], ['them', 'Соперник']]} />
      <div className="grid grid-cols-5 gap-1">
        {(m.orders[side] ?? []).map((h, i) => (
          <div key={h} className="flex flex-col items-center gap-0.5">
            <Portrait h={heroes.get(h)} size="h-8 w-full" />
            <span className="text-[9px] text-muted">{POS[i]}</span>
          </div>
        ))}
      </div>
      {r[side].parts.map((p: DraftPart) => (
        <Card key={p.key} className="p-3">
          <div className="flex justify-between text-sm font-extrabold">
            <span>{p.title}</span>
            <span className={p.points >= 0 ? 'text-ok' : 'text-[#FF8A90]'}>{p.points > 0 ? '+' : ''}{p.points}</span>
          </div>
          {p.reasons.map((x) => (
            <div key={x} className="mt-1 text-xs text-muted">· {x}</div>
          ))}
        </Card>
      ))}
      <button type="button" onClick={onExit} className="press rounded-[14px] bg-gold py-3.5 text-[15px] font-extrabold text-black">
        В лобби
      </button>
    </div>
  )
}
