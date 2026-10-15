import { useState } from 'react'

import { Icon } from '../components/icons'
import { api } from '../lib/api'
import { haptic, tg } from '../lib/telegram'
import { useGame } from '../store/game'

/** Without a subscription to the main channel the app doesn't open, same as without Steam. */
export function SubscribeGate({ channel, url }: { channel: string; url: string }) {
  const load = useGame((s) => s.load)
  const [opened, setOpened] = useState(false)
  const [busy, setBusy] = useState(false)
  const [fail, setFail] = useState(false)

  function open() {
    if (tg) tg.openTelegramLink(url)
    else window.open(url, '_blank')
    setOpened(true)
  }

  async function check() {
    setBusy(true)
    setFail(false)
    try {
      const r = await api.subscriptionCheck()
      if (r.ok) {
        haptic('medium')
        await load()
      } else {
        haptic('heavy')
        setFail(true)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-[480px] flex-col px-5 pt-6 pb-[max(20px,env(safe-area-inset-bottom))]">
      <div className="flex flex-1 flex-col items-center justify-center gap-5 text-center">
        <img src="/media/logo.jpg" alt="" className="h-[220px] w-[220px] rounded-3xl object-cover" />
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-display text-[24px] font-bold">Подпишитесь на {channel}</h1>
          <p className="m-0 text-sm text-muted">
            Здесь новости ELT, розыгрыши аркан и итоги конкурсов. Без подписки игра недоступна.
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-2.5 pt-4">
        {fail && <div className="text-center text-[13px] text-[#FF8A90]">Подписка пока не найдена — подпишитесь и проверьте ещё раз</div>}
        <button
          type="button"
          onClick={open}
          className="press flex items-center justify-center gap-2 rounded-[14px] bg-red py-[15px] text-[15px] font-extrabold text-white"
        >
          <Icon name="friends" size={18} /> Подписаться на {channel}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={check}
          className={`press rounded-[14px] border py-3.5 text-[15px] font-extrabold ${
            opened ? 'border-ice-line bg-[#0E1A24] text-ice' : 'border-line-2 bg-surface-2 text-muted'
          } disabled:opacity-60`}
        >
          {busy ? 'Проверяем…' : 'Я подписался — проверить'}
        </button>
      </div>
    </div>
  )
}
