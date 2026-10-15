import { useGLTF } from '@react-three/drei'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { Suspense, useEffect, useMemo, useRef } from 'react'
import {
  AdditiveBlending,
  AnimationMixer,
  Box3,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  InstancedMesh,
  LoopOnce,
  Matrix4,
  MeshStandardMaterial,
  Object3D,
  Quaternion,
  RepeatWrapping,
  SRGBColorSpace,
  Vector3,
  type AnimationAction,
  type Group,
  type Mesh,
  type Points,
  type SkinnedMesh,
} from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'

import { bonesOf, cleanMaterials, Gear } from '../components/Rig'

// "Pudge Hook" mini-game. Creeps run across the river; tapping the ground throws the hook at that point.
// Enemies (Dire) score points, the golden mega creep is x3, own creeps (Radiant) are a penalty and reset the combo.
// Waves speed up toward the end of the round, creeps sometimes turn around. Simulation runs in useFrame on refs.

const DIRE = ['/models/creeps/creep_2021_dire_melee.glb', '/models/creeps/creep_2021_dire_ranged.glb']
const RADIANT = ['/models/creeps/creep_2021_radiant_melee.glb', '/models/creeps/creep_2021_radiant_ranged.glb']
const MEGA = '/models/creeps/creep_2021_dire_melee_mega.glb'
const PUDGE = '/models/pudge/pudge.glb'
const HOOK_SPEED = 19
const HOOK_RANGE = 12
const GRAB_RADIUS = 0.6
const HAND = new Vector3(0.35, 1.0, -0.2)
const LINKS = 46
const SPARKS = 90

export type HitKind = 'enemy' | 'mega' | 'ally'
export type HookEvents = { onThrow: () => boolean; onHit: (kind: HitKind) => void; onMiss: () => void }

/** Deterministic generator: the round is the same for the same seed */
export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

type Creep = {
  kind: HitKind
  obj: Object3D
  mixer: AnimationMixer
  run: AnimationAction | null
  flail: AnimationAction | null
  alive: boolean
  hooked: boolean
  dir: number
  speed: number
  juke: number // seconds until turning around (if > 0)
  shadow: Mesh | null
}

function normalize(o: Object3D, height: number) {
  const box = new Box3().setFromObject(o)
  o.scale.setScalar(height / box.getSize(new Vector3()).y)
  return o
}

/** Procedural grass/dirt texture: blotchy noise, no external files */
function grassTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 256
  const g = c.getContext('2d')!
  // lush grass of the Dota mid lane: yellow-green tone, light and dark patches, rare bare dirt spots
  g.fillStyle = '#5f8f2b'
  g.fillRect(0, 0, 256, 256)
  const r = mulberry32(7)
  for (let i = 0; i < 3200; i++) {
    const v = r()
    g.fillStyle =
      v < 0.45 ? `rgba(132,176,58,${0.35 + r() * 0.3})`
        : v < 0.85 ? `rgba(62,104,30,${0.35 + r() * 0.25})`
          : v < 0.97 ? `rgba(170,196,80,${0.3})` : `rgba(128,104,62,${0.5})`
    g.fillRect(r() * 256, r() * 256, 1 + r() * 5, 1 + r() * 5)
  }
  const t = new CanvasTexture(c)
  t.wrapS = t.wrapT = RepeatWrapping
  t.repeat.set(6, 6)
  t.colorSpace = SRGBColorSpace
  return t
}

function waterTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 256
  const g = c.getContext('2d')!
  const grad = g.createLinearGradient(0, 0, 0, 256)
  grad.addColorStop(0, '#1a5f6c')
  grad.addColorStop(0.5, '#288e9c')
  grad.addColorStop(1, '#1a5f6c')
  g.fillStyle = grad
  g.fillRect(0, 0, 256, 256)
  const r = mulberry32(11)
  for (let i = 0; i < 160; i++) {
    g.strokeStyle = `rgba(220,255,250,${0.15 + r() * 0.3})`
    g.lineWidth = 1 + r() * 2
    const x = r() * 256
    const y = r() * 256
    g.beginPath()
    g.moveTo(x, y)
    g.quadraticCurveTo(x + 12, y - 4, x + 24 + r() * 20, y)
    g.stroke()
  }
  const t = new CanvasTexture(c)
  t.wrapS = t.wrapT = RepeatWrapping
  t.repeat.set(3, 1)
  t.colorSpace = SRGBColorSpace
  return t
}

