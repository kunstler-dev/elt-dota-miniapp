import { useGame, type Tab } from '../store/game'
import { Icon, type IconName } from './icons'

const TABS: [Tab, IconName, string][] = [
  ['tap', 'tap', 'Тап'],
  ['mine', 'mine', 'Прокачка'],
  ['games', 'games', 'Игры'],
  ['friends', 'friends', 'Друзья'],
  ['profile', 'user', 'Профиль'],
]

export function TabBar() {
  const tab = useGame((s) => s.tab)
  const setTab = useGame((s) => s.setTab)
  return (
    <nav className="grid grid-cols-5 gap-1 border-t border-[#1A212B] bg-bar px-2.5 pt-2 pb-[max(14px,env(safe-area-inset-bottom))]">
      {TABS.map(([t, icon, label]) => {
        const on = tab === t || (t === 'tap' && (tab === 'tasks' || tab === 'daily'))
        return (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`flex flex-col items-center gap-1 rounded-xl py-1.5 ${on ? 'bg-[#16202B] text-ice' : 'text-[#7B8798]'}`}
          >
            <Icon name={icon} />
            <span className="text-[11px] font-bold">{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
