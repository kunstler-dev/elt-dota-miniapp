import { useEffect, useState } from 'react'

import { Splash } from './components/Splash'
import { TabBar } from './components/TabBar'
import { initTelegram } from './lib/telegram'
import { ContestScreen } from './screens/ContestScreen'
import { DailyScreen } from './screens/DailyScreen'
import { FriendsScreen } from './screens/FriendsScreen'
import { GamesScreen } from './screens/GamesScreen'
import { MineScreen } from './screens/MineScreen'
import { SeasonScreen } from './screens/SeasonScreen'
import { ShopScreen } from './screens/ShopScreen'
import { ProfileScreen } from './screens/ProfileScreen'
import { SteamGate } from './screens/SteamGate'
import { SubscribeGate } from './screens/SubscribeGate'
import { TapScreen } from './screens/TapScreen'
import { TasksScreen } from './screens/TasksScreen'
import { useGame } from './store/game'

const SCREENS = {
  tap: TapScreen,
  tasks: TasksScreen,
  mine: MineScreen,
  games: GamesScreen,
  friends: FriendsScreen,
  season: SeasonScreen,
  shop: ShopScreen,
  daily: DailyScreen,
  profile: ProfileScreen,
  contest: ContestScreen,
}

const MIN_SPLASH_MS = 1800

export default function App() {
  const tab = useGame((s) => s.tab)
  const me = useGame((s) => s.me)
  const error = useGame((s) => s.error)
  const load = useGame((s) => s.load)
  const flush = useGame((s) => s.flush)
  const [minSplashDone, setMinSplashDone] = useState(false)

  useEffect(() => {
    initTelegram()
    void load()
    const t = setTimeout(() => setMinSplashDone(true), MIN_SPLASH_MS)
    // when the app is minimized, send the queued taps right away
    const onHide = () => document.visibilityState === 'hidden' && void flush()
    document.addEventListener('visibilitychange', onHide)
    return () => {
      clearTimeout(t)
      document.removeEventListener('visibilitychange', onHide)
    }
  }, [load, flush])

  if (!me || !minSplashDone) return <Splash error={error} />
  if (!me.steam) return <SteamGate />
  if (!me.subscription.ok) return <SubscribeGate channel={me.subscription.channel} url={me.subscription.url} />

  const Screen = SCREENS[tab]
  return (
    <div className="mx-auto flex h-full max-w-[480px] flex-col overflow-hidden">
      <main key={tab} className="no-scrollbar min-h-0 flex-1 overflow-y-auto">
        <Screen />
      </main>
      <TabBar />
    </div>
  )
}
