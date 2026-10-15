import { useAnimations, useGLTF } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Suspense, useEffect, useMemo, useRef } from 'react'
import {
  AdditiveBlending,
  Box3,
  BufferAttribute,
  BufferGeometry,
  MeshBasicMaterial,
  Vector3,
  type Group,
  type Material,
  type Mesh,
  type Object3D,
  type Points,
  type SkinnedMesh,
} from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'

import { bonesOf, cleanMaterials, Gear } from '../components/Rig'
import type { GuessView } from '../lib/api'

// "Guess the Hero": the model comes via session links (the hero can't be read from the URL); until answered it's a black silhouette.
// Round difficulty: rotation speed and camera angle (front -> back -> top -> close-up -> awkward angle).

const BLACK = new MeshBasicMaterial({ color: '#000000' })

const CAMERA: Record<Exclude<GuessView, 'odd'>, { pos: [number, number, number]; look: [number, number, number] }> = {
  front: { pos: [0, 1.1, 5.4], look: [0, 0.8, 0] },
  back: { pos: [0, 1.1, 5.4], look: [0, 0.8, 0] },
  high: { pos: [0, 4.4, 2.2], look: [0, 0.7, 0] },
  close: { pos: [0, 1.45, 2.3], look: [0, 1.3, 0] },
}
// "Awkward" angles: from below at the feet, almost side-on, top-side; picked by round number
const ODD: { pos: [number, number, number]; look: [number, number, number] }[] = [
  { pos: [1.2, 0.15, 3.2], look: [0, 1.2, 0] },
  { pos: [4.2, 0.9, 0.6], look: [0, 0.8, 0] },
  { pos: [-2.6, 3.6, 1.4], look: [0, 0.6, 0] },
  { pos: [0.4, 0.5, 2.0], look: [0, 0.4, 0] },
]

function Camera({ view, round }: { view: GuessView; round: number }) {
  const { camera } = useThree()
  useEffect(() => {
    const c = view === 'odd' ? ODD[round % ODD.length] : CAMERA[view]
    camera.position.set(...c.pos)
    camera.lookAt(...c.look)
  }, [camera, view, round])
  return null
}

/** Paints all meshes black (or restores the original materials), for the body and all items inside the group */
function useSilhouette(root: React.RefObject<Group | null>, hidden: boolean) {
  const originals = useRef(new Map<Mesh, Material | Material[]>())
  useFrame(() => {
    root.current?.traverse((o) => {
      const m = o as Mesh
      if (!m.isMesh) return
      if (!originals.current.has(m)) originals.current.set(m, m.material)
      const want = hidden ? BLACK : originals.current.get(m)!
      if (m.material !== want) m.material = want
    })
  })
}

function Hero({ body: bodyUrl, items, hidden, spin, view }: { body: string; items: string[]; hidden: boolean; spin: number; view: GuessView }) {
  const gltf = useGLTF(bodyUrl, false, true)
  const group = useRef<Group>(null)
  const spinRef = useRef<Group>(null)
  const { body, bones, scale, offset } = useMemo(() => {
    const body = clone(gltf.scene)
    cleanMaterials(body)
    body.traverse((o: Object3D) => {
      if ((o as SkinnedMesh).isSkinnedMesh) o.frustumCulled = false
    })
    const box = new Box3().setFromObject(body)
    const size = box.getSize(new Vector3())
    const c = box.getCenter(new Vector3())
    const scale = 1.6 / size.y
    return { body, bones: bonesOf(body), scale, offset: [-c.x * scale, -box.min.y * scale, -c.z * scale] as const }
  }, [gltf])
  const { actions, names } = useAnimations(gltf.animations, group)
  useEffect(() => {
    const idle = names.find((n) => /idle/.test(n)) ?? names[0]
    if (idle) actions[idle]?.play()
  }, [actions, names])
  useEffect(() => {
    if (spinRef.current) spinRef.current.rotation.y = view === 'back' ? Math.PI : 0
  }, [view])
  useSilhouette(group, hidden)
  // like in Character3D: center by the actual idle pose (Dota models have an offset animation root), feet at y=0
  // Height is also measured on the pose: for some models (Tiny, Tidehunter) the default pose is much smaller than the stance.
  const frames = useRef(0)
  useFrame(() => {
    const g = group.current
    const n = frames.current++
    if ((n !== 2 && n !== 3) || !g?.parent) return
    const box = new Box3()
    body.updateMatrixWorld(true)
    body.traverse((o) => {
      const m = o as SkinnedMesh
      if (!m.isSkinnedMesh || !m.visible) return
      m.computeBoundingBox()
      if (m.boundingBox) box.union(m.boundingBox.clone().applyMatrix4(m.matrixWorld))
    })
    if (box.isEmpty()) return
    if (n === 2) {
      const size = box.getSize(new Vector3())
      g.scale.multiplyScalar(Math.min(1.5 / size.y, 1.15 / Math.max(size.x, size.z)))
      return
    }
    const c = g.parent.worldToLocal(box.getCenter(new Vector3()))
    const low = g.parent.worldToLocal(box.min.clone())
    g.position.x -= c.x
    g.position.z -= c.z
    g.position.y -= low.y
    g.visible = true
  })
  useFrame((_, dt) => {
    // at an awkward angle we barely rotate: the point is the viewing angle
    const speed = hidden ? (view === 'odd' ? spin * 0.15 : spin) : 0.25
    if (spinRef.current) spinRef.current.rotation.y += dt * speed
  })
  return (
    <group ref={spinRef}>
      <group ref={group} scale={scale} position={offset} visible={false}>
        <primitive object={body} />
        {items.map((u) => (
          <Suspense key={u} fallback={null}>
            <Gear url={u} body={body} bones={bones} />
          </Suspense>
        ))}
      </group>
    </group>
  )
}

