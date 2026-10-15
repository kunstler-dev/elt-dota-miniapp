import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { Icon } from '../components/icons'
import { Card } from '../components/ui'
import { api, ApiError, type Analysis, type AnalysisPay, type AnalysisPreview, type AnalysisReport } from '../lib/api'
import { haptic, openInvoice } from '../lib/telegram'

// Last Dota 2 match breakdown from OpenDota data: mistakes, comparison with the hero median, trends, position, heroes for your rank.

const SEV: Record<'high' | 'mid' | 'low', { label: string; cls: string }> = {
  high: { label: 'важно', cls: 'bg-red-deep text-[#FF8A90] border-red/50' },
  mid: { label: 'стоит поправить', cls: 'bg-[#2A2210] text-gold border-gold/40' },
  low: { label: 'мелочь', cls: 'bg-surface-2 text-muted border-line-2' },
}

const pct = (v: number) => `${Math.round(v * 100)}%`
const num = (v: number) => (v >= 100 ? Math.round(v).toLocaleString('ru-RU') : String(v))
const dateRu =(ms: number) => new Date(ms).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })

export function AnalysisScreen({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['analysis'], queryFn: () => api.analysis(), retry: false, staleTime: 60_000 })
  const refresh = useMutation({
    mutationFn: () => api.analysis(true),
    onSuccess: (d) => qc.setQueryData(['analysis'], d),
  })
  const pay = useMutation({
    mutationFn: async () => {
      const { url } = await api.analysisInvoice()
      return openInvoice(url)
    },
    onSuccess: (status) => {
      if (status === 'paid') {
        haptic('heavy')
        setTimeout(() => void qc.invalidateQueries({ queryKey: ['analysis'] }), 1500)
      }
    },
  })

  const data: Analysis | undefined = refresh.data ?? q.data
  const err = (refresh.error ?? q.error) as ApiError | null

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ground">
      <div className="flex items-center justify-between px-4 pt-3 pb-2">
        <button type="button" aria-label="Закрыть" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface">
          <Icon name="back" size={20} />
        </button>
        <div className="font-display text-lg font-bold">Разбор матча</div>
        <button
          type="button"
          disabled={refresh.isPending}
          onClick={() => refresh.mutate()}
          className="press rounded-xl border border-line bg-surface px-3 py-2 text-xs font-extrabold disabled:opacity-50"
        >
          {refresh.isPending ? '…' : 'Обновить'}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-[max(20px,env(safe-area-inset-bottom))]">
        {q.isLoading && <Loading />}
        {err && <ErrorBox err={err} />}
        {data?.status === 'private' && <PrivateBox text={data.message} />}
        {data?.status === 'locked' && (
          <Locked preview={data.preview} pay={data.pay} busy={pay.isPending} onPay={() => pay.mutate()} payError={pay.error} />
        )}
        {data?.status === 'ok' && <Report report={data.report} parsed={data.parsed} payInfo={data.pay} />}
      </div>
    </div>
  )
}

function Loading() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center text-sm text-muted">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-line-2 border-t-red" />
      Загружаем матчи с OpenDota…
    </div>
  )
}

function ErrorBox({ err }: { err: ApiError }) {
  const text: Record<string, string> = {
    too_often: 'Обновлять можно раз в 2 минуты.',
    rate_limited: 'OpenDota сейчас перегружен. Попробуйте через минуту.',
    unavailable: 'OpenDota временно недоступен. Попробуйте позже.',
    not_found: 'Матч не найден на OpenDota.',
  }
  return <Card className="mt-3 p-4 text-sm font-bold">{text[err.message] ?? 'Не удалось загрузить разбор'}</Card>
}

function PrivateBox({ text }: { text: string }) {
  return (
    <Card className="mt-3 flex flex-col gap-2 p-4">
      <div className="text-base font-extrabold">Матчи скрыты</div>
      <div className="text-sm leading-relaxed text-muted">{text}</div>
    </Card>
  )
}

function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="mt-4">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-[13px] font-extrabold tracking-wide text-muted uppercase">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  )
}

