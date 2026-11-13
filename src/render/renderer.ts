import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { UnitInstances, isInstancedPart, markInstanced } from './unitInstances';
import { Effects } from './effects';
import { WreckField } from './wrecks';
import { applyUnfold, readUnfold, type UnfoldData, type UnfoldStart } from './unfold';
import { AssetLoader } from '../assets/loader';
import { DEPOSIT_MODEL_IDS, Landscape, PROP_IDS } from './landscape';
import type { AssetRegistry } from '../assets/registry';
import { createThreeDecoders } from '../assets/threeDecoders';
import { heightAt, slopeAt } from '../sim/map';
import { CAMERA_FOV_DEG, MAX_SLOPE, ORE_CRATE_SIZE, ORE_MAX_CRATES, TANK_LENGTH, WRECK_TTL_SEC } from '../sim/tuning';
import { isAllied, isHostile } from '../sim/diplomacy';
import { damageState } from '../sim/structures';
import { crateOre } from '../sim/economy';
import { PAD_LAND_SEC, PAD_UNLOAD_SEC, padFacing, padLayout } from '../sim/pad';
import { SIM_TICK_HZ } from '../sim/constants';
import type { DropOrder, SimStructureType, StructureState, UnitState, WorldState } from '../sim/types';
import { RtsCamera, type CameraInfo } from './camera';
import { collectPartMotions, pivotIsSpinner, updatePartMotions, type PartMotion, type PartMotionState } from './partMotion';
import {
  QUALITY_LADDER,
  QualityController,
  qualityStep,
  qualityViewFor,
  type QualityView,
} from './quality';

const TANK_ASSET_ID = 'unit.human.poc_tank';
const TERRAIN_DETAIL_ID = 'texture.terrain.detail';
/** How long a newly deployed structure takes to unfold. */
const UNFOLD_MS = 1200;
/** Units further than this from the camera draw their low-detail model (metres). */
const LOD_DISTANCE = 60;
/** From this quality level (shadows off) every unit draws its low-detail model. */
const LOD_QUALITY_LEVEL = 2;
/** How long a packed tower takes to fold out into its structure. */
const TOWER_UNFOLD_MS = 1500;
/** Metres covered by one repeat of the ground detail texture. */
const DETAIL_TILE = 7;
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
const SKIRT_DEPTH = 10;
const SKY_ZENITH = '#16233a';
const SKY_MID = '#4d6b8c';
const SKY_HORIZON = '#b9a98d';
const SKIRT_COLOR = 0x3c4234;
const FAR_COLOR = 0x2f3529;
const SHADOW_MAP_SIZE = 1024;
const MAX_FRAME_SAMPLE_MS = 2000;

const ENEMY_TINT = new THREE.Color(1, 0.35, 0.35);
const COLORBLIND_ENEMY_TINT = new THREE.Color(0.35, 0.65, 1);
const ORDER_LINE_COLOR = 0x8fd3ff;
const ORDER_LINE_Y = 0.18;
const FRIENDLY_STRUCTURE_COLOR = 0x6b8f3a;
const ENEMY_STRUCTURE_COLOR = 0x8a3a3a;
const DROP_BEAM_COLOR = 0x9adfff;
const PLACEMENT_VALID_COLOR = 0x6cf58a;
const PLACEMENT_INVALID_COLOR = 0xff5c5c;

const QUALITY_PREFERENCE_LEVEL: Record<'low' | 'medium' | 'high', number> = {
  high: 0,
  medium: 2,
  low: QUALITY_LADDER.length - 1,
};

export interface RenderStats {
  loadedModels: string[];
  meshCount: number;
  drawCalls: number;
  triangles: number;
  frame: number;
  units: number;
  /** Units drawn with their low-detail model last frame. */
  lodUnits?: number;
  /** Burning wrecks on the field, and live effect particles. */
  wrecks?: number;
  effects?: number;
  /** Moving model parts in motion right now, by "<unit or structure type> <node name>". */
  movingParts?: string[];
}

export interface ScreenBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OrderPathInfo {
  unitId: number;
  points: number;
  queued: boolean;
}

interface MaterialHost {
  material: THREE.Material | THREE.Material[];
}

// Loose ore: a mound of jagged rock chunks, dark stone flecked with orange ore and a few bright
// nuggets, built once and shared. Unit size: about 2 wide and 0.9 high.
let oreHeapGeometry: THREE.BufferGeometry | null = null;
function buildOreHeapGeometry(): THREE.BufferGeometry {
  if (oreHeapGeometry) {
    return oreHeapGeometry;
  }
  let seed = 7;
  const rand = (): number => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  const parts: THREE.BufferGeometry[] = [];
  const stone = new THREE.Color(0.16, 0.13, 0.12);
  const ore = new THREE.Color(0.62, 0.26, 0.07);
  const nugget = new THREE.Color(1.0, 0.62, 0.18);
  for (let i = 0; i < 40; i += 1) {
    const r = Math.sqrt(rand()) * 0.8;
    const a = rand() * Math.PI * 2;
    const size = 0.17 + rand() * 0.18 + (1 - r) * 0.1;
    const chunk = new THREE.IcosahedronGeometry(size, 0);
    // Jag the chunk: push each vertex in or out a little so no two rocks match.
    const pos = chunk.getAttribute('position');
    const jag = new Map<string, number>();
    for (let v = 0; v < pos.count; v += 1) {
      const key = `${pos.getX(v).toFixed(3)},${pos.getY(v).toFixed(3)},${pos.getZ(v).toFixed(3)}`;
      let k = jag.get(key);
      if (k === undefined) {
        k = 0.7 + rand() * 0.6;
        jag.set(key, k);
      }
      pos.setXYZ(v, pos.getX(v) * k * 1.2, pos.getY(v) * k * 0.8, pos.getZ(v) * k);
    }
    chunk.rotateY(rand() * Math.PI);
    chunk.rotateX((rand() - 0.5) * 0.8);
    chunk.translate(Math.cos(a) * r, Math.max(0.04, (1 - r * r) * 0.5) + size * 0.2, Math.sin(a) * r);
    const pick = rand();
    const base = pick < 0.08 ? nugget : pick < 0.5 ? ore : stone;
    const colors: number[] = [];
    for (let v = 0; v < pos.count; v += 3) {
      const shade = 0.8 + rand() * 0.35;
      for (let k = 0; k < 3; k += 1) {
        colors.push(base.r * shade, base.g * shade, base.b * shade);
      }
    }
    chunk.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    chunk.deleteAttribute('uv');
    parts.push(chunk);
  }
  oreHeapGeometry = mergeGeometries(parts, false) ?? new THREE.IcosahedronGeometry(0.6, 0);
  oreHeapGeometry.computeVertexNormals();
  for (const part of parts) {
    part.dispose();
  }
  return oreHeapGeometry;
}

