import { Coin } from '../components/icons'
import { Card, ScreenTitle } from '../components/ui'
import { fmt, short } from '../lib/format'
import { useLive } from '../store/useLive'
import { ArsenalPanel } from './ArsenalPanel'

export function MineScreen() {
  const live = useLive()
  if (!live) return null

  return (
    <div className="flex flex-col gap-3 px-4 pt-3.5 pb-6">
      <ScreenTitle title="Прокачка" subtitle="Покупайте героев и одевайте их в сеты из Dota 2" />
      <Card className="flex items-center justify-between px-3.5 py-3">
        <div className="flex items-center gap-2">
          <Coin size={22} />
          <span className="font-display text-lg font-bold tabular-nums">{fmt(live.coins)}</span>
        </div>
        <div className="text-[13px] text-muted">
          +<span className="font-extrabold text-ink">{short(live.snap.profit_per_hour)}</span> / час
        </div>
      </Card>
      <ArsenalPanel />
    </div>
  )
}
