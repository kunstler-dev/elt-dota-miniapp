import type { Arsenal } from './api'

/** Hero look for 3D: full paths to the body, items and permanent parts (SF wings, etc.). */
export type Look = { hero: string; body: string; gear: string[]; extras: string[] }

const ARCANA_BODY = '/models/pudge/pudge_arcana.glb'
const ARCANA_BACK = '/models/pudge/items/pudge_arcana_back.glb'

/** Special looks: a persona is a separate model with its own items (the hero's regular items don't fit it),
 *  an arcana has its own versions of some items (refit) and its own parts instead of permanent ones (Demon Eater wings). */
type Special = {
  gear?: string[]
  swap?: Record<string, string>
  /** replacement of the item in a slot for the look's skeleton (the weapon is held differently) */
  slot?: Record<string, (model: string | undefined) => string | undefined>
  extras?: string[]
}

const DROW_ITEMS = '/models/heroes/drow/items/'

const SPECIAL: Record<string, Special> = {
  '/models/heroes/antimage/body_persona.glb': {
    gear: ['persona_weapon', 'persona_offhand', 'persona_armor', 'persona_hair'].map((n) => `/models/heroes/antimage/items/${n}.glb`),
    extras: [],
  },
  // Arcana parts (Dread Retribution, Demon Eater) are regular slot items and combine with anything
  '/models/heroes/shadow_fiend/body_arcana.glb': { extras: [] },
  // Dread Retribution holds the weapon like a crossbow: the arcana bow becomes her crossbow, any other weapon becomes
  // the arcana's default crossbow (same as in Dota: regular bows aren't used with this look)
  '/models/heroes/drow/body_arcana.glb': {
    slot: {
      weapon: (m) => (m === DROW_ITEMS + 'drow_arcana_bow.glb' ? DROW_ITEMS + 'drow_arcana_weapon.glb' : DROW_ITEMS + 'drow_crossbow.glb'),
    },
  },
}

/** Look from the hero's Arsenal, with one "try-on" item swapped in. */
export function lookOf(a: Arsenal, tryOn?: string | null): Look {
  const byId = new Map(a.items.map((i) => [i.id, i]))
  const eq = { ...a.equipped }
  const t = tryOn ? byId.get(tryOn) : undefined
  if (t) eq[t.slot] = t.id
  const model = (slot: string) => {
    const id = eq[slot]
    return id ? byId.get(id)?.model : undefined
  }
  const body = model('body') ?? a.model.dir + a.model.body
  const gear = a.slots
    .filter((s) => s.id !== 'body')
    // Pudge's arcana has its own back piece, part of the Feast of Abscession look
    .map((s) => {
      if (s.id === 'back' && body === ARCANA_BODY) return ARCANA_BACK
      const fix = SPECIAL[body]?.slot?.[s.id]
      return fix ? fix(model(s.id)) : model(s.id)
    })
    .filter((m): m is string => !!m)
  const sp = SPECIAL[body]
  if (!sp) return { hero: a.hero, body, gear, extras: a.model.extras }
  return {
    hero: a.hero,
    body,
    gear: sp.gear ?? gear.map((m) => sp.swap?.[m] ?? m),
    extras: sp.extras ?? a.model.extras,
  }
}

/** Rarity color by set level, like Dota 2 item rarities. */
export function rarity(tier: number): { name: string; color: string } {
  if (tier === 0) return { name: 'Обычный', color: '#B0C3D9' }
  if (tier <= 2) return { name: 'Редкий', color: '#4B69FF' }
  if (tier <= 4) return { name: 'Мифический', color: '#8847FF' }
  if (tier <= 6) return { name: 'Легендарный', color: '#D32CE6' }
  if (tier <= 10) return { name: 'Бессмертный', color: '#E4AE39' }
  return { name: 'Аркана', color: '#ADE55C' }
}
