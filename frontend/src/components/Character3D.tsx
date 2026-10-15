import { OrbitControls, useAnimations, useGLTF } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Component, Suspense, useEffect, useImperativeHandle, useMemo, useRef, type ReactNode, type Ref } from 'react'
import { Box3, LoopOnce, LoopRepeat, Vector3, type AnimationAction, type Group, type SkinnedMesh } from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'

import type { Look } from '../lib/arsenal'
import { CAMERA_DIST } from './pudgeLayout'
import { bonesOf, type BoneScale, cleanMaterials, Gear, Perch, type PerchSpec } from './Rig'

// Hero models and animations come from Dota 2 files (Source 2 Viewer export + gltf-transform: meshopt, webp)

export type Mood = '' | 'dance' | 'clown' | 'scratch' | 'flex'
type Anims = {
  idle: string
  hits: string[]
  shows: [Mood, string][]
  bubbles: Partial<Record<Mood, string>>
  /** body height on stage; smaller than usual for heroes with wings/wide reach so they stay in frame */
  height?: number
}

/** Animations per body: tap plays attacks, idle (after a pause) cycles through taunts */
const ANIMS: Record<string, Anims> = {
  '/models/pudge/pudge.glb': {
    idle: 'pudge_idle_anim',
    hits: ['pudge_attack1_anim', 'pudge_attack2_anim'],
    shows: [['dance', 'pudge_taunt_money_maker_anim'], ['scratch', 'hh_idle_rare'], ['clown', 'pudge_clown_taunt'], ['flex', 'pudge_idle_alt_anim']],
    bubbles: { dance: 'Свежее мясо!', scratch: '*чешется*', clown: 'Хо-хо-хо!', flex: 'Ну, кто следующий?' },
  },
  '/models/pudge/pudge_arcana.glb': {
    idle: 'arc_mid_pudge_idle',
    hits: ['arc_mid_cleave_attack_01', 'arc_mid_attack02'],
    shows: [['dance', 'pudge_taunt_money_maker_anim'], ['scratch', 'arc_idle_rare_buttscratch'], ['clown', 'pudge_clown_taunt'], ['scratch', 'arc_idle_rare_groundscratch']],
    bubbles: { dance: 'Свежее мясо!', scratch: '*чешется*', clown: 'Хо-хо-хо!' },
  },
  '/models/heroes/axe/body.glb': {
    idle: 'idle',
    hits: ['attack_main_anim', 'attack_alt_anim'],
    shows: [['flex', 'loadout'], ['dance', 'axe_victory']],
    bubbles: { flex: 'Время рубить!', dance: 'Axe — непобедим!' },
  },
  '/models/heroes/drow/body.glb': {
    idle: 'idle_anim',
    hits: ['attack01_anim', 'attack_fast'],
    shows: [['flex', 'taunt_shoot'], ['dance', 'victory']],
    bubbles: { flex: 'В яблочко.', dance: 'Холодно?' },
  },
  '/models/heroes/antimage/body.glb': {
    idle: 'idle_anim',
    hits: ['attack1_anim', 'attack2_anim'],
    shows: [['flex', 'taunt_magic_ends_here_anim'], ['scratch', 'loadout'], ['dance', 'victory_versus']],
    bubbles: { flex: 'Магия кончается здесь!', dance: 'Ещё один маг повержен.' },
  },
  '/models/heroes/invoker/body.glb': {
    idle: 'idle_anim',
    hits: ['attack_anim', 'attack2_anim'],
    shows: [['clown', 'taunt_juggle'], ['flex', 'loadout'], ['dance', 'victory']],
    bubbles: { clown: 'Кваc, Векс, Экзорт…', flex: 'Узри мою мощь!' },
  },
  '/models/heroes/shadow_fiend/body.glb': {
    idle: 'idle_anim',
    hits: ['attack01_anim', 'attack02_anim'],
    shows: [['dance', 'taunt_fiendish_swag_anim'], ['scratch', 'idle_rare_anim'], ['flex', 'victory_anim']],
    bubbles: { dance: 'Твоя душа — моя.', flex: 'Ещё душ!' },
    height: 1.3,
  },
  '/models/heroes/shadow_fiend/body_arcana.glb': {
    idle: 'idle_anim',
    hits: ['attack01_anim', 'attack02_anim'],
    shows: [['dance', 'taunt_fiendish_swag_anim'], ['scratch', 'idle_rare_anim'], ['flex', 'victory_anim']],
    bubbles: { dance: 'Демон пирует.', flex: 'Ещё душ!' },
    height: 1.3,
  },
  '/models/heroes/drow/body_arcana.glb': {
    idle: 'drow_arc_idle',
    hits: ['drow_arc_attack', 'drow_arc_attack_fast'],
    shows: [['flex', 'drow_arc_taunt_whats_that'], ['scratch', 'drow_arc_idle_rare'], ['dance', 'drow_arc_victory']],
    bubbles: { flex: 'Что это там?', dance: 'Возмездие настигло.' },
  },
  '/models/heroes/antimage/body_persona.glb': {
    idle: 'idle',
    hits: ['attack', 'attack_alt1'],
    shows: [['flex', 'loadout'], ['scratch', 'idle_butterfly_rare'], ['dance', 'victory']],
    bubbles: { flex: 'Магия кончается здесь.', dance: 'Ещё одна победа.' },
  },
}
const FALLBACK = ANIMS['/models/pudge/pudge.glb']