/** Pedestal: dark stone, a glowing ring (turns red as time runs out) and dust in the spotlight beam */
function Stage({ urgency, revealed }: { urgency: number; revealed: boolean }) {
  const ring = useRef<Mesh>(null)
  const dust = useRef<Points>(null)
  const geo = useMemo(() => {
    const g = new BufferGeometry()
    const p = new Float32Array(120 * 3)
    for (let i = 0; i < 120; i++) {
      const a = Math.random() * Math.PI * 2
      const r = Math.random() * 1.1
      p.set([Math.cos(a) * r, Math.random() * 3, Math.sin(a) * r], i * 3)
    }
    g.setAttribute('position', new BufferAttribute(p, 3))
    return g
  }, [])
  useFrame((state, dt) => {
    const t = state.clock.elapsedTime
    if (ring.current) {
      const mat = ring.current.material as MeshBasicMaterial
      mat.color.setRGB(revealed ? 0.25 : 0.25 + 0.75 * urgency, revealed ? 0.8 : 0.55 * (1 - urgency) + 0.1, revealed ? 0.4 : 0.95 * (1 - urgency))
      const pulse = 1 + Math.sin(t * (3 + urgency * 9)) * 0.03 * (1 + urgency * 2)
      ring.current.scale.setScalar(pulse)
    }
    if (dust.current) {
      const pos = dust.current.geometry.attributes.position as BufferAttribute
      for (let i = 0; i < pos.count; i++) {
        let y = pos.getY(i) + dt * 0.12
        if (y > 3) y = 0
        pos.setY(i, y)
      }
      pos.needsUpdate = true
      dust.current.rotation.y += dt * 0.05
    }
  })
  return (
    <>
      <mesh position={[0, -0.06, 0]}>
        <cylinderGeometry args={[0.58, 0.66, 0.08, 48]} />
        <meshStandardMaterial color="#101217" roughness={0.9} />
      </mesh>
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <ringGeometry args={[0.56, 0.6, 64]} />
        <meshBasicMaterial color="#5fb7ff" transparent opacity={0.55} />
      </mesh>
      <points ref={dust} geometry={geo}>
        <pointsMaterial size={0.025} color="#9fc7ff" transparent opacity={0.6} blending={AdditiveBlending} depthWrite={false} />
      </points>
    </>
  )
}

type Props = { body: string; items: string[]; hidden: boolean; spin: number; view: GuessView; round: number; urgency: number }

export function SilhouetteScene({ body, items, hidden, spin, view, round, urgency }: Props) {
  // the revealed answer is shown from the front so you can see who it was
  const camView: GuessView = hidden ? view : 'front'
  return (
    <Canvas dpr={[1, 2]} camera={{ position: CAMERA.front.pos, fov: 30 }} gl={{ alpha: true }}>
      <Camera view={camView} round={round} />
      <ambientLight intensity={1.6} />
      <directionalLight position={[2.5, 4, 3]} intensity={3} />
      <spotLight position={[0, 5, 1.5]} angle={0.45} penumbra={0.7} intensity={hidden ? 12 : 30} color={hidden ? '#7fb2ff' : '#fff2d8'} />
      <Stage urgency={hidden ? urgency : 0} revealed={!hidden} />
      <Suspense fallback={null}>
        <Hero key={body} body={body} items={items} hidden={hidden} spin={spin} view={view} />
      </Suspense>
    </Canvas>
  )
}
