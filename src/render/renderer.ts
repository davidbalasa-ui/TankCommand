import * as THREE from 'three';
import { AssetLoader } from '../assets/loader';
import type { AssetRegistry } from '../assets/registry';
import { createThreeDecoders } from '../assets/threeDecoders';
import { heightAt, slopeAt } from '../sim/map';
import { MAX_SLOPE, TANK_LENGTH } from '../sim/tuning';
import type { UnitState, WorldState } from '../sim/types';
import { RtsCamera, type CameraInfo } from './camera';
import {
  QualityController,
  qualityStep,
  qualityViewFor,
  type QualityView,
} from './quality';

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
const TURRET_PIVOT_X = -0.3;
const UNIT_PICK_HEIGHT = 1.2;
const CAMERA_FOV_DEG = 48;
const SKIRT_DEPTH = 10;
const SKY_ZENITH = '#16233a';
const SKY_MID = '#4d6b8c';
const SKY_HORIZON = '#b9a98d';
const SKIRT_COLOR = 0x3c4234;
const FAR_COLOR = 0x2f3529;
const SHADOW_MAP_SIZE = 1024;
/**
 * A gap this large between two rendered frames means frames stopped (tab hidden,
 * simulation paused, page navigated away), not that a frame was slow. Feeding it
 * to the quality controller would degrade quality for a reason that has nothing
 * to do with rendering cost.
 */
const MAX_FRAME_SAMPLE_MS = 2000;

const ENEMY_TINT = new THREE.Color(1, 0.35, 0.35);

export interface RenderStats {
  loadedModels: string[];
  meshCount: number;
  drawCalls: number;
  frame: number;
  units: number;
}

