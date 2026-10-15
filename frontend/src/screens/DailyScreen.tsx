import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Coin, Icon } from '../components/icons'
import { Card, ScreenTitle } from '../components/ui'
import { api } from '../lib/api'
import { fmt, short } from '../lib/format'
import { haptic } from '../lib/telegram'
import { useGame } from '../store/game'

export function DailyScreen() {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const { data } = useQuery({ queryKey: ['tasks'], queryFn: api.tasks })
  const claim = useMutation({
    mutationFn: api.claimDaily,
    onSuccess: (r) => {
      haptic('medium')
      applyState(r.state)
      void qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const daily = data?.daily
  const todayReward = daily ? daily.rewards[daily.day - 1] : 0
  return (
    <div className="flex flex-col gap-[18px] px-4 pt-3.5 pb-6">
      <ScreenTitle title="Награда дня" subtitle="Заходите каждый день — награда растёт" back />

      <Card className="flex flex-col items-center gap-3 p-5 text-center">
        <div className="text-xs font-extrabold tracking-[1px] text-muted">ДЕНЬ {daily?.day ?? '…'} ИЗ {daily?.rewards.length ?? 10}</div>
        <div className="flex items-center gap-2.5">
          <Coin size={34} />
          <span className="font-display text-[34px] font-bold">{fmt(todayReward)}</span>
        </div>
        <button
          type="button"
          disabled={!daily?.claimable || claim.isPending}
          onClick={() => claim.mutate()}
          className="press w-full rounded-[14px] bg-red py-3.5 text-[15px] font-extrabold text-white disabled:bg-surface-2 disabled:text-muted"
        >
          {daily?.claimable ? 'Забрать' : 'Получено — возвращайтесь завтра'}
        </button>
      </Card>

      <div className="grid grid-cols-5 gap-2">
        {(daily?.rewards ?? []).map((a, i) => {
          const n = i + 1
          const today = n === daily!.day
          const got = daily!.claimable ? n < daily!.day : n <= daily!.day
          return (
            <div
              key={n}
              className={`flex flex-col items-center gap-1 rounded-xl border px-0.5 py-2 ${
                today && daily!.claimable
                  ? 'border-red bg-red'
                  : got
                    ? 'border-[#1F5134] bg-[#12301F] text-ok'
                    : 'border-line bg-surface'
              }`}
            >
              <span className="text-[10px] font-semibold">День {n}</span>
              {got ? <Icon name="done" size={16} /> : <Coin size={16} />}
              <span className="text-[11px] font-extrabold">{short(a)}</span>
            </div>
          )
        })}
      </div>
      <p className="m-0 text-xs leading-relaxed text-muted">
        Пропустили день — серия начнётся заново. После 10-го дня круг повторяется. Новый день — в 00:00 по Москве.
      </p>
    </div>
  )
}
