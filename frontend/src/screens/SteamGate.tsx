import { useEffect, useState } from 'react'

import { Icon } from '../components/icons'
import { api } from '../lib/api'
import { haptic, openExternal, tg } from '../lib/telegram'
import { useGame } from '../store/game'

const POINTS = [
  'Один Steam — один игрок. В топе только живые люди, призы — настоящим игрокам.',
  'Пароль вводится на сайте Steam — мы получаем только ваш публичный Steam ID и ник.',
  'Аккаунт должен быть с Dota 2: боты и пустые аккаунты не попадут в рейтинг.',
]

export function SteamGate() {
  const load = useGame((s) => s.load)
  const [waiting, setWaiting] = useState(false)
  const [busy, setBusy] = useState(false)

  // while the player is on the Steam website in the browser, periodically check whether the account got linked
  useEffect(() => {
    if (!waiting) return
    const id = setInterval(() => void load(), 3000)
    const onVisible = () => document.visibilityState === 'visible' && void load()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [waiting, load])

  async function connect() {
    setBusy(true)
    try {
      const { url } = await api.steamLink()
      haptic('medium')
      openExternal(url)
      setWaiting(true)
    } finally {
      setBusy(false)
    }
  }

  async function devLink() {
    await api.steamDevLink(`7656119${String(Date.now()).slice(-10)}`)
    await load()
  }

  return (
    <div className="mx-auto flex h-full max-w-[480px] flex-col px-5 pt-6 pb-[max(20px,env(safe-area-inset-bottom))]">
      <div className="flex flex-1 flex-col items-center justify-center gap-5 text-center">
        <img src="/media/pudge.png" alt="" className="h-[200px] w-[200px] object-contain" />
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-display text-[24px] font-bold">Привяжите Steam</h1>
          <p className="m-0 text-sm text-muted">Без этого Пудж не подпустит к тапам</p>
        </div>
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0 text-left">
          {POINTS.map((p) => (
            <li key={p} className="flex gap-2.5 rounded-2xl border border-line bg-surface p-3 text-[13px] leading-snug">
              <Icon name="done" size={18} className="mt-px shrink-0 text-ice" />
              {p}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-2.5 pt-4">
        {waiting && (
          <div className="flex items-center justify-center gap-2 text-[13px] text-muted">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-ice border-t-transparent" />
            Ждём подтверждения в Steam…
          </div>
        )}
        <button
          type="button"
          onClick={connect}
          disabled={busy}
          className="press flex items-center justify-center gap-2.5 rounded-[14px] bg-red py-[15px] text-[15px] font-extrabold text-white disabled:opacity-60"
        >
          {waiting ? 'Открыть Steam ещё раз' : 'Войти через Steam'}
        </button>
        {waiting && (
          <button type="button" onClick={() => void load()} className="py-2 text-[13px] font-bold text-ice">
            Я привязал — проверить
          </button>
        )}
        {!tg && (
          <button type="button" onClick={devLink} className="py-2 text-xs text-muted underline">
            Dev: привязать тестовый Steam
          </button>
        )}
      </div>
    </div>
  )
}
