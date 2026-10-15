import { useGLTF } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import {
  AnimationMixer,
  Matrix4,
  Vector3,
  type Bone,
  type Mesh,
  type MeshStandardMaterial,
  type Object3D,
  type SkinnedMesh,
} from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'

const FX_MATERIAL = /teleport|edge_glow|debugempty|_fx|portrait|scrolling/i
// Helper meshes and alternative item styles (Dota shows one style, the export includes all of them)
const HIDDEN_MESH = /hitbox|_style\d|_dummy/i

/**
 * Fixes materials after the Dota export: Source 2 detail masks end up in the emissive channel
 * and tint the model purple, so we remove them; helper effect meshes (teleport shell, etc.) are hidden.
 */
export function cleanMaterials(root: Object3D) {
  root.traverse((o) => {
    const mesh = o as Mesh
    if (!mesh.isMesh) return
    const mats = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) as MeshStandardMaterial[]
    if (HIDDEN_MESH.test(mesh.name) || HIDDEN_MESH.test(mesh.parent?.name ?? '') || mats.some((m) => FX_MATERIAL.test(m.name) || FX_MATERIAL.test(m.map?.name ?? ''))) {
      mesh.visible = false
      return
    }
    for (const m of mats) {
      if (m.emissiveMap) {
        m.emissiveMap = null
        m.emissive?.setRGB(0, 0, 0)
        m.needsUpdate = true
      }
    }
  })
}

/** All model bones by name. */
export function bonesOf(root: Object3D): Map<string, Bone> {
  const bones = new Map<string, Bone>()
  root.traverse((o) => {
    if ((o as Bone).isBone) bones.set(o.name, o as Bone)
  })
  return bones
}

/**
 * Body bone for an item bone. Older items name bones differently from the hero body: case (`bicep_l` / `bicep_L`),
 * a `_duplicate` suffix, a full path (`spine_0_spine_1_spine_3_clavicle_l` -> `clavicle_L`). Bones the body doesn't have
 * (hair tail, cloth) are not matched and follow their parent.
 */
function boneMatcher(bones: Map<string, Bone>) {
  const lower = new Map<string, Bone>()
  for (const [name, b] of bones) lower.set(name.toLowerCase(), b)
  const names = [...lower.keys()].sort((a, b) => b.length - a.length)
  return (name: string): Bone | undefined => {
    const exact = bones.get(name)
    if (exact) return exact
    const n = name.toLowerCase().replace(/_duplicate$/, '')
    const direct = lower.get(n)
    if (direct) return direct
    const tail = names.find((k) => n.endsWith('_' + k))
    return tail ? lower.get(tail) : undefined
  }
}

/**
 * A Dota item on the body skeleton. The item has its own skeleton with the same bone names as the hero;
 * every frame its bones copy the world transforms of the body bones. This fits both skinned meshes
 * and rigid props attached to bones (cleavers, orbs, flags).
 */
/** Scale down part of an item (e.g. SF wingspan): bones matching pattern are scaled relative to their root. */
export type BoneScale = { pattern: RegExp; root: RegExp; scale: number }

const tmpM = new Matrix4()
const tmpS = new Matrix4()
const tmpInv = new Matrix4()

export function Gear({
  url,
  body,
  bones,
  boneScale,
}: {
  url: string
  body: Object3D
  bones: Map<string, Bone>
  boneScale?: BoneScale
}) {
  const gltf = useGLTF(url, false, true)
  const { scene, pairs, groups } = useMemo(() => {
    const scene = clone(gltf.scene)
    cleanMaterials(scene)
    const pairs: [Bone, Bone][] = []
    const match = boneMatcher(bones)
    scene.traverse((o) => {
      if ((o as SkinnedMesh).isSkinnedMesh) o.frustumCulled = false
      if ((o as Bone).isBone) {
        const target = match(o.name)
        if (target) {
          o.matrixWorldAutoUpdate = false // we set the world matrix ourselves; the renderer doesn't recompute it
          pairs.push([o as Bone, target])
        }
      }
    })
    // scaling groups: root -> all of its bones matching pattern
    const groups: { root: Bone; members: Bone[] }[] = []
    if (boneScale) {
      for (const [mine] of pairs) {
        if (!boneScale.root.test(mine.name)) continue
        const members: Bone[] = []
        mine.traverse((o) => {
          if ((o as Bone).isBone && boneScale.pattern.test(o.name)) members.push(o as Bone)
        })
        groups.push({ root: mine, members })
      }
    }
    return { scene, pairs, groups }
  }, [gltf, bones, boneScale])

  // the item's useFrame is registered after the body mixer, so poses are already updated by the animation
  useFrame(() => {
    body.updateMatrixWorld(true)
    for (const [mine, target] of pairs) mine.matrixWorld.copy(target.matrixWorld)
    if (!boneScale) return
    tmpS.makeScale(boneScale.scale, boneScale.scale, boneScale.scale)
    for (const { root, members } of groups) {
      // T = W_root · S · W_root⁻¹ is a scale around the root; W' = T · W for every bone in the group
      tmpInv.copy(root.matrixWorld).invert()
      tmpM.copy(root.matrixWorld).multiply(tmpS).multiply(tmpInv)
      for (const b of members) b.matrixWorld.premultiply(tmpM)
    }
  })

  return <primitive object={scene} />
}

export type PerchSpec = {
  url: string
  /** bone the creature sits on (follows its position but stays upright) */
  bone: string
  /** offset from the bone and rotation, in model coordinates (Y up) */
  offset: [number, number, number]
  rotation: [number, number, number]
  scale?: number
  anim?: string
}

const tmp = new Vector3()

/**
 * A creature with its own skeleton and animation sitting on the hero (the crow from the Dendi set).
 * The body bones don't fit it (separate skeleton), so it follows the bone position and doesn't tilt with it.
 * Render inside the same group as the body.
 */
export function Perch({ spec, bones }: { spec: PerchSpec; bones: Map<string, Bone> }) {
  const gltf = useGLTF(spec.url, false, true)
  const scene = useMemo(() => {
    const sc = clone(gltf.scene)
    cleanMaterials(sc)
    sc.traverse((o) => {
      if ((o as SkinnedMesh).isSkinnedMesh) o.frustumCulled = false
    })
    sc.rotation.set(...spec.rotation)
    sc.scale.setScalar(spec.scale ?? 1)
    return sc
  }, [gltf, spec])
  const mixer = useMemo(() => new AnimationMixer(scene), [scene])

  useEffect(() => {
    const clip = gltf.animations.find((a) => a.name === spec.anim) ?? gltf.animations[0]
    if (clip) mixer.clipAction(clip).play()
    return () => {
      mixer.stopAllAction()
    }
  }, [mixer, gltf, spec])

  useFrame((_, dt) => {
    mixer.update(dt)
    const bone = bones.get(spec.bone)
    if (!bone || !scene.parent) return
    bone.getWorldPosition(tmp)
    scene.parent.worldToLocal(tmp)
    scene.position.set(tmp.x + spec.offset[0], tmp.y + spec.offset[1], tmp.z + spec.offset[2])
  })
  return <primitive object={scene} />
}
