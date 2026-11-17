// Map dressing: the ore and metal site models, and scattered rocks, cliff chunks and plants.
//
// Everything here is decoration drawn from the map seed; none of it touches the sim. Anything solid
// (rocks, cliff chunks, slabs, dead trees, alien fronds) sits only on ground too steep to drive, and
// only where the whole prop stays on that ground, so a tank never drives through one. Drivable
// ground gets only soft, low clutter (grass, small bushes) that units can roll over. Props are hidden round deposits and under structures, and the set is rebuilt when
// structures appear or go.
//
// Each prop model is one mesh with one material, so each prop kind is a single InstancedMesh.
import * as THREE from "three";
import { heightAt, isWaterAt, slopeAt, type MapDef } from "../sim/map";
import { MAX_SLOPE } from "../sim/tuning";
import type { DepositState, WorldState } from "../sim/types";
import { groundNoiseAt } from "./groundDetail";
import { distanceOutside, groundHeightAt } from "./outerLand";

export const PROP_IDS = [
  "prop.nature.boulder",
  "prop.nature.rock_cluster",
  "prop.nature.slab",
  "prop.nature.cliff",
  "prop.nature.shrub",
  "prop.nature.grass",
  "prop.nature.dead_tree",
  "prop.nature.tendril",
] as const;
export const DEPOSIT_MODEL_IDS = {
  ore: "prop.deposit.ore",
  metal: "prop.deposit.metal",
} as const;
const LOD_SUFFIX = ".lod";
/** Low-detail versions: drawn away from the camera and on the lower quality levels. */
export const DEPOSIT_LOD_IDS = {
  ore: `${DEPOSIT_MODEL_IDS.ore}${LOD_SUFFIX}`,
  metal: `${DEPOSIT_MODEL_IDS.metal}${LOD_SUFFIX}`,
} as const;
export const LANDSCAPE_LOD_IDS: readonly string[] = [
  ...PROP_IDS.map((id) => `${id}${LOD_SUFFIX}`),
  DEPOSIT_LOD_IDS.ore,
  DEPOSIT_LOD_IDS.metal,
];

type PropId = (typeof PROP_IDS)[number];

/** Model width is about 7 m; sites are drawn about 4.5 m across. */
const DEPOSIT_SCALE = 0.6;
/** Crystals shrink to this fraction of full size as the site runs dry. */
const DEPOSIT_MIN_GEM = 0.35;
const DEPOSIT_CLEAR = 5.5;
const STRUCTURE_CLEAR = 6;

export interface FogUniforms {
  uFog: { value: THREE.DataTexture | null };
  uFogOn: { value: number };
  uFogSize: { value: number };
}

interface Placement {
  prop: PropId;
  x: number;
  z: number;
  matrix: THREE.Matrix4;
  /** Per-instance colour multiplier, so repeated props are not identical copies. */
  tint: THREE.Color;
  /** Past the map edge: drawn without shadows (they would fall outside the shadow map anyway). */
  outside?: boolean;
}

interface PropTemplate {
  geometry: THREE.BufferGeometry;
  material: THREE.Material;
  /** The mesh's own transform inside the model file. */
  local: THREE.Matrix4;
}

function hash(ix: number, iz: number, seed: number, salt: number): number {
  let h =
    Math.imul(ix, 374761393) ^
    Math.imul(iz, 668265263) ^
    Math.imul(seed + salt * 977, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** Same darkening as the terrain under unexplored fog, for instanced props. */
export function addFogHook(
  material: THREE.Material,
  fog: FogUniforms,
  instanced: boolean,
  foliage = false,
): void {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uFog = fog.uFog;
    shader.uniforms.uFogOn = fog.uFogOn;
    shader.uniforms.uFogSize = fog.uFogSize;
    const world = instanced
      ? "vFogXZ = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xz;"
      : "vFogXZ = (modelMatrix * vec4(transformed, 1.0)).xz;";
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec2 vFogXZ;")
      .replace("#include <begin_vertex>", `#include <begin_vertex>\n${world}`);
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        "#include <common>\nvarying vec2 vFogXZ;\nuniform sampler2D uFog;\nuniform float uFogOn;\nuniform float uFogSize;",
      )
      .replace(
        "#include <color_fragment>",
        "#include <color_fragment>\nfloat fogLevel = uFogOn > 0.5 ? texture2D(uFog, vFogXZ / uFogSize + 0.5).r : 1.0;\ndiffuseColor.rgb *= fogLevel;",
      )
      // Glowing parts must go dark under fog too, or alien fronds shine out of unexplored ground.
      .replace(
        "#include <emissivemap_fragment>",
        "#include <emissivemap_fragment>\ntotalEmissiveRadiance *= fogLevel;",
      );
    if (foliage) {
      // Grass and leaves are lit mostly as if they faced the sky, the usual foliage trick: thin
      // blades seen edge-on or from behind otherwise go almost black against the lit ground.
      shader.fragmentShader = shader.fragmentShader.replace(
        "#include <normal_fragment_maps>",
        "#include <normal_fragment_maps>\nnormal = normalize(mix(normal, normalize((viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz), 0.65));",
      );
    }
  };
  material.customProgramCacheKey = () =>
    (instanced ? "tcFogInst" : "tcFog") + (foliage ? "Fol" : "");
}

