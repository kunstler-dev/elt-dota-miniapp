import { authHeader } from './telegram'

export type League = {
  index: number
  name: string
  next: string | null
  next_at: number | null
  progress: number
  rating?: number
}

export type GameState = {
  coins: number
  earned_total: number
  souls: number
  energy: number
  max_energy: number
  energy_regen: number
  tap_power: number
  active_hero: string
  profit_per_hour: number
  league: League
  server_ms: number
}

export type Steam = {
  steam_id: string
  persona: string | null
  avatar: string | null
  verified: boolean
  reasons: string[]
}

export type Me = {
  user: { id: number; first_name: string; username: string | null; is_premium: boolean; photo_url: string | null; is_admin?: boolean }
  steam: Steam | null
  subscription: { channel: string; url: string; ok: boolean }
  state: GameState
  invite_link: string | null
}

export type Daily = { day: number; claimable: boolean; rewards: number[] }
export type TaskItem = { id: string; kind: 'subscribe' | 'boost'; title: string; badge: string; url: string; souls: number; done: boolean }

export type GuessView = 'front' | 'back' | 'high' | 'close' | 'odd'
export type GuessQuestion = {
  round: number
  streak: number
  seconds: number
  spin: number
  view: GuessView
  choices: number
  reward: number
  options: { id: string; name: string }[]
  model: { body: string; items: string[] }
}

export type LookData = { hero: string; body: string; gear: string[]; extras: string[] }
export type Profile = {
  id: number
  name: string
  photo_url: string | null
  is_premium: boolean
  since_ms: number
  league: League
  earned_total: number
  tap_power: number
  profit_per_hour: number
  hero: { id: string; name: string }
  look: LookData
  heroes: { id: string; name: string; owned: boolean; tap_power: number }[]
  items_owned: number
  friends: number
  games: { hook: number; guess: number }
  week: { rank: number | null; points: number; league: number | null }
  month: { rank: number | null; points: number }
  steam: { persona: string | null; verified: boolean }
  coins?: number
  souls?: number
}
export type Leaderboard = {
  period: string
  ends_ms: number
  league: { index: number; name: string } | null
  prizes: { place: number; souls?: number; item?: string }[]
  top: { rank: number; id: number; name: string; photo_url: string | null; points: number; me: boolean }[]
  me: { rank: number | null; points: number }
}

export type FriendStatus = 'confirmed' | 'no_steam' | 'not_verified'
export type Friends = {
  invite_link: string | null
  rules: { bonus: number; bonus_premium: number; welcome: number; share_l1: number; share_l2: number; arcana_souls: number | null }
  confirmed: number
  invited: number
  souls_earned: number
  friends: { name: string; photo_url: string | null; is_premium: boolean; status: FriendStatus; souls: number }[]
}
export type TopRow = { rank: number; id: number; name: string; photo_url: string | null; value: number; me: boolean }

export type ArsenalItem = {
  id: string
  set: string
  slot: string
  model: string
  power: number
  price: number
  owned: boolean
  equipped: boolean
}
export type HeroInfo = {
  id: string
  name: string
  price: number
  power: number
  income: number
  owned: boolean
  active: boolean
  tap_power: number
}
export type Arsenal = {
  heroes: HeroInfo[]
  hero: string
  model: { dir: string; body: string; extras: string[] }
  slots: { id: string; name: string }[]
  sets: { id: string; name: string; tier: number; bonus: number }[]
  items: ArsenalItem[]
  equipped: Record<string, string | null>
  full_set: string | null
  tap_power: number
}

