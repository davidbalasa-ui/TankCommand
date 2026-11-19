// Renders one glb model with dramatic lighting to a transparent PNG data URL.
// Driven by render.mjs through window.renderModel(opts).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const loader = new GLTFLoader();

window.renderModel = async function renderModel(opts) {
  const {
    url,
    size = 1024,
    yaw = -0.6,
    pitch = 0.32,
    rim = '#3fd8ff',
    accent = '#ff8a2a',
    fov = 26,
    fill = 0.92,
  } = opts;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(size, size);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = opts.exposure ?? 1.15;
  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = opts.env ?? 0.35;

  const gltf = await loader.loadAsync(url);
  const model = gltf.scene;
  // Muzzle flash cards are hidden in the static art.
  model.traverse((o) => {
    if (/^Flash/.test(o.name)) o.visible = false;
  });
  model.rotation.y = yaw;
  scene.add(model);
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  model.position.sub(center);

  const cam = new THREE.PerspectiveCamera(fov, 1, 0.01, 1000);
  const dist = sphere.radius / Math.sin(THREE.MathUtils.degToRad(fov / 2)) / fill;
  cam.position.set(0, Math.sin(pitch) * dist, Math.cos(pitch) * dist);
  cam.lookAt(0, 0, 0);

  // Key from the upper front-left, cyan rim from behind-right, warm accent from behind-left.
  const key = new THREE.DirectionalLight('#dfe9ff', opts.key ?? 2.6);
  key.position.set(-3, 5, 4);
  const rimLight = new THREE.DirectionalLight(rim, opts.rimI ?? 5);
  rimLight.position.set(4, 2, -4);
  const accentLight = new THREE.DirectionalLight(accent, opts.accI ?? 2.2);
  accentLight.position.set(-5, 1, -3);
  scene.add(key, rimLight, accentLight, new THREE.AmbientLight('#2a3a5a', 0.6));

  renderer.render(scene, cam);
  const data = renderer.domElement.toDataURL('image/png');
  renderer.dispose();
  pmrem.dispose();
  return data;
};
window.sceneReady = true;