const ROCKS: ReadonlySet<PropId> = new Set<PropId>([
  "prop.nature.boulder",
  "prop.nature.rock_cluster",
  "prop.nature.slab",
  "prop.nature.cliff",
]);
const PLANTS: ReadonlySet<PropId> = new Set<PropId>([
  "prop.nature.grass",
  "prop.nature.shrub",
]);
/** Plant colour multiplier on lush and on dry ground. */
const PLANT_LUSH = new THREE.Color(1.1, 1.12, 0.95);
const PLANT_DRY = new THREE.Color(1.38, 1.24, 0.86);

/**
 * A colour multiplier for one prop: rocks vary in lightness and lean warm or cool, plants take the
 * dryness of the ground under them (from the same noise the terrain shader uses), everything varies
 * a little in brightness.
 */
function propTint(prop: PropId, x: number, z: number, seed: number): THREE.Color {
  const ix = Math.floor(x * 8);
  const iz = Math.floor(z * 8);
  const light = hash(ix, iz, seed, 21);
  const hue = hash(ix, iz, seed, 22) * 2 - 1;
  if (ROCKS.has(prop)) {
    const b = 0.8 + light * 0.34;
    return new THREE.Color(b * (1 + 0.06 * hue), b, b * (1 - 0.08 * hue));
  }
  if (PLANTS.has(prop)) {
    const dry = groundNoiseAt(seed, x, z).dry;
    // Shrubs are broad and catch more light than grass blades: a smaller lift.
    const b = (0.86 + light * 0.28) * (prop === "prop.nature.shrub" ? 0.78 : 1);
    return PLANT_LUSH.clone()
      .lerp(PLANT_DRY, Math.min(1, Math.max(0, dry * 1.2 - 0.1 + hue * 0.15)))
      .multiplyScalar(b);
  }
  const b = 0.88 + light * 0.24;
  return new THREE.Color(b, b, b);
}

/** Rocks also vary in height, so two boulders of one size are not the same shape. */
function propStretch(prop: PropId, x: number, z: number, seed: number): number {
  return ROCKS.has(prop)
    ? 0.84 + hash(Math.floor(x * 8), Math.floor(z * 8), seed, 23) * 0.32
    : 1;
}

/** Rough radius of a solid prop at scale 1, in metres. */
const PROP_FOOTPRINT = 1.6;

/** True when the ground all round (x, z) out to radius r is too steep to drive. */
function footprintUndrivable(
  map: MapDef,
  x: number,
  z: number,
  r: number,
): boolean {
  for (let i = 0; i < 8; i += 1) {
    const angle = (i / 8) * Math.PI * 2;
    if (
      slopeAt(map, x + Math.cos(angle) * r, z + Math.sin(angle) * r) <=
      MAX_SLOPE
    ) {
      return false;
    }
  }
  return true;
}

