import { lazy, Suspense } from 'react'

import type { Profile } from '../lib/api'
import { fmt, short } from '../lib/format'
import { Avatar } from './Avatar'
import { Bolt, Coin, Icon, Soul } from './icons'
import { Card } from './ui'

const Character3D = lazy(() => import('./Character3D').then((m) => ({ default: m.Character3D })))

/** Player profile: the hero in 3D in their look, league, stats, heroes, mini-games and leaderboard places. */
export function ProfileView({ p }: { p: Profile }) {
  const days = Math.max(1, Math.round((Date.now() - p.since_ms) / 86_400_000))
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Avatar name={p.name} photo={p.photo_url} size={52} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-1.5 truncate font-display text-lg font-bold">
            {p.name}
            {p.is_premium && <Icon name="star" size={15} className="text-gold" />}
          </div>
          <div className="text-xs text-muted">
            {p.steam.persona ? `Steam · ${p.steam.persona}` : 'Steam'}
            {p.steam.verified ? ' · проверен' : ' · не проверен'} · в игре {days} дн.
          </div>
        </div>
        <img src={`/media/ranks/rank_${p.league.index + 1}.png`} alt={p.league.name} className="h-12 w-12 object-contain" />
      </div>

      <div className="relative -mx-4 h-[280px] overflow-hidden">
        <span
          className="pointer-events-none absolute rounded-[50%] border-2 border-[#5A1A1F] bg-[#1C0A0C]"
          style={{ left: '24%', right: '24%', bottom: 20, height: 48, boxShadow: '0 0 40px 4px rgba(212,37,47,.22)' }}
        />
        <Suspense fallback={null}>
          <Character3D mode="preview" look={p.look} cameraDist={6} />
        </Suspense>
        <div className="pointer-events-none absolute top-2 left-4 flex flex-col gap-1">
          <span className="rounded-lg bg-black/60 px-2 py-1 text-[13px] font-extrabold">{p.hero.name}</span>
          <span className="flex items-center gap-1 rounded-lg bg-black/60 px-2 py-1 text-xs font-bold">
            <Bolt size={12} /> сила тапа {p.tap_power}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat label="Лига" value={p.league.name} />
        <Stat label="Заработано" value={short(p.earned_total)} icon={<Coin size={13} />} />
        <Stat label="Доход/ч" value={`+${short(p.profit_per_hour)}`} />
        <Stat label="Неделя" value={p.week.rank ? `#${p.week.rank}` : '—'} sub={`${fmt(p.week.points)} очк.`} />
        <Stat label="Месяц" value={p.month.rank ? `#${p.month.rank}` : '—'} sub={`${fmt(p.month.points)} очк.`} />
        <Stat label="Друзья" value={String(p.friends)} />
      </div>

      {p.coins !== undefined && (
        <Card className="grid grid-cols-2 divide-x divide-line py-2.5 text-center">
          <span className="flex items-center justify-center gap-1.5 font-display font-bold">
            <Coin size={16} /> {fmt(p.coins)}
          </span>
          <span className="flex items-center justify-center gap-1.5 font-display font-bold">
            <Soul size={16} /> {fmt(p.souls ?? 0)}
          </span>
        </Card>
      )}

      <Card className="flex flex-col gap-2 p-3">
        <div className="text-sm font-extrabold">Герои</div>
        <div className="grid grid-cols-3 gap-2">
          {p.heroes.map((h) => (
            <div key={h.id} className="flex flex-col overflow-hidden rounded-lg border border-line bg-surface-2">
              <img src={`/media/heroes/${h.id}.png`} alt="" className={`aspect-[16/9] w-full object-cover ${h.owned ? '' : 'opacity-30 grayscale'}`} />
              <span className="flex items-center justify-between px-1.5 py-1 text-[10px] font-bold">
                <span className="truncate">{h.name}</span>
                {h.owned && (
                  <span className="flex items-center gap-0.5 text-muted">
                    <Bolt size={9} />
                    {h.tap_power}
                  </span>
                )}
              </span>
            </div>
          ))}
        </div>
        <div className="text-xs text-muted">Предметов в арсенале: {p.items_owned}</div>
      </Card>

      <Card className="grid grid-cols-2 divide-x divide-line py-3 text-center">
        <div className="flex flex-col gap-0.5">
          <span className="font-display text-lg font-bold">{p.games.hook}</span>
          <span className="text-[11px] text-muted">рекорд «Хука»</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="font-display text-lg font-bold">{p.games.guess}</span>
          <span className="text-[11px] text-muted">лучшая серия «Угадай героя»</span>
        </div>
      </Card>
    </div>
  )
}

function Stat({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon?: React.ReactNode }) {
  return (
    <Card className="flex flex-col items-center gap-0.5 px-1.5 py-2.5 text-center">
      <span className="text-[10px] text-muted">{label}</span>
      <span className="flex items-center gap-1 truncate text-[13px] font-extrabold">
        {icon}
        {value}
      </span>
      {sub && <span className="text-[10px] text-muted">{sub}</span>}
    </Card>
  )
}