export interface ScreenBounds {
  x: number;
  y: number;
  width: number;
  height: number;
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

/**
 * World-space bounds of the meshes under `root` that are actually drawn.
 *
 * The PoC glb ships with a 200x200 ground `Plane` used by its render setup, and
 * `Box3.setFromObject` walks *every* child — including ones with
 * `visible === false`. Measuring that plane made the model's footprint 200
 * units instead of ~4, which collapsed the scale factor and drew the tanks as a
 * couple of pixels inside their selection rings; the same inflated box also made
 * `unitScreenBounds` report a huge rectangle, so a screen-size check could pass
 * without ever looking at the tank itself. Measuring each visible mesh with
 * `Box3.setFromObject` and unioning the results keeps both numbers honest.
 */
function unitBounds(root: THREE.Object3D): THREE.Box3 {
  root.updateMatrixWorld(true);
  const bounds = new THREE.Box3();
  const meshBounds = new THREE.Box3();
  root.traverseVisible((object) => {
    if (!(object instanceof THREE.Mesh)) {
      return;
    }
    meshBounds.setFromObject(object);
    if (!meshBounds.isEmpty()) {
      bounds.union(meshBounds);
    }
  });
  return bounds;
}

function tintMaterial(
  material: THREE.Material,
  tint: THREE.Color | null,
  darken: boolean,
): void {
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

function createFallbackTank(): THREE.Group {
  const group = new THREE.Group();
  const hull = new THREE.Mesh(
    new THREE.BoxGeometry(TANK_LENGTH, 1.1, 2.4),
    new THREE.MeshStandardMaterial({ color: 0x5a7d3a, roughness: 0.9 }),
  );
  hull.position.y = 0.55;
  const turret = new THREE.Mesh(
    new THREE.BoxGeometry(1.8, 0.7, 1.4),
    new THREE.MeshStandardMaterial({ color: 0x46632e, roughness: 0.9 }),
  );
  turret.position.set(0, 1.4, 0);
  const pivot = new THREE.Object3D();
  pivot.name = 'TurretPivot';
  pivot.position.set(TURRET_PIVOT_X, 0, 0);
  pivot.add(turret);
  group.add(hull);
  group.add(pivot);
  return group;
}

export function createRenderer(canvas: HTMLCanvasElement): THREE.WebGLRenderer {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
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
  private readonly qualityController = new QualityController();
  private terrain: THREE.Mesh | null = null;
  private skirt: THREE.Mesh | null = null;
  private farPlane: THREE.Mesh | null = null;
  private pickTargets: THREE.Object3D[] = [];
  private skyTexture: THREE.Texture | null = null;
  private templateRoot: THREE.Group | null = null;
  private directional: THREE.DirectionalLight;
  private lightTarget: THREE.Object3D;
  private marker: THREE.Mesh | null = null;
  private markerTtl = 0;
  private world: WorldState;
  private lastTick = -1;
  private lastRenderAt = 0;
  private basePixelRatio = 1;
  private shadowsEnabled = true;
  private frame = 0;
  private disposed = false;

  constructor(canvas: HTMLCanvasElement, registry: AssetRegistry, world: WorldState) {
    this.world = world;
    this.renderer = createRenderer(canvas);
    this.basePixelRatio = Math.min(globalThis.devicePixelRatio || 1, 2);
    this.renderer.setPixelRatio(this.basePixelRatio);
    this.camera = new THREE.PerspectiveCamera(CAMERA_FOV_DEG, 1, 0.1, 4000);
    this.rtsCamera = new RtsCamera(world.map.size);
    const ownUnits = world.units.filter((unit) => unit.owner === 1);
    if (ownUnits.length > 0) {
      const centerX = ownUnits.reduce((sum, unit) => sum + unit.x, 0) / ownUnits.length;
      const centerZ = ownUnits.reduce((sum, unit) => sum + unit.z, 0) / ownUnits.length;
      this.rtsCamera.setTarget(centerX, centerZ);
    } else {
      this.rtsCamera.setTarget(0, 0);
    }

    this.directional = new THREE.DirectionalLight(0xfff3d6, 2.8);
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

  /** Current dynamic quality settings. Read-only. */
  quality(): QualityView {
    return qualityViewFor(this.qualityController.level, this.basePixelRatio);
  }

  applyCamera(): void {
    const position = this.rtsCamera.position((x, z) => heightAt(this.world.map, x, z));
    this.camera.position.set(position.x, position.y, position.z);
    const targetY = heightAt(this.world.map, this.rtsCamera.targetX, this.rtsCamera.targetZ) + 1;
    this.camera.lookAt(this.rtsCamera.targetX, targetY, this.rtsCamera.targetZ);
    this.camera.updateMatrixWorld();
  }

  /**
   * Raycasts the rendered terrain *and* the ground skirt that wraps the map, so
   * a right-click on any visible ground issues an order. Points outside the map
   * are clamped into it by the simulation.
   */
  pickGround(clientX: number, clientY: number): { x: number; z: number } | null {
    if (this.pickTargets.length === 0) {
      return null;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
      -((clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1,
    );
    this.raycaster.setFromCamera(ndc, this.camera);
    const hits = this.raycaster.intersectObjects(this.pickTargets, false);
    const first = hits[0];
    if (!first) {
      return null;
    }
    return { x: first.point.x, z: first.point.z };
  }

  /**
   * Canvas-space position of a unit's picking centre: the same projection
   * `pickUnit` compares against the pick radius, and the point a caller has to
   * click to be guaranteed within the radius. Read-only; does not perform a
   * pick itself.
   */
  unitScreenCentre(id: number): { x: number; y: number } | null {
    const unit = this.world.units.find((item) => item.id === id);
    if (!unit) {
      return null;
    }
    return this.projectPoint(
      unit.x,
      heightAt(this.world.map, unit.x, unit.z) + UNIT_PICK_HEIGHT,
      unit.z,
    );
  }

  /** Canvas-space bounding box of a unit's *visible* rendered model. */
  unitScreenBounds(id: number): ScreenBounds | null {
    const visual = this.unitRoots.get(id);
    if (!visual) {
      return null;
    }
    this.camera.updateMatrixWorld();
    const box = unitBounds(visual.root);
    if (box.isEmpty()) {
      return null;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    for (let corner = 0; corner < 8; corner += 1) {
      const point = new THREE.Vector3(
        (corner & 1) === 1 ? box.max.x : box.min.x,
        (corner & 2) === 2 ? box.max.y : box.min.y,
        (corner & 4) === 4 ? box.max.z : box.min.z,
      );
      point.project(this.camera);
      const x = rect.left + (point.x * 0.5 + 0.5) * rect.width;
      const y = rect.top + (-point.y * 0.5 + 0.5) * rect.height;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
    if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
      return null;
    }
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
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
        heightAt(this.world.map, unit.x, unit.z) + UNIT_PICK_HEIGHT,
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

  /**
   * Projection of the *rendered* terrain surface at (x, z).
   *
   * The drawn mesh is two triangles per cell, so its surface is piecewise linear
   * across the cell diagonal (a-c-b / b-c-d), whereas `heightAt` interpolates
   * bilinearly. Projecting with the bilinear height while picking against the
   * mesh leaves a systematic offset that grows on steep cells, which is exactly
   * the error ground picking must not have. Reproducing the mesh interpolation
   * here makes `worldToScreen` and the pick raycast exact inverses.
   */
  worldToScreen(x: number, z: number): { x: number; y: number } {
    const screen = this.projectPoint(x, this.surfaceHeightAt(x, z), z);
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
    this.updateQuality();
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
    this.skyTexture?.dispose();
    this.loader.release(TANK_ASSET_ID);
    this.renderer.dispose();
  }

  /**
   * Feeds the frame time to the quality controller and applies the result when
   * the level changes. Started from `render`, so it runs once per rendered frame
   * and measures exactly the cost this class is responsible for.
   */
  private updateQuality(): void {
    const now = performance.now();
    const previous = this.lastRenderAt;
    this.lastRenderAt = now;
    if (previous === 0) {
      return;
    }
    const frameMs = now - previous;
    if (frameMs <= 0 || frameMs > MAX_FRAME_SAMPLE_MS) {
      // Frames stopped rather than running slowly; not a rendering-cost signal.
      return;
    }
    if (this.qualityController.sample(frameMs)) {
      this.applyQuality();
    }
  }

  private applyQuality(): void {
    const level = this.qualityController.level;
    const view = qualityViewFor(level, this.basePixelRatio);
    const step = qualityStep(level);

    this.renderer.setPixelRatio(view.pixelRatio);

    const shadowsChanged = view.shadows !== this.shadowsEnabled;
    this.shadowsEnabled = view.shadows;
    this.renderer.shadowMap.enabled = view.shadows;
    this.directional.castShadow = view.shadows;

    if (view.shadows) {
      const size = Math.max(256, Math.round(SHADOW_MAP_SIZE * step.shadowMapScale));
      this.directional.shadow.mapSize.set(size, size);
      const map = this.directional.shadow.map;
      if (map) {
        // Force three to allocate a target of the new size on the next render.
        map.dispose();
        this.directional.shadow.map = null;
      }
    }

    if (shadowsChanged) {
      // Toggling shadow rendering changes the shader program, so every material
      // that can receive or cast a shadow has to be recompiled once.
      this.renderer.shadowMap.needsUpdate = true;
      this.scene.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) {
          return;
        }
        const host: MaterialHost = object;
        const materials = Array.isArray(host.material) ? host.material : [host.material];
        for (const material of materials) {
          material.needsUpdate = true;
        }
      });
    }
  }

  private surfaceHeightAt(x: number, z: number): number {
    const map = this.world.map;
    const half = map.size / 2;
    const gx = clamp((x + half) / map.cellSize, 0, map.cols - 0.000001);
    const gz = clamp((z + half) / map.cellSize, 0, map.rows - 0.000001);
    const ix = Math.min(map.cols - 1, Math.floor(gx));
    const iz = Math.min(map.rows - 1, Math.floor(gz));
    const u = gx - ix;
    const v = gz - iz;
    const stride = map.cols + 1;
    const h00 = map.heights[iz * stride + ix] ?? 0;
    const h10 = map.heights[iz * stride + ix + 1] ?? 0;
    const h01 = map.heights[(iz + 1) * stride + ix] ?? 0;
    const h11 = map.heights[(iz + 1) * stride + ix + 1] ?? 0;
    if (u + v <= 1) {
      return h00 + (h10 - h00) * u + (h01 - h00) * v;
    }
    return h11 + (h01 - h11) * (1 - u) + (h10 - h11) * (1 - v);
  }

  private buildScene(): void {
    this.skyTexture = this.buildSky();
    this.scene.background = this.skyTexture;

    const hemisphere = new THREE.HemisphereLight(0xd2e6ff, 0x3b3524, 0.55);
    this.scene.add(hemisphere);

    this.directional.castShadow = true;
    this.directional.shadow.mapSize.set(SHADOW_MAP_SIZE, SHADOW_MAP_SIZE);
    this.directional.shadow.bias = -0.0008;
    this.directional.shadow.normalBias = 0.6;
    this.directional.shadow.camera.left = -30;
    this.directional.shadow.camera.right = 30;
    this.directional.shadow.camera.top = 30;
    this.directional.shadow.camera.bottom = -30;
    this.directional.shadow.camera.near = 1;
    this.directional.shadow.camera.far = 240;
    this.scene.add(this.directional);
    this.scene.add(this.lightTarget);
    this.directional.target = this.lightTarget;

    this.terrain = this.buildTerrain();
    this.scene.add(this.terrain);
    this.skirt = this.buildSkirt();
    if (this.skirt) {
      this.scene.add(this.skirt);
    }
    this.farPlane = this.buildFarPlane();
    if (this.farPlane) {
      this.scene.add(this.farPlane);
    }
    this.scene.add(this.buildBorder());

    this.pickTargets = [this.terrain, this.skirt, this.farPlane].filter(
      (mesh): mesh is THREE.Mesh => mesh !== null,
    );
  }

  /** Vertical sky gradient so the screen never shows a flat void above or below. */
  private buildSky(): THREE.Texture {
    const canvas = document.createElement('canvas');
    canvas.width = 4;
    canvas.height = 256;
    const context = canvas.getContext('2d');
    if (context) {
      const gradient = context.createLinearGradient(0, 0, 0, canvas.height);
      gradient.addColorStop(0, SKY_ZENITH);
      gradient.addColorStop(0.55, SKY_MID);
      gradient.addColorStop(1, SKY_HORIZON);
      context.fillStyle = gradient;
      context.fillRect(0, 0, canvas.width, canvas.height);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    return texture;
  }

  private mapFloor(): number {
    const heights = this.world.map.heights;
    let minHeight = Number.POSITIVE_INFINITY;
    for (let index = 0; index < heights.length; index += 1) {
      const value = heights[index] ?? 0;
      if (value < minHeight) {
        minHeight = value;
      }
    }
    return (Number.isFinite(minHeight) ? minHeight : 0) - SKIRT_DEPTH;
  }

  /** Vertical curtain around the map edge so the terrain never meets a void. */
  private buildSkirt(): THREE.Mesh | null {
    const map = this.world.map;
    const half = map.size / 2;
    const stride = map.cols + 1;
    const floor = this.mapFloor();

    const read = (ix: number, iz: number): { x: number; y: number; z: number } => ({
      x: -half + ix * map.cellSize,
      y: map.heights[iz * stride + ix] ?? 0,
      z: -half + iz * map.cellSize,
    });

    const loop: Array<{ x: number; y: number; z: number }> = [];
    for (let ix = 0; ix <= map.cols; ix += 1) {
      loop.push(read(ix, 0));
    }
    for (let iz = 1; iz <= map.rows; iz += 1) {
      loop.push(read(map.cols, iz));
    }
    for (let ix = map.cols - 1; ix >= 0; ix -= 1) {
      loop.push(read(ix, map.rows));
    }
    for (let iz = map.rows - 1; iz >= 1; iz -= 1) {
      loop.push(read(0, iz));
    }
    if (loop.length < 2) {
      return null;
    }

    const positions: number[] = [];
    for (let index = 0; index < loop.length; index += 1) {
      const a = loop[index];
      const b = loop[(index + 1) % loop.length];
      if (!a || !b) {
        continue;
      }
      positions.push(a.x, a.y, a.z, a.x, floor, a.z, b.x, b.y, b.z);
      positions.push(b.x, b.y, b.z, a.x, floor, a.z, b.x, floor, b.z);
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({
      color: SKIRT_COLOR,
      roughness: 1,
      metalness: 0,
      side: THREE.DoubleSide,
    });
    return new THREE.Mesh(geometry, material);
  }

  private buildFarPlane(): THREE.Mesh {
    const map = this.world.map;
    const geometry = new THREE.PlaneGeometry(map.size * 12, map.size * 12);
    const material = new THREE.MeshStandardMaterial({
      color: FAR_COLOR,
      roughness: 1,
      metalness: 0,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = this.mapFloor() - 0.05;
    return mesh;
  }

  private buildTerrain(): THREE.Mesh {
    const map = this.world.map;
    const stride = map.cols + 1;
    const vertexCount = stride * (map.rows + 1);
    const positions = new Float32Array(vertexCount * 3);
    const colors = new Float32Array(vertexCount * 3);
    const half = map.size / 2;

    let minHeight = Number.POSITIVE_INFINITY;
    let maxHeight = Number.NEGATIVE_INFINITY;
    for (let index = 0; index < map.heights.length; index += 1) {
      const value = map.heights[index] ?? 0;
      if (value < minHeight) {
        minHeight = value;
      }
      if (value > maxHeight) {
        maxHeight = value;
      }
    }
    const heightSpan = Math.max(0.001, maxHeight - minHeight);

    const valley = new THREE.Color(0x4c6b33);
    const meadow = new THREE.Color(0x82904c);
    const tan = new THREE.Color(0xb79b69);
    const rock = new THREE.Color(0x93938f);
    const blockedRock = new THREE.Color(0x2a2a29);

    for (let iz = 0; iz <= map.rows; iz += 1) {
      const z = -half + iz * map.cellSize;
      for (let ix = 0; ix <= map.cols; ix += 1) {
        const x = -half + ix * map.cellSize;
        const index = iz * stride + ix;
        const y = heightAt(map, x, z);
        positions[index * 3] = x;
        positions[index * 3 + 1] = y;
        positions[index * 3 + 2] = z;

        const heightNorm = clamp((y - minHeight) / heightSpan, 0, 1);
        const slope = slopeAt(map, x, z);
        const slopeNorm = clamp(slope / MAX_SLOPE, 0, 1);
        const color = valley.clone().lerp(meadow, clamp(heightNorm * 2.2, 0, 1));
        color.lerp(tan, slopeNorm * 0.8);
        color.lerp(rock, clamp((heightNorm - 0.45) / 0.55, 0, 1) * 0.85);
        if (slope > MAX_SLOPE) {
          color.lerp(blockedRock, 0.82);
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
      flatShading: true,
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
    const material = new THREE.LineBasicMaterial({ color: 0xdfe8f5 });
    return new THREE.LineLoop(geometry, material);
  }

  private updateLight(): void {
    const targetX = this.rtsCamera.targetX;
    const targetZ = this.rtsCamera.targetZ;
    const targetY = heightAt(this.world.map, targetX, targetZ);
    this.lightTarget.position.set(targetX, targetY, targetZ);
    this.directional.position.set(targetX + 42, targetY + 60, targetZ + 26);
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
    // The PoC glb contains a 200x200 ground plane used by its render setup. It
    // must not render and must not contribute to the measured bounds: leaving it
    // in the graph made the measured footprint 200 units instead of ~4, which
    // collapsed the scale factor and drew tanks as a few pixels.
    const plane = model.getObjectByName('Plane');
    if (plane) {
      plane.visible = false;
      plane.removeFromParent();
    }

    model.updateMatrixWorld(true);
    const pivot = new THREE.Object3D();
    pivot.name = 'TurretPivot';
    pivot.position.set(TURRET_PIVOT_X, 0, 0);
    model.add(pivot);
    model.updateMatrixWorld(true);
    for (const name of TURRET_NODES) {
      const node = model.getObjectByName(name);
      if (node && node !== pivot) {
        pivot.attach(node);
      }
    }
    model.updateMatrixWorld(true);

    const bounds = unitBounds(model);
    if (!bounds.isEmpty()) {
      const size = new THREE.Vector3();
      bounds.getSize(size);
      const footprint = Math.max(size.x, size.z, 0.0001);
      model.scale.multiplyScalar(TANK_LENGTH / footprint);
      model.updateMatrixWorld(true);

      const scaledBounds = unitBounds(model);
      const centre = new THREE.Vector3();
      scaledBounds.getCenter(centre);
      model.position.x -= centre.x;
      model.position.z -= centre.z;
      model.position.y -= scaledBounds.min.y;
    }

    const root = new THREE.Group();
    root.add(model);
    root.updateMatrixWorld(true);
    return root;
  }

  private prepareFallback(): THREE.Group {
    const root = new THREE.Group();
    root.add(createFallbackTank());
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
    } else {
      root = this.prepareFallback();
    }
    cloneMaterials(root, unit.owner === 2);
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
        const geometry = new THREE.RingGeometry(2.6, 3.0, 32);
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