/** Where the props go: fixed for a map, so a replay or reload looks the same. */
export function scatterProps(map: MapDef): Placement[] {
  const out: Placement[] = [];
  const half = map.size / 2;
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const s = new THREE.Vector3();
  const p = new THREE.Vector3();
  const place = (
    prop: PropId,
    x: number,
    z: number,
    scale: number,
    yaw: number,
    sink: number,
  ): void => {
    q.setFromAxisAngle(up, yaw);
    s.set(scale, scale * propStretch(prop, x, z, map.seed), scale);
    p.set(x, heightAt(map, x, z) - sink * scale, z);
    out.push({
      prop,
      x,
      z,
      matrix: new THREE.Matrix4().compose(p, q, s),
      tint: propTint(prop, x, z, map.seed),
    });
  };
  for (let cz = 0; cz < map.rows; cz += 1) {
    for (let cx = 0; cx < map.cols; cx += 1) {
      const r = hash(cx, cz, map.seed, 1);
      const jx = hash(cx, cz, map.seed, 2);
      const jz = hash(cx, cz, map.seed, 3);
      const x = -half + (cx + 0.15 + jx * 0.7) * map.cellSize;
      const z = -half + (cz + 0.15 + jz * 0.7) * map.cellSize;
      // Keep the border strip clear, where the map edge line runs.
      if (
        Math.abs(x) > half - 2 ||
        Math.abs(z) > half - 2 ||
        isWaterAt(map, x, z)
      ) {
        continue;
      }
      const yaw = hash(cx, cz, map.seed, 4) * Math.PI * 2;
      const size = hash(cx, cz, map.seed, 5);
      const slope = slopeAt(map, x, z);
      if (slope > MAX_SLOPE) {
        // Steep ground: crags and boulders, dense enough to read as a rocky face, plus the odd
        // dead tree or frond. Only where the prop's whole footprint is undrivable.
        let prop: PropId | null = null;
        let scale = 1;
        let sink = 0;
        if (r < 0.26) {
          prop = "prop.nature.cliff";
          scale = 0.55 + size * 0.5;
          sink = 0.35;
        } else if (r < 0.46) {
          prop = "prop.nature.boulder";
          scale = 0.7 + size * 0.7;
          sink = 0.25;
        } else if (r < 0.58) {
          prop = "prop.nature.rock_cluster";
          scale = 0.6 + size * 0.5;
          sink = 0.15;
        } else if (r < 0.63) {
          prop = "prop.nature.slab";
          scale = 0.4 + size * 0.3;
          sink = 0.15;
        } else if (r < 0.66) {
          prop = "prop.nature.dead_tree";
          scale = 0.7 + size * 0.5;
        } else if (r < 0.69) {
          prop = "prop.nature.tendril";
          scale = 0.7 + size * 0.5;
        }
        if (prop && footprintUndrivable(map, x, z, PROP_FOOTPRINT * scale)) {
          place(prop, x, z, scale, yaw, sink);
        }
        continue;
      }
      // Drivable ground (open and hillside): only soft clutter units can roll over.
      const patch = hash(cx >> 3, cz >> 3, map.seed, 6);
      const density = (0.4 + patch * 1.2) * (slope > MAX_SLOPE * 0.6 ? 0.5 : 1);
      const t = r / density;
      if (t < 0.05) {
        place("prop.nature.grass", x, z, 0.9 + size * 0.8, yaw, 0);
      } else if (t < 0.064) {
        place("prop.nature.shrub", x, z, 0.5 + size * 0.4, yaw, 0.05);
      }
    }
  }
  scatterOutside(map, out);
  return out;
}

/** How far past the map edge scenery is scattered (the hills beyond fade into haze). */
const OUTSIDE_REACH = 80;
const OUTSIDE_CELL = 4.5;
const OUTSIDE_SUFFIX = ":out";
const FAR_SUFFIX = ":far";
/** Props and sites within this distance of the camera target draw their full models (metres). */
const NEAR_RADIUS = 34;
/** Zoomed out further than this (camera to target, metres), every prop draws low-detail. */
const FULL_DETAIL_VIEW = 56;
/** The near/far split is redone after the camera target moves this far (metres). */
const RELAYOUT_STEP = 8;
/** Shrubs and grass only this far past the edge (metres); beyond it, rocks and dead trees. */
const OUTSIDE_PLANT_REACH = 22;

/**
 * Scenery on the land round the map: rocks, crags and dead trees on the hills, grass and shrubs
 * near the edge, thinning out with distance. Nothing out here can be driven to.
 */
