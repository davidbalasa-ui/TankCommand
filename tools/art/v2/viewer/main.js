// Dev-only line-up viewer: the game's lighting and camera angle, with models standing on grass.
//   ?files=human/lancer.glb,alien/stinger.glb&scales=1,1&dist=26&cols=4&kind=unit|structure
// window.__ready() is true once every model has loaded and a frame is drawn.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { Blast, LIFE as BLAST_LIFE } from './blast.js';

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
const pitch = THREE.MathUtils.degToRad(Number(q.get('pitch') || 49));
const cz = ((rows - 1) * gap) / 2;
camera.position.set(0, Math.sin(pitch) * dist, cz + Math.cos(pitch) * dist);
camera.lookAt(0, 0, cz);

let loaded = 0;
// Moving parts (extras.anim written by motion.py): posed for a given time, as the game does.
const parts = [];
const turn = new THREE.Quaternion();
const hash = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const firePeriod = Number(q.get('fire') || 0);
const moving = q.get('move') === '1';
const hit = (x, a, r) => (x < 0 ? 0 : x < a ? x / a : Math.max(0, 1 - (x - a) / r) ** 2);
const rep = (spec, tf, fn) => { let v = 0; for (let k = 0; k < (spec.repeat || 1); k += 1) v = Math.max(v, fn(tf - (spec.delay || 0) - k * (spec.every || 0))); return v; };
const roots = [];
const holders = [];
const pose = (t) => {
  // Every unit fires on its own clock: scene extras fire.period (s) overrides the viewer's fire= period.
  const clock = (fire) => (firePeriod ? (t % ((fire && fire.period) || firePeriod)) : 1e9);
  for (const { root, fire } of roots) {
    if (!fire) continue;
    const tf0 = clock(fire);
    let k = 0;
    for (let i = 0; i < (fire.repeat || 1); i += 1) {
      const tf = tf0 - i * (fire.every || 0);
      if (tf < 0) continue;
      const x = tf - fire.attack;
      const v = tf < fire.attack ? tf / fire.attack : Math.exp(-4 * x / fire.recover) * Math.cos(6 * x / fire.recover);
      if (Math.abs(v) > Math.abs(k)) k = v;
    }
    root.rotation.z = firePeriod ? fire.kick * k : 0;
    root.position.x = firePeriod ? -fire.slide * k : 0;
  }
  // Whole-unit idle life (scene extras idle): hover bob, roll sway, engine shudder.
  for (const { root, idle, y0 } of roots) {
    if (!idle) continue;
    root.position.y = y0 + (idle.bob || 0) * Math.sin(Math.PI * 2 * (idle.bobSpeed || 0.5) * t) + (idle.shake || 0) * Math.sin(t * 61) * Math.sin(t * 37);
    root.rotation.x = (idle.sway || 0) * Math.sin(Math.PI * 2 * (idle.swaySpeed || 0.3) * t + 1.3);
  }
  for (const { node, spec, rest, pos, fire } of parts) {
    const tf = clock(fire);
    if (spec.type === 'scroll') { if (moving && node.material && node.material.map) node.material.map.offset.x = spec.speed * t; continue; }
    if (spec.type === 'recoil') {
      const a = new THREE.Vector3(...spec.axis).normalize();
      node.position.copy(pos).addScaledVector(a, -spec.dist * rep(spec, tf, (x) => hit(x, spec.attack, spec.recover)));
      continue;
    }
    if (spec.type === 'slide') {
      const a = new THREE.Vector3(...spec.axis).normalize();
      node.position.copy(pos).addScaledVector(a, spec.amp * Math.sin(Math.PI * 2 * spec.speed * t + (spec.phase || 0)) + (spec.snap ? spec.snap * hit(tf, spec.attack, spec.recover) : 0));
      continue;
    }
    if (spec.type === 'flash') {
      node.visible = rep(spec, tf, (x) => (x >= 0 && x < spec.dur ? 1 : 0)) > 0;
      continue;
    }
    if (spec.type === 'launch') {
      const x = tf - spec.delay;
      const a = new THREE.Vector3(...spec.axis).normalize();
      node.visible = !(x >= spec.dur && tf < spec.reload);
      node.position.copy(pos).addScaledVector(a, x > 0 && x < spec.dur ? spec.travel * (x / spec.dur) ** 2 : 0);
      continue;
    }
    const axis = spec.axis ? new THREE.Vector3(...spec.axis).normalize() : null;
    if (spec.type === 'spin') {
      node.quaternion.copy(rest).multiply(turn.setFromAxisAngle(axis, spec.speed * t));
    } else if (spec.type === 'swing') {
      node.quaternion.copy(rest).multiply(turn.setFromAxisAngle(axis, spec.amp * Math.sin(Math.PI * 2 * spec.speed * t + (spec.phase || 0)) + (spec.snap ? spec.snap * hit(tf, spec.attack, spec.recover) : 0)));
    } else if (spec.type === 'flicker') {
      const tick = Math.floor(t * spec.rate);
      node.visible = (spec.fireOn && tf < spec.fireOn) || (hash(tick) < spec.duty && Math.floor(hash(tick + 0.5) * spec.slots) === spec.slot);
    }
  }
  if (useBlast) for (const m of muzzles) m.node.visible = false;
};

