import type { ReactNode } from 'react'

import { useGame } from '../store/game'
import { Icon } from './icons'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-surface ${className}`}>{children}</div>
}

export function ScreenTitle({ title, subtitle, back }: { title: string; subtitle?: string; back?: boolean }) {
  const setTab = useGame((s) => s.setTab)
  return (
    <div className="flex items-center gap-2.5">
      {back && (
        <button
          type="button"
          aria-label="Назад"
          onClick={() => setTab('tap')}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface"
        >
          <Icon name="back" size={20} />
        </button>
      )}
      <div className="flex flex-col gap-1">
        <h1 className="m-0 font-display text-[22px] font-bold">{title}</h1>
        {subtitle && <div className="text-[13px] text-muted">{subtitle}</div>}
      </div>
    </div>
  )
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: [T, string][]
  onChange: (v: T) => void
}) {
  return (
    <div
      className="grid gap-1 rounded-[14px] border border-line bg-surface p-1"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map(([v, label]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`rounded-[10px] py-2.5 text-[13px] font-bold ${v === value ? 'bg-line text-ink' : 'text-muted'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export function Progress({ value, color = 'bg-ice', height = 8 }: { value: number; color?: string; height?: number }) {
  return (
    <div className="overflow-hidden rounded bg-track" style={{ height }}>
      <div className={`h-full rounded ${color} transition-[width] duration-300`} style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  )
}
