// Wrapper over window.Telegram.WebApp: in a regular browser (local development) everything is a safe no-op.

type Haptic = {
  impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
  notificationOccurred: (type: 'error' | 'success' | 'warning') => void
}

type WebApp = {
  initData: string
  ready: () => void
  expand: () => void
  disableVerticalSwipes?: () => void
  setHeaderColor?: (color: string) => void
  setBackgroundColor?: (color: string) => void
  openTelegramLink: (url: string) => void
  openLink: (url: string) => void
  openInvoice?: (url: string, cb?: (status: 'paid' | 'cancelled' | 'failed' | 'pending') => void) => void
  HapticFeedback?: Haptic
  platform?: string
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp }
  }
}

export const tg: WebApp | undefined = window.Telegram?.WebApp?.initData ? window.Telegram.WebApp : undefined

export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
  tg.disableVerticalSwipes?.()
  tg.setHeaderColor?.('#07090D')
  tg.setBackgroundColor?.('#07090D')
}

/** External link in the system browser (Steam sign-in doesn't work inside the Telegram WebView). */
export function openExternal(url: string) {
  if (tg) tg.openLink(url)
  else window.open(url, '_blank')
}

/** Telegram Stars payment: the invoice opens on top of the Mini App, the result arrives in a callback. */
export function openInvoice(url: string): Promise<string> {
  return new Promise((resolve) => {
    if (tg?.openInvoice) tg.openInvoice(url, resolve)
    else {
      window.open(url, '_blank')
      resolve('pending')
    }
  })
}

export function haptic(style: 'light' | 'medium' | 'heavy' = 'light') {
  tg?.HapticFeedback?.impactOccurred(style)
}

/** Authorization header for the API. Outside Telegram it's a dev user (the backend accepts it only with DEV_AUTH=1). */
export function authHeader(): string {
  if (tg) return `tma ${tg.initData}`
  const id = new URLSearchParams(location.search).get('dev') ?? '1'
  return `tma dev:${id}`
}