function scatterOutside(map: MapDef, out: Placement[]): void {
  const half = map.size / 2;
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const s = new THREE.Vector3();
  const p = new THREE.Vector3();
  const reach = half + OUTSIDE_REACH;
  const cells = Math.ceil((reach * 2) / OUTSIDE_CELL);
  for (let cz = 0; cz < cells; cz += 1) {
    for (let cx = 0; cx < cells; cx += 1) {
      const x =
        -reach + (cx + 0.1 + hash(cx, cz, map.seed, 12) * 0.8) * OUTSIDE_CELL;
      const z =
        -reach + (cz + 0.1 + hash(cx, cz, map.seed, 13) * 0.8) * OUTSIDE_CELL;
      const d = distanceOutside(map, x, z);
      // Leave the strip right at the edge clear so the edge marker reads.
      if (d < 3 || d > OUTSIDE_REACH) {
        continue;
      }
      const r = hash(cx, cz, map.seed, 11);
      // Thinner further out; the haze hides the rest. Small plants only near the edge, where they
      // can be seen; further out only cheap rock and tree silhouettes (keeps the triangle count
      // within the phone budget).
      const near = d < OUTSIDE_PLANT_REACH;
      if (r > (near ? 0.14 : 0.05) * (1 - d / (OUTSIDE_REACH * 1.25))) {
        continue;
      }
      const pick = hash(cx, cz, map.seed, 14);
      const size = hash(cx, cz, map.seed, 15);
      const yaw = hash(cx, cz, map.seed, 16) * Math.PI * 2;
      const slope =
        Math.abs(
          groundHeightAt(map, x + 1.5, z) - groundHeightAt(map, x - 1.5, z),
        ) +
        Math.abs(
          groundHeightAt(map, x, z + 1.5) - groundHeightAt(map, x, z - 1.5),
        );
      let prop: PropId;
      let scale: number;
      let sink = 0;
      if (near && slope > 1.6 && pick < 0.45) {
        prop = "prop.nature.cliff";
        scale = 0.8 + size * 0.9;
        sink = 0.4;
      } else if (pick < 0.3) {
        prop = "prop.nature.boulder";
        scale = 0.8 + size * 1.1;
        sink = 0.3;
      } else if (pick < 0.45) {
        prop = "prop.nature.rock_cluster";
        scale = 0.7 + size * 0.8;
        sink = 0.15;
      } else if (pick < 0.58) {
        prop = "prop.nature.dead_tree";
        scale = 0.8 + size * 0.7;
      } else if (!near) {
        prop = "prop.nature.dead_tree";
        scale = 0.8 + size * 0.7;
      } else if (pick < 0.68) {
        prop = "prop.nature.shrub";
        scale = 0.6 + size * 0.6;
        sink = 0.05;
      } else if (pick < 0.84) {
        continue;
      } else {
        prop = "prop.nature.grass";
        scale = 1 + size * 0.9;
      }
      q.setFromAxisAngle(up, yaw);
      s.set(scale, scale * propStretch(prop, x, z, map.seed), scale);
      p.set(x, groundHeightAt(map, x, z) - sink * scale, z);
      out.push({
        prop,
        x,
        z,
        matrix: new THREE.Matrix4().compose(p, q, s),
        tint: propTint(prop, x, z, map.seed),
        outside: true,
      });
    }
  }
}

export class Landscape {
  private readonly group = new THREE.Group();
  private readonly templates = new Map<PropId, PropTemplate>();
  private readonly lodTemplates = new Map<PropId, PropTemplate>();
  /**
   * Instanced props, keyed by prop id: the plain key holds the full models near the camera,
   * ':far' the low-detail ones further off, ':out' the shadowless low-detail set past the map edge.
   */
  private readonly meshes = new Map<string, THREE.InstancedMesh>();
  private placements: Placement[] = [];
  /** Placements left after clearing round deposits and structures. */
  private shown: Placement[] = [];
  private structureKey = "";
  private readonly depositTemplates = new Map<string, THREE.Object3D>();
  private readonly depositLodTemplates = new Map<string, THREE.Object3D>();
  private readonly depositViews = new Map<number, DepositView>();
  private shadows = true;
  /** Full models near the camera (high quality); false draws every prop low-detail. */
  private fullDetail = true;
  private focusX = 0;
  private focusZ = 0;
  /** Camera zoomed out past FULL_DETAIL_VIEW. */
  private zoomedOut = false;
  /** Focus the near/far split was last laid out for (NaN: never). */
  private laidX = Number.NaN;
  private laidZ = Number.NaN;

  constructor(
    private readonly scene: THREE.Scene,
    private readonly map: MapDef,
    private readonly fog: FogUniforms,
  ) {
    this.group.name = "Landscape";
    this.scene.add(this.group);
    this.placements = scatterProps(map);
  }

