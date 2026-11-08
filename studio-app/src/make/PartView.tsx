import React, { Component, Suspense, useEffect, useState } from 'react';
import { Canvas, useLoader, useThree } from '@react-three/fiber';
import { Bounds, OrbitControls } from '@react-three/drei';
import { PMREMGenerator } from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { MATERIALS } from '../watermelon/ViewportTools';

/* The checked part as the maker will hold it: the version's own STL, Z up, in Studio's porcelain
   finish under the same local room light. It is a view; it never changes the part. */

function Room() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const generator = new PMREMGenerator(gl); const room = new RoomEnvironment();
    const texture = generator.fromScene(room).texture; scene.environment = texture; scene.environmentIntensity = 0.7;
    return () => { scene.environment = null; texture.dispose(); room.dispose(); generator.dispose(); };
  }, [gl, scene]);
  return null;
}
function Part({ url, onReady }: { url: string; onReady: () => void }) {
  const geometry = useLoader(STLLoader, url);
  const { invalidate } = useThree();
  useEffect(() => { invalidate(); const frame = requestAnimationFrame(onReady); return () => cancelAnimationFrame(frame); }, [geometry, invalidate, onReady]);
  const finish = MATERIALS.porcelain;
  return <mesh geometry={geometry}><meshPhysicalMaterial color={finish.color} metalness={finish.metalness} roughness={finish.roughness} clearcoat={0.15} /></mesh>;
}
class Fallback extends Component<{ children: React.ReactNode; fallback: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

export default function PartView({ url, label, fallback }: { url: string; label: string; fallback: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const done = React.useCallback(() => setReady(true), []);
  // data-ready marks the first frame with the part drawn (tests and screenshots wait for it).
  return <div className="mk-part" role="img" aria-label={label} data-ready={ready || undefined}>
    <Fallback fallback={fallback}>
      <Canvas camera={{ position: [1, -1.4, 0.9], up: [0, 0, 1], fov: 30 }} frameloop="demand" dpr={[1, 2]} gl={{ preserveDrawingBuffer: true }}>
        <Room />
        <directionalLight position={[2, -3, 4]} intensity={1.2} />
        <Suspense fallback={null}><Bounds fit clip observe margin={1.25}><Part url={url} onReady={done} /></Bounds></Suspense>
        <OrbitControls makeDefault enablePan={false} />
      </Canvas>
    </Fallback>
  </div>;
}
