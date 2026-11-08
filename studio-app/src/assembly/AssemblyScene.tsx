// The assembly in 3D: one mesh per manifest instance, placed by its transform and moved by its
// derived explode offset. Studio adds no geometry of its own; display state comes from view.ts.
import { useEffect, useState, type RefObject } from 'react';
import { useLoader, useThree, type ThreeEvent } from '@react-three/fiber';
import { Bounds } from '@react-three/drei';
import { Mesh, MeshPhysicalMaterial } from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { MATERIALS, type ViewStyle } from '../watermelon/ViewportTools';
import { explodedPosition, type AssemblyManifest, type Instance } from './manifest';
import { displayOf, type AssemblyViewState } from './view';

/** The selection accent and hover glint per theme, matching --d-accent and the cream value ink. */
export const SCENE_ACCENT = { dark: { selected: '#e57b46', hover: '#f0e2c8' }, light: { selected: '#b24c1b', hover: '#2f2a23' } };
const GHOST_OPACITY = 0.16;
// A ghost passes clicks through to what is behind it. Never pass raycast={undefined}: R3F would
// assign it and the mesh would stop being pickable at all.
// Hardware and bought parts read as what they are: steel, and a neutral dark housing.
const KIND_FINISH: Record<Exclude<Instance['kind'], 'printed'>, { color: string; metalness: number; roughness: number }> = {
  hardware: { color: '#9a9ea3', metalness: 0.85, roughness: 0.32 },
  component: { color: '#3c3b39', metalness: 0.1, roughness: 0.6 },
};

/** Where each instance actually is in the scene, read back from three.js for tests and tools. */
export type SceneProbe = Record<string, { visible: boolean; opacity: number; highlighted: boolean; position: [number, number, number] }>;

/** Written straight onto the viewport element, so reading the scene never re-renders Studio. */
function Probe({ target, view, manifest }: { target: RefObject<HTMLElement | null>; view: AssemblyViewState; manifest: AssemblyManifest }) {
  const { scene, invalidate } = useThree();
  useEffect(() => {
    const probe: SceneProbe = {};
    scene.traverse(object => {
      const mesh = object as Mesh;
      if (!mesh.isMesh || !mesh.userData.instance) return;
      const material = mesh.material as MeshPhysicalMaterial;
      probe[mesh.userData.instance] = { visible: mesh.visible, opacity: material.transparent ? material.opacity : 1, highlighted: !!mesh.userData.highlighted, position: mesh.position.toArray() as [number, number, number] };
    });
    target.current?.setAttribute('data-instances', JSON.stringify(probe)); invalidate();
  }, [scene, target, view, manifest, invalidate]);
  return null;
}

export function AssemblyScene({ manifest, meshUrl, view, style, wireframe, accent, onSelect, probeTarget }: {
  manifest: AssemblyManifest; meshUrl: (instance: Instance) => string; view: AssemblyViewState; style: ViewStyle; wireframe: boolean;
  accent: { selected: string; hover: string }; onSelect: (id: string) => void; probeTarget: RefObject<HTMLElement | null>;
}) {
  const geometries = useLoader(STLLoader, manifest.instances.map(meshUrl));
  const [hover, setHover] = useState<string | null>(null);
  const printed = MATERIALS[style.material];
  return <>
    <Bounds fit clip observe margin={1.4}>
      {manifest.instances.map((instance, i) => {
        const display = displayOf(view, instance.id);
        const selected = view.selected === instance.id;
        const finish = instance.kind === 'printed' ? printed : KIND_FINISH[instance.kind];
        const ghost = display === 'ghost';
        return <mesh key={instance.id} geometry={geometries[i]} visible={display !== 'hidden'}
          position={explodedPosition(manifest, instance.id, view.explode)} quaternion={instance.transform.quaternion}
          userData={{ cadBody: true, body: instance.id, instance: instance.id, highlighted: selected && display !== 'hidden' }}
          {...(ghost ? { raycast: () => null } : {})} renderOrder={ghost ? 1 : 0}
          onClick={(e: ThreeEvent<MouseEvent>) => { if (e.delta > 4) return; e.stopPropagation(); onSelect(instance.id); }}
          onPointerOver={(e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); setHover(instance.id); }}
          onPointerOut={() => setHover(h => h === instance.id ? null : h)}>
          {/* Keyed on ghost: three only re-sorts and re-blends a material whose transparency it compiled with. */}
          <meshPhysicalMaterial key={ghost ? 'ghost' : 'solid'} color={finish.color} metalness={finish.metalness} roughness={finish.roughness}
            emissive={selected ? accent.selected : hover === instance.id ? accent.hover : '#000000'} emissiveIntensity={selected ? 0.55 : hover === instance.id ? 0.08 : 0}
            clearcoat={0.15} wireframe={wireframe} transparent={ghost} opacity={ghost ? GHOST_OPACITY : 1} depthWrite={!ghost}/>
        </mesh>;
      })}
      {/* X-ray of the selection: a part inside another (a screw in its hole) still shows where it is. */}
      {manifest.instances.map((instance, i) => view.selected === instance.id && displayOf(view, instance.id) !== 'hidden' &&
        <mesh key={`xray-${instance.id}`} geometry={geometries[i]} position={explodedPosition(manifest, instance.id, view.explode)} quaternion={instance.transform.quaternion} raycast={() => null} renderOrder={2}>
          <meshBasicMaterial color={accent.selected} transparent opacity={0.32} depthTest={false} depthWrite={false}/>
        </mesh>)}
    </Bounds>
    <Probe target={probeTarget} view={view} manifest={manifest}/>
  </>;
}