// Soft layered muzzle blasts (blast.js) in place of the solid flash meshes; blast=0 shows the old meshes.
const useBlast = q.get('blast') !== '0';
const blast = new Blast(scene);
const muzzles = [];
const shotsAt = (m, t) => {
  // Every shot of this gun whose blast is still alive at time t: [{ t0, seed }].
  const P = (m.fire && m.fire.period) || firePeriod;
  if (!firePeriod || !P) return [];
  const out = [];
  const cyc = Math.floor(t / P);
  for (let c = cyc - 1; c <= cyc; c += 1) {
    if (c < 0) continue;
    for (let k = 0; k < (m.spec.repeat || 1); k += 1) {
      const t0 = c * P + (m.spec.delay || 0) + k * (m.spec.every || 0);
      if (t - t0 > -1e-6 && t - t0 < BLAST_LIFE) out.push({ t0, seed: m.id * 101 + c * 7 + k });
    }
  }
  return out;
};
// How heavy a gun is (0..1) from its size: big guns throw more smoke and blow dust off the ground.
const heavyOf = (S) => Math.max(0, Math.min(1, (S - 0.45) / 0.25));
// Blast size from the gun's size, compressed so the biggest guns don't drown the tank.
const blastSize = (S) => 0.36 * (S / 0.3) ** 0.52;
window.__muzzles = muzzles;
window.__setTime = (t) => {
  blast.begin();
  if (useBlast) {
    const live = [];
    for (const m of muzzles) for (const s of shotsAt(m, t)) live.push({ m, s });
    for (const { m, s } of live) {
      pose(s.t0 + 0.001);
      m.node.updateWorldMatrix(true, false);
      s.p = m.local.clone().applyMatrix4(m.node.matrixWorld);
      s.dir = m.axis.clone().transformDirection(m.node.matrixWorld).normalize();
      s.S = m.size * m.node.matrixWorld.getMaxScaleOnAxis();
    }
    pose(t);
    for (const { m, s } of live) {
      // The muzzle keeps recoiling after the shot: the blast is born where it fired, the hot tip moves on.
      m.node.updateWorldMatrix(true, false);
      const pm = m.local.clone().applyMatrix4(m.node.matrixWorld);
      blast.shot(camera, s.p, s.dir, blastSize(s.S), Math.max(0, t - s.t0), s.seed, pm, heavyOf(s.S));
    }
  } else {
    pose(t);
  }
  blast.end();
  renderer.render(scene, camera);
};

