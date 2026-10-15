import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Icon, Soul } from '../components/icons'
import { Card, ScreenTitle } from '../components/ui'
import { api, ApiError, type TaskItem } from '../lib/api'
import { fmt } from '../lib/format'
import { haptic, tg } from '../lib/telegram'
import { useGame } from '../store/game'

const ERRORS: Record<string, string> = {
  not_subscribed: 'Подписка не найдена — подпишитесь и проверьте ещё раз',
  not_boosted: 'Буст не найден. Бустить каналы могут только пользователи Telegram Premium',
  check_unavailable: 'Telegram не ответил, попробуйте через минуту',
}

export function TasksScreen() {
  const qc = useQueryClient()
  const applyState = useGame((s) => s.applyState)
  const { data } = useQuery({ queryKey: ['tasks'], queryFn: api.tasks })
  const [opened, setOpened] = useState<Set<string>>(new Set())
  const [error, setError] = useState<{ id: string; text: string } | null>(null)

  const check = useMutation({
    mutationFn: (id: string) => api.checkTask(id),
    onSuccess: (r) => {
      haptic('medium')
      setError(null)
      applyState(r.state)
      void qc.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (e, id) => {
      haptic('heavy')
      const code = e instanceof ApiError ? e.message : ''
      setError({ id, text: ERRORS[code] ?? 'Не получилось проверить' })
    },
  })

  function open(t: TaskItem) {
    if (tg) tg.openTelegramLink(t.url)
    else window.open(t.url, '_blank')
    setOpened((s) => new Set(s).add(t.id))
  }

  return (
    <div className="flex flex-col gap-[18px] px-4 pt-3.5 pb-6">
      <ScreenTitle title="Задания" subtitle="Выполняйте задания — получайте души для магазина" back />

      <section className="flex flex-col gap-2.5">
        {data?.tasks.map((t) => (
          <Card key={t.id} className="flex flex-col gap-2 p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-surface-2 font-display text-xs font-bold text-ice">
                {t.badge}
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="text-sm font-bold">{t.title}</div>
                <div className="flex items-center gap-1 text-[13px] font-bold text-[#FF8A5C]">
                  <Soul size={13} />+{fmt(t.souls)}
                </div>
              </div>
              {t.done ? (
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#12301F] text-ok" aria-label="Выполнено">
                  <Icon name="done" size={18} />
                </span>
              ) : opened.has(t.id) ? (
                <button
                  type="button"
                  disabled={check.isPending}
                  onClick={() => check.mutate(t.id)}
                  className="press rounded-[10px] bg-red px-3.5 py-2 text-[13px] font-extrabold text-white disabled:opacity-60"
                >
                  Проверить
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => open(t)}
                  className="press rounded-[10px] border border-line-2 bg-surface-2 px-3.5 py-2 text-[13px] font-extrabold"
                >
                  {t.kind === 'boost' ? 'Забустить' : 'Подписаться'}
                </button>
              )}
            </div>
            {t.kind === 'boost' && !t.done && (
              <div className="text-xs text-muted">Нужен Telegram Premium — у премиум-аккаунтов есть бусты для каналов</div>
            )}
            {error?.id === t.id && <div className="text-xs text-[#FF8A90]">{error.text}</div>}
          </Card>
        ))}
      </section>
    </div>
  )
}