const PROPS = '/models/props/'
type PropName = 'oak1' | 'oak2' | 'pine' | 'bush' | 'fern' | 'rock1' | 'rock2'
/** Prop height on the scene (map models are in Dota units, normalized by height) */
const PROP_H: Record<PropName, number> = { oak1: 4.6, oak2: 4.2, pine: 6.2, bush: 0.9, fern: 0.55, rock1: 0.45, rock2: 0.4 }

/** Foliage and grass in Dota are tinted by the engine (textures are grey), so we tint them to mid-lane green ourselves */
const LEAF = new Color('#8fc24a')
const GRASS = new Color('#7fb83e')
const tinted = new Map<string, MeshStandardMaterial>()
function tint(o: Object3D, n: PropName) {
  if (n === 'rock1' || n === 'rock2') return
  o.traverse((x) => {
    const m = x as Mesh
    if (!m.isMesh) return
    const base = m.material as MeshStandardMaterial
    if (!/leaves|bush|grass|fern|pine/i.test(base.name) && n !== 'fern') return
    const key = base.uuid
    if (!tinted.has(key)) {
      const t = base.clone()
      t.color = (n === 'fern' ? GRASS : LEAF).clone()
      tinted.set(key, t)
    }
    m.material = tinted.get(key)!
  })
}

/** Trees, bushes, grass and rocks from the Dota map: forest on the far bank, rocks by the river, bushes at the edges */
function Scenery() {
  const names = Object.keys(PROP_H) as PropName[]
  const gltfs = names.map((n) => useGLTF(PROPS + n + '.glb', false, true)) // eslint-disable-line react-hooks/rules-of-hooks
  const objects = useMemo(() => {
    const src = Object.fromEntries(names.map((n, i) => [n, gltfs[i].scene as Object3D])) as unknown as Record<PropName, Object3D>
    const r = mulberry32(5)
    const out: Object3D[] = []
    const put = (n: PropName, x: number, z: number, s = 1) => {
      const o = normalize(clone(src[n]), PROP_H[n] * s)
      cleanMaterials(o)
      tint(o, n)
      o.position.set(x, 0, z)
      o.rotation.y = r() * Math.PI * 2
      out.push(o)
    }
    // far bank: dense forest of oaks and pines in two rows
    // far bank: forest only at the sides, an open space in the middle where the opponent stands (like mid)
    for (const side of [-1, 1]) {
      for (let i = 0; i < 4; i++) put(i % 3 === 2 ? 'pine' : i % 2 ? 'oak2' : 'oak1', side * (2.6 + i * 1.3 + r() * 0.4), -13.2 - r() * 1.4, 0.85 + r() * 0.35)
      for (let i = 0; i < 3; i++) put(i % 2 ? 'pine' : 'oak1', side * (3.4 + i * 1.6 + r() * 0.5), -16 - r() * 1.2, 1 + r() * 0.3)
    }
    // rocks on both banks
    for (let i = 0; i < 6; i++) put(i % 2 ? 'rock1' : 'rock2', -5 + i * 2 + (r() - 0.5), -3.15 - r() * 0.3, 0.7 + r() * 0.6)
    for (let i = 0; i < 6; i++) put(i % 2 ? 'rock2' : 'rock1', -5.5 + i * 2.1 + (r() - 0.5), -12 + r() * 0.3, 0.8 + r() * 0.6)
    // near bank: bushes and ferns at the edges, scattered grass
    for (const side of [-1, 1]) {
      put('bush', side * (2.6 + r()), -1.2 - r(), 1.1)
      put('fern', side * (2.0 + r() * 0.6), -2.3 - r() * 0.5, 1.2)
      put('bush', side * (3.2 + r()), 0.6, 1.2)
    }
    return out
  }, gltfs) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      {objects.map((o, i) => (
        <primitive key={i} object={o} />
      ))}
    </>
  )
}

// The river sits below the banks: creeps run through the water, steps lead down from both banks (like mid in Dota)
const RIVER_Y = -0.45
const BANK_NEAR = -3.3
const BANK_FAR = -11.9
const STAIR_W = 2.2
const STEPS = 4