export type AnalysisPay = {
  mode: 'beta' | 'sub' | 'free' | 'locked'
  beta: boolean
  price: number
  free_left: number
  free_per_week: number
  next_free_ms: number | null
  subscription: { active: boolean; expires_ms: number; recurring: boolean; cancelled: boolean } | null
}
type HeroRef = { hero_id: number; name: string; img: string | null }
export type AnalysisReport = {
  profile: { name: string | null; avatar: string | null; rank_tier: number | null; bracket: number; bracket_name: string }
  last: {
    match_id: number
    hero: string
    hero_img: string | null
    win: boolean
    duration: string
    start_time: number
    kills: number
    deaths: number
    assists: number
    kda: number
    pos: number
    pos_name: string
    lane_name: string
    stats: { gpm: number; xpm: number; last_hits: number; denies: number; lh10: number | null; kp: number; obs: number | null }
    benchmarks: { label: string; value: number; median: number | null; pct: number | null }[]
    items: { key: string; name: string; t: string }[]
    lane: { known: boolean; result?: string; text: string }
    parsed: boolean
  } | null
  mistakes: { severity: 'high' | 'mid' | 'low'; title: string; tip: string }[]
  trends: {
    games: number
    wins: number
    winrate: number
    avg: { kda: number; gpm: number; xpm: number; deaths: number }
    delta: { gpm: number; deaths: number; winrate: number }
    streak: { win: boolean; n: number }
    series: { win: boolean; gpm: number; kda: number }[]
    heroes: (HeroRef & { games: number; winrate: number })[]
  }
  position: { best: number; name: string; explanation: string; rows: { pos: number; name: string; games: number; winrate: number | null; kda: number }[] }
  heroes: { top: (HeroRef & { reason: string })[]; drop: (HeroRef & { reason: string })[] }
  meta: { bracket_name: string; best: (HeroRef & { winrate: number })[]; worst: (HeroRef & { winrate: number })[] }
  tips: { title: string; text: string }[]
}
export type AnalysisPreview = {
  match_id: number
  hero: string
  hero_img: string | null
  win: boolean
  kills: number
  deaths: number
  assists: number
  duration: string
  gpm: number
  xpm: number
}
export type Analysis =
  | { status: 'ok'; report: AnalysisReport; parsed: boolean; parse_requested: boolean; pay: AnalysisPay }
  | { status: 'locked'; preview: AnalysisPreview | null; pay: AnalysisPay }
  | { status: 'private'; message: string; pay: AnalysisPay }

export type GuildShort = {
  id: number
  name: string
  emblem: string
  emblem_url: string | null
  about: string
  members: number
  max_members: number
  points: number
  rank: number | null
}
export type GuildQuest = {
  id: string
  title: string
  progress: number
  tiers: { tier: number; goal: number; souls: number; done: boolean; claimed: boolean; can_claim: boolean }[]
}
export type GuildDetail = GuildShort & {
  owner_id: number
  members_list: { id: number; name: string; photo_url: string | null; role: 'owner' | 'member'; points: number; me: boolean }[]
  my_role: 'owner' | 'member' | null
  my_points: number
  quests: GuildQuest[]
  ends_ms: number
}
export type GuildHome = {
  guild: GuildDetail | null
  top: GuildShort[]
  rules: { create_cost: number; max_members: number; min_contrib: number; emblems: string[]; war_prizes: number[] }
  rejoin_in_ms: number
}

export type AdminStats = {
  server_ms: number
  users: {
    total: number
    online: number
    today: number
    week: number
    new_today: number
    new_week: number
    subscribed: number
    steam_linked: number
    steam_verified: number
    referred: number
  }
  daily_claims_today: number
  tasks: { id: string; title: string; souls: number; done: number; today: number }[]
  games: Record<'hook' | 'guess', { players_today: number; plays_today: number }>
  economy: { coins: number; earned_total: number; souls: number }
  guilds: number
  analysis: { active_subs: number; stars_total: number }
}
export type AdminPrize = {
  id: number
  period: string
  place: number
  prize: string
  status: 'pending' | 'sent'
  user_id: number
  name: string
  steam_id: string | null
  persona: string | null
}
export type AdminAnalysis = {
  settings: { beta_free: boolean; price: number; free_per_week: number }
  subscribers: { user_id: number; name: string; expires_ms: number; active: boolean; paid: number; charge_id: string }[]
  payments: { charge_id: string; user_id: number; amount: number; created_ms: number; refunded_ms: number | null }[]
}

export type ContestEntry = {
  id: number
  platform: 'youtube' | 'tiktok'
  url: string
  title: string | null
  author: string | null
  views: number
  views_ms: number
  status: 'pending' | 'approved' | 'rejected'
  note: string | null
  published_ms: number | null
  created_ms: number
}
export type Contest = {
  id: string
  phase: 'soon' | 'active' | 'finished'
  start_ms: number | null
  end_ms: number | null
  prizes: number[]
  max_entries: number
  hashtag: string
  top: { rank: number; id: number; name: string; photo_url: string | null; views: number; videos: number; prize_rub: number; me: boolean }[]
  me: { views: number; rank: number | null; entries: ContestEntry[] }
}
export type AdminContest = {
  phase: Contest['phase']
  start_ms: number | null
  end_ms: number | null
  entries: (ContestEntry & { user_id: number; user: string; manual: boolean; fetch_error: string | null })[]
}

