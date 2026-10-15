import { useQuery } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'

import { Avatar } from '../components/Avatar'
import { Soul } from '../components/icons'
import { PlayerSheet } from '../components/PlayerSheet'
import { Card, ScreenTitle, Segmented } from '../components/ui'
import { api } from '../lib/api'
import { fmt } from '../lib/format'

type Kind = 'week' | 'month'

function left(ms: number) {
  const d = Math.max(0, ms - Date.now())
  const days = Math.floor(d / 86_400_000)
  const hours = Math.floor((d % 86_400_000) / 3_600_000)
  return days > 0 ? `${days} д ${hours} ч` : `${hours} ч ${Math.floor((d % 3_600_000) / 60_000)} мин`
}

export function SeasonScreen() {
  const [kind, setKind] = useState<Kind>('week')
  const [player, setPlayer] = useState<number | null>(null)
  const { data } = useQuery({ queryKey: ['top', kind], queryFn: () => api.top(kind), refetchInterval: 60_000 })
  const [, tick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => tick((x) => x + 1), 60_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex flex-col gap-3.5 px-4 pt-3.5 pb-6">
      <ScreenTitle title="Рейтинг" subtitle="Очки дают тапы, мини-игры, награда дня и задания — прокачка не влияет" back />
      <Segmented<Kind>
        value={kind}
        onChange={setKind}
        options={[
          ['week', 'Неделя · моя лига'],
          ['month', 'Месяц · все'],
        ]}
      />

      {data && (
        <div className="flex flex-col gap-3 rounded-[18px] border border-[#5A1A1F] bg-red-deep p-3.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-extrabold tracking-[1px] text-[#FF8A90]">
              {kind === 'week' ? `ПРИЗЫ ЛИГИ «${data.league?.name.toUpperCase()}»` : 'ПРИЗЫ МЕСЯЦА'}
            </span>
            <span className="text-xs text-[#C9A5A8]">до конца {left(data.ends_ms)}</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {kind === 'week' ? (
              <>
                <Prize place="1 место" value={data.prizes[0]?.souls} />
                <Prize place="2 место" value={data.prizes[1]?.souls} />
                <Prize place="3 место" value={data.prizes[2]?.souls} />
              </>
            ) : (
              <>
                <PrizeItem place="1 место" item="Аркана" />
                <PrizeItem place="2–3" item="Immortal" />
                <PrizeItem place="4–10" item="Dota Plus" />
              </>
            )}
          </div>
          <div className="text-[11px] leading-relaxed text-[#C9A5A8]">
            {kind === 'week'
              ? 'Соревнуетесь только с игроками своей лиги. Души 4–10 местам тоже. Нужен проверенный Steam.'
              : 'Предметы приходят на ваш Steam после проверки итогов. Нужен проверенный Steam.'}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {data?.top.length === 0 && <Card className="p-4 text-center text-[13px] text-muted">Пока пусто — станьте первым</Card>}
        {data?.top.map((r) => (
          <button
            key={r.id}
            type="button"
            onClick={() => setPlayer(r.id)}
            className={`press flex items-center gap-3 rounded-[14px] border bg-surface p-2.5 text-left ${r.me ? 'border-ice-line' : 'border-line'}`}
          >
            <span className={`w-7 text-center font-display text-sm font-bold ${r.rank === 1 ? 'text-gold' : r.rank <= 3 ? 'text-ink' : 'text-muted'}`}>
              {r.rank}
            </span>
            <Avatar name={r.name} photo={r.photo_url} size={34} />
            <span className="flex-1 truncate text-sm font-bold">{r.name}</span>
            <span className="text-[13px] font-extrabold tabular-nums">{fmt(r.points)}</span>
          </button>
        ))}
      </div>

      {data && (
        <div className="sticky bottom-0 flex items-center gap-3 rounded-[14px] border border-ice-line bg-[#0E1A24] px-3 py-2.5">
          <span className="w-12 font-display text-sm font-bold text-ice">{data.me.rank ? `#${data.me.rank}` : '—'}</span>
          <span className="flex-1 text-sm font-extrabold">Вы</span>
          <span className="text-[13px] font-extrabold tabular-nums">{fmt(data.me.points)} очк.</span>
        </div>
      )}

      <AnimatePresence>{player !== null && <PlayerSheet id={player} onClose={() => setPlayer(null)} />}</AnimatePresence>
    </div>
  )
}

function Prize({ place, value }: { place: string; value?: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5 rounded-xl bg-[#1F1013] p-2">
      <span className="text-[11px] text-[#C9A5A8]">{place}</span>
      <span className="flex items-center gap-1 text-sm font-extrabold">
        <Soul size={13} />
        {value ? fmt(value) : '—'}
      </span>
    </div>
  )
}

function PrizeItem({ place, item }: { place: string; item: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 rounded-xl bg-[#1F1013] p-2">
      <span className="text-[11px] text-[#C9A5A8]">{place}</span>
      <span className="text-sm font-extrabold">{item}</span>
    </div>
  )
}