const PUDGE_GEAR = ['weapon', 'leftweapon', 'leftarm', 'back', 'belt', 'bracer', 'hair'].map((n) => `/models/pudge/${n}.glb`)
const SF = '/models/heroes/shadow_fiend/'
const SF_GEAR = ['items/shadow_fiend_head.glb', 'items/shadow_fiend_shoulders.glb', 'items/shadow_fiend_arms.glb'].map((n) => SF + n)
const SF_WINGS = { pattern: /Wing/, root: /Wing0_/, scale: 0.6 }

/** Mid-lane opponent: Shadow Fiend on the far bank, standing opposite Pudge and waiting */
function Rival() {
  const gltf = useGLTF(SF + 'body.glb', false, true)
  const { body, bones, mixer } = useMemo(() => {
    const body = normalize(clone(gltf.scene), 2.1)
    cleanMaterials(body)
    body.traverse((o) => {
      if ((o as SkinnedMesh).isSkinnedMesh) o.frustumCulled = false
    })
    body.position.set(0, 0, -13.4)
    const mixer = new AnimationMixer(body)
    const idle = gltf.animations.find((a) => a.name === 'idle_anim') ?? gltf.animations[0]
    if (idle) mixer.clipAction(idle).play()
    return { body, bones: bonesOf(body), mixer }
  }, [gltf])
  useFrame((_, dt) => mixer.update(Math.min(dt, 0.05)))
  return (
    <>
      <primitive object={body} />
      {SF_GEAR.map((u) => (
        <Suspense key={u} fallback={null}>
          <Gear url={u} body={body} bones={bones} />
        </Suspense>
      ))}
      <Suspense fallback={null}>
        <Gear url={SF + 'shadow_fiend_wings.glb'} body={body} bones={bones} boneScale={SF_WINGS} />
      </Suspense>
    </>
  )
}

const GOLD = new Color('#f5c542')

function tintGold(o: Object3D) {
  o.traverse((x) => {
    const m = x as Mesh
    if (!m.isMesh) return
    const gold = (mat: MeshStandardMaterial) => {
      const c = mat.clone()
      c.color?.lerp(GOLD, 0.35)
      c.emissive = GOLD.clone().multiplyScalar(0.12)
      c.metalness = 0.7
      c.roughness = 0.35
      return c
    }
    m.material = Array.isArray(m.material)
      ? m.material.map((x) => gold(x as MeshStandardMaterial))
      : gold(m.material as MeshStandardMaterial)
  })
}