  /** Registers any landscape model by its asset id (props, sites and their low-detail versions). */
  addModel(id: string, model: THREE.Object3D): void {
    if (id === DEPOSIT_MODEL_IDS.ore || id === DEPOSIT_MODEL_IDS.metal) {
      this.addDepositModel(id === DEPOSIT_MODEL_IDS.ore ? "ore" : "metal", model);
    } else if (id === DEPOSIT_LOD_IDS.ore || id === DEPOSIT_LOD_IDS.metal) {
      this.depositLodTemplates.set(id === DEPOSIT_LOD_IDS.ore ? "ore" : "metal", model);
      this.dropDepositViews(() => true);
    } else if (id.endsWith(LOD_SUFFIX)) {
      this.addPropLod(id.slice(0, -LOD_SUFFIX.length), model);
    } else {
      this.addPropModel(id, model);
    }
  }

  /** Registers a loaded prop model (one mesh, one material). */
  addPropModel(id: string, model: THREE.Object3D): void {
    if (!(PROP_IDS as readonly string[]).includes(id)) {
      return;
    }
    const mesh = firstMesh(model);
    if (!mesh || Array.isArray(mesh.material)) {
      return;
    }
    const material = mesh.material.clone();
    addFogHook(material, this.fog, true, PLANTS.has(id as PropId));
    this.templates.set(id as PropId, {
      geometry: mesh.geometry,
      material,
      local: mesh.matrixWorld.clone(),
    });
    this.structureKey = "#"; // force a rebuild
  }

  /** Registers a prop's low-detail geometry; it is drawn with the full model's material. */
  private addPropLod(id: string, model: THREE.Object3D): void {
    if (!(PROP_IDS as readonly string[]).includes(id)) {
      return;
    }
    const mesh = firstMesh(model);
    if (!mesh) {
      return;
    }
    this.lodTemplates.set(id as PropId, {
      geometry: mesh.geometry,
      material: mesh.material as THREE.Material,
      local: mesh.matrixWorld.clone(),
    });
    this.structureKey = "#";
  }

  /** Registers a loaded ore or metal site model. */
  addDepositModel(kind: "ore" | "metal", model: THREE.Object3D): void {
    this.depositTemplates.set(kind, model);
    // Swap any placeholder discs (or the other version of this site) for the new model.
    this.dropDepositViews((view) => view.fallback || view.kind === kind);
  }