function HeroImg({ src, className = 'h-10 w-[72px]' }: { src: string | null; className?: string }) {
  return src ? (
    <img src={src} alt="" className={`${className} shrink-0 rounded-lg object-cover`} />
  ) : (
    <div className={`${className} shrink-0 rounded-lg bg-surface-2`} />
  )
}

function MatchHead(p: { hero: string; img: string | null; win: boolean; k: number; d: number; a: number; duration: string; sub?: string }) {
  return (
    <Card className="flex items-center gap-3 p-3">
      <HeroImg src={p.img} className="h-14 w-[100px]" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="truncate text-base font-extrabold">{p.hero}</span>
          <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-extrabold ${p.win ? 'bg-[#12301F] text-ok' : 'bg-red-deep text-[#FF8A90]'}`}>
            {p.win ? 'ПОБЕДА' : 'ПОРАЖЕНИЕ'}
          </span>
        </div>
        <div className="text-sm font-bold">
          {p.k} / <span className="text-[#FF8A90]">{p.d}</span> / {p.a}
          <span className="ml-2 text-xs font-semibold text-muted">{p.duration}</span>
        </div>
        {p.sub && <div className="truncate text-xs text-muted">{p.sub}</div>}
      </div>
    </Card>
  )
}

function Locked(props: { preview: AnalysisPreview | null; pay: AnalysisPay; busy: boolean; onPay: () => void; payError: Error | null }) {
  const { preview: p, pay } = props
  return (
    <div className="flex flex-col gap-3 pt-2">
      {p && <MatchHead hero={p.hero} img={p.hero_img} win={p.win} k={p.kills} d={p.deaths} a={p.assists} duration={p.duration} sub={`GPM ${p.gpm} · XPM ${p.xpm}`} />}
      <Card className="flex flex-col gap-3 p-4">
        <div className="text-base font-extrabold">Бесплатный разбор на этой неделе уже использован</div>
        <div className="text-sm leading-relaxed text-muted">
          {pay.free_per_week} разбор в неделю — бесплатно.
          {pay.next_free_ms ? ` Следующий бесплатный — ${dateRu(pay.next_free_ms)}.` : ''} С подпиской — разбор каждого матча, ошибки,
          тренды, лучшая позиция и герои под ваш ранг.
        </div>
        <button
          type="button"
          disabled={props.busy}
          onClick={props.onPay}
          className="press rounded-xl bg-gold py-3.5 text-[15px] font-extrabold text-black disabled:opacity-60"
        >
          Подписка на 30 дней — {pay.price} ⭐
        </button>
        {props.payError && <div className="text-center text-xs font-bold text-[#FF8A90]">Не удалось открыть оплату</div>}
        <div className="text-center text-[11px] text-muted">Продлевается автоматически, отменить можно в настройках Telegram</div>
      </Card>
    </div>
  )
}

function PayBadge({ pay }: { pay: AnalysisPay }) {
  const text =
    pay.mode === 'beta'
      ? 'Бета: бесплатно'
      : pay.mode === 'sub' && pay.subscription
        ? `Подписка до ${dateRu(pay.subscription.expires_ms)}`
        : `Бесплатных на неделе: ${pay.free_left}`
  return <span className="rounded-lg bg-surface-2 px-2 py-1 text-[11px] font-extrabold text-muted">{text}</span>
}

function Report({ report: r, parsed, payInfo }: { report: AnalysisReport; parsed: boolean; payInfo: AnalysisPay }) {
  const last = r.last
  const t = r.trends
  return (
    <div className="pt-1">
      <div className="flex items-center gap-3">
        {r.profile.avatar ? <img src={r.profile.avatar} alt="" className="h-10 w-10 rounded-xl" /> : null}
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-extrabold">{r.profile.name ?? 'Игрок'}</span>
          <span className="text-xs text-muted">Ранг: {r.profile.bracket_name}</span>
        </div>
        <PayBadge pay={payInfo} />
      </div>

      {last && (
        <Section title="Последний матч">
          <MatchHead
            hero={last.hero}
            img={last.hero_img}
            win={last.win}
            k={last.kills}
            d={last.deaths}
            a={last.assists}
            duration={last.duration}
            sub={`${last.pos_name} · линия: ${last.lane_name}`}
          />
          {!parsed && (
            <div className="mt-2 rounded-xl border border-dashed border-line-2 p-3 text-xs leading-relaxed text-muted">
              Матч ещё не разобран OpenDota — мы запросили разбор. Линия, добивания к 10:00 и тайминги предметов появятся через 5–15 минут: нажмите «Обновить».
            </div>
          )}
          <div className="mt-2 grid grid-cols-4 gap-2">
            <Stat label="GPM" value={last.stats.gpm} />
            <Stat label="XPM" value={last.stats.xpm} />
            <Stat label="KDA" value={last.kda} />
            <Stat label="Участие" value={pct(last.stats.kp)} />
          </div>
          {last.lane.known && <div className="mt-2 text-sm font-bold">{last.lane.text}</div>}
        </Section>
      )}

      {last && last.benchmarks.some((b) => b.pct != null) && (
        <Section title="Сравнение с игроками на герое">
          <Card className="flex flex-col gap-2.5 p-3">
            {last.benchmarks.map((b) => (
              <div key={b.label} className="flex flex-col gap-1">
                <div className="flex justify-between text-xs">
                  <span className="font-bold">{b.label}</span>
                  <span className="text-muted">
                    {num(b.value)}
                    {b.median != null && ` · медиана ${num(b.median)}`}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={`h-full rounded-full ${(b.pct ?? 0) < 0.3 ? 'bg-red' : (b.pct ?? 0) < 0.6 ? 'bg-gold' : 'bg-ok'}`}
                    style={{ width: `${Math.max(4, (b.pct ?? 0) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
            <div className="text-[11px] text-muted">Полоса — какой процент игр на этом герое у вас хуже</div>
          </Card>
        </Section>
      )}

      {r.mistakes.length > 0 && (
        <Section title="Ошибки и как исправить">
          <div className="flex flex-col gap-2">
            {r.mistakes.map((m) => (
              <Card key={m.title} className="flex flex-col gap-1.5 p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-extrabold">{m.title}</span>
                  <span className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-extrabold ${SEV[m.severity].cls}`}>{SEV[m.severity].label}</span>
                </div>
                <div className="text-xs leading-relaxed text-muted">{m.tip}</div>
              </Card>
            ))}
          </div>
        </Section>
      )}

      {last && last.items.length > 0 && (
        <Section title="Тайминги предметов">
          <Card className="flex flex-wrap gap-2 p-3">
            {last.items.map((i) => (
              <span key={i.key} className="rounded-lg bg-surface-2 px-2 py-1 text-xs font-bold">
                {i.name} <span className="text-muted">{i.t}</span>
              </span>
            ))}
          </Card>
        </Section>
      )}

      <Section title="Как поднять MMR">
        <div className="flex flex-col gap-2">
          {r.tips.map((tip, i) => (
            <Card key={tip.title} className="flex gap-3 p-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-red font-display text-sm font-bold text-white">{i + 1}</span>
              <div className="flex flex-col gap-1">
                <span className="text-sm font-extrabold">{tip.title}</span>
                <span className="text-xs leading-relaxed text-muted">{tip.text}</span>
              </div>
            </Card>
          ))}
        </div>
      </Section>

      {t.games > 0 && (
        <Section title={`Последние ${t.games} игр`} right={<span className="text-xs font-bold">{pct(t.winrate)} побед</span>}>
          <Card className="flex flex-col gap-3 p-3">
            <div className="flex h-10 items-end gap-[3px]">
              {t.series.map((m, i) => (
                <div
                  key={i}
                  className={`flex-1 rounded-sm ${m.win ? 'bg-ok' : 'bg-red'}`}
                  style={{ height: `${Math.min(100, 25 + m.kda * 15)}%`, opacity: 0.85 }}
                />
              ))}
            </div>
            <div className="grid grid-cols-4 gap-2">
              <Stat label="KDA" value={t.avg.kda} />
              <Stat label="GPM" value={t.avg.gpm} delta={t.delta.gpm} />
              <Stat label="Смерти" value={t.avg.deaths} delta={t.delta.deaths} invert />
              <Stat label="Серия" value={`${t.streak.n}${t.streak.win ? 'W' : 'L'}`} />
            </div>
            <div className="flex flex-col gap-1.5">
              {t.heroes.map((h) => (
                <div key={h.hero_id} className="flex items-center gap-2 text-xs">
                  <HeroImg src={h.img} className="h-6 w-11" />
                  <span className="flex-1 truncate font-bold">{h.name}</span>
                  <span className="text-muted">{h.games} игр</span>
                  <span className={`w-10 text-right font-extrabold ${h.winrate >= 0.5 ? 'text-ok' : 'text-[#FF8A90]'}`}>{pct(h.winrate)}</span>
                </div>
              ))}
            </div>
          </Card>
        </Section>
      )}

      <Section title="Ваша позиция">
        <Card className="flex flex-col gap-2 p-3">
          <div className="text-base font-extrabold">{r.position.name}</div>
          <div className="text-xs leading-relaxed text-muted">{r.position.explanation}</div>
          <div className="grid grid-cols-5 gap-1.5">
            {r.position.rows.map((p) => (
              <div
                key={p.pos}
                className={`flex flex-col items-center rounded-lg py-1.5 text-[11px] ${p.pos === r.position.best ? 'bg-red text-white' : 'bg-surface-2'}`}
              >
                <span className="font-extrabold">Pos {p.pos}</span>
                <span className="opacity-80">{p.games} игр</span>
                <span className="font-bold">{p.winrate != null ? pct(p.winrate) : '—'}</span>
              </div>
            ))}
          </div>
        </Card>
      </Section>

      {(r.heroes.top.length > 0 || r.heroes.drop.length > 0) && (
        <Section title="Герои для вас">
          <Card className="flex flex-col gap-2 p-3">
            {r.heroes.top.map((h) => (
              <HeroRow key={h.hero_id} img={h.img} name={h.name} reason={h.reason} tag="играть" good />
            ))}
            {r.heroes.drop.map((h) => (
              <HeroRow key={h.hero_id} img={h.img} name={h.name} reason={h.reason} tag="отложить" />
            ))}
          </Card>
        </Section>
      )}

      {r.meta.best.length > 0 && (
        <Section title={`Сильнейшие герои: ${r.meta.bracket_name}`}>
          <Card className="flex flex-col gap-1.5 p-3">
            {r.meta.best.slice(0, 5).map((h) => (
              <div key={h.hero_id} className="flex items-center gap-2 text-xs">
                <HeroImg src={h.img} className="h-6 w-11" />
                <span className="flex-1 truncate font-bold">{h.name}</span>
                <span className="font-extrabold text-ok">{(h.winrate * 100).toFixed(1)}%</span>
              </div>
            ))}
          </Card>
        </Section>
      )}

      <div className="mt-4 text-center text-[11px] text-muted">Данные: OpenDota. Разбор обновляется после каждого нового матча.</div>
    </div>
  )
}

function HeroRow(p: { img: string | null; name: string; reason: string; tag: string; good?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <HeroImg src={p.img} className="h-8 w-14" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-extrabold">{p.name}</span>
        <span className="truncate text-[11px] text-muted">{p.reason}</span>
      </div>
      <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-extrabold ${p.good ? 'bg-[#12301F] text-ok' : 'bg-red-deep text-[#FF8A90]'}`}>{p.tag}</span>
    </div>
  )
}

function Stat({ label, value, delta, invert }: { label: string; value: number | string; delta?: number; invert?: boolean }) {
  const good = delta != null && (invert ? delta < 0 : delta > 0)
  return (
    <div className="flex flex-col items-center rounded-xl bg-surface-2 py-2">
      <span className="text-[10px] font-bold text-muted uppercase">{label}</span>
      <span className="text-sm font-extrabold">{value}</span>
      {delta != null && delta !== 0 && (
        <span className={`text-[10px] font-bold ${good ? 'text-ok' : 'text-[#FF8A90]'}`}>
          {delta > 0 ? '+' : ''}
          {Math.abs(delta) >= 10 ? Math.round(delta) : Math.round(delta * 10) / 10}
        </span>
      )}
    </div>
  )
}
