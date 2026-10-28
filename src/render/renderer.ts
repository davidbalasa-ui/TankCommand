import * as THREE from 'three';
import { AssetLoader } from '../assets/loader';
import type { AssetRegistry } from '../assets/registry';
import { createThreeDecoders, fallbackModel } from '../assets/threeDecoders';
import { heightAt, slopeAt } from '../sim/map';
import { MAX_SLOPE, UNIT_RADIUS } from '../sim/tuning';
import type { UnitState, WorldState } from '../sim/types';
import { RtsCamera, type CameraInfo } from './camera';

const TANK_ASSET_ID = 'unit.human.poc_tank';
const TURRET_NODES = [
  'Turret',
  'Mantlet',
  'Barrel',
  'Brake',
  'Hatch',
  'Sensor',
  'Lens',
  'Rack',
  'Antenna',
];

const ENEMY_TINT = new THREE.Color(1, 0.35, 0.35);

export interface RenderStats {
  loadedModels: string[];
  meshCount: number;
  drawCalls: number;
  frame: number;
  units: number;
}

/**
 * `Mesh`'s `material` property is declared as the generic type parameter
 * `TMaterial`. Narrowing a type parameter with `Array.isArray` does not filter
 * the union — it yields `TMaterial & any[]`, whose element type is `any`, which
 * turns every material access into an unsafe-any lint error. Reading and
 * writing the property through this concrete slot keeps the element type exact.
 */
interface MaterialHost {
  material: THREE.Material | THREE.Material[];
}

interface UnitVisual {
  root: THREE.Object3D;
  turretPivot: THREE.Object3D | null;
  owner: number;
}

interface PositionSnapshot {
  x: number;
  z: number;
  heading: number;
  turretHeading: number;
}

interface Flash {
  mesh: THREE.Mesh;
  ttl: number;
}

interface HealthBar {
  outer: HTMLDivElement;
  fill: HTMLDivElement;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function tintMaterial(
  material: THREE.Material,
  tint: THREE.Color | null,
  darken: boolean,
): void {
  // `'color' in material` narrows the property to `unknown`, so the check is
  // type-safe without asserting a concrete material subclass.
  if (!('color' in material)) {
    return;
  }
  const color: unknown = material.color;
  if (!(color instanceof THREE.Color)) {
    return;
  }
  if (tint) {
    color.multiply(tint);
  }
  if (darken) {
    color.multiplyScalar(0.25);
  }
}

function cloneWithTint(
  material: THREE.Material,
  tint: THREE.Color | null,
  darken: boolean,
): THREE.Material {
  const clone: THREE.Material = material.clone();
  tintMaterial(clone, tint, darken);
  return clone;
}

function remapMeshMaterials(
  root: THREE.Object3D,
  mapMaterial: (material: THREE.Material) => THREE.Material,
): void {
  root.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) {
      return;
    }
    const host: MaterialHost = object;
    const source = host.material;
    if (Array.isArray(source)) {
      host.material = source.map((material) => mapMaterial(material));
    } else {
      host.material = mapMaterial(source);
    }
  });
}

function cloneMaterials(root: THREE.Object3D, enemy: boolean): void {
  remapMeshMaterials(root, (material) =>
    cloneWithTint(material, enemy ? ENEMY_TINT : null, false),
  );
}

function darkenMaterials(root: THREE.Object3D): void {
  remapMeshMaterials(root, (material) => cloneWithTint(material, null, true));
}

export function createRenderer(canvas: HTMLCanvasElement): THREE.WebGLRenderer {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  return renderer;
}

export class RenderView {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera: THREE.PerspectiveCamera;
  private readonly rtsCamera: RtsCamera;
  private readonly observer: ResizeObserver;
  private readonly loader: AssetLoader<THREE.Object3D, THREE.Texture, ArrayBuffer>;
  private readonly loadedModels: string[] = [];
  private readonly raycaster = new THREE.Raycaster();
  private readonly overlay: HTMLDivElement;
  private readonly healthBars = new Map<number, HealthBar>();
  private readonly unitRoots = new Map<number, UnitVisual>();
  private readonly selectionRings = new Map<number, THREE.Mesh>();
  private readonly projectileMeshes = new Map<number, THREE.Mesh>();
  private readonly projectilePositions = new Map<number, { x: number; y: number; z: number }>();
  private readonly flashes: Flash[] = [];
  private readonly wrecksGroup = new THREE.Group();
  private readonly wreckMeshes: THREE.Object3D[] = [];
  private readonly selection: number[] = [];
  private readonly previousSnapshots = new Map<number, PositionSnapshot>();
  private readonly currentSnapshots = new Map<number, PositionSnapshot>();
  private terrain: THREE.Mesh | null = null;
  private templateRoot: THREE.Group | null = null;
  private directional: THREE.DirectionalLight;
  private lightTarget: THREE.Object3D;
  private marker: THREE.Mesh | null = null;
  private markerTtl = 0;
  private world: WorldState;
  private lastTick = -1;
  private frame = 0;
  private disposed = false;

