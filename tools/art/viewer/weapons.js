// Dev-only weapon effects demo: the game's Effects module with the new aircraft, each attacking a
// ground target in its own lane. window.__advance(dt) steps time for frame capture.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { Effects } from '../../../src/render/effects.ts';
import { attachHaloBlades, updateHaloBlades } from '../../../src/render/haloBlades.ts';

const TANK_LENGTH = 4.5;
const W = 1280;
const H = 720;
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(W, H);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x8fb4d8);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.45;
const sun = new THREE.DirectionalLight(0xfff3d6, 2.8);
sun.position.set(30, 60, 20);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -70, right: 70, top: 50, bottom: -50 });
scene.add(sun);
scene.add(new THREE.HemisphereLight(0xd2e6ff, 0x3b3524, 0.55));
const tex = (() => {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#4c6a33';
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 4000; i += 1) {
    const v = (i * 7919) % 100 / 100;
    g.fillStyle = v < 0.5 ? 'rgba(60,85,40,0.5)' : v < 0.85 ? 'rgba(95,120,60,0.45)' : 'rgba(120,105,70,0.4)';
    g.fillRect((i * 37) % 256, (i * 91) % 256, 3, 3);
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(12, 12);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
})();
const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.95 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const camera = new THREE.PerspectiveCamera(48, W / H, 0.5, 500);
const pitch = THREE.MathUtils.degToRad(42);
const dist = 70;
camera.position.set(0, Math.sin(pitch) * dist, Math.cos(pitch) * dist + 4);
camera.lookAt(0, 0, 4);

const effects = new Effects(scene);
const loader = new GLTFLoader();
function prepare(gltf, scale) {
  const root = gltf.scene;
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  root.position.sub(centre);
  const holder = new THREE.Group();
  holder.add(root);
  holder.scale.setScalar((TANK_LENGTH / Math.max(size.x, size.z)) * scale);
  root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  scene.add(holder);
  return holder;
}

// ?close follows the Halo with a near camera to check the blade sweep.
const CLOSE = new URLSearchParams(location.search).has('close');
const LANES = [-36, -18, 0, 18, 36];
const spec = [
  { lane: 0, file: '/assets/models/human/falcon.glb', scale: 1.15, kind: 'laser', speed: 45, every: 0.28, range: 16 },
  { lane: 1, file: '/assets/models/human/condor.glb', scale: 1.7, kind: 'bombs', speed: 20, every: 0.5, range: 4 },
  { lane: 2, file: '/assets/models/alien/halo.glb', scale: 1.2, kind: 'lightning', speed: 45, every: 0.35, range: 16 },
  { lane: 3, file: '/assets/models/alien/disc.glb', scale: 1.25, kind: 'ground_beam', speed: 60, every: 1.4, range: 5 },
];
const targets = [];
const units = [];
let loaded = 0;
loader.load('/assets/models/human/lancer.glb', (gltf) => {
  for (const x of LANES) {
    const t = prepare({ scene: gltf.scene.clone(true), animations: [] }, 1);
    t.position.set(x, 0.9, 6);
    targets.push(t);
  }
  loaded += 1;
});
for (const s of spec) {
  loader.load(s.file, (gltf) => {
    const holder = prepare(gltf, s.scale);
    units.push({ ...s, holder, cool: 0, halo: s.file.endsWith('halo.glb') ? attachHaloBlades(holder) : null });
    loaded += 1;
  });
}
const shots = [];
let spore = 0;
let time = 0;

function fly(u, t) {
  // A strafing pass over the target, looping: in from the back of the field, out past the camera.
  const loop = 6;
  const p = ((t + u.lane * 0.9) % loop) / loop;
  const z = -22 + p * 50;
  const x = LANES[u.lane] + Math.sin(p * Math.PI * 2) * 1.5;
  const hover = u.kind === 'ground_beam';
  u.holder.position.set(x, hover ? 7 + Math.sin(t * 2) * 0.3 : 6.5, hover ? -2 + Math.sin(t * 0.7) * 3 : z);
  u.holder.rotation.set(0, hover ? t * 0.4 : -Math.PI / 2, 0);
}