const IDLE_DELAY_MS = 4000
const IDLE_GAP_MS = 7000
// body height in scene units (measured on the bare body: hats/weapons don't change the scale)
const HEIGHT = 1.55

// The crow from the Free to Play (Dendi) set sits on Pudge's left shoulder while that set's shoulder piece is equipped
const CROW_WITH = '/models/pudge/items/ftp_dendi_shoulder.glb'
const CROW: PerchSpec = {
  url: '/models/pudge/items/ftp_dendi_crow.glb',
  bone: 'clavicle_L',
  offset: [0.15, 0.5, 0.05],
  rotation: [0, 0.6, 0],
  scale: 1.4,
  anim: 'crow_idle',
}

/** Scaled-down parts: Shadow Fiend's wings are huge in game and don't fit a phone screen */
const BONE_SCALE: Record<string, BoneScale> = {
  '/models/heroes/shadow_fiend/shadow_fiend_wings.glb': { pattern: /Wing/, root: /Wing0_/, scale: 0.6 },
}

export type CharacterHandle = { hit: () => void }

type ModelProps = { handle?: Ref<CharacterHandle>; onMood?: (text: string) => void; look: Look; shows: boolean }

function Model({ handle, onMood, look, shows }: ModelProps) {
  const base = useGLTF(look.body, false, true)
  const anims = ANIMS[look.body] ?? FALLBACK
  const group = useRef<Group>(null)

  const { body, bones, scale, offset } = useMemo(() => {
    const body = clone(base.scene)
    cleanMaterials(body)
    body.traverse((o) => {
      if ((o as SkinnedMesh).isSkinnedMesh) o.frustumCulled = false
    })
    const bones = bonesOf(body)
    // normalize by the body: height HEIGHT, feet at y=0, centered
    const box = new Box3().setFromObject(body)
    const size = box.getSize(new Vector3())
    const c = box.getCenter(new Vector3())
    const scale = (anims.height ?? HEIGHT) / size.y
    return { body, bones, scale, offset: [-c.x * scale, -box.min.y * scale, -c.z * scale] as const }
  }, [base, anims.height])

  const { actions, mixer } = useAnimations(base.animations, group)
  const current = useRef<AnimationAction | null>(null)

  // Center by the actual idle pose (in Dota animations the root is sometimes offset from the default pose):
  // on the 3rd frame compute the bounding box of the skinned meshes and shift the hero to stand exactly on the pedestal.
  const frames = useRef(0)
  const centerBox = useMemo(() => new Box3(), [])
  useFrame(() => {
    if (frames.current++ !== 2 || !group.current) return
    centerBox.makeEmpty()
    body.updateMatrixWorld(true)
    body.traverse((o) => {
      const m = o as SkinnedMesh
      if (!m.isSkinnedMesh || !m.visible) return
      m.computeBoundingBox()
      if (m.boundingBox) centerBox.union(m.boundingBox.clone().applyMatrix4(m.matrixWorld))
    })
    if (centerBox.isEmpty()) return
    const c = centerBox.getCenter(new Vector3())
    const parent = group.current.parent
    if (parent) parent.worldToLocal(c)
    group.current.position.x -= c.x
    group.current.position.z -= c.z
  })
  const hitIdx = useRef(0)
  const lastTap = useRef(0)
  const showIdx = useRef(0)
  const moodRef = useRef(onMood)
  useEffect(() => {
    moodRef.current = onMood
  })

  function play(name: string, once: boolean, fade = 0.15, speed = 1) {
    const next = actions[name]
    if (!next) return
    next.reset().setEffectiveTimeScale(speed).setLoop(once ? LoopOnce : LoopRepeat, Infinity)
    next.clampWhenFinished = once
    if (current.current && current.current !== next) next.crossFadeFrom(current.current, fade, false)
    next.play()
    current.current = next
  }

  useEffect(() => {
    play(anims.idle, false, 0)
    const backToIdle = () => {
      moodRef.current?.('')
      play(anims.idle, false, 0.25)
    }
    mixer.addEventListener('finished', backToIdle)
    lastTap.current = performance.now()
    let nextShowAt = lastTap.current + IDLE_DELAY_MS
    const timer = shows
      ? setInterval(() => {
          const now = performance.now()
          if (now - lastTap.current < IDLE_DELAY_MS) {
            nextShowAt = lastTap.current + IDLE_DELAY_MS
            return
          }
          if (now >= nextShowAt && current.current === actions[anims.idle]) {
            const [mood, anim] = anims.shows[showIdx.current++ % anims.shows.length]
            moodRef.current?.(anims.bubbles[mood] ?? '')
            play(anim, true, 0.3)
            nextShowAt = now + IDLE_GAP_MS
          }
        }, 300)
      : undefined
    return () => {
      clearInterval(timer)
      mixer.removeEventListener('finished', backToIdle)
    }
    // play is stable in meaning (it takes actions from this effect's closure)
  }, [actions, mixer, shows]) // eslint-disable-line react-hooks/exhaustive-deps

  useImperativeHandle(handle, () => ({
    hit() {
      lastTap.current = performance.now()
      moodRef.current?.('')
      play(anims.hits[hitIdx.current++ % anims.hits.length], true, 0.06, 1.8)
    },
  }))

  return (
    <group ref={group} rotation={[0, -0.35, 0]}>
      <group scale={scale} position={offset}>
        <primitive object={body} />
        {look.gear.includes(CROW_WITH) && (
          <Suspense fallback={null}>
            <Perch spec={CROW} bones={bones} />
          </Suspense>
        )}
        {[...look.extras, ...look.gear].map((url) => (
          // each item loads on its own: changing one doesn't reload the rest
          <Suspense key={url} fallback={null}>
            <Gear url={url} body={body} bones={bones} boneScale={BONE_SCALE[url]} />
          </Suspense>
        ))}
      </group>
    </group>
  )
}

