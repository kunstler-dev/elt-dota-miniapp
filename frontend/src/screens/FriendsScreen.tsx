import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { AnimatePresence } from 'framer-motion'

import { Avatar } from '../components/Avatar'
import { PlayerSheet } from '../components/PlayerSheet'
import { Icon, Soul } from '../components/icons'
import { Card, Segmented } from '../components/ui'
import { api, type FriendStatus } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic, tg } from '../lib/telegram'
import { GuildPanel } from './GuildPanel'
import { useGame } from '../store/game'
import { ChatView } from '../components/ChatView'

const STATUS: Record<FriendStatus, [string, string]> = {
  confirmed: ['Засчитан', 'text-ok'],
  no_steam: ['Ждём привязку Steam', 'text-gold'],
  not_verified: ['Steam не прошёл проверку', 'text-[#FF8A90]'],
}

type View = 'mine' | 'top'

type Tab = 'friends' | 'guild' | 'chat'

/** Friends tab: referrals and guild. */
export function FriendsScreen() {
  const [tab, setTab] = useState<Tab>('friends')
  const isAdmin = useGame((s) => !!s.me?.user.is_admin)
  return (
    <div className="flex min-h-full flex-col">
      <div className="px-4 pt-3">
        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            ['friends', 'Друзья'],
            ['guild', 'Гильдия'],
            ['chat', 'Чат'],
          ]}
        />
      </div>
      {tab === 'friends' ? (
        <FriendsPanel />
      ) : tab === 'guild' ? (
        <GuildPanel />
      ) : (
        <div className="px-4 pt-3">
          <div className="mb-2 text-xs text-muted">Мировой чат: все игроки ELT. Без ссылок и рекламы.</div>
          <ChatView channel="world" canModerate={isAdmin} />
        </div>
      )}
    </div>
  )
}

