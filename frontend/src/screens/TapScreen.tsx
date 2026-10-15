import { useQuery } from '@tanstack/react-query'

import { Bolt, Coin, Icon, type IconName } from '../components/icons'
import { HeroStage } from '../components/HeroStage'
import { ShopButton } from '../components/ShopButton'
import { Progress } from '../components/ui'
import { api } from '../lib/api'
import { fmt, short } from '../lib/format'
import { useGame, type Tab } from '../store/game'
import { useLive } from '../store/useLive'

export function TapScreen() {
  const me = useGame((s) => s.me)
  const setTab = useGame((s) => s.setTab)
  const live = useLive()
  const { data: tasks } = useQuery({ queryKey: ['tasks'], queryFn: api.tasks })
  const tasksLeft = tasks?.tasks.filter((t) => !t.done).length ?? 0
  const { data: contest } = useQuery({ queryKey: ['contest'], queryFn: api.contest })
  const { data: fr } = useQuery({ queryKey: ['friends'], queryFn: api.friends })
  const perFriend = fr?.rules.bonus ?? 500
  if (!me || !live) return null
  const { snap } = live
  const lg = snap.league

  return (
    <div className="flex flex-col gap-3 px-4 pt-3 pb-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {me.user.photo_url ? (
            <img src={me.user.photo_url} alt="" className="h-10 w-10 rounded-xl border border-line-2 object-cover" />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-line-2 bg-surface-2 font-display text-base font-bold text-ice">
              {(me.user.first_name || me.user.username || '?').slice(0, 1).toUpperCase()}
            </div>
          )}
          <div className="flex flex-col gap-0.5">
            <div className="text-[15px] font-bold">{me.user.username ?? me.user.first_name}</div>
            <div className="max-w-[150px] truncate text-xs text-muted">
              {me.steam?.persona ? `Steam · ${me.steam.persona}` : 'Steam привязан'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Сезон и рейтинги"
            onClick={() => setTab('season')}
            className="press flex h-[46px] w-[46px] flex-col items-center justify-center gap-0.5 rounded-xl border border-ice-line bg-[#0E1A24] text-ice"
          >
            <Icon name="season" size={20} />
            <span className="text-[9px] font-extrabold tracking-[0.5px]">ТОП</span>
          </button>
          <ShopButton />
        </div>
      </div>

      <button
        type="button"
        onClick={() => setTab('season')}
        className="press flex items-center gap-3 rounded-2xl border border-line bg-surface px-3 py-2.5 text-left"
      >
        <img src={`/media/ranks/rank_${lg.index + 1}.png`} alt="" className="h-11 w-11 object-contain" />
        <div className="flex flex-1 flex-col gap-1.5">
          <div className="flex justify-between text-[13px]">
            <span className="font-bold">Лига «{lg.name}»</span>
            {lg.next && <span className="text-muted">до «{lg.next}» {Math.round(lg.progress * 100)}%</span>}
          </div>
          <Progress value={lg.progress} />
        </div>
        <Icon name="chevron" size={18} className="text-muted" />
      </button>

      <div className="grid grid-cols-3 gap-2.5">
        <DailyTile
          to="daily"
          icon="calendar"
          title="Награда дня"
          sub={tasks ? (tasks.daily.claimable ? `день ${tasks.daily.day}` : 'получено') : '…'}
          dot={tasks?.daily.claimable}
        />
        <DailyTile
          to="tasks"
          icon="check"
          title="Задания"
          sub={tasksLeft ? `${tasksLeft} за души` : 'все выполнены'}
          dot={!!tasksLeft}
        />
        <DailyTile
          to="contest"
          icon="star"
          title="Конкурс"
          sub="100 000 ₽"
          dot={contest?.phase === 'active' && contest.me.entries.length === 0}
        />
      </div>

      {/* friends are the main path to prizes */}
      <button
        type="button"
        onClick={() => setTab('friends')}
        className="press -mt-1 flex items-center justify-between gap-2 rounded-xl border border-[#8A6A22] px-3 py-2 text-left"
        style={{ background: 'linear-gradient(120deg, #3a2a0c, #15110a)' }}
      >
        <span className="flex items-center gap-2 text-[13px] font-extrabold text-[#F5D27A]">
          <Icon name="friends" size={18} /> Пригласи друга — +{perFriend} душ
        </span>
        <span className="text-[11px] font-bold text-[#e8d9b0]">{fr?.rules.arcana_souls ? `аркана ≈ ${Math.ceil(fr.rules.arcana_souls / perFriend)} друзей →` : 'призы →'}</span>
      </button>

      <div className="flex flex-col items-center gap-0.5">
        <div className="flex items-center justify-center gap-2.5">
          <Coin size={36} />
          <div className="font-display text-[36px] font-bold tracking-tight tabular-nums">{fmt(live.coins)}</div>
        </div>
        <div className="text-xs text-muted">
          ELT COIN · <span className="font-extrabold text-ink">+{short(snap.profit_per_hour)}</span> в час
        </div>
      </div>

      <div className="flex justify-center">
        <HeroStage />
      </div>

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 text-[15px] font-extrabold tabular-nums">
          <Bolt />
          {live.energy} / {snap.max_energy}
        </div>
        <button
          type="button"
          className="press flex items-center gap-1.5 rounded-xl border border-line-2 bg-surface-2 px-3.5 py-2 text-[13px] font-bold"
        >
          <Icon name="boost" size={16} className="text-gold" />
          Бусты
        </button>
      </div>
      <div className="-mt-1.5">
        <Progress value={live.energy / snap.max_energy} color="bg-gold" height={10} />
      </div>
    </div>
  )
}

function DailyTile({ to, icon, title, sub, dot }: { to: Tab; icon: IconName; title: string; sub: string; dot?: boolean }) {
  const setTab = useGame((s) => s.setTab)
  return (
    <button
      type="button"
      onClick={() => setTab(to)}
      className="press relative flex flex-col items-center gap-1.5 rounded-2xl border border-line bg-surface px-1.5 pt-3 pb-2.5"
    >
      {dot && <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-[#E0313B]" />}
      <Icon name={icon} size={28} className="text-ice" />
      <span className="text-xs font-bold">{title}</span>
      <span className="text-[11px] text-muted">{sub}</span>
    </button>
  )
}