function fire(u, target) {
  const from = u.holder.position.clone();
  from.y -= 0.3;
  const to = target.position.clone().add(new THREE.Vector3((Math.random() - 0.5) * 1.2, 0.2, (Math.random() - 0.5) * 1.2));
  const obj = effects.projectileMesh(u.kind, u.lane < 2);
  scene.add(obj);
  effects.muzzle(from.x, from.y, from.z, u.kind);
  shots.push({ obj, from, to, kind: u.kind, speed: u.speed, d: 0, len: from.distanceTo(to), shooter: u, splash: u.kind === 'bombs' ? 3 : u.kind === 'ground_beam' ? 3.5 : 0.3 });
}

window.__ready = () => loaded === spec.length + 1;
window.__advance = (dt) => {
  time += dt;
  for (const u of units) {
    fly(u, time);
    if (u.halo) updateHaloBlades(u.halo, dt, true);
    const target = targets[u.lane];
    u.cool -= dt;
    const dz = Math.abs(u.holder.position.z - target.position.z);
    const inRange = u.kind === 'bombs' ? dz < u.range : u.kind === 'ground_beam' ? true : u.holder.position.z < target.position.z - 2 && dz < u.range;
    if (u.cool <= 0 && inRange) {
      fire(u, target);
      u.cool = u.every;
    }
  }
  // Third faction: a ground launcher lobbing a slow spore pod.
  spore -= dt;
  if (spore <= 0) {
    spore = 2.2;
    const from = new THREE.Vector3(LANES[4], 1, -14);
    const obj = effects.projectileMesh('spore', false);
    scene.add(obj);
    shots.push({ obj, from, to: targets[4].position.clone(), kind: 'spore', speed: 12, d: 0, len: 20, lob: true, splash: 3 });
  }
  for (let i = shots.length - 1; i >= 0; i -= 1) {
    const s = shots[i];
    s.d += s.speed * dt;
    const p = Math.min(1, s.d / s.len);
    const prev = s.obj.position.clone();
    s.obj.position.lerpVectors(s.from, s.to, p);
    if (s.kind === 'bombs') {
      s.obj.position.y = s.from.y + (s.to.y - s.from.y) * p * p;
    }
    if (s.lob) {
      s.obj.position.y += Math.sin(p * Math.PI) * 7;
      s.obj.scale.setScalar(1 + Math.sin(time * 9) * 0.12);
    }
    const dir = s.obj.position.clone().sub(prev);
    if (dir.lengthSq() > 1e-6) s.obj.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir.normalize());
    if (s.kind === 'lightning') effects.lightning(s.shooter.holder.position.clone().setY(s.shooter.holder.position.y - 0.2), s.obj.position, 0xffd27a, 0.05, 10, 0.55);
    if (s.kind === 'ground_beam') effects.beam(s.shooter.holder.position.clone().setY(s.shooter.holder.position.y - 0.5), s.obj.position, 0.9, 0.05);
    if (p >= 1) {
      effects.impact(s.kind, s.obj.position.x, s.obj.position.y, s.obj.position.z, 0, s.splash);
      scene.remove(s.obj);
      effects.disposeProjectileMesh(s.obj);
      shots.splice(i, 1);
    }
  }
  effects.update(dt);
  if (CLOSE) {
    const h = units.find((u) => u.halo);
    if (h) {
      camera.position.set(h.holder.position.x + 7, h.holder.position.y + 6, h.holder.position.z + 7);
      camera.lookAt(h.holder.position);
    }
  }
  renderer.render(scene, camera);
};
let last = 0;
function loop(ms) {
  if (window.__ready()) window.__advance(Math.min(0.05, (ms - last) / 1000));
  last = ms;
  requestAnimationFrame(loop);
}
if (!location.search.includes('capture')) requestAnimationFrame(loop);
