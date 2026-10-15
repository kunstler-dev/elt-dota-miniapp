import { useGLTF } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useMemo } from 'react'
import { AdditiveBlending, Box3, DoubleSide, Vector3, type Material, type Mesh, type MeshStandardMaterial } from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'

import { cleanMaterials } from '../components/Rig'

// Radiant Ancient behind Pudge on the Hook card. Static scene: frames render only on demand.
// In Dota the engine draws the tree petals and crystal glow (textures are grey), so we do it in a shader:
// light desaturated canopy pixels -> pink blossoms, light-blue stone pixels -> glowing crystals.

const URL = '/models/props/ancient.glb'

function bloomTree(m: MeshStandardMaterial) {
  m.alphaTest = 0.35
  m.side = DoubleSide
  m.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace(
      '#include <map_fragment>',
      `#include <map_fragment>
      {
        float l = dot(diffuseColor.rgb, vec3(0.3, 0.59, 0.11));
        float sat = max(max(diffuseColor.r, diffuseColor.g), diffuseColor.b) - min(min(diffuseColor.r, diffuseColor.g), diffuseColor.b);
        if (l > 0.16 && sat < 0.12) diffuseColor.rgb = vec3(1.0, 0.28, 0.58) * (0.75 + l * 0.6);
      }`,
    )
  }
}

function glowCrystals(m: MeshStandardMaterial) {
  m.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace(
      '#include <emissivemap_fragment>',
      `#include <emissivemap_fragment>
      if (diffuseColor.b > diffuseColor.r + 0.1) totalEmissiveRadiance += vec3(0.35, 0.65, 1.0) * 0.9;`,
    )
  }
}

function Ancient() {
  const gltf = useGLTF(URL, false, true)
  const obj = useMemo(() => {
    const o = clone(gltf.scene)
    cleanMaterials(o)
    o.traverse((x) => {
      const mesh = x as Mesh
      if (!mesh.isMesh) return
      const mats = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) as Material[]
      const fixed = mats.map((mm) => {
        const c = (mm as MeshStandardMaterial).clone()
        if (/tree/i.test(c.name)) bloomTree(c)
        else glowCrystals(c)
        return c
      })
      mesh.material = Array.isArray(mesh.material) ? fixed : fixed[0]
    })
    const box = new Box3().setFromObject(o)
    const size = box.getSize(new Vector3())
    const c = box.getCenter(new Vector3())
    const s = 3 / size.y
    o.scale.setScalar(s)
    o.position.set(-c.x * s, -box.min.y * s, -c.z * s)
    o.rotation.y = -0.5
    return o
  }, [gltf])
  return (
    <>
      <primitive object={obj} />
      {/* light-blue beam of light above the Ancient */}
      <mesh position={[0, 3.2, 0]}>
        <cylinderGeometry args={[0.35, 0.55, 4.5, 24, 1, true]} />
        <meshBasicMaterial color="#7cc8ff" transparent opacity={0.22} blending={AdditiveBlending} depthWrite={false} side={DoubleSide} />
      </mesh>
    </>
  )
}

export function AncientScene() {
  return (
    <Canvas frameloop="demand" dpr={[1, 2]} camera={{ position: [0, 4.6, 5.6], fov: 38 }} gl={{ alpha: true }}
      onCreated={({ camera }) => camera.lookAt(0, 1.1, 0)}>
      <hemisphereLight args={['#fff2dc', '#4a5a2a', 1.5]} />
      <directionalLight position={[-3, 6, 4]} intensity={3.2} color="#fff0cc" />
      <pointLight position={[0, 1.6, 0.6]} intensity={10} distance={5} color="#8fd0ff" />
      <Ancient />
    </Canvas>
  )
}
