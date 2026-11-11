// Dev-only line-up viewer: the game's lighting and camera angle, with models standing on grass.
//   ?files=human/lancer.glb,alien/stinger.glb&scales=1,1&dist=26&cols=4&kind=unit|structure
// window.__ready() is true once every model has loaded and a frame is drawn.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

const q = new URLSearchParams(location.search);
const files = (q.get('files') || '').split(',').filter(Boolean);
const scales = (q.get('scales') || '').split(',').map(Number);
const dist = Number(q.get('dist') || 30);
const cols = Number(q.get('cols') || 4);
const gap = Number(q.get('gap') || 8);
const kind = q.get('kind') || 'unit';
const TANK_LENGTH = 4.5;
const W = Number(q.get('w') || 1600);
const H = Number(q.get('h') || 900);

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
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
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -70, right: 70, top: 70, bottom: -70 });
scene.add(sun);
scene.add(new THREE.HemisphereLight(0xd2e6ff, 0x3b3524, 0.55));

const c = document.createElement('canvas');
c.width = c.height = 256;
const g = c.getContext('2d');
g.fillStyle = '#4c6a33';
g.fillRect(0, 0, 256, 256);
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
for (let i = 0; i < 4000; i += 1) {
  const v = rnd();
  g.fillStyle = v < 0.5 ? 'rgba(60,85,40,0.5)' : v < 0.85 ? 'rgba(95,120,60,0.45)' : 'rgba(120,105,70,0.4)';
  g.fillRect(rnd() * 256, rnd() * 256, 3, 3);
}
const tex = new THREE.CanvasTexture(c);
tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
tex.repeat.set(14, 14);
tex.colorSpace = THREE.SRGBColorSpace;
const ground = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.95 }));
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const rows = Math.ceil(files.length / cols);
const camera = new THREE.PerspectiveCamera(48, W / H, 0.5, 800);
const pitch = THREE.MathUtils.degToRad(49);
const cz = ((rows - 1) * gap) / 2;
camera.position.set(0, Math.sin(pitch) * dist, cz + Math.cos(pitch) * dist);
camera.lookAt(0, 0, cz);

let loaded = 0;
const loader = new GLTFLoader();
files.forEach((file, i) => {
  loader.load(`./models/${file}`, (gltf) => {
    const root = gltf.scene;
    let box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const holder = new THREE.Group();
    holder.add(root);
    const s = kind === 'unit' ? (TANK_LENGTH / Math.max(size.x, size.z)) * (scales[i] || 1) : (scales[i] || 1);
    holder.scale.setScalar(s);
    holder.rotation.y = kind === 'unit' ? -0.6 : 0;
    box = new THREE.Box3().setFromObject(holder);
    const centre = box.getCenter(new THREE.Vector3());
    const col = i % cols;
    const row = Math.floor(i / cols);
    holder.position.set((col - (Math.min(cols, files.length) - 1) / 2) * gap - centre.x, -box.min.y, row * gap - centre.z);
    root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    scene.add(holder);
    loaded += 1;
  }, undefined, () => { loaded += 1; });
});
window.__ready = () => loaded === files.length;
function loop() {
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