export type ShopKind = 'arcana' | 'immortal' | 'crimson' | 'golden' | 'other'
export type ShopItem = {
  id: string
  title: string
  kind: ShopKind
  about: string
  price: number
  stock: number | null
  need_note: boolean
  image: string | null
  active: boolean
  sort: number
  usd_cents: number | null
  listings: number | null
  usd_ms: number
}
export type ShopOrder = {
  id: number
  item_id: string
  title: string
  price: number
  note: string
  status: 'pending' | 'sent' | 'cancelled'
  admin_note: string | null
  created_ms: number
  updated_ms: number
}
export type AdminShop = {
  souls_per_usd: number
  refreshing: boolean
  items: ShopItem[]
  orders: (ShopOrder & { user_id: number; user: string; steam_id: string | null; persona: string | null })[]
}

export type DraftHero = { id: number; name: string; roles: string[]; attack: string; attr: string; winrate: number; img: string }
export type DraftLobby = {
  ready: boolean
  rating: { elo: number; games: number; wins: number }
  queue: { since_ms: number; wait_ms: number } | null
  active: string | null
  bot_rewards_left: number
  bot_coins: { win: number; loss: number }
  month: { period: string; ends_ms: number; points: number; games: number; min_games: number; prizes: number[] }
  ladder: { rank: number; id: number; name: string; photo_url: string | null; points: number; games: number; wins: number; me: boolean }[]
}
export type DraftPart = { key: string; title: string; points: number; reasons: string[] }
export type DraftMatchState = {
  id: string
  status: 'draft' | 'place' | 'done'
  me: 'A' | 'B'
  ranked: boolean
  deadline_ms: number
  turn: { kind: 'ban' | 'pick'; side: 'A' | 'B'; step: number } | null
  sequence: { kind: 'ban' | 'pick'; side: 'A' | 'B' }[]
  actions: { kind: 'ban' | 'pick'; side: 'A' | 'B'; hero: number; auto: boolean }[]
  players: Record<'A' | 'B', { id: number | null; name: string }>
  orders: Record<'A' | 'B', number[] | null>
  result?: {
    A: { score: number; parts: DraftPart[] }
    B: { score: number; parts: DraftPart[] }
    winner: 'A' | 'B'
    coin: boolean
    diff: number
    decisive: [string, number][]
  }
  winner?: 'A' | 'B'
  delta?: Record<'A' | 'B', number>
  reward?: number
}

export type ChatMsg = {
  id: number
  user_id: number
  name: string
  photo_url: string | null
  league: string | null
  guild: string | null
  text: string
  created_ms: number
  me: boolean
}