function World({ seed, running, duration, events }: { seed: number; running: boolean; duration: number; events: HookEvents }) {
  const dire = [useGLTF(DIRE[0], false, true), useGLTF(DIRE[1], false, true)]
  const radiant = [useGLTF(RADIANT[0], false, true), useGLTF(RADIANT[1], false, true)]
  const mega = useGLTF(MEGA, false, true)
  const pudgeGltf = useGLTF(PUDGE, false, true)
  const rng = useMemo(() => mulberry32(seed), [seed])
  const { camera } = useThree()
  const grass = useMemo(grassTexture, [])
  const water = useMemo(waterTexture, [])

  const pudge = useMemo(() => {
    const p = normalize(clone(pudgeGltf.scene), 1.6)
    cleanMaterials(p)
    p.rotation.y = Math.PI
    return p
  }, [pudgeGltf])
  const pudgeBones = useMemo(() => bonesOf(pudge), [pudge])
  const pudgeMixer = useMemo(() => new AnimationMixer(pudge), [pudge])
  const pudgeActions = useMemo(() => {
    const find = (n: string) => pudgeGltf.animations.find((a) => a.name === n)
    const idle = find('pudge_idle_anim')
    const hook = find('pudge_meathook_start_anim')
    return { idle: idle && pudgeMixer.clipAction(idle), hook: hook && pudgeMixer.clipAction(hook) }
  }, [pudgeGltf, pudgeMixer])

  // creep pool: 5 enemies, 3 allies, 1 mega creep
  const creeps = useMemo<Creep[]>(() => {
    const make = (src: typeof mega, kind: HitKind, height: number): Creep => {
      const obj = normalize(clone(src.scene), height)
      cleanMaterials(obj)
      if (kind === 'mega') tintGold(obj)
      obj.traverse((o) => {
        if ((o as SkinnedMesh).isSkinnedMesh) o.frustumCulled = false
      })
      obj.visible = false
      const mixer = new AnimationMixer(obj)
      const clip = (n: string) => src.animations.find((a) => a.name === n)
      const run = clip('run')
      const flail = clip('flail')
      return {
        kind, obj, mixer, run: run ? mixer.clipAction(run) : null, flail: flail ? mixer.clipAction(flail) : null,
        alive: false, hooked: false, dir: 1, speed: 2, juke: 0, shadow: null,
      }
    }
    return [
      ...Array.from({ length: 5 }, (_, i) => make(dire[i % 2], 'enemy', 1.0)),
      ...Array.from({ length: 3 }, (_, i) => make(radiant[i % 2], 'ally', 1.0)),
      make(mega, 'mega', 1.25),
    ]
  }, [dire[0], dire[1], radiant[0], radiant[1], mega]) // eslint-disable-line react-hooks/exhaustive-deps

  const hook = useRef({ state: 'idle' as 'idle' | 'out' | 'back', pos: new Vector3(), dir: new Vector3(), dist: 0, grabbed: -1 })
  const head = useRef<Group>(null)
  const links = useRef<InstancedMesh>(null)
  const marker = useRef<Mesh>(null)
  const markerLife = useRef(0)
  const nextSpawn = useRef(0.3)
  const elapsed = useRef(0)
  const shake = useRef(0)
  const camBase = useMemo(() => camera.position.clone(), [camera])

  // hit sparks: points with velocities, fade in ~0.6 s
  const sparks = useMemo(() => {
    const geo = new BufferGeometry()
    geo.setAttribute('position', new BufferAttribute(new Float32Array(SPARKS * 3).fill(-50), 3))
    geo.setAttribute('color', new BufferAttribute(new Float32Array(SPARKS * 3), 3))
    return { geo, vel: new Float32Array(SPARKS * 3), life: new Float32Array(SPARKS), next: 0 }
  }, [])
  const sparksRef = useRef<Points>(null)

  function burst(at: Vector3, color: Color, n: number) {
    const pos = sparks.geo.attributes.position as BufferAttribute
    const col = sparks.geo.attributes.color as BufferAttribute
    for (let i = 0; i < n; i++) {
      const k = sparks.next
      sparks.next = (sparks.next + 1) % SPARKS
      pos.setXYZ(k, at.x, 0.7, at.z)
      col.setXYZ(k, color.r, color.g, color.b)
      const a = Math.random() * Math.PI * 2
      const sp = 1.5 + Math.random() * 3
      sparks.vel[k * 3] = Math.cos(a) * sp
      sparks.vel[k * 3 + 1] = 2 + Math.random() * 3
      sparks.vel[k * 3 + 2] = Math.sin(a) * sp
      sparks.life[k] = 0.5 + Math.random() * 0.3
    }
  }

  useEffect(() => {
    pudgeActions.idle?.play()
  }, [pudgeActions])
  useEffect(() => {
    elapsed.current = 0
  }, [seed])

  /** Difficulty grows toward the end of the round: 0 -> 1 */
  const heat = () => Math.min(1, elapsed.current / duration)

  function spawn() {
    const r = rng()
    // the share of allied creeps grows toward the end, so it's harder not to make a mistake
    const want: HitKind = r < 0.08 ? 'mega' : r < 0.3 + 0.12 * heat() ? 'ally' : 'enemy'
    const c = creeps.find((x) => !x.alive && x.kind === want) ?? creeps.find((x) => !x.alive && x.kind === 'enemy')
    if (!c) return
    c.dir = rng() < 0.5 ? 1 : -1
    const base = c.kind === 'mega' ? 3.6 : 1.7
    c.speed = (base + rng() * 2.0) * (1 + 0.8 * heat())
    c.juke = rng() < 0.18 + 0.2 * heat() ? 0.6 + rng() * 1.6 : 0
    // running lane: between the ends of the steps (steps go into the water STEPS x 0.32 from each bank)
    const laneNear = BANK_NEAR - STEPS * 0.32 - 0.3
    const laneFar = BANK_FAR + STEPS * 0.32 + 0.3
    c.obj.position.set(-c.dir * 5.2, RIVER_Y, laneNear - rng() * (laneNear - laneFar))
    c.obj.rotation.set(0, c.dir > 0 ? Math.PI / 2 : -Math.PI / 2, 0)
    c.obj.visible = true
    c.alive = true
    c.hooked = false
    c.flail?.stop()
    c.run?.reset().setEffectiveTimeScale(c.speed / 2.4).play()
  }

  const tmpObj = useMemo(() => new Object3D(), [])
  const tmpQ = useMemo(() => new Quaternion(), [])
  const spinQ = useMemo(() => new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), Math.PI / 2), [])
  const hiddenM = useMemo(() => new Matrix4().makeTranslation(0, -50, 0), [])

  useFrame((state, dtRaw) => {
    const dt = Math.min(dtRaw, 0.05)
    pudgeMixer.update(dt)
    for (const c of creeps) c.mixer.update(dt)
    water.offset.x += dt * 0.05
    water.offset.y = Math.sin(state.clock.elapsedTime * 0.6) * 0.03

    // camera shake after a hit
    if (shake.current > 0) {
      shake.current = Math.max(0, shake.current - dt)
      const k = shake.current * 0.25
      camera.position.set(camBase.x + (Math.random() - 0.5) * k, camBase.y + (Math.random() - 0.5) * k, camBase.z)
    } else camera.position.copy(camBase)

    // sparks
    const pos = sparks.geo.attributes.position as BufferAttribute
    for (let i = 0; i < SPARKS; i++) {
      if (sparks.life[i] <= 0) continue
      sparks.life[i] -= dt
      sparks.vel[i * 3 + 1] -= 9 * dt
      pos.setXYZ(i, pos.getX(i) + sparks.vel[i * 3] * dt, Math.max(0.02, pos.getY(i) + sparks.vel[i * 3 + 1] * dt), pos.getZ(i) + sparks.vel[i * 3 + 2] * dt)
      if (sparks.life[i] <= 0) pos.setXYZ(i, 0, -50, 0)
    }
    pos.needsUpdate = true

    if (marker.current) {
      markerLife.current = Math.max(0, markerLife.current - dt)
      marker.current.visible = markerLife.current > 0
      marker.current.scale.setScalar(1 + (0.5 - markerLife.current) * 1.4)
      ;(marker.current.material as MeshStandardMaterial).opacity = markerLife.current * 1.6
    }

    if (running) {
      elapsed.current += dt
      nextSpawn.current -= dt
      if (nextSpawn.current <= 0) {
        spawn()
        nextSpawn.current = (0.55 + rng() * 0.8) * (1 - 0.4 * heat())
      }
      for (const c of creeps) {
        if (!c.alive || c.hooked) continue
        if (c.juke > 0) {
          c.juke -= dt
          if (c.juke <= 0) {
            c.dir = -c.dir // turning around: you can't just shoot with a lead
            c.obj.rotation.y = c.dir > 0 ? Math.PI / 2 : -Math.PI / 2
          }
        }
        c.obj.position.x += c.dir * c.speed * dt
        if (Math.abs(c.obj.position.x) > 5.6) {
          c.alive = false
          c.obj.visible = false
        }
      }
    }

    const h = hook.current
    if (h.state === 'out') {
      h.pos.addScaledVector(h.dir, HOOK_SPEED * dt)
      h.dist += HOOK_SPEED * dt
      const hit = creeps.findIndex((c) => c.alive && !c.hooked &&
        Math.hypot(c.obj.position.x - h.pos.x, c.obj.position.z - h.pos.z) < GRAB_RADIUS * (c.kind === 'mega' ? 1.15 : 1))
      if (hit >= 0) {
        const c = creeps[hit]
        c.hooked = true
        c.run?.stop()
        c.flail?.reset().play()
        h.grabbed = hit
        h.state = 'back'
        burst(c.obj.position, c.kind === 'mega' ? GOLD : c.kind === 'ally' ? new Color('#6fd16f') : new Color('#c4161c'), c.kind === 'mega' ? 40 : 22)
        shake.current = c.kind === 'ally' ? 0.15 : 0.3
      } else if (h.dist >= HOOK_RANGE) {
        h.state = 'back'
      }
    } else if (h.state === 'back') {
      const to = new Vector3(HAND.x, 0, HAND.z).sub(new Vector3(h.pos.x, 0, h.pos.z))
      const step = HOOK_SPEED * 1.2 * dt
      if (to.length() <= step) {
        h.state = 'idle'
        if (h.grabbed >= 0) {
          const c = creeps[h.grabbed]
          c.alive = false
          c.obj.visible = false
          h.grabbed = -1
          events.onHit(c.kind)
        } else events.onMiss()
      } else {
        h.pos.addScaledVector(to.normalize(), step)
      }
      if (h.grabbed >= 0) {
        const inRiver = h.pos.z < BANK_NEAR && h.pos.z > BANK_FAR
        creeps[h.grabbed].obj.position.set(h.pos.x, inRiver ? RIVER_Y : 0, h.pos.z)
      }
    }

    if (head.current) {
      head.current.visible = h.state !== 'idle'
      head.current.position.set(h.pos.x, 0.6, h.pos.z)
      head.current.lookAt(HAND.x, 0.6, HAND.z)
    }
    // chain: links along the line from the hand to the hook, every other one rotated 90°
    const mesh = links.current
    if (mesh) {
      const from = new Vector3(HAND.x, HAND.y, HAND.z)
      const to = new Vector3(h.pos.x, 0.6, h.pos.z)
      const len = from.distanceTo(to)
      const n = h.state === 'idle' ? 0 : Math.min(LINKS, Math.max(2, Math.round(len / 0.26)))
      tmpQ.setFromUnitVectors(new Vector3(0, 0, 1), to.clone().sub(from).normalize())
      for (let i = 0; i < LINKS; i++) {
        if (i >= n) {
          mesh.setMatrixAt(i, hiddenM)
          continue
        }
        tmpObj.position.lerpVectors(from, to, (i + 0.5) / n)
        tmpObj.quaternion.copy(tmpQ)
        if (i % 2) tmpObj.quaternion.multiply(spinQ)
        tmpObj.updateMatrix()
        mesh.setMatrixAt(i, tmpObj.matrix)
      }
      mesh.instanceMatrix.needsUpdate = true
    }
  })

  function onGround(e: ThreeEvent<PointerEvent>) {
    e.stopPropagation()
    const h = hook.current
    if (!running || h.state !== 'idle' || !events.onThrow()) return
    const target = new Vector3(e.point.x, 0, e.point.z)
    if (marker.current) {
      marker.current.position.set(target.x, (target.z < BANK_NEAR && target.z > BANK_FAR ? RIVER_Y : 0) + 0.04, target.z)
      markerLife.current = 0.5
    }
    h.pos.set(HAND.x, 0, HAND.z)
    h.dir.copy(target.sub(h.pos).setY(0).normalize())
    h.dist = 0
    h.state = 'out'
    pudge.rotation.y = Math.atan2(h.dir.x, h.dir.z)
    const a = pudgeActions.hook
    if (a) {
      a.reset().setLoop(LoopOnce, 1).setEffectiveTimeScale(1.6).play()
      a.clampWhenFinished = false
    }
  }

  return (
    <>
      <fog attach="fog" args={['#a9bccb', 15, 34]} />
      {/* transparent plane for taps: the hook is thrown at a point at ground level */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, -5]} onPointerDown={onGround}>
        <planeGeometry args={[34, 34]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
      {/* banks above the river, like on mid */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, (BANK_NEAR + 12) / 2]}>
        <planeGeometry args={[34, 12 - BANK_NEAR]} />
        <meshStandardMaterial map={grass} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, (BANK_FAR - 30) / 2]}>
        <planeGeometry args={[34, BANK_FAR + 30]} />
        <meshStandardMaterial map={grass} />
      </mesh>
      {/* riverbed and water, where the creeps run */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, RIVER_Y - 0.05, (BANK_NEAR + BANK_FAR) / 2]}>
        <planeGeometry args={[34, BANK_NEAR - BANK_FAR]} />
        <meshStandardMaterial color="#6b6a52" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, RIVER_Y + 0.02, (BANK_NEAR + BANK_FAR) / 2]}>
        <planeGeometry args={[34, BANK_NEAR - BANK_FAR]} />
        <meshStandardMaterial map={water} transparent opacity={0.9} roughness={0.15} metalness={0.2} emissive="#0b3f48" emissiveIntensity={0.15} />
      </mesh>
      {/* stone bank walls and steps down to the water in the middle (both sides) */}
      {[BANK_NEAR, BANK_FAR].map((z, k) => (
        <group key={z}>
          {[-1, 1].map((side) => (
            <mesh key={side} position={[side * (STAIR_W / 2 + 8.5), RIVER_Y / 2, z + (k ? 0.12 : -0.12)]}>
              <boxGeometry args={[17, -RIVER_Y + 0.08, 0.3]} />
              <meshStandardMaterial color="#a39d82" roughness={0.95} />
            </mesh>
          ))}
          {Array.from({ length: STEPS }, (_, i) => {
            const h = (-RIVER_Y * (STEPS - i)) / STEPS // the top step is level with the bank
            const depth = 0.32
            const zz = k ? z + depth * (i + 0.5) : z - depth * (i + 0.5)
            return (
              <mesh key={i} position={[0, RIVER_Y + h / 2 - 0.02, zz]}>
                <boxGeometry args={[STAIR_W, h, depth]} />
                <meshStandardMaterial color={i % 2 ? '#bdb699' : '#ccc5a6'} roughness={0.9} />
              </mesh>
            )
          })}
          {[-1, 1].map((side) => (
            <mesh key={side} position={[side * (STAIR_W / 2 + 0.12), RIVER_Y / 2 + 0.08, z + (k ? 1 : -1) * STEPS * 0.16]}>
              <boxGeometry args={[0.24, -RIVER_Y + 0.25, STEPS * 0.32]} />
              <meshStandardMaterial color="#8f8970" roughness={0.95} />
            </mesh>
          ))}
        </group>
      ))}
      <Suspense fallback={null}>
        <Scenery />
      </Suspense>
      {/* Pudge's platform */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <circleGeometry args={[1.1, 32]} />
        <meshStandardMaterial color="#7b6a48" transparent opacity={0.9} roughness={1} />
      </mesh>
      <primitive object={pudge} />
      {/* Pudge's default look: hook, cleaver, arm, shoulder, belt, bracers, hair */}
      {PUDGE_GEAR.map((u) => (
        <Suspense key={u} fallback={null}>
          <Gear url={u} body={pudge} bones={pudgeBones} />
        </Suspense>
      ))}
      <Suspense fallback={null}>
        <Rival />
      </Suspense>
      {creeps.map((c, i) => (
        <primitive key={i} object={c.obj} />
      ))}
      <mesh ref={marker} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
        <ringGeometry args={[0.35, 0.45, 32]} />
        <meshStandardMaterial color="#ff4d55" emissive="#ff4d55" emissiveIntensity={1.5} transparent />
      </mesh>
      <group ref={head} visible={false}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.27, 0.07, 8, 18, Math.PI * 1.4]} />
          <meshStandardMaterial color="#b9c0c8" metalness={0.9} roughness={0.25} />
        </mesh>
        <mesh position={[0, 0, 0.27]} rotation={[Math.PI / 2, 0, 0]}>
          <coneGeometry args={[0.07, 0.22, 8]} />
          <meshStandardMaterial color="#d7dde3" metalness={0.9} roughness={0.2} />
        </mesh>
      </group>
      <instancedMesh ref={links} args={[undefined, undefined, LINKS]} frustumCulled={false}>
        <torusGeometry args={[0.085, 0.025, 6, 10]} />
        <meshStandardMaterial color="#8c949d" metalness={0.85} roughness={0.35} />
      </instancedMesh>
      <points ref={sparksRef} geometry={sparks.geo} frustumCulled={false}>
        <pointsMaterial size={0.14} vertexColors transparent blending={AdditiveBlending} depthWrite={false} />
      </points>
    </>
  )
}

export function HookScene({ seed, running, duration, events }: { seed: number; running: boolean; duration: number; events: HookEvents }) {
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 10.5, 5.3], fov: 50 }} onCreated={({ camera }) => camera.lookAt(0, 0, -6.2)}>
      <color attach="background" args={['#a9bccb']} />
      {/* mid-lane daylight: blue sky, warm sun from the side, green bounce light from the grass */}
      <hemisphereLight args={['#d6e8ff', '#5a7a2a', 1.5]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[-5, 9, 3]} intensity={3.4} color="#fff0cc" />
      <directionalLight position={[4, 3, -6]} intensity={0.8} color="#9fd0ff" />
      <World seed={seed} running={running} duration={duration} events={events} />
    </Canvas>
  )
}

useGLTF.preload(PUDGE, false, true)
;[...DIRE, ...RADIANT, MEGA].forEach((c) => useGLTF.preload(c, false, true))
