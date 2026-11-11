// Dev-only flyby viewer: the game's lighting, camera angle and unit scaling, with candidate models
// flying loops over grass. window.__step(t) renders the frame at time t (seconds) for capture.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

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
Object.assign(sun.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60 });
scene.add(sun);
scene.add(new THREE.HemisphereLight(0xd2e6ff, 0x3b3524, 0.55));

// Ground: game-like grass with some variation.
const tex = (() => {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#4c6a33';
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 4000; i += 1) {
    const v = Math.random();
    g.fillStyle = v < 0.5 ? 'rgba(60,85,40,0.5)' : v < 0.85 ? 'rgba(95,120,60,0.45)' : 'rgba(120,105,70,0.4)';
    g.fillRect(Math.random() * 256, Math.random() * 256, 3, 3);
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(10, 10);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
})();
const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.95 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// Game camera: FOV 48, ~49 degree pitch, distance ~40 (the default view).
const camera = new THREE.PerspectiveCamera(48, W / H, 0.5, 500);
const pitch = THREE.MathUtils.degToRad(49);
const dist = 38;
camera.position.set(0, Math.sin(pitch) * dist, Math.cos(pitch) * dist);
camera.lookAt(0, 0, 0);

const loader = new GLTFLoader();
function prepare(gltf, scale) {
  const root = gltf.scene;
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  root.position.sub(centre);
  const holder = new THREE.Group();
  holder.add(root);
  const norm = TANK_LENGTH / Math.max(size.x, size.z);
  holder.scale.setScalar(norm * scale);
  root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  const mixer = gltf.animations.length ? new THREE.AnimationMixer(root) : null;
  if (mixer) mixer.clipAction(gltf.animations[0]).play();
  return { holder, mixer };
}

const specs = [
  { file: 'a_falcon.glb', row: -1, kind: 'fighter', scale: 1.15, phase: 0 },
  { file: 'a_disc.glb', row: -1, kind: 'saucer', scale: 1.25, phase: 1.6 },
  { file: 'b_falcon.glb', row: 1, kind: 'fighter', scale: 1.15, phase: 0 },
  { file: 'b_disc.glb', row: 1, kind: 'saucer', scale: 1.25, phase: 1.6 },
];
const units = [];
let loaded = 0;
for (const s of specs) {
  loader.load(`./models/${s.file}`, (gltf) => {
    const u = { ...s, ...prepare(gltf, s.scale) };
    scene.add(u.holder);
    units.push(u);
    loaded += 1;
  });
}

function place(u, t) {
  // Both entries at the same depth: A on the left half, B on the right half.
  const bx = u.row * 11;
  if (u.kind === 'fighter') {
    const w = 0.6;
    const a = t * w + u.phase;
    const x = bx + Math.sin(a) * 6;
    const z = -5 + Math.sin(2 * a) * 2.4;
    const dx = Math.cos(a) * 6 * w;
    const dz = Math.cos(2 * a) * 2 * 2.4 * w;
    u.holder.position.set(x, 6, z);
    u.holder.rotation.set(0, -Math.atan2(dz, dx), 0);
    u.holder.rotateX(-Math.sin(2 * a) * 0.5 * Math.sign(Math.cos(a)));
  } else {
    const a = t * 0.5 + u.phase;
    const x = bx + Math.cos(a) * 3.5;
    const z = 6 + Math.sin(a) * 1.6;
    u.holder.position.set(x, 6 + Math.sin(t * 2.1) * 0.35, z);
    u.holder.rotation.set(0, -(a + Math.PI / 2), 0);
  }
  if (u.mixer) u.mixer.setTime(t);
}

window.__ready = () => loaded === specs.length;
window.__step = (t) => {
  for (const u of units) place(u, t);
  renderer.render(scene, camera);
};
function loop(ms) {
  window.__step(ms / 1000);
  requestAnimationFrame(loop);
}
if (!location.search.includes('capture')) requestAnimationFrame(loop);