// A small painted texture so cargo reads at a glance: a dark steel frame around an ore (orange,
// with a rock glyph) or metal (steel blue, ingot bars) panel, and hazard corners.
function cargoTexture(kind: 'ore' | 'metal' | 'kit'): THREE.Texture | null {
  if (typeof document === 'undefined') {
    return null;
  }
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const g = canvas.getContext('2d');
  if (!g) {
    return null;
  }
  const panel = kind === 'ore' ? '#c8742c' : kind === 'metal' ? '#7f93a6' : '#5c6a3a';
  const mark = kind === 'ore' ? '#ffcf7a' : kind === 'metal' ? '#6ee6ff' : '#d8e0a0';
  g.fillStyle = '#23272c';
  g.fillRect(0, 0, 64, 64);
  g.fillStyle = panel;
  g.fillRect(7, 7, 50, 50);
  g.fillStyle = 'rgba(0,0,0,0.25)';
  for (let y = 11; y < 57; y += 8) {
    g.fillRect(7, y, 50, 2);
  }
  g.fillStyle = mark;
  if (kind === 'ore') {
    g.beginPath();
    g.moveTo(20, 42);
    g.lineTo(26, 24);
    g.lineTo(38, 20);
    g.lineTo(46, 34);
    g.lineTo(40, 44);
    g.closePath();
    g.fill();
  } else if (kind === 'metal') {
    g.fillRect(18, 22, 28, 6);
    g.fillRect(18, 31, 28, 6);
    g.fillRect(18, 40, 28, 6);
  }
  g.fillStyle = '#f2c230';
  for (const [x, y] of [[0, 0], [56, 0], [0, 56], [56, 56]] as const) {
    g.fillRect(x, y, 8, 8);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

interface UnitVisual {
  root: THREE.Object3D;
  turretPivot: THREE.Object3D | null;
  owner: number;
  lift: number;
  /** Smoothed nose-up pitch and side roll from the ground under the unit (radians). */
  pitch: number;
  roll: number;
  /** Half the hull length, used to sample the ground in front of and behind the unit. */
  reach: number;
  /** Instancing batch: model and look shared by every unit drawn in the same InstancedMesh. */
  batchKey: string;
  /** Low-detail geometry per instanced part (same order), when the model has a _lod file. */
  lod: THREE.BufferGeometry[] | null;
  typeId: string;
  /** Arcadian: gold weapons and the idle gold crackle. */
  alien: boolean;
  /** 1 right after firing, easing back to 0: the turret kicks back and the hull rocks. */
  recoil: number;
  /** The turret pivot's rest position, for the recoil kick. */
  pivotRest: THREE.Vector3 | null;
  /** Moving parts from the model's anim extras (drums, dishes, wings). */
  parts: PartMotion[];
  /** Hover units and aircraft bob gently. */
  floats: boolean;
  /** Aircraft lean into turns (radians of roll, smoothed). */
  bank: number;
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

const ENVIRONMENT_INTENSITY = 0.45;

interface StructureVisual {
  mesh: THREE.Mesh;
  height: number;
  barrel: THREE.Mesh | null;
  baseColor: THREE.Color;
  // Set when the structure type has a loaded model: the box stays as an invisible picking body.
  model: THREE.Object3D | null;
  modelPivot: THREE.Object3D | null;
  modelColors: Array<{ material: THREE.MeshStandardMaterial; base: THREE.Color }>;
  /** Model scale once fully unfolded (the rise animation scales up to it). */
  modelScale: number;
  /** The Shard's floating heart (bobs, spins, and flares as it charges and fires). */
  core: { node: THREE.Object3D; baseY: number; spin: number; flare: number } | null;
  /** Moving parts from the model's anim extras (radar dishes, spinning crowns). */
  parts: PartMotion[];
}

/**
 * A landing pad's deck, measured from its model: heights above the ground at the pad centre,
 * sampled every DECK_STEP metres along the exit axis from `u0`. Past the deck the samples fall off
 * no steeper than DECK_MAX_SLOPE, which is the ramp units drive down.
 */
interface PadDeck {
  x: number;
  z: number;
  fx: number;
  fz: number;
  half: number;
  u0: number;
  ground: number;
  heights: number[];
}

const DECK_STEP = 0.5;
const DECK_MAX_SLOPE = 0.45; // rise per metre on the exit ramp

function deckHeightAt(deck: PadDeck, x: number, z: number): number | null {
  const dx = x - deck.x;
  const dz = z - deck.z;
  const u = dx * deck.fx + dz * deck.fz;
  const v = -dx * deck.fz + dz * deck.fx;
  if (Math.abs(v) > deck.half + 0.5) {
    return null;
  }
  const index = (u - deck.u0) / DECK_STEP;
  if (index < 0 || index > deck.heights.length - 1) {
    return null;
  }
  const i = Math.floor(index);
  const a = deck.heights[i] ?? 0;
  const b = deck.heights[Math.min(deck.heights.length - 1, i + 1)] ?? 0;
  return deck.ground + a + (b - a) * (index - i);
}

function structureHeight(kind: string): number {
  switch (kind) {
    case 'pad':
      return 1.2;
    case 'turret':
      return 1.8;
    case 'radar':
      return 3.4;
    default:
      return 2.4;
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Shortest-way blend between two angles, so a heading crossing ±π never spins a full turn. */
function lerpAngle(a: number, b: number, t: number): number {
  let diff = b - a;
  while (diff > Math.PI) {
    diff -= Math.PI * 2;
  }
  while (diff < -Math.PI) {
    diff += Math.PI * 2;
  }
  return a + diff * t;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function unitBounds(root: THREE.Object3D): THREE.Box3 {
  root.updateMatrixWorld(true);
  const bounds = new THREE.Box3();
  const meshBounds = new THREE.Box3();
  // Model meshes drawn by instancing are hidden on the unit itself but still count.
  root.traverse((object) => {
    if (!(object instanceof THREE.Mesh) || (!object.visible && !isInstancedPart(object))) {
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

function cloneMaterials(root: THREE.Object3D, enemy: boolean, colourBlind: boolean): void {
  const tint = enemy ? (colourBlind ? COLORBLIND_ENEMY_TINT : ENEMY_TINT) : null;
  remapMeshMaterials(root, (material) => cloneWithTint(material, tint, false));
}

/** Chars a wreck: soot-black, lights out, dull. */
function darkenMaterials(root: THREE.Object3D): void {
  remapMeshMaterials(root, (material) => {
    const clone = cloneWithTint(material, null, true);
    if (clone instanceof THREE.MeshStandardMaterial) {
      clone.color.setRGB(0.07, 0.062, 0.055);
      clone.envMapIntensity = 0.25;
      clone.emissive.setRGB(0, 0, 0);
      clone.emissiveMap = null;
      clone.roughness = 1;
      clone.metalness = Math.min(clone.metalness, 0.3);
    }
    return clone;
  });
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

const WORKER_LABEL_ZOOM = 32;

function workerLabelText(kind: string, capacity: number, job: UnitState['job']): string {
  const load = job && capacity > 0 ? ` ${Math.floor(job.load)}/${capacity}` : '';
  if (kind === 'oreMiner') {
    switch (job?.stage) {
      case 'digging':
        return `Mining${load}`;
      case 'toDeposit':
        return 'Miner · to ore';
      case 'toPad':
        return `To pad${load}`;
      case 'waiting':
        return `Waiting at pad${load}`;
      case 'unloading':
        return 'Unloading';
      default:
        return job ? 'Miner' : 'Miner · idle';
    }
  }
  switch (job?.stage) {
    case 'toStation':
    case 'toDeposit':
      return 'Hauler · to pickup';
    case 'loading':
      return `Hauler · loading${load}`;
    case 'toPad':
      return `Hauler · to pad${load}`;
    case 'waiting':
      return 'Hauler · waiting';
    case 'unloading':
      return 'Hauler · unloading';
    default:
      return job ? 'Hauler' : 'Hauler · idle';
  }
}

const THUMB_WIDTH = 112;
const THUMB_HEIGHT = 104;

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
  private readonly ready: Promise<void>;
  private readonly raycaster = new THREE.Raycaster();
  private readonly overlay: HTMLDivElement;
  private readonly healthBars = new Map<number, HealthBar>();
  private readonly workerLabels = new Map<number, HTMLDivElement>();
  private readonly unitRoots = new Map<number, UnitVisual>();
  private readonly structureVisuals = new Map<number, StructureVisual>();
  /** Measured deck height along each pad's exit axis, so units sit on the deck and roll down. */
  private readonly padDecks = new Map<number, PadDeck>();
  private landscape: Landscape | null = null;
  private terrainDetail: { value: THREE.Texture | null } = { value: null };
  private readonly beamPool: THREE.Mesh[] = [];
  private readonly selectionRings = new Map<number, THREE.Mesh>();
  /** Footprints where your packed buildings are heading to unpack (overhaul step 5). */
  private readonly unpackSpots = new Map<number, THREE.Mesh>();
  private readonly flashes: Flash[] = [];
  private readonly projectileVisuals = new Map<
    number,
    {
      object: THREE.Object3D;
      kind: string | undefined;
      splash: number;
      offset: number;
      startX: number;
      startZ: number;
      shooterId: number | undefined;
      aim: number;
      alien: boolean;
      /** Shard lance: where it started, and the seed and time of its last kink re-roll. */
      from?: THREE.Vector3;
      seed?: number;
      rolled?: number;
    }
  >();
  private readonly unitInstances = new UnitInstances(this.scene);
  private readonly wreckInstances = new UnitInstances(this.scene);
  private readonly effects = new Effects(this.scene);
  private readonly wrecksGroup = new THREE.Group();
  private readonly wreckField = new WreckField(this.wrecksGroup, this.wreckInstances, this.effects, darkenMaterials);
  private lastFrameAt = 0;
  /** Real seconds since the last frame (capped), so effects keep their timing at any frame rate. */
  private frameDt = 1 / 60;
  /** Which side's look each structure had, for its death blast after it has left the world. */
  private readonly structureAlien = new Map<number, boolean>();
  private readonly selection: number[] = [];
  private readonly previousSnapshots = new Map<number, PositionSnapshot>();
  private readonly currentSnapshots = new Map<number, PositionSnapshot>();
  private readonly qualityController = new QualityController();
  private readonly orderLines = new Map<number, THREE.Line>();
  private terrain: THREE.Mesh | null = null;
  private fogTexture: THREE.DataTexture | null = null;
  private fogUniforms: { uFog: { value: THREE.DataTexture | null }; uFogOn: { value: number }; uFogSize: { value: number } } = {
    uFog: { value: null },
    uFogOn: { value: 0 },
    uFogSize: { value: 200 },
  };
  private fogCells: string | null = null;
  private readonly contactMeshes: THREE.Mesh[] = [];
  private readonly markerMeshes: THREE.Group[] = [];
  private objectiveMarkers: Array<{ x: number; z: number; radius: number }> = [];
  private contacts: Array<{ x: number; z: number }> = [];
  private skirt: THREE.Mesh | null = null;
  private farPlane: THREE.Mesh | null = null;
  private pickTargets: THREE.Object3D[] = [];
  private skyTexture: THREE.Texture | null = null;
  private templateRoot: THREE.Group | null = null;
  // Per-model templates keyed by asset id (unit type modelId); units without one use templateRoot.
  private readonly templates = new Map<string, THREE.Group>();
  private readonly thumbnails = new Map<string, string>();
  private readonly registry: AssetRegistry;
  private directional: THREE.DirectionalLight;
  private lightTarget: THREE.Object3D;
  private marker: THREE.Mesh | null = null;
  private markerTtl = 0;
  private placementGhost: THREE.Mesh | null = null;
  private placementType: SimStructureType | null = null;
  private world: WorldState;
  private lastTick = -1;
  private lastRenderAt = 0;
  private basePixelRatio = 1;
  private shadowsEnabled = true;
  private frame = 0;
  // Structures seen so far, and when the ones that appeared mid-game came up (performance.now()),
  // for the unfold animation. Kept outside the visuals, which are rebuilt when models load.
  private readonly structureSeen = new Set<number>();
  private readonly structureBorn = new Map<number, number>();
  /** Towers folding out part by part (models with packed poses), keyed by structure id. */
  private readonly structureFolding = new Map<number, { born: number; start: UnfoldStart }>();
  /** Real seconds since the last rendered frame, for moving model parts. */
  private motionDt = 0;
  private lastMotionAt: number | null = null;
  /** Where units that are packing up into a structure stand and face, for the fold-out to start from. */
  private readonly deployingUnits = new Map<number, { x: number; z: number; heading: number }>();
  /** Low-detail geometry per unit model id, one per mesh in traversal order. */
  private readonly lodGeometry = new Map<string, THREE.BufferGeometry[]>();
  private lodUnits = 0;
  /** New portraits allowed this frame: each one reads pixels back, which stalls on the GPU. */
  private thumbnailBudget = 1;
  private disposed = false;
  private qualityPreference: 'auto' | 'low' | 'medium' | 'high' = 'auto';
  private healthBarsMode: 'damaged' | 'always' = 'damaged';
  private colorBlind = false;

  constructor(canvas: HTMLCanvasElement, registry: AssetRegistry, world: WorldState) {
    this.world = world;
    this.registry = registry;
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
    this.ready = this.loadTemplate().catch(() => undefined);
  }

  /**
   * Resolves once every model, texture and landscape piece this view asked for has loaded or failed
   * (or after `timeoutMs`), so callers can keep the scene hidden instead of showing placeholder boxes.
   */
  whenReady(timeoutMs = 20_000): Promise<void> {
    return Promise.race([
      this.ready,
      new Promise<void>((resolve) => {
        window.setTimeout(resolve, timeoutMs);
      }),
    ]);
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

  quality(): QualityView {
    return qualityViewFor(this.effectiveQualityLevel(), this.basePixelRatio);
  }

  setQualityPreference(preference: 'auto' | 'low' | 'medium' | 'high'): void {
    if (this.qualityPreference === preference) {
      return;
    }
    this.qualityPreference = preference;
    if (preference === 'auto') {
      this.qualityController.reset();
    }
    this.applyQuality();
  }

  setHealthBarsMode(mode: 'damaged' | 'always'): void {
    this.healthBarsMode = mode;
  }

  setColorBlindMode(enabled: boolean): void {
    if (this.colorBlind === enabled) {
      return;
    }
    this.colorBlind = enabled;
    this.rebuildUnitVisuals();
  }

  applyCamera(): void {
    const position = this.rtsCamera.position((x, z) => heightAt(this.world.map, x, z));
    this.camera.position.set(position.x, position.y, position.z);
    const targetY = heightAt(this.world.map, this.rtsCamera.targetX, this.rtsCamera.targetZ) + 1;
    this.camera.lookAt(this.rtsCamera.targetX, targetY, this.rtsCamera.targetZ);
    this.camera.updateMatrixWorld();
  }

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

  cameraFootprint(): Array<{ x: number; z: number }> {
    if (this.pickTargets.length === 0) {
      return [];
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return [];
    }
    const corners: Array<{ x: number; y: number }> = [
      { x: rect.left, y: rect.top },
      { x: rect.right, y: rect.top },
      { x: rect.right, y: rect.bottom },
      { x: rect.left, y: rect.bottom },
    ];
    const result: Array<{ x: number; z: number }> = [];
    for (const corner of corners) {
      const ndc = new THREE.Vector2(
        ((corner.x - rect.left) / Math.max(1, rect.width)) * 2 - 1,
        -((corner.y - rect.top) / Math.max(1, rect.height)) * 2 + 1,
      );
      this.raycaster.setFromCamera(ndc, this.camera);
      const hits = this.raycaster.intersectObjects(this.pickTargets, false);
      const first = hits[0];
      if (!first) {
        return [];
      }
      result.push({ x: first.point.x, z: first.point.z });
    }
    return result;
  }

  /** Ground height for a unit: the terrain, or a landing pad's deck and ramp where it stands on one. */
  private unitGroundAt(x: number, z: number): number {
    const ground = heightAt(this.world.map, x, z);
    for (const deck of this.padDecks.values()) {
      if (Math.abs(x - deck.x) > deck.half + 8 || Math.abs(z - deck.z) > deck.half + 8) {
        continue;
      }
      const top = deckHeightAt(deck, x, z);
      if (top !== null && top > ground) {
        return top;
      }
    }
    return ground;
  }

  /** Samples the pad model's deck along the exit axis with downward rays (once, when it loads). */
  private measurePadDeck(world: WorldState, structure: StructureState, visual: StructureVisual, half: number): void {
    const model = visual.model;
    if (!model) {
      return;
    }
    // Parents too: the pad's body was only just positioned this frame.
    model.updateWorldMatrix(true, true);
    const facing = padFacing(structure);
    const fx = Math.round(Math.cos(facing));
    const fz = Math.round(Math.sin(facing));
    const ground = heightAt(world.map, structure.x, structure.z);
    const ray = new THREE.Raycaster();
    const down = new THREE.Vector3(0, -1, 0);
    const origin = new THREE.Vector3();
    const u0 = -half;
    const heights: number[] = [];
    for (let u = u0; u <= half + 0.001; u += DECK_STEP) {
      // Take the lowest of three rays across the lane, so a railing or light doesn't count as deck.
      let top = Number.POSITIVE_INFINITY;
      for (const v of [-1.2, 0, 1.2]) {
        origin.set(structure.x + fx * u - fz * v, ground + 30, structure.z + fz * u + fx * v);
        ray.set(origin, down);
        const hit = ray.intersectObject(model, true)[0];
        top = Math.min(top, hit ? hit.point.y - ground : 0);
      }
      heights.push(Math.max(0, Math.min(4, top)));
    }
    // Ramp: past the highest point toward the exit, never drop faster than the max slope, and
    // carry on past the edge until it reaches the ground.
    let peak = 0;
    heights.forEach((height, index) => {
      if (height >= (heights[peak] ?? 0)) {
        peak = index;
      }
    });
    for (let i = peak + 1; i < heights.length; i += 1) {
      heights[i] = Math.max(heights[i] ?? 0, (heights[i - 1] ?? 0) - DECK_MAX_SLOPE * DECK_STEP);
    }
    while ((heights[heights.length - 1] ?? 0) > 0.01) {
      heights.push(Math.max(0, (heights[heights.length - 1] ?? 0) - DECK_MAX_SLOPE * DECK_STEP));
    }
    this.padDecks.set(structure.id, { x: structure.x, z: structure.z, fx, fz, half, u0, ground, heights });
  }

  /** Deck height at a pad's centre, where deliveries touch down. */
  private padDeckTop(world: WorldState, pad: StructureState): number {
    const deck = this.padDecks.get(pad.id);
    const top = deck ? deckHeightAt(deck, pad.x, pad.z) : null;
    return top ?? heightAt(world.map, pad.x, pad.z) + structureHeight('pad') * 0.35;
  }

  unitScreenCentre(id: number): { x: number; y: number } | null {
    const unit = this.world.units.find((item) => item.id === id);
    if (!unit) {
      return null;
    }
    return this.projectPoint(
      unit.x,
      this.unitGroundAt(unit.x, unit.z) + UNIT_PICK_HEIGHT,
      unit.z,
    );
  }

  unitIsOnScreen(id: number): boolean {
    const centre = this.unitScreenCentre(id);
    if (!centre) {
      return false;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    return (
      centre.x >= rect.left &&
      centre.x <= rect.right &&
      centre.y >= rect.top &&
      centre.y <= rect.bottom
    );
  }

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
        this.unitGroundAt(unit.x, unit.z) + UNIT_PICK_HEIGHT,
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
      const enemy = candidates.filter((candidate) => !isAllied(this.world, 1, candidate.owner));
      if (enemy.length > 0) {
        pool = enemy;
      }
    }
    pool.sort((a, b) => a.distance - b.distance);
    return pool[0]?.id ?? null;
  }

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

  orderPaths(): OrderPathInfo[] {
    const result: OrderPathInfo[] = [];
    for (const id of this.selection) {
      const unit = this.world.units.find((item) => item.id === id);
      if (!unit || unit.path.length === 0) {
        continue;
      }
      const queued =
        (unit.order.kind === 'move' || unit.order.kind === 'attackMove') &&
        unit.order.queue;
      result.push({ unitId: id, points: unit.path.length + 1, queued });
    }
    return result;
  }

  showPlacement(structureTypeId: string, x: number, z: number, valid: boolean): void {
    const type = this.world.structureTypes.get(structureTypeId);
    if (!type) {
      return;
    }
    this.placementType = type;
    const size = Math.max(type.footprint.cellsX, type.footprint.cellsZ) * this.world.map.cellSize;
    const height = structureHeight(type.kind);
    const groundY = heightAt(this.world.map, x, z);
    if (!this.placementGhost) {
      const geometry = new THREE.BoxGeometry(size, height, size);
      const material = new THREE.MeshBasicMaterial({
        color: PLACEMENT_VALID_COLOR,
        transparent: true,
        opacity: 0.55,
        side: THREE.DoubleSide,
      });
      this.placementGhost = new THREE.Mesh(geometry, material);
      this.scene.add(this.placementGhost);
    }
    this.placementGhost.position.set(x, groundY + height / 2, z);
    const material = this.placementGhost.material;
    if (material instanceof THREE.MeshBasicMaterial) {
      material.color.setHex(valid ? PLACEMENT_VALID_COLOR : PLACEMENT_INVALID_COLOR);
    }
  }

  clearPlacement(): void {
    this.placementType = null;
    if (!this.placementGhost) {
      return;
    }
    this.scene.remove(this.placementGhost);
    this.placementGhost.geometry.dispose();
    const material = this.placementGhost.material;
    if (material instanceof THREE.Material) {
      material.dispose();
    }
    this.placementGhost = null;
  }

  render(alpha: number, world: WorldState): void {
    this.world = world;
    const now = performance.now();
    this.motionDt = this.lastMotionAt === null ? 0 : (now - this.lastMotionAt) / 1000;
    this.lastMotionAt = now;
    this.updateQuality();
    this.updateSnapshots(world);
    this.applyCamera();
    this.updateLight();
    this.syncUnits(alpha);
    this.syncStructures(world);
    this.landscape?.sync(world);
    this.syncDropBeams(world);
    this.syncPadTraffic(world, alpha);
    this.syncWorkerCargo(world, alpha);
    this.syncProjectiles();
    this.syncWrecks();
    this.syncContacts();
    this.syncObjectiveMarkers();
    this.syncSelection();
    this.syncUnpackSpots();
    this.syncOrderLines();
    this.syncHealthBars();
    this.syncWorkerLabels();
    this.updateMarker();
    this.updateFlashes();
    this.effects.update(this.frameDt);
    this.frame += 1;
    this.thumbnailBudget = 1;
    this.renderer.render(this.scene, this.camera);
  }

  // Fog texture and anonymous sensor contacts for the player's side. `cells` is the vision string.
  setPerception(
    fog: { cells: string; cols: number; rows: number } | null,
    contacts: Array<{ x: number; z: number }>,
  ): void {
    this.contacts = contacts;
    if (!fog) {
      this.fogUniforms.uFogOn.value = 0;
      return;
    }
    if (this.fogCells !== fog.cells) {
      this.fogCells = fog.cells;
      const data = new Uint8Array(fog.cols * fog.rows);
      for (let i = 0; i < data.length; i += 1) {
        const ch = fog.cells.charAt(i);
        data[i] = ch === '2' ? 255 : ch === '1' ? 105 : 0;
      }
      let texture = this.fogTexture;
      if (!texture || texture.image.width !== fog.cols) {
        texture?.dispose();
        texture = new THREE.DataTexture(data, fog.cols, fog.rows, THREE.RedFormat, THREE.UnsignedByteType);
        texture.magFilter = THREE.LinearFilter;
        texture.minFilter = THREE.LinearFilter;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        this.fogTexture = texture;
        this.fogUniforms.uFog.value = texture;
      } else {
        (texture.image.data as Uint8Array).set(data);
      }
      texture.needsUpdate = true;
    }
    this.fogUniforms.uFogOn.value = 1;
  }

  // Mission goal areas (sim/triggers missionMarkers): a pulsing ring on the ground plus a tall beam
  // so the spot can be found at any zoom.
  setObjectiveMarkers(markers: Array<{ x: number; z: number; radius: number }>): void {
    this.objectiveMarkers = markers;
  }

  objectiveMarkerCount(): number {
    return this.markerMeshes.filter((group) => group.visible).length;
  }

  private syncObjectiveMarkers(): void {
    while (this.markerMeshes.length < this.objectiveMarkers.length) {
      const group = new THREE.Group();
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.92, 1, 48),
        new THREE.MeshBasicMaterial({ color: 0xffd23f, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.name = 'ring';
      const beam = new THREE.Mesh(
        new THREE.CylinderGeometry(0.25, 0.25, 30, 8, 1, true),
        new THREE.MeshBasicMaterial({ color: 0xffd23f, transparent: true, opacity: 0.35, depthWrite: false }),
      );
      beam.position.y = 15;
      group.add(ring, beam);
      this.scene.add(group);
      this.markerMeshes.push(group);
    }
    const pulse = 0.65 + 0.3 * Math.sin(this.frame * 0.08);
    for (let i = 0; i < this.markerMeshes.length; i += 1) {
      const group = this.markerMeshes[i];
      const marker = this.objectiveMarkers[i];
      if (!group) {
        continue;
      }
      group.visible = marker !== undefined;
      if (marker) {
        group.position.set(marker.x, heightAt(this.world.map, marker.x, marker.z) + 0.3, marker.z);
        const ring = group.getObjectByName('ring');
        if (ring instanceof THREE.Mesh) {
          ring.scale.setScalar(marker.radius);
          (ring.material as THREE.MeshBasicMaterial).opacity = pulse;
        }
      }
    }
  }

  private syncContacts(): void {
    while (this.contactMeshes.length < this.contacts.length) {
      const mesh = new THREE.Mesh(
        new THREE.RingGeometry(0.9, 1.3, 20),
        new THREE.MeshBasicMaterial({ color: 0xd0d0d0, transparent: true, opacity: 0.8, side: THREE.DoubleSide }),
      );
      mesh.rotation.x = -Math.PI / 2;
      this.scene.add(mesh);
      this.contactMeshes.push(mesh);
    }
    const pulse = 1 + 0.25 * Math.sin(this.frame * 0.15);
    for (let i = 0; i < this.contactMeshes.length; i += 1) {
      const mesh = this.contactMeshes[i];
      const contact = this.contacts[i];
      if (!mesh) {
        continue;
      }
      mesh.visible = contact !== undefined;
      if (contact) {
        mesh.position.set(contact.x, heightAt(this.world.map, contact.x, contact.z) + 0.4, contact.z);
        mesh.scale.setScalar(pulse * 1.6);
      }
    }
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
      triangles: this.renderer.info.render.triangles,
      frame: this.frame,
      units: this.unitRoots.size,
      lodUnits: this.lodUnits,
      wrecks: this.wreckField.count,
      effects: this.effects.count,
      movingParts: this.movingParts(),
    };
  }

  private movingParts(): string[] {
    const out: string[] = [];
    for (const visual of this.unitRoots.values()) {
      for (const part of visual.parts) {
        if (part.blend > 0.5) {
          out.push(`${visual.typeId} ${part.node.name}`);
        }
      }
    }
    for (const [id, visual] of this.structureVisuals) {
      const typeId = this.world.structures.find((item) => item.id === id)?.typeId ?? '?';
      for (const part of visual.parts) {
        if (part.blend > 0.5) {
          out.push(`${typeId} ${part.node.name}`);
        }
      }
    }
    return out.sort();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.effects.dispose();
    this.landscape?.dispose();
    this.terrainDetail.value?.dispose();
    this.unitInstances.clear();
    this.wreckInstances.clear();
    for (const group of this.markerMeshes) {
      group.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          const mesh = object as THREE.Mesh<THREE.BufferGeometry, THREE.Material>;
          mesh.geometry.dispose();
          mesh.material.dispose();
        }
      });
    }
    for (const mesh of this.contactMeshes) {
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
    }
    this.observer.disconnect();
    this.overlay.remove();
    this.clearPlacement();
    this.skyTexture?.dispose();
    this.loader.release(TANK_ASSET_ID);
    this.renderer.dispose();
  }

  /** Frees the WebGL context right away (title backdrop), instead of waiting for garbage collection. */
  releaseContext(): void {
    this.renderer.forceContextLoss();
  }

  private effectiveQualityLevel(): number {
    if (this.qualityPreference === 'auto') {
      return this.qualityController.level;
    }
    return QUALITY_PREFERENCE_LEVEL[this.qualityPreference];
  }

  private updateQuality(): void {
    if (this.qualityPreference !== 'auto') {
      return;
    }
    const now = performance.now();
    const previous = this.lastRenderAt;
    this.lastRenderAt = now;
    if (previous === 0) {
      return;
    }
    const frameMs = now - previous;
    if (frameMs <= 0 || frameMs > MAX_FRAME_SAMPLE_MS) {
      return;
    }
    if (this.qualityController.sample(frameMs)) {
      this.applyQuality();
    }
  }

  private applyQuality(): void {
    const level = this.effectiveQualityLevel();
    const view = qualityViewFor(level, this.basePixelRatio);
    this.effects.setDetail(1 - level * 0.13);
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
        map.dispose();
        this.directional.shadow.map = null;
      }
    }

    this.landscape?.setShadows(view.shadows);
    if (shadowsChanged) {
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

    // Soft reflected light for metal surfaces. Without an environment, metallic materials only
    // reflect black and the Kesh bronze and Terran gunmetal read dull. Built once, tiny, and cheap.
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = ENVIRONMENT_INTENSITY;
    pmrem.dispose();

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
    this.landscape = new Landscape(this.scene, this.world.map, this.fogUniforms);
    const waterLevel = this.world.map.waterLevel;
    if (waterLevel !== null) {
      const water = new THREE.Mesh(
        new THREE.PlaneGeometry(this.world.map.size, this.world.map.size),
        new THREE.MeshStandardMaterial({
          color: 0x2f6f9f,
          roughness: 0.25,
          transparent: true,
          opacity: 0.72,
        }),
      );
      water.rotation.x = -Math.PI / 2;
      water.position.y = waterLevel;
      this.scene.add(water);
    }
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
    // Ground kind per vertex (grass, dirt, rock weights): picks which detail channel the shader uses.
    const surface = new Float32Array(vertexCount * 3);
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
    const blockedRock = new THREE.Color(0x60594d);

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
        const rockWeight = slope > MAX_SLOPE ? 1 : clamp(Math.max((heightNorm - 0.45) / 0.4, (slopeNorm - 0.55) / 0.45), 0, 1);
        const dirtWeight = clamp(slopeNorm * 1.4 - 0.1, 0, 1) * (1 - rockWeight);
        surface[index * 3] = 1 - rockWeight - dirtWeight;
        surface[index * 3 + 1] = dirtWeight;
        surface[index * 3 + 2] = rockWeight;
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
    geometry.setAttribute('surface', new THREE.BufferAttribute(surface, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 1,
      metalness: 0,
    });
    const uniforms = this.fogUniforms;
    const detail = this.terrainDetail;
    uniforms.uFogSize.value = map.size;
    material.onBeforeCompile = (shader) => {
      shader.uniforms.uFog = uniforms.uFog;
      shader.uniforms.uFogOn = uniforms.uFogOn;
      shader.uniforms.uFogSize = uniforms.uFogSize;
      shader.uniforms.uDetail = detail;
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec2 vFogXZ;\nattribute vec3 surface;\nvarying vec3 vSurface;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvFogXZ = position.xz;\nvSurface = surface;');
      shader.fragmentShader = shader.fragmentShader
        .replace(
          '#include <common>',
          '#include <common>\nvarying vec2 vFogXZ;\nuniform sampler2D uFog;\nuniform float uFogOn;\nuniform float uFogSize;\nvarying vec3 vSurface;' +
            (detail.value ? '\nuniform sampler2D uDetail;' : ''),
        )
        .replace(
          '#include <color_fragment>',
          '#include <color_fragment>\n' +
            // Ground detail: fine grass, pebbles or cracks by ground kind, plus broad patches so a
            // field is not one flat colour. Off until the texture has loaded.
            (detail.value
              ? `vec3 dFine = texture2D(uDetail, vFogXZ / ${DETAIL_TILE.toFixed(1)}).rgb - 0.5;
vec3 dBroad = texture2D(uDetail, vFogXZ / ${(DETAIL_TILE * 6.3).toFixed(1)} + 0.37).rgb - 0.5;
vec3 w = vSurface / max(0.001, vSurface.x + vSurface.y + vSurface.z);
diffuseColor.rgb *= 1.0 + dot(dFine, w) * 1.3 + dBroad.r * 0.55;
diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(1.08, 0.98, 0.82), clamp(dBroad.g * 2.0, 0.0, 1.0) * w.x);
`
              : '') +
            'if (uFogOn > 0.5) { float fogLevel = texture2D(uFog, vFogXZ / uFogSize + 0.5).r; diffuseColor.rgb *= fogLevel; }',
        );
    };
    material.customProgramCacheKey = () => (detail.value ? 'terrainDetail' : 'terrain');
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
    this.rtsCamera.setViewport(this.camera.aspect, CAMERA_FOV_DEG);
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
    if (world.tick < this.lastTick) {
      // A new match or a loaded save: the old battlefield's wrecks go.
      this.wreckField.clear();
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
      } else {
        this.templateRoot = this.prepareFallback();
      }
    } catch {
      if (!this.disposed) {
        this.templateRoot = this.prepareFallback();
      }
    }
    if (this.disposed) {
      return;
    }
    this.rebuildUnitVisuals();
    await Promise.all([this.loadUnitModels(), this.loadLandscape()]);
  }

  // Ground detail texture, ore and metal site models and the scattered props. Any that fail to load
  // leave the plain terrain, the placeholder deposit discs, or no props.
  private async loadLandscape(): Promise<void> {
    const ids = [TERRAIN_DETAIL_ID, DEPOSIT_MODEL_IDS.ore, DEPOSIT_MODEL_IDS.metal, ...PROP_IDS].filter((id) =>
      this.registry.has(id),
    );
    const results = await Promise.allSettled(ids.map((id) => this.loader.load(id)));
    if (this.disposed) {
      return;
    }
    ids.forEach((id, index) => {
      const result = results[index];
      if (result?.status !== 'fulfilled') {
        return;
      }
      const asset = result.value;
      if (id === TERRAIN_DETAIL_ID && asset instanceof THREE.Texture) {
        asset.wrapS = THREE.RepeatWrapping;
        asset.wrapT = THREE.RepeatWrapping;
        asset.anisotropy = 4;
        asset.needsUpdate = true;
        this.terrainDetail.value = asset;
        // Recompile the terrain shader with the detail lookup switched on.
        const terrainMaterial = this.terrain?.material;
        if (terrainMaterial instanceof THREE.Material) {
          terrainMaterial.needsUpdate = true;
        }
        this.loadedModels.push(id);
      } else if (asset instanceof THREE.Object3D && this.landscape) {
        if (id === DEPOSIT_MODEL_IDS.ore) {
          this.landscape.addDepositModel('ore', asset);
        } else if (id === DEPOSIT_MODEL_IDS.metal) {
          this.landscape.addDepositModel('metal', asset);
        } else {
          this.landscape.addPropModel(id, asset);
        }
        this.loadedModels.push(id);
      }
    });
  }

  // Load every distinct unit and structure model the world's types name (besides the shared fallback tank).
  // Structure types whose model is not in the asset manifest keep their plain box.
  private async loadUnitModels(): Promise<void> {
    const ids = new Set<string>();
    for (const type of this.world.unitTypes.values()) {
      if (type.modelId && type.modelId !== TANK_ASSET_ID) {
        ids.add(type.modelId);
      }
    }
    for (const type of this.world.structureTypes.values()) {
      if (type.modelId && this.registry.has(type.modelId)) {
        ids.add(type.modelId);
      }
    }
    // Fetch and decode in parallel (about 40 small files), then register in a fixed order.
    const sorted = [...ids].sort();
    const lodIds = sorted.filter((id) => !id.startsWith('structure.') && this.registry.has(`${id}.lod`));
    const [results, lodResults] = await Promise.all([
      Promise.allSettled(sorted.map((id) => this.loader.load(id))),
      Promise.allSettled(lodIds.map((id) => this.loader.load(`${id}.lod`))),
    ]);
    if (this.disposed) {
      return;
    }
    lodIds.forEach((id, index) => {
      const result = lodResults[index];
      if (result?.status === 'fulfilled' && result.value instanceof THREE.Object3D) {
        // Geometry only: the low-detail file's placeholder material is replaced by the full model's.
        const geometries: THREE.BufferGeometry[] = [];
        result.value.traverse((object) => {
          if (object instanceof THREE.Mesh) {
            geometries.push(object.geometry as THREE.BufferGeometry);
            const material: unknown = object.material;
            if (material instanceof THREE.Material) {
              material.dispose();
            }
          }
        });
        this.lodGeometry.set(id, geometries);
      }
    });
    let loaded = false;
    sorted.forEach((id, index) => {
      const result = results[index];
      // A rejected load (unknown or broken model) leaves those units on the fallback tank.
      if (result?.status === 'fulfilled' && result.value instanceof THREE.Object3D) {
        const template = id.startsWith('structure.')
          ? this.prepareStructureTemplate(result.value)
          : this.prepareTemplate(result.value);
        this.templates.set(id, template);
        this.loadedModels.push(id);
        loaded = true;
      }
    });
    if (loaded) {
      this.rebuildUnitVisuals();
    }
  }

  /**
   * A small portrait of a unit or structure type (UI selection panel, build cards), rendered once
   * from its loaded model and cached as a PNG data URL. Null until the model has loaded, and for
   * all but one new portrait per frame (ask again later).
   */
  thumbnail(kind: 'unit' | 'structure', typeId: string): string | null {
    const key = `${kind}:${typeId}`;
    const cached = this.thumbnails.get(key);
    if (cached) {
      return cached;
    }
    const modelId =
      kind === 'unit' ? this.world.unitTypes.get(typeId)?.modelId : this.world.structureTypes.get(typeId)?.modelId;
    const template = modelId ? this.templates.get(modelId) : undefined;
    if (!template || this.disposed || this.thumbnailBudget <= 0) {
      // Callers ask again on their next refresh; a menu fills in one portrait per frame.
      return null;
    }
    this.thumbnailBudget -= 1;
    const width = THUMB_WIDTH;
    const height = THUMB_HEIGHT;
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xd2e6ff, 0x3b3524, 1.1));
    const key1 = new THREE.DirectionalLight(0xfff3d6, 2.6);
    key1.position.set(4, 6, 5);
    const rim = new THREE.DirectionalLight(0x8fd8ff, 1.4);
    rim.position.set(-5, 3, -4);
    scene.add(key1, rim);
    const model = template.clone(true);
    cloneMaterials(model, false, this.colorBlind);
    scene.add(model);
    model.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(model);
    const centre = new THREE.Vector3();
    const size = new THREE.Vector3();
    bounds.getCenter(centre);
    bounds.getSize(size);
    const radius = Math.max(0.001, size.length() / 2);
    const camera = new THREE.PerspectiveCamera(30, width / height, 0.01, 100);
    const distance = (radius / Math.sin(THREE.MathUtils.degToRad(15))) * 0.7;
    const direction = new THREE.Vector3(1, 0.75, 1.15).normalize();
    camera.position.copy(centre).addScaledVector(direction, distance);
    camera.lookAt(centre);
    const target = new THREE.WebGLRenderTarget(width, height, { samples: 4 });
    target.texture.colorSpace = THREE.SRGBColorSpace;
    const previousTarget = this.renderer.getRenderTarget();
    const previousClear = this.renderer.getClearColor(new THREE.Color());
    const previousAlpha = this.renderer.getClearAlpha();
    const previousShadows = this.renderer.shadowMap.enabled;
    let url: string | null = null;
    try {
      this.renderer.shadowMap.enabled = false;
      this.renderer.setRenderTarget(target);
      this.renderer.setClearColor(0x000000, 0);
      this.renderer.clear();
      this.renderer.render(scene, camera);
      const pixels = new Uint8Array(width * height * 4);
      this.renderer.readRenderTargetPixels(target, 0, 0, width, height, pixels);
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const g = canvas.getContext('2d');
      if (g) {
        const image = g.createImageData(width, height);
        for (let row = 0; row < height; row += 1) {
          const src = (height - 1 - row) * width * 4;
          image.data.set(pixels.subarray(src, src + width * 4), row * width * 4);
        }
        g.putImageData(image, 0, 0);
        url = canvas.toDataURL('image/png');
      }
    } finally {
      this.renderer.setRenderTarget(previousTarget);
      this.renderer.setClearColor(previousClear, previousAlpha);
      this.renderer.shadowMap.enabled = previousShadows;
      target.dispose();
      model.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          const material: unknown = object.material;
          if (material instanceof THREE.Material) {
            material.dispose();
          }
        }
      });
    }
    if (url) {
      this.thumbnails.set(key, url);
    }
    return url;
  }

  private templateFor(typeId: string): THREE.Group | null {
    const modelId = this.world.unitTypes.get(typeId)?.modelId;
    return (modelId ? this.templates.get(modelId) : undefined) ?? this.templateRoot;
  }

  private prepareTemplate(model: THREE.Object3D): THREE.Group {
    const plane = model.getObjectByName('Plane');
    if (plane) {
      plane.visible = false;
      plane.removeFromParent();
    }

    model.updateMatrixWorld(true);
    // New models (tools/art) ship their own TurretPivot; the proof-of-concept tank needs one built.
    if (!model.getObjectByName('TurretPivot')) {
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
    this.unitInstances.clear();
    this.syncUnits(0);
    // Structures created before their models arrived are rebuilt with the model.
    for (const visual of this.structureVisuals.values()) {
      this.disposeStructureVisual(visual);
    }
    this.structureVisuals.clear();
    this.syncStructures(this.world);
  }

  // Structure models are normalised to a 1 x 1 footprint, centred, standing on y = 0.
  // Fold-out towers normalise on their deployed pose without the Carrier (the folded hull).
  private prepareStructureTemplate(model: THREE.Object3D): THREE.Group {
    model.updateMatrixWorld(true);
    const unfold = readUnfold(model);
    const bounds = unfold ? unfold.bounds : new THREE.Box3().setFromObject(model);
    let normScale = 1;
    if (!bounds.isEmpty()) {
      const size = new THREE.Vector3();
      bounds.getSize(size);
      normScale = 1 / Math.max(size.x, size.z, 0.0001);
      model.scale.multiplyScalar(normScale);
      model.updateMatrixWorld(true);
      // Fold-out bounds come from readUnfold (no Carrier); scaling about the origin scales them too.
      const scaled = unfold ? bounds.clone().applyMatrix4(new THREE.Matrix4().makeScale(normScale, normScale, normScale)) : new THREE.Box3().setFromObject(model);
      const centre = new THREE.Vector3();
      scaled.getCenter(centre);
      model.position.x -= centre.x;
      model.position.z -= centre.z;
      model.position.y -= scaled.min.y;
    }
    const root = new THREE.Group();
    if (unfold) {
      const data: UnfoldData = { ...unfold.data, normScale };
      root.userData.unfold = data;
    }
    root.add(model);
    root.updateMatrixWorld(true);
    return root;
  }

  /** New structures rise out of the ground footprint and settle with a slight overshoot. */
  private animateUnfold(id: number, visual: StructureVisual): void {
    const born = this.structureBorn.get(id);
    if (born === undefined || !visual.model) {
      return;
    }
    const t = (performance.now() - born) / UNFOLD_MS;
    if (t >= 1) {
      visual.model.scale.setScalar(visual.modelScale);
      this.structureBorn.delete(id);
      return;
    }
    // Rise smoothly to a little past full height over the first three quarters, then settle.
    const smooth = (x: number): number => x * x * (3 - 2 * x);
    const k = t < 0.75 ? 1.06 * smooth(t / 0.75) : 1.06 - 0.06 * smooth((t - 0.75) / 0.25);
    const s = visual.modelScale;
    visual.model.scale.set(s * (0.6 + 0.4 * k), s * Math.max(0.05, k), s * (0.6 + 0.4 * k));
  }

  private disposeStructureVisual(visual: StructureVisual): void {
    this.scene.remove(visual.mesh);
    visual.mesh.geometry.dispose();
    const material = visual.mesh.material;
    if (material instanceof THREE.Material) {
      material.dispose();
    }
    for (const entry of visual.modelColors) {
      entry.material.dispose();
    }
  }

  private createUnitVisual(unit: UnitState): UnitVisual {
    let root: THREE.Object3D;
    const template = this.templateFor(unit.typeId);
    if (template) {
      root = template.clone(true);
      // Templates are normalised to one tank length; heavies, bombers and scouts differ.
      const scale = this.world.unitTypes.get(unit.typeId)?.visualScale ?? 1;
      root.scale.setScalar(scale);
    } else {
      root = this.prepareFallback();
    }
    cloneMaterials(root, isHostile(this.world, 1, unit.owner), this.colorBlind);
    root.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });
    const enemy = isHostile(this.world, 1, unit.owner);
    markInstanced(root);
    const modelId = this.world.unitTypes.get(unit.typeId)?.modelId;
    let lod = template && modelId ? (this.lodGeometry.get(modelId) ?? null) : null;
    if (lod) {
      let meshes = 0;
      root.traverse((object) => {
        if (object instanceof THREE.Mesh && isInstancedPart(object)) {
          meshes += 1;
        }
      });
      // Only when the low-detail file has exactly the full model's meshes.
      if (meshes !== lod.length) {
        lod = null;
      }
    }
    this.scene.add(root);
    const parts = collectPartMotions(root);
    // A TurretPivot with its own motion is a spinner, not a gun: it is never aimed or kicked.
    const aimed = pivotIsSpinner(parts) ? null : (root.getObjectByName('TurretPivot') ?? null);
    return {
      root,
      turretPivot: aimed,
      owner: unit.owner,
      lift: 0,
      pitch: 0,
      roll: 0,
      reach: Math.max(0.6, (this.world.unitTypes.get(unit.typeId)?.radius ?? 1.6) * 0.75),
      batchKey: `${template ? unit.typeId : 'fallback'}|${enemy ? 'enemy' : 'own'}`,
      lod,
      typeId: unit.typeId,
      alien: this.world.factions.find((item) => item.player === unit.owner)?.faction === 'alien',
      recoil: 0,
      pivotRest: aimed?.position.clone() ?? null,
      parts,
      floats: this.world.unitTypes.get(unit.typeId)?.movement === 'hover',
      bank: 0,
    };
  }

  private syncUnits(alpha: number): void {
    const alive = new Set(this.world.units.map((unit) => unit.id));
    for (const [id, visual] of this.unitRoots) {
      if (!alive.has(id)) {
        this.unitDied(visual);
        this.scene.remove(visual.root);
        this.unitRoots.delete(id);
      }
    }
    this.unitInstances.begin();
    const allLod = this.effectiveQualityLevel() >= LOD_QUALITY_LEVEL;
    const eye = this.camera.position;
    this.lodUnits = 0;
    let arcBudget = 3;

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
      if (unit.transform) {
        this.deployingUnits.set(unit.id, { x: unit.x, z: unit.z, heading: unit.heading });
      }
      const x = lerp(previous.x, current.x, alpha);
      const z = lerp(previous.z, current.z, alpha);
      const heading = lerpAngle(previous.heading, current.heading, alpha);
      const turretHeading = lerpAngle(previous.turretHeading, current.turretHeading, alpha);
      const airType = unit.air ? this.world.unitTypes.get(unit.typeId)?.air : null;
      const wantLift =
        unit.air && (unit.air.mode === 'flying' || unit.air.mode === 'returning')
          ? (airType?.cruiseHeight ?? 6)
          : 0;
      visual.lift += (wantLift - visual.lift) * 0.08;
      const ground = this.unitGroundAt(x, z);
      // Sit the hull on the slope: pitch from the ground ahead and behind, roll from either side.
      let wantPitch = 0;
      let wantRoll = 0;
      if (visual.lift < 0.3) {
        const r = visual.reach;
        const fx = Math.cos(heading) * r;
        const fz = Math.sin(heading) * r;
        const front = this.unitGroundAt(x + fx, z + fz);
        const back = this.unitGroundAt(x - fx, z - fz);
        // Local +Z of the model is world (-sin h, cos h).
        const side = this.unitGroundAt(x - fz, z + fx);
        const otherSide = this.unitGroundAt(x + fz, z - fx);
        wantPitch = Math.atan2(front - back, 2 * r);
        wantRoll = -Math.atan2(side - otherSide, 2 * r);
      }
      visual.pitch += (wantPitch - visual.pitch) * 0.25;
      visual.roll += (wantRoll - visual.roll) * 0.25;
      // The middle of the hull follows the average of the four samples' plane, which the centre
      // height already approximates; lift keeps aircraft above it.
      // Hover units and aircraft in the air bob gently, each on its own beat.
      const airborne = visual.lift > 0.3;
      const bob =
        visual.floats || airborne
          ? Math.sin(performance.now() / 1000 * (airborne ? 1.4 : 2.1) + unit.id * 1.7) * (airborne ? 0.18 : 0.07)
          : 0;
      // Aircraft lean into turns: roll follows how fast the heading is changing.
      let wantBank = 0;
      if (airborne) {
        const turnRate = Math.atan2(Math.sin(current.heading - previous.heading), Math.cos(current.heading - previous.heading));
        wantBank = Math.max(-0.55, Math.min(0.55, turnRate * 6));
      }
      visual.bank += (wantBank - visual.bank) * 0.1;
      visual.root.position.set(x, ground + visual.lift + bob, z);
      visual.root.rotation.set(visual.roll + visual.bank, -heading, visual.pitch, 'YZX');
      if (visual.turretPivot) {
        const rel = heading - turretHeading;
        visual.turretPivot.rotation.y = rel;
        if (visual.pivotRest) {
          // Recoil: the turret jumps back along its barrel and the hull rocks nose-up.
          const kick = visual.recoil * 0.28;
          visual.turretPivot.position.set(
            visual.pivotRest.x - Math.cos(rel) * kick,
            visual.pivotRest.y,
            visual.pivotRest.z + Math.sin(rel) * kick,
          );
        }
      }
      if (visual.recoil > 0.001) {
        visual.root.rotation.z += visual.recoil * 0.07 * Math.cos(heading - turretHeading);
        visual.recoil *= 0.82;
      }
      if (visual.parts.length > 0) {
        updatePartMotions(visual.parts, this.unitMotionState(unit, current, previous), this.motionDt);
      }
      if (visual.alien && visual.root.visible && arcBudget > 0 && Math.random() < 0.025) {
        arcBudget -= 1;
        this.effects.arcAround(x, ground + visual.lift + 0.9 * visual.root.scale.y, z, 1.1 * visual.root.scale.y);
      }
      if (visual.root.visible) {
        visual.root.updateMatrixWorld(true);
        const far = allLod || visual.root.position.distanceToSquared(eye) > LOD_DISTANCE * LOD_DISTANCE;
        if (visual.lod && far) {
          this.lodUnits += 1;
          this.unitInstances.add(`${visual.batchKey}|lod`, visual.root, visual.lod);
        } else {
          this.unitInstances.add(visual.batchKey, visual.root);
        }
      }
    }
    this.unitInstances.end(this.shadowsEnabled);
  }

  /** What a unit is doing, for its moving parts (miner drums, repair turrets, wings). */
  private unitMotionState(unit: UnitState, current: PositionSnapshot, previous: PositionSnapshot): PartMotionState {
    const moving = Math.hypot(current.x - previous.x, current.z - previous.z) > 1e-4 || unit.speed > 0.05;
    const job = unit.job;
    const mining = job?.kind === 'oreMiner' && job.stage === 'digging';
    let working = mining || job?.stage === 'loading' || job?.stage === 'unloading';
    const repair = this.world.unitTypes.get(unit.typeId)?.repair;
    if (!working && repair && unit.hp > 0 && !unit.transform) {
      // A repair vehicle works while anything friendly and hurt is in reach (as updateRepair heals).
      working = this.world.units.some((other) => {
        if (other.id === unit.id || other.hp <= 0 || !isAllied(this.world, unit.owner, other.owner)) {
          return false;
        }
        const max = this.world.unitTypes.get(other.typeId)?.hp ?? other.hp;
        return other.hp < max && Math.hypot(other.x - unit.x, other.z - unit.z) <= repair.radius;
      });
    }
    const top = this.world.unitTypes.get(unit.typeId)?.topSpeed ?? 0;
    const pace = top > 0 ? Math.min(1.2, Math.abs(unit.speed) / top) : moving ? 1 : 0;
    return { mining, working, moving, pace };
  }

  private syncStructures(world: WorldState): void {
    const alive = new Set<number>();
    for (const structure of world.structures) {
      if (structure.hp <= 0) {
        continue;
      }
      const type = world.structureTypes.get(structure.typeId);
      if (!type) {
        continue;
      }
      alive.add(structure.id);
      this.structureAlien.set(structure.id, type.faction === 'alien');
      let visual = this.structureVisuals.get(structure.id);
      if (!visual) {
        const size = Math.max(type.footprint.cellsX, type.footprint.cellsZ) * world.map.cellSize;
        const height = structureHeight(type.kind);
        const geometry = new THREE.BoxGeometry(size, height, size);
        const material = new THREE.MeshStandardMaterial({
          color: structure.owner === 1 ? FRIENDLY_STRUCTURE_COLOR : ENEMY_STRUCTURE_COLOR,
          roughness: 0.8,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        let barrel: THREE.Mesh | null = null;
        if (type.kind === 'turret') {
          barrel = new THREE.Mesh(
            new THREE.BoxGeometry(0.5, 0.5, size * 0.9),
            new THREE.MeshStandardMaterial({ color: 0x333a44 }),
          );
          barrel.position.set(0, height / 2 + 0.3, size * 0.35);
          const pivot = new THREE.Group();
          pivot.add(barrel);
          mesh.add(pivot);
          barrel.userData.pivot = pivot;
        }
        this.scene.add(mesh);
        let model: THREE.Object3D | null = null;
        let modelPivot: THREE.Object3D | null = null;
        let structureParts: PartMotion[] = [];
        const modelColors: StructureVisual['modelColors'] = [];
        const template = type.modelId ? this.templates.get(type.modelId) : undefined;
        if (template) {
          model = template.clone(true);
          // The Shard is a neutral force of nature: it keeps its own violet, never the enemy tint.
          const shard = type.modelId.startsWith('structure.shard.');
          cloneMaterials(model, !shard && isHostile(this.world, 1, structure.owner), this.colorBlind);
          model.scale.setScalar(size * 0.96);
          model.position.y = -height / 2;
          model.traverse((object) => {
            if (object instanceof THREE.Mesh) {
              object.castShadow = true;
              object.receiveShadow = true;
              const own: unknown = object.material;
              if (own instanceof THREE.MeshStandardMaterial) {
                modelColors.push({ material: own, base: own.color.clone() });
              }
            }
          });
          structureParts = collectPartMotions(model);
          modelPivot = pivotIsSpinner(structureParts) ? null : (model.getObjectByName('TurretPivot') ?? null);
          if (type.kind === 'pad') {
            // The model's ramp (+X) points along the pad's exit edge.
            model.rotation.y = -padFacing(structure);
          }
          mesh.add(model);
          // The box stays as the picking and selection body, but is not drawn.
          material.visible = false;
          if (barrel) {
            barrel.visible = false;
          }
        }
        visual = {
          mesh,
          height,
          barrel,
          baseColor: new THREE.Color(structure.owner === 1 ? FRIENDLY_STRUCTURE_COLOR : ENEMY_STRUCTURE_COLOR),
          model,
          modelPivot,
          modelColors,
          modelScale: model ? model.scale.x : 1,
          core: null,
          parts: structureParts,
        };
        const coreNode = model?.getObjectByName('Core');
        if (coreNode) {
          visual.core = { node: coreNode, baseY: coreNode.position.y, spin: 0, flare: 0 };
        }
        this.structureVisuals.set(structure.id, visual);
      }
      if (!this.structureSeen.has(structure.id)) {
        this.structureSeen.add(structure.id);
        // Anything already there on the first frame was placed with the map, not deployed.
        const start = this.frame > 1 ? this.foldStart(structure, type, visual) : null;
        if (start) {
          this.structureFolding.set(structure.id, { born: performance.now(), start });
        }
        if (this.frame > 1) {
          if (!start) {
            this.structureBorn.set(structure.id, performance.now());
          }
          const size = Math.max(type.footprint.cellsX, type.footprint.cellsZ) * world.map.cellSize;
          this.effects.deploy(
            structure.x,
            heightAt(world.map, structure.x, structure.z),
            structure.z,
            size,
            structure.typeId.includes('.alien.'),
          );
        }
      }
      const folding = this.structureFolding.get(structure.id);
      const unfoldData = visual.model?.userData.unfold as UnfoldData | undefined;
      const inner = visual.model?.children[0];
      const packWork = structure.work?.kind === 'pack' ? structure.work : null;
      if (packWork && unfoldData && inner && type.packSec > 0) {
        // Packing up plays the fold-out backwards, ending on the packed unit (which faces east).
        const start = this.foldStart(structure, type, visual);
        if (start) {
          applyUnfold(inner, unfoldData, packWork.left / type.packSec, { ...start, yaw: 0 }, -structure.turretHeading);
          this.structureFolding.set(structure.id, { born: Number.NEGATIVE_INFINITY, start });
        }
      } else if (folding && unfoldData && inner) {
        const t = (performance.now() - folding.born) / TOWER_UNFOLD_MS;
        if (applyUnfold(inner, unfoldData, t, folding.start, -structure.turretHeading)) {
          this.structureFolding.delete(structure.id);
        }
      } else {
        this.animateUnfold(structure.id, visual);
      }
      visual.mesh.position.set(
        structure.x,
        heightAt(world.map, structure.x, structure.z) + visual.height / 2,
        structure.z,
      );
      if (
        type.kind === 'pad' &&
        visual.model &&
        !this.padDecks.has(structure.id) &&
        !this.structureBorn.has(structure.id) &&
        !this.structureFolding.has(structure.id)
      ) {
        this.measurePadDeck(world, structure, visual, (Math.max(type.footprint.cellsX, type.footprint.cellsZ) * world.map.cellSize) / 2);
      }
      const damage = damageState(structure.hp, type.hp);
      const shade = damage === 'ok' ? 1 : damage === 'light' ? 0.8 : damage === 'heavy' ? 0.55 : 0.35;
      const material = visual.mesh.material;
      if (material instanceof THREE.MeshStandardMaterial) {
        material.color.copy(visual.baseColor).multiplyScalar(shade);
        material.emissive.setRGB(damage === 'critical' ? 0.35 : 0, 0, 0);
      }
      for (const entry of visual.modelColors) {
        entry.material.color.copy(entry.base).multiplyScalar(shade);
      }
      if (visual.core) {
        // Bob and spin; in the last half second before a shot the heart brightens and spins faster.
        const core = visual.core;
        const charging = structure.reloadLeft > 0 && structure.reloadLeft < 0.5 ? 1 - structure.reloadLeft / 0.5 : 0;
        core.flare = Math.max(core.flare * 0.9, charging);
        core.spin += 0.012 + core.flare * 0.08;
        const t = performance.now() / 1000;
        core.node.rotation.y = core.spin;
        core.node.position.y = core.baseY + Math.sin(t * 1.3 + structure.id) * 0.06;
        core.node.scale.setScalar(1 + core.flare * 0.18);
      }
      if (visual.parts.length > 0 && !this.structureFolding.has(structure.id)) {
        // Packed structures only start their motion once fully unfolded.
        updatePartMotions(
          visual.parts,
          { mining: structure.depositId != null, working: structure.depositId != null, moving: false },
          this.motionDt,
        );
      }
      if (visual.modelPivot && !this.structureFolding.has(structure.id)) {
        // Model weapons point along +X, like the units: same heading convention as unit turrets.
        visual.modelPivot.rotation.y = -structure.turretHeading;
      }
      const pivot = visual.barrel?.userData.pivot as THREE.Object3D | undefined;
      if (pivot) {
        pivot.rotation.y = structure.turretHeading;
      }
      const packing = structure.work?.kind === 'pack' || structure.work?.kind === 'dismantle';
      visual.mesh.scale.y = packing && !unfoldData ? 0.7 : 1;
    }
    this.syncRubble(world);
    for (const [id, visual] of this.structureVisuals) {
      if (!alive.has(id)) {
        this.structureDied(world, id, visual);
        this.disposeStructureVisual(visual);
        this.structureVisuals.delete(id);
        this.structureFolding.delete(id);
        this.padDecks.delete(id);
      }
    }
    for (const id of this.deployingUnits.keys()) {
      if (!world.units.some((unit) => unit.id === id && unit.transform)) {
        this.deployingUnits.delete(id);
      }
    }
  }

  /**
   * Where a fold-out tower starts: the size and facing of the packed unit it came from. Null when
   * the model has no fold data or the packed unit's model is not loaded (the plain rise plays).
   */
  private foldStart(
    structure: { x: number; z: number },
    type: SimStructureType,
    visual: StructureVisual,
  ): UnfoldStart | null {
    // The packed vehicle it came from: its repack type, or (radar, airfield) the one that lands as it.
    const packedId =
      type.packedUnitId ?? [...this.world.unitTypes.values()].find((unit) => unit.deploysTo === type.id)?.id ?? null;
    if (!visual.model?.userData.unfold || !packedId) {
      return null;
    }
    const unitType = this.world.unitTypes.get(packedId);
    const unitModel = unitType?.modelId ? this.templates.get(unitType.modelId)?.children[0] : undefined;
    if (!unitType || !unitModel || visual.modelScale <= 0) {
      return null;
    }
    let heading = 0;
    for (const entry of this.deployingUnits.values()) {
      if (Math.abs(entry.x - structure.x) < 0.05 && Math.abs(entry.z - structure.z) < 0.05) {
        heading = entry.heading;
        break;
      }
    }
    return {
      packedScale: (unitModel.scale.x * (unitType.visualScale ?? 1)) / visual.modelScale,
      yaw: -heading,
    };
  }

  private readonly rubbleMeshes: THREE.Mesh[] = [];

  private syncRubble(world: WorldState): void {
    while (this.rubbleMeshes.length < world.rubble.length) {
      const mesh = new THREE.Mesh(
        new THREE.CylinderGeometry(1, 1.2, 0.5, 7),
        new THREE.MeshStandardMaterial({ color: 0x4a4540, roughness: 1 }),
      );
      this.scene.add(mesh);
      this.rubbleMeshes.push(mesh);
    }
    while (this.rubbleMeshes.length > world.rubble.length) {
      const mesh = this.rubbleMeshes.pop();
      if (mesh) {
        this.scene.remove(mesh);
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
    }
    for (let i = 0; i < world.rubble.length; i += 1) {
      const item = world.rubble[i];
      const mesh = this.rubbleMeshes[i];
      if (item && mesh) {
        mesh.scale.set(item.radius, 1, item.radius);
        mesh.position.set(item.x, heightAt(world.map, item.x, item.z) + 0.2, item.z);
      }
    }
  }

  // ---- Landing pad traffic -------------------------------------------------------------
  // Deliveries descend onto the pad (sim: DropOrder.landingSec), workers hand cargo across to the
  // pad's lift (job stage 'unloading'), and the cargo then rises away (drop beams of kind ore/metal).
  private readonly landingVisuals = new Map<number, THREE.Object3D>();
  private readonly cargoVisuals = new Map<string, THREE.Mesh>();
  private cargoGeometry: THREE.BoxGeometry | null = null;
  private readonly cargoMaterials = new Map<string, THREE.Material>();

  private cargoMaterial(kind: 'ore' | 'metal' | 'kit'): THREE.Material {
    let material = this.cargoMaterials.get(kind);
    if (!material) {
      const glow = kind === 'ore' ? 0x5a2a08 : kind === 'metal' ? 0x0c3442 : 0x1a2208;
      material = new THREE.MeshStandardMaterial({
        map: cargoTexture(kind),
        emissive: glow,
        emissiveIntensity: 0.6,
        roughness: 0.55,
        metalness: 0.45,
      });
      this.cargoMaterials.set(kind, material);
    }
    return material;
  }

  private oreHeapMaterial: THREE.Material | null = null;

  /** A mound of loose ore about `size` wide. */
  private oreHeap(size: number): THREE.Mesh {
    if (!this.oreHeapMaterial) {
      this.oreHeapMaterial = new THREE.MeshStandardMaterial({
        vertexColors: true,
        flatShading: true,
        roughness: 0.75,
        metalness: 0.25,
        emissive: 0x2a1204,
      });
    }
    const mesh = new THREE.Mesh(buildOreHeapGeometry(), this.oreHeapMaterial);
    mesh.scale.setScalar(size / 2);
    mesh.castShadow = true;
    mesh.name = 'OreHeap';
    return mesh;
  }

  private cargoMesh(kind: 'ore' | 'metal' | 'kit', size: number): THREE.Mesh {
    if (kind === 'ore') {
      return this.oreHeap(size * 1.2);
    }
    if (!this.cargoGeometry) {
      this.cargoGeometry = new THREE.BoxGeometry(1, 1, 1);
    }
    const mesh = new THREE.Mesh(this.cargoGeometry, this.cargoMaterial(kind));
    mesh.scale.set(size, size * 0.75, size);
    mesh.castShadow = true;
    return mesh;
  }

  private makeLandingVisual(world: WorldState, order: DropOrder): THREE.Object3D {
    const group = new THREE.Group();
    let body: THREE.Object3D;
    if (order.itemKind === 'unit') {
      const template = this.templateFor(order.itemId);
      if (template) {
        body = template.clone(true);
        body.scale.setScalar(world.unitTypes.get(order.itemId)?.visualScale ?? 1);
      } else {
        body = this.prepareFallback();
      }
      cloneMaterials(body, isHostile(world, 1, order.owner), this.colorBlind);
      body.userData.ownMaterials = true;
    } else {
      body = this.cargoMesh('kit', 3);
      body.position.y = 1.1;
    }
    group.add(body);
    const human = world.factions.find((entry) => entry.player === order.owner)?.faction !== 'alien';
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(1.4, 6, 12, 1, true),
      new THREE.MeshBasicMaterial({
        color: human ? 0x66e0ff : 0xffc24a,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    flame.rotation.x = Math.PI; // point down
    flame.position.y = -3;
    flame.name = 'LandingFlame';
    group.add(flame);
    this.scene.add(group);
    return group;
  }

  private disposeLandingVisual(group: THREE.Object3D): void {
    this.scene.remove(group);
    const shared = new Set<unknown>(this.cargoMaterials.values());
    group.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        const geometry: unknown = object.geometry;
        if (object.name === 'LandingFlame' && geometry instanceof THREE.BufferGeometry) {
          geometry.dispose();
        }
        const material: unknown = object.material;
        if (material instanceof THREE.Material && !shared.has(material)) {
          material.dispose();
        }
      }
    });
  }

  private syncPadTraffic(world: WorldState, alpha: number): void {
    const tickSec = 1 / SIM_TICK_HZ;
    const live = new Set<number>();
    for (const order of world.dropQueue) {
      if (order.landingSec === undefined) {
        continue;
      }
      const pad = world.structures.find((item) => item.id === order.padId && item.hp > 0);
      if (!pad || (order.owner !== 1 && !this.structureVisuals.has(pad.id))) {
        continue;
      }
      live.add(order.id);
      let visual = this.landingVisuals.get(order.id);
      if (!visual) {
        visual = this.makeLandingVisual(world, order);
        this.landingVisuals.set(order.id, visual);
      }
      const t = Math.min(1, Math.max(0, (order.landingSec + alpha * tickSec) / PAD_LAND_SEC));
      const eased = 1 - (1 - t) ** 3; // fast from high up, settling gently onto the deck
      const deck = this.padDeckTop(world, pad);
      visual.position.set(pad.x, deck + (1 - eased) * 42, pad.z);
      visual.rotation.y = -padFacing(pad);
      const flame = visual.getObjectByName('LandingFlame');
      if (flame) {
        flame.scale.setScalar(Math.max(0.05, 1 - t * 0.8));
        flame.visible = t < 0.98;
      }
    }
    for (const [id, visual] of this.landingVisuals) {
      if (!live.has(id)) {
        this.disposeLandingVisual(visual);
        this.landingVisuals.delete(id);
      }
    }

    // Cargo: worker -> pad lift while unloading, then rising off the lift.
    const liveCargo = new Set<string>();
    for (const unit of world.units) {
      const job = unit.job;
      if (!job || job.stage !== 'unloading' || unit.hp <= 0) {
        continue;
      }
      const pad = world.structures.find((item) => item.id === job.dockPadId && item.hp > 0);
      if (!pad) {
        continue;
      }
      const key = `u${unit.id}`;
      liveCargo.add(key);
      const kind = job.cargo ?? (job.kind === 'oreMiner' ? 'ore' : 'metal');
      let mesh = this.cargoVisuals.get(key);
      if (!mesh) {
        mesh = this.cargoMesh(kind, 1.6);
        this.scene.add(mesh);
        this.cargoVisuals.set(key, mesh);
      }
      const layout = padLayout(world, pad);
      const dock = layout.docks[job.dockSide ?? 0] ?? layout.docks[0]!;
      const left = Math.max(0, (job.unloadLeft ?? PAD_UNLOAD_SEC) - alpha * tickSec);
      const t = Math.min(1, Math.max(0, 1 - left / PAD_UNLOAD_SEC));
      const x = unit.x + (dock.liftX - unit.x) * t;
      const z = unit.z + (dock.liftZ - unit.z) * t;
      const ground = heightAt(world.map, x, z);
      mesh.position.set(x, ground + 1.6 + Math.sin(t * Math.PI) * 1.8, z);
      mesh.rotation.y = -layout.facing;
    }
    world.dropBeams.forEach((beam, index) => {
      if (beam.kind !== 'ore' && beam.kind !== 'metal') {
        return;
      }
      const key = `b${index}:${beam.kind}`;
      liveCargo.add(key);
      let mesh = this.cargoVisuals.get(key);
      if (!mesh) {
        mesh = this.cargoMesh(beam.kind, 1.6);
        this.scene.add(mesh);
        this.cargoVisuals.set(key, mesh);
      }
      const total = beam.total ?? 1;
      const t = Math.min(1, Math.max(0, 1 - (beam.ttl - alpha * tickSec) / total));
      const ground = heightAt(world.map, beam.x, beam.z);
      mesh.position.set(beam.x, ground + 1.6 + t * t * 34, beam.z);
      mesh.rotation.y = t * 2.5;
    });
    for (const [key, mesh] of this.cargoVisuals) {
      if (!liveCargo.has(key)) {
        this.scene.remove(mesh);
        this.cargoVisuals.delete(key);
      }
    }
  }

  // ---- Worker status -------------------------------------------------------------------
  // Miners show the ore in their hopper (and shake while grinding), haulers carry their crates or
  // metal containers on their back, and full crates stack up beside each ore deposit.
  private readonly workerCargo = new Map<string, THREE.Mesh>();
  private readonly unitTopCache = new Map<string, { top: number; ax: number; az: number; length: number }>();

  // Where cargo sits on a unit model, in the unit's own frame: the deck height (a little under the
  // highest point, which is usually an antenna) and the middle of the body.
  private unitTop(typeId: string, root: THREE.Object3D): { top: number; ax: number; az: number; length: number } {
    let top = this.unitTopCache.get(typeId);
    if (!top) {
      const saved = root.rotation.y;
      root.rotation.y = 0;
      root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root);
      root.rotation.y = saved;
      root.updateMatrixWorld(true);
      top = box.isEmpty()
        ? { top: 1.2, ax: 0, az: 0, length: TANK_LENGTH }
        : {
            top: Math.max(0.6, (box.max.y - root.position.y) * 0.78),
            ax: (box.min.x + box.max.x) / 2 - root.position.x,
            az: (box.min.z + box.max.z) / 2 - root.position.z,
            length: box.max.x - box.min.x,
          };
      this.unitTopCache.set(typeId, top);
    }
    return top;
  }

  private workerMesh(live: Set<string>, key: string, make: () => THREE.Mesh): THREE.Mesh {
    live.add(key);
    let mesh = this.workerCargo.get(key);
    if (!mesh) {
      mesh = make();
      this.scene.add(mesh);
      this.workerCargo.set(key, mesh);
    }
    return mesh;
  }

  private syncWorkerCargo(world: WorldState, alpha: number): void {
    const live = new Set<string>();
    const time = (world.tick + alpha) / SIM_TICK_HZ;
    for (const unit of world.units) {
      const job = unit.job;
      const visual = this.unitRoots.get(unit.id);
      if (!job || unit.hp <= 0 || !visual || !visual.root.visible) {
        continue;
      }
      const type = world.unitTypes.get(unit.typeId);
      const anchor = this.unitTop(unit.typeId, visual.root);
      const top = anchor.top;
      const turn = visual.root.rotation.y;
      // Both factions' miners carry their hopper (bin or ore sac) and haulers their bed behind the
      // middle of the body.
      const ax = anchor.ax - anchor.length * (job.kind === 'oreMiner' ? 0.22 : 0.17);
      const base = new THREE.Vector3(
        visual.root.position.x + Math.cos(turn) * ax + Math.sin(turn) * anchor.az,
        visual.root.position.y,
        visual.root.position.z - Math.sin(turn) * ax + Math.cos(turn) * anchor.az,
      );
      if (job.kind === 'oreMiner') {
        const hopper = Math.max(ORE_CRATE_SIZE, type?.carryCapacity ?? ORE_CRATE_SIZE);
        const fill = Math.min(1, job.load / hopper);
        const grinding = job.stage === 'digging';
        if (fill > 0.02 || grinding) {
          const heap = this.workerMesh(live, `m${unit.id}`, () => this.oreHeap(2));
          // The heap rises out of the bin as it fills; grinding makes it churn.
          const size = 0.5 + fill * 0.9;
          heap.scale.set(size * 1.2, 0.35 + fill * 0.9, size);
          const shake = grinding ? Math.sin(time * 31 + unit.id) * 0.05 : 0;
          heap.position.set(base.x + shake, base.y + top - 0.45 + fill * 0.25, base.z - shake);
          heap.rotation.set(0, visual.root.rotation.y + (grinding ? Math.sin(time * 9) * 0.15 : 0), 0);
        }
        // Grinding: the miner body judders while it chews through the deposit.
        if (grinding) {
          visual.root.position.y += Math.abs(Math.sin(time * 27 + unit.id)) * 0.08;
        }
        continue;
      }
      if (job.load > 0 && job.stage !== 'unloading') {
        const heading = visual.root.rotation.y;
        const fill = Math.min(1, job.load / Math.max(ORE_CRATE_SIZE, type?.carryCapacity ?? ORE_CRATE_SIZE));
        if ((job.cargo ?? 'metal') === 'ore') {
          // Raw ore heaped in the hauler's bed, bigger the more it carries.
          const heap = this.workerMesh(live, `t${unit.id}:ore`, () => this.oreHeap(2));
          heap.scale.set(0.75 + fill * 0.55, 0.55 + fill * 0.65, 0.6 + fill * 0.35);
          heap.position.set(base.x, base.y + top - 0.8, base.z);
          heap.rotation.y = heading;
        } else {
          const crates = Math.min(3, Math.max(1, Math.round(job.load / ORE_CRATE_SIZE)));
          for (let i = 0; i < crates; i += 1) {
            const crate = this.workerMesh(live, `t${unit.id}:${i}`, () => this.cargoMesh('metal', 1.2));
            const along = (i - (crates - 1) / 2) * 1.3;
            crate.position.set(
              base.x + Math.cos(heading) * along,
              base.y + top + 0.3,
              base.z - Math.sin(heading) * along,
            );
            crate.rotation.y = heading;
          }
        }
      }
    }
    // Dug ore piles up in a loose mound beside the deposit (one per side), growing as miners dump
    // their bins and shrinking as haulers scoop it away.
    for (const deposit of world.deposits) {
      for (const pile of deposit.crates ?? []) {
        const fill = Math.min(1, crateOre(deposit, pile.owner) / (ORE_MAX_CRATES * ORE_CRATE_SIZE));
        const pad = world.structures.find((item) => item.owner === pile.owner && item.hp > 0);
        const towards = pad ? Math.atan2(pad.z - deposit.z, pad.x - deposit.x) : pile.owner;
        const x = deposit.x + Math.cos(towards) * 2.8;
        const z = deposit.z + Math.sin(towards) * 2.8;
        const heap = this.workerMesh(live, `d${deposit.id}:${pile.owner}`, () => this.oreHeap(2));
        const spread = 0.8 + fill * 1.0;
        heap.scale.set(spread, 0.5 + fill * 1.1, spread * 0.9);
        heap.position.set(x, heightAt(world.map, x, z) - 0.05, z);
        heap.rotation.y = -towards + deposit.id;
      }
    }
    for (const [key, mesh] of this.workerCargo) {
      if (!live.has(key)) {
        this.scene.remove(mesh);
        this.workerCargo.delete(key);
      }
    }
  }

  private syncDropBeams(world: WorldState): void {
    const arrivals = world.dropBeams.filter((beam) => (beam.kind ?? 'arrive') === 'arrive');
    while (this.beamPool.length < arrivals.length) {
      const geometry = new THREE.CylinderGeometry(1.5, 1.5, 20, 10);
      const material = new THREE.MeshBasicMaterial({
        color: DROP_BEAM_COLOR,
        transparent: true,
        opacity: 0.6,
      });
      const mesh = new THREE.Mesh(geometry, material);
      this.scene.add(mesh);
      this.beamPool.push(mesh);
    }
    while (this.beamPool.length > arrivals.length) {
      const mesh = this.beamPool.pop();
      if (!mesh) {
        continue;
      }
      this.scene.remove(mesh);
      mesh.geometry.dispose();
      const material = mesh.material;
      if (material instanceof THREE.Material) {
        material.dispose();
      }
    }
    for (let index = 0; index < arrivals.length; index += 1) {
      const beam = arrivals[index];
      const mesh = this.beamPool[index];
      if (!beam || !mesh) {
        continue;
      }
      mesh.position.set(beam.x, heightAt(world.map, beam.x, beam.z) + 10, beam.z);
      const material = mesh.material;
      if (material instanceof THREE.MeshBasicMaterial) {
        material.opacity = Math.min(0.6, Math.max(0, beam.ttl));
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
        this.unitGroundAt(unit.x, unit.z) + 0.06,
        unit.z,
      );
    }
  }

  /**
   * A flat green footprint where each of your packed buildings will unpack, brighter while it is
   * selected, so a redirect (tap the ground with it selected) shows where it will stand.
   */
  private syncUnpackSpots(): void {
    const selected = new Set(this.selection);
    const live = new Set<number>();
    for (const unit of this.world.units) {
      const target = unit.deployTarget;
      const typeId = target && unit.owner === 1 ? this.world.unitTypes.get(unit.typeId)?.deploysTo : undefined;
      const type = typeId ? this.world.structureTypes.get(typeId) : undefined;
      if (!target || !type) {
        continue;
      }
      live.add(unit.id);
      let spot = this.unpackSpots.get(unit.id);
      if (!spot) {
        const size = Math.max(type.footprint.cellsX, type.footprint.cellsZ) * this.world.map.cellSize;
        const geometry = new THREE.PlaneGeometry(size, size);
        const material = new THREE.MeshBasicMaterial({
          color: PLACEMENT_VALID_COLOR,
          transparent: true,
          opacity: 0.3,
          depthWrite: false,
          side: THREE.DoubleSide,
        });
        spot = new THREE.Mesh(geometry, material);
        spot.rotation.x = -Math.PI / 2;
        this.scene.add(spot);
        this.unpackSpots.set(unit.id, spot);
      }
      spot.position.set(target.x, heightAt(this.world.map, target.x, target.z) + 0.08, target.z);
      const material = spot.material;
      if (material instanceof THREE.MeshBasicMaterial) {
        material.opacity = selected.has(unit.id) ? 0.55 : 0.25;
      }
    }
    for (const [id, spot] of this.unpackSpots) {
      if (!live.has(id)) {
        this.scene.remove(spot);
        spot.geometry.dispose();
        const material = spot.material;
        if (material instanceof THREE.Material) {
          material.dispose();
        }
        this.unpackSpots.delete(id);
      }
    }
  }

  private syncOrderLines(): void {
    const selected = new Set(this.selection);
    for (const [id, line] of this.orderLines) {
      if (!selected.has(id)) {
        this.scene.remove(line);
        line.geometry.dispose();
        this.orderLines.delete(id);
      }
    }

    for (const id of this.selection) {
      const unit = this.world.units.find((item) => item.id === id);
      if (!unit || unit.path.length === 0) {
        const line = this.orderLines.get(id);
        if (line) {
          this.scene.remove(line);
          line.geometry.dispose();
          this.orderLines.delete(id);
        }
        continue;
      }

      const points = [
        new THREE.Vector3(
          unit.x,
          heightAt(this.world.map, unit.x, unit.z) + ORDER_LINE_Y,
          unit.z,
        ),
        ...unit.path.map((point) =>
          new THREE.Vector3(
            point.x,
            heightAt(this.world.map, point.x, point.z) + ORDER_LINE_Y,
            point.z,
          ),
        ),
      ];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      let line = this.orderLines.get(id);
      if (!line) {
        const material = new THREE.LineBasicMaterial({
          color: ORDER_LINE_COLOR,
          transparent: true,
          opacity: 0.85,
        });
        line = new THREE.Line(geometry, material);
        this.scene.add(line);
        this.orderLines.set(id, line);
      } else {
        line.geometry.dispose();
        line.geometry = geometry;
      }
    }
  }

  private syncHealthBars(): void {
    const alive = new Set<number>();
    for (const unit of this.world.units) {
      const type = this.world.unitTypes.get(unit.typeId);
      const maxHp = type?.hp ?? unit.hp;
      const selected = this.selection.includes(unit.id);
      if (!selected && this.healthBarsMode === 'damaged' && unit.hp >= maxHp) {
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

  /**
   * Floating status tags over the player's workers ("Mining 18/30", "Hauler · to pad"), shown
   * while a worker is selected or the camera is zoomed in, so mining is readable at a glance.
   */
  private syncWorkerLabels(): void {
    const zoomedIn = this.rtsCamera.distance <= WORKER_LABEL_ZOOM;
    const shown = new Set<number>();
    for (const unit of this.world.units) {
      if (unit.owner !== 1 || unit.hp <= 0) {
        continue;
      }
      const type = this.world.unitTypes.get(unit.typeId);
      if (!type?.workerKind || (!zoomedIn && !this.selection.includes(unit.id))) {
        continue;
      }
      const screen = this.projectPoint(unit.x, heightAt(this.world.map, unit.x, unit.z) + 3.2, unit.z);
      if (!screen) {
        continue;
      }
      shown.add(unit.id);
      let label = this.workerLabels.get(unit.id);
      if (!label) {
        label = document.createElement('div');
        label.className = `worker-label ${type.workerKind === 'oreMiner' ? 'miner' : 'hauler'}`;
        this.overlay.append(label);
        this.workerLabels.set(unit.id, label);
      }
      const text = workerLabelText(type.workerKind, type.carryCapacity, unit.job);
      if (label.textContent !== text) {
        label.textContent = text;
      }
      label.style.left = `${screen.x}px`;
      label.style.top = `${screen.y - 12}px`;
    }
    for (const [id, label] of this.workerLabels) {
      if (!shown.has(id)) {
        label.remove();
        this.workerLabels.delete(id);
      }
    }
  }

  private syncProjectiles(): void {
    const ids = new Set(this.world.projectiles.map((projectile) => projectile.id));
    for (const [id, visual] of this.projectileVisuals) {
      if (!ids.has(id)) {
        const at = visual.object.position;
        const ground = heightAt(this.world.map, at.x, at.z);
        this.effects.impact(visual.kind, at.x, at.y, at.z, ground, visual.splash, visual.alien);
        if (visual.kind === 'shard' && visual.from) {
          // A fading violet afterimage of the lance's path.
          this.effects.shardLance(visual.from, at, 0.35, 0.3, visual.seed ?? 0);
        }
        this.scene.remove(visual.object);
        this.effects.disposeProjectileMesh(visual.object);
        this.projectileVisuals.delete(id);
      }
    }

    for (const projectile of this.world.projectiles) {
      let visual = this.projectileVisuals.get(projectile.id);
      if (!visual) {
        // Where the shot visibly leaves from: an aircraft fires from up in the air, so the visual
        // starts at the aircraft and closes onto the sim's path by the time it reaches the target.
        const shooter = projectile.shooterId === undefined ? undefined : this.unitRoots.get(projectile.shooterId);
        const airborne = shooter !== undefined && shooter.lift > 0.5;
        const offset = airborne ? shooter.root.position.y - 0.25 - projectile.y : 0;
        const human = this.world.factions.find((item) => item.player === projectile.owner)?.faction !== 'alien';
        const object = this.effects.projectileMesh(projectile.kind, human);
        this.scene.add(object);
        visual = {
          object,
          kind: projectile.kind,
          splash: projectile.splashRadius,
          offset,
          startX: projectile.x,
          startZ: projectile.z,
          shooterId: projectile.shooterId,
          aim: projectile.aimDistance ?? 0,
          alien: !human,
        };
        this.projectileVisuals.set(projectile.id, visual);
        this.effects.muzzle(projectile.x, projectile.y + offset, projectile.z, projectile.kind, !human, projectile.vx, projectile.vz);
        if (shooter && !airborne) {
          shooter.recoil = 1;
        }
      }
      const travelled = Math.hypot(projectile.x - visual.startX, projectile.z - visual.startZ);
      const progress = visual.aim > 0.01 ? Math.min(1, travelled / visual.aim) : 1;
      // Bombs fall (slow at first, then faster); energy shots fly straight from the gun.
      const left = visual.kind === 'bombs' ? 1 - progress * progress : 1 - progress;
      const y = projectile.y + visual.offset * left;
      const previous = visual.object.position.clone();
      visual.object.position.set(projectile.x, y, projectile.z);
      const direction = new THREE.Vector3().subVectors(visual.object.position, previous);
      if (direction.lengthSq() < 1e-6 || previous.lengthSq() === 0) {
        direction.set(projectile.vx, projectile.vy, projectile.vz);
      }
      if (direction.lengthSq() > 0.000001) {
        visual.object.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), direction.normalize());
      }
      // The Shard's lance runs from its heart to the shot's head, kinks re-rolled a few times a shot.
      if (visual.kind === 'shard') {
        const from = this.shardHeart(visual.shooterId);
        if (from) {
          visual.from = from;
          this.effects.shardLance(from, visual.object.position, 1, 0.05, visual.seed ?? 0);
          if (performance.now() - (visual.rolled ?? 0) > 110) {
            visual.seed = Math.random() * 1000;
            visual.rolled = performance.now();
          }
        }
      }
      // Lightning and the ground beam are drawn from the gun to the shot's head every frame.
      if (visual.kind === 'lightning' || visual.kind === 'ground_beam') {
        const shooter = visual.shooterId === undefined ? undefined : this.unitRoots.get(visual.shooterId);
        if (shooter?.root.visible) {
          const from = shooter.root.position.clone();
          from.y -= visual.kind === 'ground_beam' ? 0.5 : 0.2;
          if (visual.kind === 'lightning') {
            this.effects.lightning(from, visual.object.position, 0xffd27a, 0.05, 10, 0.55);
          } else {
            this.effects.beam(from, visual.object.position, 0.9, 0.05);
          }
        }
      }
    }
  }

  /** World position of a Shard structure's heart (its Core node), for the lance to start from. */
  private shardHeart(structureId: number | undefined): THREE.Vector3 | null {
    if (structureId === undefined) {
      return null;
    }
    const core = this.structureVisuals.get(structureId)?.core;
    if (!core) {
      return null;
    }
    core.flare = 1;
    return core.node.getWorldPosition(new THREE.Vector3());
  }

  private syncWrecks(): void {
    const now = performance.now();
    const dt = this.lastFrameAt === 0 ? 1 / 60 : Math.min(0.1, (now - this.lastFrameAt) / 1000);
    this.lastFrameAt = now;
    this.frameDt = Math.min(0.05, dt);
    this.wreckField.update(dt, this.shadowsEnabled);
  }

  /** A unit just left the world: if the sim left a fresh wreck where it was, it was destroyed. */
  private unitDied(visual: UnitVisual): void {
    const at = visual.root.position;
    const wreck = this.world.wrecks.find(
      (item) => item.ttl > WRECK_TTL_SEC - 4 && Math.hypot(item.x - at.x, item.z - at.z) < 4,
    );
    if (!wreck || !visual.root.visible) {
      return;
    }
    const size = visual.root.scale.y;
    const gy = this.unitGroundAt(wreck.x, wreck.z);
    const air = visual.lift > 0.5;
    this.effects.unitDeath(at.x, at.y, at.z, gy, size, visual.alien, air);
    if (this.templateFor(visual.typeId)) {
      visual.root.position.set(wreck.x, at.y, wreck.z);
      visual.root.updateMatrixWorld(true);
      this.wreckField.add(visual.root, visual.typeId, gy, size, air);
    }
  }

  /** A structure just left the world: destroyed ones (they leave rubble) go up in a big blast. */
  private structureDied(world: WorldState, id: number, visual: StructureVisual): void {
    const alien = this.structureAlien.get(id) ?? false;
    this.structureAlien.delete(id);
    const at = visual.mesh.position;
    const rubble = world.rubble.find((item) => Math.hypot(item.x - at.x, item.z - at.z) < 1);
    if (!rubble) {
      return;
    }
    const gy = heightAt(world.map, rubble.x, rubble.z);
    const width = Math.max(2, rubble.radius * 1.4);
    this.effects.structureDeath(rubble.x, gy, rubble.z, width, alien);
    this.effects.addBurner(rubble.x, gy + 0.6, rubble.z, Math.min(2.5, width * 0.4), 8, 22);
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

  private placementGhostType(): SimStructureType | null {
    return this.placementType;
  }
}