  constructor(canvas: HTMLCanvasElement, registry: AssetRegistry, world: WorldState) {
    this.world = world;
    this.renderer = createRenderer(canvas);
    this.camera = new THREE.PerspectiveCamera(55, 1, 0.1, 1000);
    this.rtsCamera = new RtsCamera(world.map.size);
    const firstOwn = world.units.find((unit) => unit.owner === 1);
    if (firstOwn) {
      this.rtsCamera.setTarget(firstOwn.x, firstOwn.z);
    } else {
      this.rtsCamera.setTarget(0, 0);
    }

    this.scene.background = new THREE.Color('#090D16');
    this.directional = new THREE.DirectionalLight(0xffffff, 2.2);
    this.lightTarget = new THREE.Object3D();
    this.buildScene();

    this.overlay = document.createElement('div');
    this.overlay.className = 'hud-overlay';
    canvas.parentElement?.append(this.overlay);

    this.observer = new ResizeObserver(() => {
      this.resize(canvas);
    });
    this.observer.observe(canvas);
    this.resize(canvas);

    const baseUrl = new URL('.', document.baseURI).toString();
    this.loader = new AssetLoader<THREE.Object3D, THREE.Texture, ArrayBuffer>({
      registry,
      baseUrl,
      decoders: createThreeDecoders(),
      fetchBytes: async (url) => {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} for ${url}`);
        }
        return response.arrayBuffer();
      },
    });

    this.scene.add(this.wrecksGroup);
    void this.loadTemplate();
  }

  getCamera(): RtsCamera {
    return this.rtsCamera;
  }

  setSelection(ids: number[]): void {
    this.selection.length = 0;
    for (const id of ids) {
      if (!this.selection.includes(id)) {
        this.selection.push(id);
      }
    }
  }

  setCamera(info: Partial<CameraInfo>): void {
    if (typeof info.targetX === 'number') {
      this.rtsCamera.targetX = info.targetX;
    }
    if (typeof info.targetZ === 'number') {
      this.rtsCamera.targetZ = info.targetZ;
    }
    if (typeof info.distance === 'number') {
      this.rtsCamera.setDistance(info.distance);
    }
    if (typeof info.yaw === 'number') {
      this.rtsCamera.yaw = info.yaw;
    }
    this.rtsCamera.clampTarget();
    this.applyCamera();
  }

  cameraInfo(): CameraInfo {
    return this.rtsCamera.info();
  }

  applyCamera(): void {
    const position = this.rtsCamera.position((x, z) => heightAt(this.world.map, x, z));
    this.camera.position.set(position.x, position.y, position.z);
    const targetY = heightAt(this.world.map, this.rtsCamera.targetX, this.rtsCamera.targetZ) + 1;
    this.camera.lookAt(this.rtsCamera.targetX, targetY, this.rtsCamera.targetZ);
    this.camera.updateMatrixWorld();
  }

  pickGround(clientX: number, clientY: number): { x: number; z: number } | null {
    if (!this.terrain) {
      return null;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
      -((clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    const hits = this.raycaster.intersectObject(this.terrain, false);
    const first = hits[0];
    if (!first) {
      return null;
    }
    return { x: first.point.x, z: first.point.z };
  }

  pickUnit(
    clientX: number,
    clientY: number,
    preferOwn: boolean,
    touch: boolean,
  ): number | null {
    const radius = touch ? 36 : 24;
    const candidates: Array<{ id: number; owner: number; distance: number }> = [];
    for (const unit of this.world.units) {
      const screen = this.projectPoint(
        unit.x,
        heightAt(this.world.map, unit.x, unit.z) + 1.2,
        unit.z,
      );
      if (!screen) {
        continue;
      }
      const distance = Math.hypot(screen.x - clientX, screen.y - clientY);
      if (distance <= radius) {
        candidates.push({ id: unit.id, owner: unit.owner, distance });
      }
    }
    if (candidates.length === 0) {
      return null;
    }
    let pool = candidates;
    if (preferOwn) {
      const own = candidates.filter((candidate) => candidate.owner === 1);
      if (own.length > 0) {
        pool = own;
      }
    } else {
      const enemy = candidates.filter((candidate) => candidate.owner !== 1);
      if (enemy.length > 0) {
        pool = enemy;
      }
    }
    pool.sort((a, b) => a.distance - b.distance);
    return pool[0]?.id ?? null;
  }

  worldToScreen(x: number, z: number): { x: number; y: number } {
    const screen = this.projectPoint(x, heightAt(this.world.map, x, z) + 0.1, z);
    return screen ?? { x: 0, y: 0 };
  }

  pulseMarker(x: number, z: number): void {
    if (!this.marker) {
      const geometry = new THREE.RingGeometry(1.4, 1.9, 32);
      const material = new THREE.MeshBasicMaterial({
        color: 0x8fd3ff,
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
      });
      this.marker = new THREE.Mesh(geometry, material);
      this.marker.rotation.x = -Math.PI / 2;
      this.scene.add(this.marker);
    }
    this.marker.position.set(x, heightAt(this.world.map, x, z) + 0.08, z);
    this.marker.scale.setScalar(1);
    this.markerTtl = 1;
    const material = this.marker.material;
    if (material instanceof THREE.MeshBasicMaterial) {
      material.opacity = 0.9;
    }
  }

  render(alpha: number, world: WorldState): void {
    this.world = world;
    this.updateSnapshots(world);
    this.applyCamera();
    this.updateLight();
    this.syncUnits(alpha);
    this.syncProjectiles();
    this.syncWrecks();
    this.syncSelection();
    this.syncHealthBars();
    this.updateMarker();
    this.updateFlashes();
    this.frame += 1;
    this.renderer.render(this.scene, this.camera);
  }

  stats(): RenderStats {
    let meshCount = 0;
    this.scene.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        meshCount += 1;
      }
    });
    return {
      loadedModels: [...this.loadedModels],
      meshCount,
      drawCalls: this.renderer.info.render.calls,
      frame: this.frame,
      units: this.unitRoots.size,
    };
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.observer.disconnect();
    this.overlay.remove();
    this.loader.release(TANK_ASSET_ID);
    this.renderer.dispose();
  }

  private buildScene(): void {
    const hemisphere = new THREE.HemisphereLight(0xffffff, 0x223322, 1.2);
    this.scene.add(hemisphere);

    this.directional.castShadow = true;
    this.directional.shadow.mapSize.set(1024, 1024);
    this.directional.shadow.camera.left = -30;
    this.directional.shadow.camera.right = 30;
    this.directional.shadow.camera.top = 30;
    this.directional.shadow.camera.bottom = -30;
    this.directional.shadow.camera.near = 1;
    this.directional.shadow.camera.far = 180;
    this.scene.add(this.directional);
    this.scene.add(this.lightTarget);
    this.directional.target = this.lightTarget;

    this.terrain = this.buildTerrain();
    this.scene.add(this.terrain);
    this.scene.add(this.buildBorder());
  }

  private buildTerrain(): THREE.Mesh {
    const map = this.world.map;
    const stride = map.cols + 1;
    const vertexCount = stride * (map.rows + 1);
    const positions = new Float32Array(vertexCount * 3);
    const colors = new Float32Array(vertexCount * 3);
    const low = new THREE.Color(0x6b6b3a);
    const high = new THREE.Color(0x8a8a8a);
    const rock = new THREE.Color(0x3a3a3a);
    const half = map.size / 2;

    for (let iz = 0; iz <= map.rows; iz += 1) {
      const z = -half + iz * map.cellSize;
      for (let ix = 0; ix <= map.cols; ix += 1) {
        const x = -half + ix * map.cellSize;
        const index = iz * stride + ix;
        const y = heightAt(map, x, z);
        positions[index * 3] = x;
        positions[index * 3 + 1] = y;
        positions[index * 3 + 2] = z;

        const heightT = clamp((y + 4) / 12, 0, 1);
        const color = low.clone().lerp(high, heightT);
        const slope = slopeAt(map, x, z);
        color.lerp(rock, clamp(slope / (MAX_SLOPE * 0.85), 0, 1));
        if (slope > MAX_SLOPE) {
          color.multiplyScalar(0.55);
        }
        colors[index * 3] = color.r;
        colors[index * 3 + 1] = color.g;
        colors[index * 3 + 2] = color.b;
      }
    }

    const indices: number[] = [];
    for (let iz = 0; iz < map.rows; iz += 1) {
      for (let ix = 0; ix < map.cols; ix += 1) {
        const a = iz * stride + ix;
        const b = a + 1;
        const c = a + stride;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 1,
      metalness: 0,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.receiveShadow = true;
    return mesh;
  }

  private buildBorder(): THREE.LineLoop {
    const map = this.world.map;
    const half = map.size / 2;
    const points = [
      new THREE.Vector3(-half, heightAt(map, -half, -half) + 0.25, -half),
      new THREE.Vector3(half, heightAt(map, half, -half) + 0.25, -half),
      new THREE.Vector3(half, heightAt(map, half, half) + 0.25, half),
      new THREE.Vector3(-half, heightAt(map, -half, half) + 0.25, half),
    ];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({ color: 0x9fb6d6 });
    return new THREE.LineLoop(geometry, material);
  }

  private updateLight(): void {
    const targetX = this.rtsCamera.targetX;
    const targetZ = this.rtsCamera.targetZ;
    const targetY = heightAt(this.world.map, targetX, targetZ);
    this.lightTarget.position.set(targetX, targetY, targetZ);
    this.directional.position.set(targetX + 30, targetY + 50, targetZ + 20);
    this.directional.shadow.camera.left = -30;
    this.directional.shadow.camera.right = 30;
    this.directional.shadow.camera.top = 30;
    this.directional.shadow.camera.bottom = -30;
    this.directional.shadow.camera.updateProjectionMatrix();
  }

  private resize(canvas: HTMLCanvasElement): void {
    const width = Math.max(1, canvas.clientWidth);
    const height = Math.max(1, canvas.clientHeight);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.applyCamera();
  }

  private projectPoint(x: number, y: number, z: number): { x: number; y: number } | null {
    const vector = new THREE.Vector3(x, y, z).project(this.camera);
    if (vector.z < -1 || vector.z > 1) {
      return null;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    return {
      x: rect.left + (vector.x * 0.5 + 0.5) * rect.width,
      y: rect.top + (-vector.y * 0.5 + 0.5) * rect.height,
    };
  }

  private updateSnapshots(world: WorldState): void {
    if (world.tick === this.lastTick) {
      return;
    }
    this.previousSnapshots.clear();
    for (const [id, snapshot] of this.currentSnapshots) {
      this.previousSnapshots.set(id, { ...snapshot });
    }
    this.currentSnapshots.clear();
    for (const unit of world.units) {
      this.currentSnapshots.set(unit.id, {
        x: unit.x,
        z: unit.z,
        heading: unit.heading,
        turretHeading: unit.turretHeading,
      });
    }
    this.lastTick = world.tick;
  }

  private async loadTemplate(): Promise<void> {
    try {
      const asset = await this.loader.load(TANK_ASSET_ID);
      if (this.disposed) {
        return;
      }
      if (asset instanceof THREE.Object3D) {
        this.templateRoot = this.prepareTemplate(asset);
        this.loadedModels.push(TANK_ASSET_ID);
        this.rebuildUnitVisuals();
      } else {
        this.templateRoot = this.prepareFallback();
        this.rebuildUnitVisuals();
      }
    } catch {
      if (!this.disposed) {
        this.templateRoot = this.prepareFallback();
        this.rebuildUnitVisuals();
      }
    }
  }

  private prepareTemplate(model: THREE.Object3D): THREE.Group {
    const plane = model.getObjectByName('Plane');
    if (plane) {
      plane.visible = false;
    }

    model.updateMatrixWorld(true);
    const pivot = new THREE.Object3D();
    pivot.name = 'TurretPivot';
    pivot.position.set(-0.3, 0, 0);
    model.add(pivot);
    model.updateMatrixWorld(true);
    for (const name of TURRET_NODES) {
      const node = model.getObjectByName(name);
      if (node && node !== pivot) {
        pivot.attach(node);
      }
    }

    const box = new THREE.Box3().setFromObject(model);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDimension = Math.max(size.x, size.z, 0.001);
    const targetLength = UNIT_RADIUS * 2.8;
    const scale = targetLength / maxDimension;
    model.scale.setScalar(scale);
    model.updateMatrixWorld(true);

    const scaledBox = new THREE.Box3().setFromObject(model);
    const center = new THREE.Vector3();
    scaledBox.getCenter(center);
    model.position.x -= center.x;
    model.position.z -= center.z;
    model.position.y -= scaledBox.min.y;

    const root = new THREE.Group();
    root.add(model);
    return root;
  }

  private prepareFallback(): THREE.Group {
    const root = new THREE.Group();
    root.add(fallbackModel());
    return root;
  }

  private rebuildUnitVisuals(): void {
    for (const visual of this.unitRoots.values()) {
      this.scene.remove(visual.root);
    }
    this.unitRoots.clear();
    this.syncUnits(0);
  }

  private createUnitVisual(unit: UnitState): UnitVisual {
    let root: THREE.Object3D;
    if (this.templateRoot) {
      root = this.templateRoot.clone(true);
      cloneMaterials(root, unit.owner === 2);
    } else {
      root = new THREE.Group();
      const mesh = fallbackModel();
      root.add(mesh);
      cloneMaterials(root, unit.owner === 2);
    }
    root.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });
    this.scene.add(root);
    return {
      root,
      turretPivot: root.getObjectByName('TurretPivot') ?? null,
      owner: unit.owner,
    };
  }

  private syncUnits(alpha: number): void {
    const alive = new Set(this.world.units.map((unit) => unit.id));
    for (const [id, visual] of this.unitRoots) {
      if (!alive.has(id)) {
        this.scene.remove(visual.root);
        this.unitRoots.delete(id);
      }
    }

    for (const unit of this.world.units) {
      let visual = this.unitRoots.get(unit.id);
      if (!visual) {
        visual = this.createUnitVisual(unit);
        this.unitRoots.set(unit.id, visual);
      }
      const current = this.currentSnapshots.get(unit.id) ?? {
        x: unit.x,
        z: unit.z,
        heading: unit.heading,
        turretHeading: unit.turretHeading,
      };
      const previous = this.previousSnapshots.get(unit.id) ?? current;
      const x = lerp(previous.x, current.x, alpha);
      const z = lerp(previous.z, current.z, alpha);
      const heading = lerp(previous.heading, current.heading, alpha);
      const turretHeading = lerp(previous.turretHeading, current.turretHeading, alpha);
      visual.root.position.set(x, heightAt(this.world.map, x, z), z);
      visual.root.rotation.y = -heading;
      if (visual.turretPivot) {
        visual.turretPivot.rotation.y = heading - turretHeading;
      }
    }
  }

  private syncSelection(): void {
    const selected = new Set(this.selection);
    for (const [id, ring] of this.selectionRings) {
      if (!selected.has(id)) {
        this.scene.remove(ring);
        this.selectionRings.delete(id);
      }
    }
    for (const id of this.selection) {
      const unit = this.world.units.find((item) => item.id === id);
      if (!unit) {
        continue;
      }
      let ring = this.selectionRings.get(id);
      if (!ring) {
        const geometry = new THREE.RingGeometry(1.9, 2.2, 32);
        const material = new THREE.MeshBasicMaterial({
          color: 0x6cf58a,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.9,
        });
        ring = new THREE.Mesh(geometry, material);
        ring.rotation.x = -Math.PI / 2;
        this.scene.add(ring);
        this.selectionRings.set(id, ring);
      }
      ring.position.set(
        unit.x,
        heightAt(this.world.map, unit.x, unit.z) + 0.06,
        unit.z,
      );
    }
  }

  private syncHealthBars(): void {
    const alive = new Set<number>();
    for (const unit of this.world.units) {
      const type = this.world.unitTypes.get(unit.typeId);
      const maxHp = type?.hp ?? unit.hp;
      const selected = this.selection.includes(unit.id);
      if (!selected && unit.hp >= maxHp) {
        continue;
      }
      alive.add(unit.id);
      let bar = this.healthBars.get(unit.id);
      if (!bar) {
        const outer = document.createElement('div');
        outer.className = 'health-bar';
        const fill = document.createElement('div');
        fill.className = 'health-fill';
        outer.append(fill);
        this.overlay.append(outer);
        bar = { outer, fill };
        this.healthBars.set(unit.id, bar);
      }
      const screen = this.projectPoint(
        unit.x,
        heightAt(this.world.map, unit.x, unit.z) + 3.2,
        unit.z,
      );
      if (!screen) {
        bar.outer.style.display = 'none';
        continue;
      }
      bar.outer.style.display = 'block';
      bar.outer.style.left = `${screen.x}px`;
      bar.outer.style.top = `${screen.y}px`;
      const ratio = clamp(unit.hp / Math.max(1, maxHp), 0, 1);
      bar.fill.style.width = `${ratio * 100}%`;
      bar.fill.style.background =
        ratio > 0.55 ? '#5ee07a' : ratio > 0.25 ? '#f2c94c' : '#ff5c5c';
    }

    for (const [id, bar] of this.healthBars) {
      if (!alive.has(id)) {
        bar.outer.remove();
        this.healthBars.delete(id);
      }
    }
  }

  private syncProjectiles(): void {
    const ids = new Set(this.world.projectiles.map((projectile) => projectile.id));
    for (const [id, mesh] of this.projectileMeshes) {
      if (!ids.has(id)) {
        const position = this.projectilePositions.get(id);
        if (position) {
          this.createFlash(position.x, position.y, position.z);
        }
        this.scene.remove(mesh);
        this.projectileMeshes.delete(id);
        this.projectilePositions.delete(id);
      }
    }

    for (const projectile of this.world.projectiles) {
      let mesh = this.projectileMeshes.get(projectile.id);
      if (!mesh) {
        const geometry = new THREE.BoxGeometry(0.14, 0.14, 1.4);
        const material = new THREE.MeshBasicMaterial({ color: 0xfff2a0 });
        mesh = new THREE.Mesh(geometry, material);
        this.scene.add(mesh);
        this.projectileMeshes.set(projectile.id, mesh);
      }
      mesh.position.set(projectile.x, projectile.y, projectile.z);
      const direction = new THREE.Vector3(
        projectile.vx,
        projectile.vy,
        projectile.vz,
      ).normalize();
      if (direction.lengthSq() > 0.001) {
        const quaternion = new THREE.Quaternion().setFromUnitVectors(
          new THREE.Vector3(0, 0, 1),
          direction,
        );
        mesh.quaternion.copy(quaternion);
      }
      this.projectilePositions.set(projectile.id, {
        x: projectile.x,
        y: projectile.y,
        z: projectile.z,
      });
    }
  }

  private syncWrecks(): void {
    while (this.wreckMeshes.length < this.world.wrecks.length) {
      const source = this.templateRoot ?? this.prepareFallback();
      const root = source.clone(true);
      darkenMaterials(root);
      root.scale.y = 0.55;
      this.wrecksGroup.add(root);
      this.wreckMeshes.push(root);
    }
    while (this.wreckMeshes.length > this.world.wrecks.length) {
      const mesh = this.wreckMeshes.pop();
      if (mesh) {
        this.wrecksGroup.remove(mesh);
      }
    }
    for (let i = 0; i < this.world.wrecks.length; i += 1) {
      const wreck = this.world.wrecks[i];
      const mesh = this.wreckMeshes[i];
      if (!wreck || !mesh) {
        continue;
      }
      mesh.position.set(
        wreck.x,
        heightAt(this.world.map, wreck.x, wreck.z) - 0.25,
        wreck.z,
      );
    }
  }

  private createFlash(x: number, y: number, z: number): void {
    const geometry = new THREE.SphereGeometry(0.55, 8, 6);
    const material = new THREE.MeshBasicMaterial({
      color: 0xffc46b,
      transparent: true,
      opacity: 0.95,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    this.scene.add(mesh);
    this.flashes.push({ mesh, ttl: 0.18 });
  }

  private updateFlashes(): void {
    for (let i = this.flashes.length - 1; i >= 0; i -= 1) {
      const flash = this.flashes[i];
      if (!flash) {
        continue;
      }
      flash.ttl -= 1 / 60;
      const material = flash.mesh.material;
      if (material instanceof THREE.MeshBasicMaterial) {
        material.opacity = Math.max(0, flash.ttl / 0.18);
      }
      flash.mesh.scale.multiplyScalar(1.04);
      if (flash.ttl <= 0) {
        this.scene.remove(flash.mesh);
        this.flashes.splice(i, 1);
      }
    }
  }

  private updateMarker(): void {
    if (!this.marker || this.markerTtl <= 0) {
      return;
    }
    this.markerTtl -= 1 / 60;
    this.marker.scale.setScalar(1 + (1 - this.markerTtl) * 0.8);
    const material = this.marker.material;
    if (material instanceof THREE.MeshBasicMaterial) {
      material.opacity = Math.max(0, this.markerTtl * 0.9);
    }
    if (this.markerTtl <= 0) {
      this.scene.remove(this.marker);
      this.marker = null;
    }
  }
}