  setShadows(on: boolean): void {
    this.shadows = on;
    for (const [key, mesh] of this.meshes) {
      mesh.castShadow = on && !key.endsWith(OUTSIDE_SUFFIX);
    }
    for (const view of this.depositViews.values()) {
      view.root.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.castShadow = on;
        }
      });
    }
  }

  /**
   * True on the higher quality levels: props near the camera use their full models. False draws
   * every prop and site from its low-detail model.
   */
  setFullDetail(on: boolean): void {
    if (on === this.fullDetail) {
      return;
    }
    this.fullDetail = on;
    this.layoutProps();
  }

  /** Number of props drawn (for tests and the stats overlay). */
  propCount(): number {
    let count = 0;
    for (const mesh of this.meshes.values()) {
      count += mesh.count;
    }
    return count;
  }

  /** Props drawn from full and from low-detail models (for tests). */
  detailCounts(): { full: number; low: number } {
    let full = 0;
    let low = 0;
    for (const [key, mesh] of this.meshes) {
      if (key.endsWith(FAR_SUFFIX) || key.endsWith(OUTSIDE_SUFFIX)) {
        low += mesh.count;
      } else {
        full += mesh.count;
      }
    }
    return { full, low };
  }

  /**
   * `focusX`, `focusZ`: the camera's ground target, `viewDistance` its distance from the camera,
   * for the near/far model split.
   */
  sync(
    world: WorldState,
    focusX = this.focusX,
    focusZ = this.focusZ,
    viewDistance = 0,
  ): void {
    this.focusX = focusX;
    this.focusZ = focusZ;
    const zoomedOut = viewDistance > FULL_DETAIL_VIEW;
    const zoomChanged = zoomedOut !== this.zoomedOut;
    this.zoomedOut = zoomedOut;
    this.syncDeposits(world);
    const key =
      world.structures.map((s) => s.id).join(",") +
      `|${world.deposits.filter((d) => d.amount > 0).length}`;
    if (key !== this.structureKey && this.templates.size > 0) {
      this.structureKey = key;
      this.filterProps(world);
      this.layoutProps();
    } else if (
      this.fullDetail &&
      (zoomChanged ||
        Number.isNaN(this.laidX) ||
        (focusX - this.laidX) ** 2 + (focusZ - this.laidZ) ** 2 >
          RELAYOUT_STEP * RELAYOUT_STEP)
    ) {
      this.layoutProps();
    }
  }

  private filterProps(world: WorldState): void {
    const clear: Array<{ x: number; z: number; r: number }> = [];
    for (const deposit of world.deposits) {
      clear.push({ x: deposit.x, z: deposit.z, r: DEPOSIT_CLEAR });
    }
    for (const structure of world.structures) {
      const type = world.structureTypes.get(structure.typeId);
      const cells = type
        ? Math.max(type.footprint.cellsX, type.footprint.cellsZ)
        : 3;
      clear.push({
        x: structure.x,
        z: structure.z,
        r: Math.max(STRUCTURE_CLEAR, cells * this.map.cellSize * 0.75 + 1.5),
      });
    }
    this.shown = this.placements.filter(
      (placement) =>
        !clear.some(
          (c) =>
            (placement.x - c.x) ** 2 + (placement.z - c.z) ** 2 < c.r * c.r,
        ),
    );
  }

  /** True when a prop or site at (x, z) draws its full model. */
  private isNear(x: number, z: number): boolean {
    return (
      this.fullDetail &&
      !this.zoomedOut &&
      (x - this.focusX) ** 2 + (z - this.focusZ) ** 2 < NEAR_RADIUS * NEAR_RADIUS
    );
  }

  /** Sorts the shown props into near (full model), far and outside (low-detail) batches. */
  private layoutProps(): void {
    this.laidX = this.focusX;
    this.laidZ = this.focusZ;
    const byKey = new Map<string, Placement[]>();
    for (const placement of this.shown) {
      if (!this.templates.has(placement.prop)) {
        continue;
      }
      const lod = this.lodTemplates.has(placement.prop);
      const key = placement.outside
        ? placement.prop + OUTSIDE_SUFFIX
        : lod && !this.isNear(placement.x, placement.z)
          ? placement.prop + FAR_SUFFIX
          : placement.prop;
      const list = byKey.get(key) ?? [];
      list.push(placement);
      byKey.set(key, list);
    }
    const matrix = new THREE.Matrix4();
    for (const [prop, template] of this.templates) {
      const lod = this.lodTemplates.get(prop) ?? template;
      for (const suffix of ["", FAR_SUFFIX, OUTSIDE_SUFFIX]) {
        const key = prop + suffix;
        const list = byKey.get(key) ?? [];
        const look = suffix === "" ? template : lod;
        const outside = suffix === OUTSIDE_SUFFIX;
        let mesh = this.meshes.get(key);
        if (!mesh && list.length === 0) {
          continue;
        }
        if (
          !mesh ||
          mesh.instanceMatrix.count < list.length ||
          mesh.geometry !== look.geometry
        ) {
          if (mesh) {
            this.group.remove(mesh);
            mesh.dispose();
          }
          // Room to spare, so moving the camera rarely needs a new buffer.
          const capacity = Math.max(1, Math.ceil(list.length * 1.25));
          mesh = new THREE.InstancedMesh(look.geometry, template.material, capacity);
          mesh.name = `Prop:${key}`;
          mesh.frustumCulled = false;
          mesh.receiveShadow = !outside;
          mesh.castShadow = this.shadows && !outside;
          this.meshes.set(key, mesh);
          this.group.add(mesh);
        }
        const target = mesh;
        list.forEach((placed, index) => {
          matrix.multiplyMatrices(placed.matrix, look.local);
          target.setMatrixAt(index, matrix);
          target.setColorAt(index, placed.tint);
        });
        target.count = list.length;
        target.visible = list.length > 0;
        target.instanceMatrix.needsUpdate = true;
        if (target.instanceColor) {
          target.instanceColor.needsUpdate = true;
        }
      }
    }
  }

  private syncDeposits(world: WorldState): void {
    const alive = new Set<number>();
    for (const deposit of world.deposits) {
      if (deposit.amount <= 0) {
        continue;
      }
      alive.add(deposit.id);
      let view = this.depositViews.get(deposit.id);
      const lod =
        this.depositLodTemplates.has(deposit.kind) &&
        !this.isNear(deposit.x, deposit.z);
      if (view && !view.fallback && view.lod !== lod) {
        this.group.remove(view.root);
        this.depositViews.delete(deposit.id);
        view = undefined;
      }
      if (!view) {
        view = this.makeDeposit(deposit, lod);
        this.depositViews.set(deposit.id, view);
        this.group.add(view.root);
      }
      const full =
        deposit.maxAmount > 0
          ? Math.min(1, deposit.amount / deposit.maxAmount)
          : 1;
      const gem = DEPOSIT_MIN_GEM + (1 - DEPOSIT_MIN_GEM) * full;
      for (const part of view.gems) {
        part.scale.setScalar(gem);
      }
    }
    this.dropDepositViews((_view, id) => !alive.has(id));
  }

  private dropDepositViews(
    test: (view: DepositView, id: number) => boolean,
  ): void {
    for (const [id, view] of this.depositViews) {
      if (test(view, id)) {
        this.group.remove(view.root);
        if (view.fallback) {
          disposeFallback(view.root);
        }
        this.depositViews.delete(id);
      }
    }
  }

  private makeDeposit(deposit: DepositState, lod: boolean): DepositView {
    const template = this.depositTemplates.get(deposit.kind);
    const y = heightAt(this.map, deposit.x, deposit.z);
    if (!template) {
      const mesh = new THREE.Mesh(
        new THREE.CylinderGeometry(1.2, 1.2, 0.4, 10),
        new THREE.MeshStandardMaterial({
          color: deposit.kind === "ore" ? 0xc0508a : 0x5a8fc8,
          roughness: 0.6,
        }),
      );
      mesh.position.set(deposit.x, y + 0.2, deposit.z);
      mesh.receiveShadow = true;
      return { root: mesh, gems: [], fallback: true, lod: false, kind: deposit.kind };
    }
    const lodTemplate = lod ? this.depositLodTemplates.get(deposit.kind) : undefined;
    // The low-detail site wears the full model's materials, matched by name.
    const materials = new Map<string, THREE.Material>();
    if (lodTemplate) {
      template.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          for (const material of [object.material].flat() as THREE.Material[]) {
            materials.set(material.name, material);
          }
        }
      });
    }
    const root = (lodTemplate ?? template).clone(true);
    root.name = `Deposit:${deposit.id}`;
    root.position.set(deposit.x, y, deposit.z);
    root.rotation.y = deposit.id * 2.39996;
    root.scale.setScalar(DEPOSIT_SCALE);
    const gems: THREE.Object3D[] = [];
    root.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.castShadow = this.shadows;
        object.receiveShadow = true;
        const mesh = object as THREE.Mesh<
          THREE.BufferGeometry,
          THREE.Material | THREE.Material[]
        >;
        if (lodTemplate) {
          mesh.material = Array.isArray(mesh.material)
            ? mesh.material.map((m) => materials.get(m.name) ?? m)
            : (materials.get(mesh.material.name) ?? mesh.material);
        }
        const material = Array.isArray(mesh.material)
          ? mesh.material[0]
          : mesh.material;
        if (material?.name === "OreGem") {
          gems.push(object);
        }
      }
    });
    return { root, gems, fallback: false, lod: Boolean(lodTemplate), kind: deposit.kind };
  }

  dispose(): void {
    for (const mesh of this.meshes.values()) {
      mesh.dispose();
    }
    for (const template of this.templates.values()) {
      template.material.dispose();
    }
    for (const view of this.depositViews.values()) {
      if (view.fallback) {
        disposeFallback(view.root);
      }
    }
    this.scene.remove(this.group);
  }
}

interface DepositView {
  root: THREE.Object3D;
  gems: THREE.Object3D[];
  fallback: boolean;
  /** Drawn from the low-detail model. */
  lod: boolean;
  kind: string;
}

function firstMesh(model: THREE.Object3D): THREE.Mesh | null {
  model.updateMatrixWorld(true);
  let found: THREE.Mesh | null = null;
  model.traverse((object) => {
    if (!found && object instanceof THREE.Mesh) {
      found = object;
    }
  });
  return found;
}

function disposeFallback(root: THREE.Object3D): void {
  if (root instanceof THREE.Mesh) {
    const mesh = root as THREE.Mesh<THREE.BufferGeometry, THREE.Material>;
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
}
