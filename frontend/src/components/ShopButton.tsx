import { short } from '../lib/format'
import { useGame } from '../store/game'
import { Icon, Soul } from './icons'

/** Shop button in the style of the Dota HUD: gold frame, top right, souls balance next to it. */
export function ShopButton() {
  const souls = useGame((s) => s.snap?.souls ?? 0)
  const setTab = useGame((s) => s.setTab)
  return (
    <button
      type="button"
      onClick={() => setTab('shop')}
      className="press flex items-center gap-2 rounded-xl border border-[#8A6A22] bg-[#1E180B] py-1.5 pr-3 pl-2"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#C9A24A] text-[#1E180B]">
        <Icon name="shop" size={18} />
      </span>
      <span className="flex flex-col items-start leading-tight">
        <span className="text-[10px] font-extrabold tracking-[1.5px] text-[#E8C46A]">МАГАЗИН</span>
        <span className="flex items-center gap-1 text-sm font-extrabold tabular-nums">
          <Soul size={14} />
          {short(souls)}
        </span>
      </span>
    </button>
  )
}
