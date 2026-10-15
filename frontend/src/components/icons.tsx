// Icons are inline SVG with stroke=currentColor so classes can color them.

type P = { className?: string; size?: number }

export function Coin({ size = 18, className }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <path d="M12 2l8 6-8 14L4 8z" fill="#6CC4FF" />
      <path d="M4 8h16M12 2l-3 6 3 14 3-14z" fill="none" stroke="#0B3550" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

/** Soul: the Shadow Fiend "Necromastery" skill icon from Dota 2 files */
export function Soul({ size = 18, className = '' }: P) {
  return (
    <img
      src="/media/souls.png"
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      draggable={false}
      className={`inline-block shrink-0 ${className}`}
      style={{ width: size, height: size, borderRadius: Math.max(2, size / 6), boxShadow: '0 0 0 1px rgba(0,0,0,.6)' }}
    />
  )
}

export function Bolt({ size = 20, className }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="#F5C542" aria-hidden="true" className={className}>
      <path d="M13 2L4 14h7l-1 8 9-12h-7z" />
    </svg>
  )
}

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.9,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function Icon({ name, size = 22, className }: P & { name: IconName }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={className} {...stroke}>
      {PATHS[name]}
    </svg>
  )
}

export type IconName = keyof typeof PATHS

const PATHS = {
  tap: <path d="M12 2l8 6-8 14L4 8z" />,
  mine: (
    <>
      <path d="M3 17l6-6 4 4 8-8" />
      <path d="M15 7h6v6" />
    </>
  ),
  games: (
    <>
      <rect x="2" y="7" width="20" height="11" rx="5" />
      <path d="M7 11v3M5.5 12.5h3M15.5 12h.01M18 13.5h.01" />
    </>
  ),
  friends: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5" />
      <path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c2.2.6 3.5 2.4 3.5 5.2" />
    </>
  ),
  season: (
    <>
      <path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z" />
      <path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </>
  ),
  cards: (
    <>
      <rect x="3" y="4" width="5" height="16" rx="1.5" />
      <rect x="9.5" y="4" width="5" height="16" rx="1.5" />
      <rect x="16" y="4" width="5" height="16" rx="1.5" />
    </>
  ),
  check: (
    <>
      <path d="M9 11l3 3 8-8" />
      <path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
    </>
  ),
  chevron: <path d="M9 6l6 6-6 6" />,
  back: <path d="M15 6l-6 6 6 6" />,
  boost: (
    <>
      <path d="M5 15l7-7 7 7" />
      <path d="M5 21l7-7 7 7" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </>
  ),
  star: <path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z" />,
  quiz: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01" />
    </>
  ),
  done: <path d="M5 12l5 5 9-10" />,
  shop: (
    <>
      <path d="M5 8h14l-1.2 11.2a2 2 0 0 1-2 1.8H8.2a2 2 0 0 1-2-1.8z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </>
  ),
}