function FriendsPanel() {
  const [view, setView] = useState<View>('mine')
  const [copied, setCopied] = useState(false)
  const [player, setPlayer] = useState<number | null>(null)
  const { data } = useQuery({ queryKey: ['friends'], queryFn: api.friends })
  const { data: top } = useQuery({ queryKey: ['top-referrals'], queryFn: api.topReferrals, enabled: view === 'top' })
  const link = data?.invite_link
  const r = data?.rules

  function share() {
    if (!link) return
    const text = 'Залетай в ELT: бей Пуджа, качай героев и забирай арканы'
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`
    if (tg) tg.openTelegramLink(url)
    else window.open(url, '_blank')
  }

  async function copy() {
    if (!link) return
    await navigator.clipboard.writeText(link).catch(() => undefined)
    haptic('light')
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-4 px-4 pt-3.5 pb-6">
        <div className="flex flex-col items-center gap-1 pt-1.5 text-center">
          <h1 className="m-0 font-display text-2xl font-bold">Приглашай друзей</h1>
          <div className="max-w-[310px] text-[13px] text-muted">Души за каждого друга и процент с его душ — навсегда</div>
        </div>

        {r && (
          <div className="grid grid-cols-2 gap-2.5">
            <Rule icon={<Icon name="user" className="text-ice" />} value={`+${r.bonus}`} text="за друга" />
            <Rule icon={<Icon name="star" className="text-gold" />} value={`+${r.bonus_premium}`} text="за друга с Premium" />
            <div className="col-span-2">
              <Rule
                icon={<Icon name="mine" className="text-ice" />}
                value={`${Math.round(r.share_l1 * 100)}%`}
                text={`с душ друзей и ${Math.round(r.share_l2 * 100)}% с их друзей — навсегда`}
              />
            </div>
          </div>
        )}

        <Card className="grid grid-cols-3 divide-x divide-line py-3 text-center">
          <Stat value={data?.confirmed ?? 0} label="засчитано" />
          <Stat value={data?.invited ?? 0} label="приглашено" />
          <div className="flex flex-col items-center gap-0.5">
            <span className="flex items-center gap-1 font-display text-lg font-bold">
              <Soul size={16} />
              {fmt(data?.souls_earned ?? 0)}
            </span>
            <span className="text-[11px] text-muted">душ принесли</span>
          </div>
        </Card>

        <Segmented<View>
          value={view}
          onChange={setView}
          options={[
            ['mine', 'Мои друзья'],
            ['top', 'Топ пригласивших'],
          ]}
        />

        {view === 'mine' ? (
          <div className="flex flex-col gap-2">
            {data && data.friends.length === 0 && (
              <Card className="p-4 text-center text-[13px] text-muted">Пока никого — отправьте ссылку первому другу</Card>
            )}
            {data?.friends.map((f, i) => (
              <Card key={i} className="flex items-center gap-3 rounded-[14px] p-3">
                <Avatar name={f.name} photo={f.photo_url} />
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center gap-1 truncate text-sm font-bold">
                    {f.name}
                    {f.is_premium && <Icon name="star" size={13} className="text-gold" />}
                  </div>
                  <div className={`text-xs ${STATUS[f.status][1]}`}>{STATUS[f.status][0]}</div>
                </div>
                <span className="flex items-center gap-1 text-[13px] font-extrabold">
                  <Soul size={13} />+{fmt(f.souls)}
                </span>
              </Card>
            ))}
            <p className="m-0 text-xs leading-relaxed text-muted">
              Друг засчитывается, когда привяжет Steam и аккаунт пройдёт проверку: открытый профиль, возраст от 180 дней и
              опыт в Dota 2. Боты и мультиаккаунты наград не приносят.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {top?.top.length === 0 && <Card className="p-4 text-center text-[13px] text-muted">Рейтинг пока пуст — будьте первым</Card>}
            {top?.top.map((t) => (
              <button key={t.rank} type="button" onClick={() => setPlayer(t.id)} className={`press flex items-center gap-3 rounded-[14px] border bg-surface p-2.5 text-left ${t.me ? 'border-ice-line' : 'border-line'}`}>
                <span
                  className={`w-7 text-center font-display text-sm font-bold ${t.rank === 1 ? 'text-gold' : t.rank <= 3 ? 'text-ink' : 'text-muted'}`}
                >
                  {t.rank}
                </span>
                <Avatar name={t.name} photo={t.photo_url} size={34} />
                <span className="flex-1 truncate text-sm font-bold">{t.name}</span>
                <span className="text-[13px] font-extrabold">{t.value}</span>
              </button>
            ))}
            {top && (
              <div className="text-center text-xs text-muted">
                {top.me.rank ? `Вы на ${top.me.rank} месте` : 'Пригласите первого друга, чтобы попасть в рейтинг'}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="sticky bottom-0 flex gap-2.5 border-t border-[#1A212B] bg-ground px-4 py-2.5">
        <button
          type="button"
          onClick={share}
          disabled={!link}
          className="press flex-1 rounded-[14px] bg-red py-[15px] text-[15px] font-extrabold text-white disabled:opacity-50"
        >
          Пригласить друга
        </button>
        <button
          type="button"
          onClick={copy}
          disabled={!link}
          aria-label="Скопировать ссылку"
          className="press flex w-[52px] items-center justify-center rounded-[14px] border border-line-2 bg-surface-2 disabled:opacity-50"
        >
          <Icon name={copied ? 'done' : 'copy'} size={20} />
        </button>
      </div>
      <AnimatePresence>{player !== null && <PlayerSheet id={player} onClose={() => setPlayer(null)} />}</AnimatePresence>
    </div>
  )
}

function Rule({ icon, value, text }: { icon: React.ReactNode; value: string; text: string }) {
  return (
    <Card className="flex flex-col gap-1.5 p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-2">{icon}</span>
        <span className="flex items-center gap-1 font-display text-base font-bold">
          {value}
          {!value.endsWith('%') && <Soul size={14} />}
        </span>
      </div>
      <span className="text-xs leading-snug text-muted">{text}</span>
    </Card>
  )
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="font-display text-lg font-bold">{fmt(value)}</span>
      <span className="text-[11px] text-muted">{label}</span>
    </div>
  )
}