const loader = new GLTFLoader();
const lod = q.get('lod') === '1';
const loadModel = (file, done, fail) => {
  if (!lod) { loader.load(`./models/${file}`, done, undefined, fail); return; }
  // Low-detail files carry no textures: borrow the material from the full model, as the game does.
  loader.load(`./models/${file}`, (full) => {
    let mat = null;
    full.scene.traverse((o) => { if (o.isMesh && !mat) mat = o.material; });
    loader.load(`./models/${file.replace('.glb', '_lod.glb')}`, (low) => {
      low.scene.traverse((o) => { if (o.isMesh) o.material = mat; });
      done(low);
    }, undefined, fail);
  }, undefined, fail);
};
files.forEach((file, i) => {
  loadModel(file, (gltf) => {
    const root = gltf.scene;
    let box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const holder = new THREE.Group();
    holder.add(root);
    const s = kind === 'unit' ? (TANK_LENGTH / Math.max(size.x, size.z)) * (scales[i] || 1) : (scales[i] || 1);
    holder.scale.setScalar(s);
    holder.rotation.y = q.has('yaw') ? Number(q.get('yaw')) : kind === 'unit' ? -0.6 : 0;
    box = new THREE.Box3().setFromObject(holder);
    const centre = box.getCenter(new THREE.Vector3());
    const col = i % cols;
    const row = Math.floor(i / cols);
    holder.position.set((col - (Math.min(cols, files.length) - 1) / 2) * gap - centre.x, -box.min.y + Number(q.get('lift') || 0), row * gap - centre.z);
    const unitFire = gltf.scene.userData && gltf.scene.userData.fire;
    root.traverse((o) => { if (o.userData && o.userData.anim) parts.push({ node: o, spec: o.userData.anim, rest: o.quaternion.clone(), pos: o.position.clone(), fire: unitFire }); });
    roots.push({ root, fire: gltf.scene.userData && gltf.scene.userData.fire, idle: gltf.scene.userData && gltf.scene.userData.idle, y0: root.position.y });
    root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    root.updateWorldMatrix(true, true);
    root.traverse((o) => {
      if (!(o.userData && o.userData.anim && o.userData.anim.type === 'flash')) return;
      // Muzzle = the back end of the flash mesh along its axis, in the flash node's own space.
      const axis = new THREE.Vector3(...o.userData.anim.axis).normalize();
      const inv = o.matrixWorld.clone().invert();
      const bb = new THREE.Box3();
      o.traverse((c) => { if (c.isMesh) { c.geometry.computeBoundingBox(); bb.union(c.geometry.boundingBox.clone().applyMatrix4(c.matrixWorld.clone().premultiply(inv))); } });
      if (bb.isEmpty()) return;
      const ctr = bb.getCenter(new THREE.Vector3());
      const ext = bb.getSize(new THREE.Vector3());
      const len = Math.abs(ext.dot(axis));
      const local = ctr.addScaledVector(axis, -len / 2);
      o.traverse((c) => { if (c.isMesh) c.castShadow = false; });
      muzzles.push({ node: o, spec: o.userData.anim, fire: unitFire, axis, local, size: len * 0.65, id: muzzles.length + 1 });
    });
    holders[i] = holder;
    scene.add(holder);
    loaded += 1;
  }, () => { loaded += 1; });
});
window.__ready = () => loaded === files.length;
// Label anchors for line-up sheets: the point on the ground just in front of each model, as screen fractions.
window.__anchors = () => holders.flatMap((h) => {
  const bx = new THREE.Box3().setFromObject(h);
  const p = new THREE.Vector3((bx.min.x + bx.max.x) / 2, 0, bx.max.z + 0.6).project(camera);
  return [(p.x + 1) / 2, (1 - p.y) / 2];
});
if (q.has('t')) { const wait = setInterval(() => { if (window.__ready()) { window.__setTime(Number(q.get('t'))); clearInterval(wait); } }, 100); }
function loop() {
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