class Fallback extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

type Props = {
  look: Look
  handle?: Ref<CharacterHandle>
  /** Hero speech bubble during a taunt ('' clears it) */
  onMood?: (text: string) => void
  /** stage: the tapper (idle taunts, no controls); preview: the Arsenal (rotate with a finger) */
  mode?: 'stage' | 'preview'
  cameraDist?: number
}

export function Character3D({ look, handle, onMood, mode = 'stage', cameraDist = CAMERA_DIST }: Props) {
  const still = <img src="/media/pudge.png" alt="" draggable={false} className="h-full w-full object-contain" />
  const preview = mode === 'preview'
  return (
    <Fallback fallback={still}>
      <Canvas
        className={preview ? 'touch-none' : 'pointer-events-none'}
        dpr={[1, 2]}
        camera={{ position: [0, 1.25, cameraDist], fov: 30 }}
        gl={{ alpha: true, antialias: true }}
        onCreated={({ camera }) => camera.lookAt(0, 1.05, 0)}
      >
        <ambientLight intensity={1.8} />
        <directionalLight position={[2.5, 4, 3]} intensity={3.2} />
        <directionalLight position={[-3, 2, 1]} intensity={0.8} color="#9fd4ff" />
        <pointLight position={[-1.5, 2, -2]} intensity={12} color="#ff3344" />
        <Suspense fallback={null}>
          {/* body change (another hero or an arcana): a new model with its own animations */}
          <Model key={look.body} handle={handle} onMood={onMood} look={look} shows={!preview} />
        </Suspense>
        {preview && (
          <OrbitControls
            target={[0, 1.05, 0]}
            enableZoom={false}
            enablePan={false}
            minPolarAngle={Math.PI / 2.6}
            maxPolarAngle={Math.PI / 2}
            rotateSpeed={0.8}
          />
        )}
      </Canvas>
    </Fallback>
  )
}