export type ChatAdmin = {
  bans: { user_id: number; name: string; until_ms: number; permanent: boolean; reason: string }[]
  reports: { id: number; channel: string; text: string; user_id: number; name: string; reports: number; hidden: boolean; created_ms: number }[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', Authorization: authHeader(), ...init?.headers },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, body.detail ?? res.statusText)
  return body as T
}

export const api = {
  me: () => request<Me>('/me'),
  tap: (taps: number) => request<{ accepted: number; state: GameState }>('/tap', { method: 'POST', body: JSON.stringify({ taps }) }),
  tasks: () => request<{ daily: Daily; tasks: TaskItem[] }>('/tasks'),
  claimDaily: () => request<{ reward: number; daily: Daily; state: GameState }>('/daily/claim', { method: 'POST' }),
  checkTask: (id: string) => request<{ souls: number; state: GameState }>(`/tasks/${id}/check`, { method: 'POST' }),
  steamLink: () => request<{ url: string }>('/steam/link', { method: 'POST' }),
  steamDevLink: (steam_id: string) =>
    request<{ steam: Steam }>('/steam/dev-link', { method: 'POST', body: JSON.stringify({ steam_id }) }),
  subscriptionCheck: () => request<{ ok: boolean }>('/subscription/check', { method: 'POST' }),
  profile: (id?: number) => request<Profile>(id ? `/profile/${id}` : '/profile'),
  top: (kind: 'week' | 'month') => request<Leaderboard>(`/top/${kind}`),
  friends: () => request<Friends>('/friends'),
  arsenal: (hero?: string) => request<Arsenal>(hero ? `/arsenal?hero=${hero}` : '/arsenal'),
  buyItem: (id: string) => request<ArsenalChange>(`/arsenal/${encodeURIComponent(id)}/buy`, { method: 'POST' }),
  equipItem: (id: string) => request<ArsenalChange>(`/arsenal/${encodeURIComponent(id)}/equip`, { method: 'POST' }),
  buyHero: (id: string) => request<{ arsenal: Arsenal; state: GameState }>(`/heroes/${id}/buy`, { method: 'POST' }),
  selectHero: (id: string) => request<{ arsenal: Arsenal; state: GameState }>(`/heroes/${id}/select`, { method: 'POST' }),
  topReferrals: () => request<{ top: TopRow[]; me: { rank: number | null; value: number } }>('/top/referrals'),
  games: () => request<Record<'hook' | 'guess', { plays_left: number; plays_per_day: number; best: number }>>('/games'),
  hookStart: () =>
    request<{ session: string; seed: number; duration: number; cooldown_ms: number; coin_per_hit: number; plays_left: number }>(
      '/games/hook/start',
      { method: 'POST' },
    ),
  hookFinish: (session: string, hits: number, score: number) =>
    request<{ reward: number; best: number; state: GameState }>('/games/hook/finish', {
      method: 'POST',
      body: JSON.stringify({ session, hits, score }),
    }),
  chat: (channel: string, after = 0) =>
    request<{ messages: ChatMsg[]; cooldown_ms: number; muted_until: number | null; muted_reason: string | null }>(
      `/chat/${channel}${after ? `?after=${after}` : ''}`,
    ),
  chatReport: (id: number) => request<{ ok: boolean; hidden: boolean }>(`/chat/msg/${id}/report`, { method: 'POST' }),
  chatAdmin: () => request<ChatAdmin>('/chat/admin/state'),
  chatBan: (user_id: number, minutes: number, reason = '', purge = false) =>
    request<{ ok: boolean }>('/chat/admin/ban', { method: 'POST', body: JSON.stringify({ user_id, minutes, reason, purge }) }),
  chatUnban: (user_id: number) => request<{ ok: boolean }>(`/chat/admin/ban/${user_id}`, { method: 'DELETE' }),
  chatRestore: (id: number) => request<{ ok: boolean }>(`/chat/admin/msg/${id}/restore`, { method: 'POST' }),
  chatSend: (channel: string, text: string) =>
    request<{ message: ChatMsg }>(`/chat/${channel}`, { method: 'POST', body: JSON.stringify({ text }) }),
  chatDelete: (id: number) => request<{ ok: boolean }>(`/chat/msg/${id}`, { method: 'DELETE' }),
  draftLobby: () => request<DraftLobby>('/draft'),
  draftHeroes: () => request<{ heroes: DraftHero[]; positions: Record<string, string> }>('/draft/heroes'),
  draftQueue: () => request<{ match_id: string | null; since_ms?: number; wait_ms?: number }>('/draft/queue', { method: 'POST' }),
  draftPoll: () => request<{ match_id: string | null; searching?: boolean; left_ms?: number; bot?: boolean }>('/draft/queue'),
  draftLeave: () => request<{ ok: boolean }>('/draft/queue', { method: 'DELETE' }),
  draftMatch: (id: string) => request<DraftMatchState>(`/draft/match/${id}`),
  draftAct: (id: string, hero: number) =>
    request<DraftMatchState>(`/draft/match/${id}/act`, { method: 'POST', body: JSON.stringify({ hero }) }),
  draftPlace: (id: string, order: number[]) =>
    request<DraftMatchState>(`/draft/match/${id}/place`, { method: 'POST', body: JSON.stringify({ order }) }),
  shop: () => request<{ items: ShopItem[]; orders: ShopOrder[]; max_pending: number; souls_per_usd: number }>('/shop'),
  shopBuy: (id: string, note: string) =>
    request<{ order: ShopOrder; state: GameState }>(`/shop/${id}/buy`, { method: 'POST', body: JSON.stringify({ note }) }),
  adminShop: () => request<AdminShop>('/admin/shop'),
  adminShopItem: (id: string, patch: { stock?: number; unlimited?: boolean; active?: boolean }) =>
    request<{ item: ShopItem }>(`/admin/shop/items/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  adminShopRate: (souls_per_usd: number) =>
    request<{ souls_per_usd: number }>('/admin/shop/rate', { method: 'POST', body: JSON.stringify({ souls_per_usd }) }),
  adminShopRefresh: () => request<{ started: boolean }>('/admin/shop/refresh', { method: 'POST' }),
  adminShopOrder: (id: number, status: 'sent' | 'cancelled', admin_note?: string) =>
    request<{ order: ShopOrder }>(`/admin/shop/orders/${id}`, { method: 'POST', body: JSON.stringify({ status, admin_note }) }),
  contest: () => request<Contest>('/contest'),
  contestSubmit: (url: string) => request<{ entry: ContestEntry }>('/contest/entries', { method: 'POST', body: JSON.stringify({ url }) }),
  contestRemove: (id: number) => request<{ ok: boolean }>(`/contest/entries/${id}`, { method: 'DELETE' }),
  adminContest: () => request<AdminContest>('/admin/contest'),
  adminContestStart: () => request<{ start_ms: number; end_ms: number }>('/admin/contest/start', { method: 'POST' }),
  adminContestReview: (id: number, body: { status?: string; views?: number; note?: string }) =>
    request<{ entry: ContestEntry }>(`/admin/contest/entries/${id}`, { method: 'POST', body: JSON.stringify(body) }),
  adminContestRefresh: () => request<{ updated: number; failed: number }>('/admin/contest/refresh', { method: 'POST' }),
  adminStats: () => request<AdminStats>('/admin/stats'),
  adminPrizes: () => request<{ prizes: AdminPrize[] }>('/admin/prizes'),
  adminPrizeSent: (id: number) => request<{ ok: boolean }>(`/admin/prizes/${id}/sent`, { method: 'POST' }),
  adminAnalysis: () => request<AdminAnalysis>('/admin/analysis'),
  adminAnalysisSettings: (body: { beta_free?: boolean; price?: number }) =>
    request<{ settings: AdminAnalysis['settings'] }>('/admin/analysis/settings', { method: 'POST', body: JSON.stringify(body) }),
  adminRefund: (charge_id: string) =>
    request<{ ok: boolean }>('/admin/analysis/refund', { method: 'POST', body: JSON.stringify({ charge_id }) }),
  guild: () => request<GuildHome>('/guild'),
  guildInfo: (id: number) => request<GuildDetail>(`/guilds/${id}`),
  guildCreate: (name: string, image: string, about: string) =>
    request<{ guild: GuildDetail; state: GameState }>('/guilds', { method: 'POST', body: JSON.stringify({ name, image, about }) }),
  guildEmblem: (image: string) => request<{ guild: GuildDetail }>('/guild/emblem', { method: 'POST', body: JSON.stringify({ image }) }),
  guildJoin: (id: number) => request<{ guild: GuildDetail }>(`/guilds/${id}/join`, { method: 'POST' }),
  guildLeave: () => request<{ ok: boolean }>('/guild/leave', { method: 'POST' }),
  guildKick: (uid: number) => request<{ guild: GuildDetail }>(`/guild/kick/${uid}`, { method: 'POST' }),
  guildClaim: (quest: string, tier: number) =>
    request<{ souls: number; guild: GuildDetail; state: GameState }>(`/guild/quests/${quest}/${tier}/claim`, { method: 'POST' }),
  analysis: (refresh = false) => request<Analysis>(refresh ? '/analysis?refresh=1' : '/analysis'),
  analysisParse: () => request<{ requested: boolean; match_id: number }>('/analysis/parse', { method: 'POST' }),
  analysisInvoice: () => request<{ url: string; price: number }>('/analysis/invoice', { method: 'POST' }),
  guessStart: () => request<{ session: string; plays_left: number; question: GuessQuestion }>('/games/guess/start', { method: 'POST' }),
  guessAnswer: (session: string, hero: string) =>
    request<{
      correct: boolean
      timeout: boolean
      answer: { id: string; name: string }
      reward: number
      streak: number
      next: GuessQuestion | null
      state: GameState
    }>('/games/guess/answer', { method: 'POST', body: JSON.stringify({ session, hero }) }),
}

export type ArsenalChange = { arsenal: Arsenal; state: GameState }
