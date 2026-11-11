// Map dressing: the ore and metal site models, and scattered rocks, cliff chunks and plants.
//
// Everything here is decoration drawn from the map seed; none of it touches the sim. Big rocks and
// cliff chunks sit only on ground too steep to drive, so they show where tanks cannot go. Open
// ground gets low clutter (grass, bushes, small stones, dead trees, alien fronds) that units simply
// drive over. Props are hidden round deposits and under structures, and the set is rebuilt when
// structures appear or go.
//
// Each prop model is one mesh with one material, so each prop kind is a single InstancedMesh.
import * as THREE from 'three';
import { heightAt, isWaterAt, slopeAt, type MapDef } from '../sim/map';
import { MAX_SLOPE } from '../sim/tuning';
import type { DepositState, WorldState } from '../sim/types';

export const PROP_IDS = [
  'prop.nature.boulder',
  'prop.nature.rock_cluster',
  'prop.nature.slab',
  'prop.nature.cliff',
  'prop.nature.shrub',
  'prop.nature.grass',
  'prop.nature.dead_tree',
  'prop.nature.tendril',
] as const;
export const DEPOSIT_MODEL_IDS = { ore: 'prop.deposit.ore', metal: 'prop.deposit.metal' } as const;

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
}

interface PropTemplate {
  geometry: THREE.BufferGeometry;
  material: THREE.Material;
  /** The mesh's own transform inside the model file. */
  local: THREE.Matrix4;
}

function hash(ix: number, iz: number, seed: number, salt: number): number {
  let h = Math.imul(ix, 374761393) ^ Math.imul(iz, 668265263) ^ Math.imul(seed + salt * 977, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** Same darkening as the terrain under unexplored fog, for instanced props. */
export function addFogHook(material: THREE.Material, fog: FogUniforms, instanced: boolean): void {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uFog = fog.uFog;
    shader.uniforms.uFogOn = fog.uFogOn;
    shader.uniforms.uFogSize = fog.uFogSize;
    const world = instanced
      ? 'vFogXZ = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xz;'
      : 'vFogXZ = (modelMatrix * vec4(transformed, 1.0)).xz;';
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec2 vFogXZ;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>\n${world}`);
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        '#include <common>\nvarying vec2 vFogXZ;\nuniform sampler2D uFog;\nuniform float uFogOn;\nuniform float uFogSize;',
      )
      .replace(
        '#include <color_fragment>',
        '#include <color_fragment>\nfloat fogLevel = uFogOn > 0.5 ? texture2D(uFog, vFogXZ / uFogSize + 0.5).r : 1.0;\ndiffuseColor.rgb *= fogLevel;',
      )
      // Glowing parts must go dark under fog too, or alien fronds shine out of unexplored ground.
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\ntotalEmissiveRadiance *= fogLevel;');
  };
  material.customProgramCacheKey = () => (instanced ? 'tcFogInst' : 'tcFog');
}

/** Where the props go: fixed for a map, so a replay or reload looks the same. */
export function scatterProps(map: MapDef): Placement[] {
  const out: Placement[] = [];
  const half = map.size / 2;
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const s = new THREE.Vector3();
  const p = new THREE.Vector3();
  const place = (prop: PropId, x: number, z: number, scale: number, yaw: number, sink: number): void => {
    q.setFromAxisAngle(up, yaw);
    s.set(scale, scale, scale);
    p.set(x, heightAt(map, x, z) - sink * scale, z);
    out.push({ prop, x, z, matrix: new THREE.Matrix4().compose(p, q, s) });
  };
  for (let cz = 0; cz < map.rows; cz += 1) {
    for (let cx = 0; cx < map.cols; cx += 1) {
      const r = hash(cx, cz, map.seed, 1);
      const jx = hash(cx, cz, map.seed, 2);
      const jz = hash(cx, cz, map.seed, 3);
      const x = -half + (cx + 0.15 + jx * 0.7) * map.cellSize;
      const z = -half + (cz + 0.15 + jz * 0.7) * map.cellSize;
      // Keep the border strip clear, where the map edge line runs.
      if (Math.abs(x) > half - 2 || Math.abs(z) > half - 2 || isWaterAt(map, x, z)) {
        continue;
      }
      const yaw = hash(cx, cz, map.seed, 4) * Math.PI * 2;
      const size = hash(cx, cz, map.seed, 5);
      const slope = slopeAt(map, x, z);
      if (slope > MAX_SLOPE) {
        // Steep ground: crags and boulders, dense enough to read as a rocky face.
        if (r < 0.26) {
          place('prop.nature.cliff', x, z, 0.55 + size * 0.5, yaw, 0.35);
        } else if (r < 0.46) {
          place('prop.nature.boulder', x, z, 0.7 + size * 0.7, yaw, 0.25);
        } else if (r < 0.58) {
          place('prop.nature.rock_cluster', x, z, 0.6 + size * 0.5, yaw, 0.15);
        }
        continue;
      }
      if (slope > MAX_SLOPE * 0.6) {
        // Hillside: loose stones and the odd boulder at the foot of steep ground.
        if (r < 0.05) {
          place('prop.nature.rock_cluster', x, z, 0.4 + size * 0.4, yaw, 0.1);
        } else if (r < 0.08) {
          place('prop.nature.slab', x, z, 0.4 + size * 0.3, yaw, 0.15);
        } else if (r < 0.11) {
          place('prop.nature.grass', x, z, 0.9 + size * 0.6, yaw, 0);
        }
        continue;
      }
      // Open ground: sparse low clutter, a little thicker in patches.
      const patch = hash(cx >> 3, cz >> 3, map.seed, 6);
      const density = 0.4 + patch * 1.2;
      const t = r / density;
      if (t < 0.045) {
        place('prop.nature.grass', x, z, 0.9 + size * 0.8, yaw, 0);
      } else if (t < 0.058) {
        place('prop.nature.shrub', x, z, 0.6 + size * 0.6, yaw, 0.05);
      } else if (t < 0.064) {
        place('prop.nature.slab', x, z, 0.3 + size * 0.3, yaw, 0.15);
      } else if (t < 0.069) {
        place('prop.nature.rock_cluster', x, z, 0.3 + size * 0.3, yaw, 0.1);
      } else if (t < 0.072) {
        place('prop.nature.dead_tree', x, z, 0.7 + size * 0.5, yaw, 0);
      } else if (t < 0.075) {
        place('prop.nature.tendril', x, z, 0.7 + size * 0.5, yaw, 0);
      }
    }
  }
  return out;
}

export class Landscape {
  private readonly group = new THREE.Group();
  private readonly templates = new Map<PropId, PropTemplate>();
  private readonly meshes = new Map<PropId, THREE.InstancedMesh>();
  private placements: Placement[] = [];
  private structureKey = '';
  private readonly depositTemplates = new Map<string, THREE.Object3D>();
  private readonly depositViews = new Map<number, { root: THREE.Object3D; gems: THREE.Object3D[]; fallback: boolean }>();
  private shadows = true;

  constructor(
    private readonly scene: THREE.Scene,
    private readonly map: MapDef,
    private readonly fog: FogUniforms,
  ) {
    this.group.name = 'Landscape';
    this.scene.add(this.group);
    this.placements = scatterProps(map);
  }

  /** Registers a loaded prop model (one mesh, one material). */
  addPropModel(id: string, model: THREE.Object3D): void {
    if (!(PROP_IDS as readonly string[]).includes(id)) {
      return;
    }
    model.updateMatrixWorld(true);
    let found: THREE.Mesh | null = null;
    model.traverse((object) => {
      if (!found && object instanceof THREE.Mesh) {
        found = object;
      }
    });
    const mesh = found as THREE.Mesh | null;
    if (!mesh || Array.isArray(mesh.material)) {
      return;
    }
    const material = mesh.material.clone();
    addFogHook(material, this.fog, true);
    this.templates.set(id as PropId, { geometry: mesh.geometry, material, local: mesh.matrixWorld.clone() });
    this.structureKey = '#'; // force a rebuild
  }

  /** Registers a loaded ore or metal site model. */
  addDepositModel(kind: 'ore' | 'metal', model: THREE.Object3D): void {
    this.depositTemplates.set(kind, model);
    // Swap any placeholder discs already drawn for the real model.
    for (const [id, view] of this.depositViews) {
      if (view.fallback) {
        this.group.remove(view.root);
        disposeFallback(view.root);
        this.depositViews.delete(id);
      }
    }
  }

  setShadows(on: boolean): void {
    this.shadows = on;
    for (const mesh of this.meshes.values()) {
      mesh.castShadow = on;
    }
    for (const view of this.depositViews.values()) {
      view.root.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.castShadow = on;
        }
      });
    }
  }

  /** Number of props drawn (for tests and the stats overlay). */
  propCount(): number {
    let count = 0;
    for (const mesh of this.meshes.values()) {
      count += mesh.count;
    }
    return count;
  }

  sync(world: WorldState): void {
    this.syncDeposits(world);
    const key = world.structures.map((s) => s.id).join(',') + `|${world.deposits.filter((d) => d.amount > 0).length}`;
    if (key !== this.structureKey && this.templates.size > 0) {
      this.structureKey = key;
      this.rebuildProps(world);
    }
  }

  private rebuildProps(world: WorldState): void {
    const clear: Array<{ x: number; z: number; r: number }> = [];
    for (const deposit of world.deposits) {
      clear.push({ x: deposit.x, z: deposit.z, r: DEPOSIT_CLEAR });
    }
    for (const structure of world.structures) {
      const type = world.structureTypes.get(structure.typeId);
      const cells = type ? Math.max(type.footprint.cellsX, type.footprint.cellsZ) : 3;
      clear.push({ x: structure.x, z: structure.z, r: Math.max(STRUCTURE_CLEAR, cells * this.map.cellSize * 0.75 + 1.5) });
    }
    const byProp = new Map<PropId, THREE.Matrix4[]>();
    for (const placement of this.placements) {
      if (!this.templates.has(placement.prop)) {
        continue;
      }
      if (clear.some((c) => (placement.x - c.x) ** 2 + (placement.z - c.z) ** 2 < c.r * c.r)) {
        continue;
      }
      const list = byProp.get(placement.prop) ?? [];
      list.push(placement.matrix);
      byProp.set(placement.prop, list);
    }
    const matrix = new THREE.Matrix4();
    for (const [prop, template] of this.templates) {
      const list = byProp.get(prop) ?? [];
      let mesh = this.meshes.get(prop);
      if (!mesh || mesh.instanceMatrix.count < list.length) {
        if (mesh) {
          this.group.remove(mesh);
          mesh.dispose();
        }
        mesh = new THREE.InstancedMesh(template.geometry, template.material, Math.max(1, list.length));
        mesh.name = `Prop:${prop}`;
        mesh.frustumCulled = false;
        mesh.receiveShadow = true;
        mesh.castShadow = this.shadows;
        this.meshes.set(prop, mesh);
        this.group.add(mesh);
      }
      list.forEach((placed, index) => {
        matrix.multiplyMatrices(placed, template.local);
        mesh.setMatrixAt(index, matrix);
      });
      mesh.count = list.length;
      mesh.visible = list.length > 0;
      mesh.instanceMatrix.needsUpdate = true;
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
      if (!view) {
        view = this.makeDeposit(deposit);
        this.depositViews.set(deposit.id, view);
        this.group.add(view.root);
      }
      const full = deposit.maxAmount > 0 ? Math.min(1, deposit.amount / deposit.maxAmount) : 1;
      const gem = DEPOSIT_MIN_GEM + (1 - DEPOSIT_MIN_GEM) * full;
      for (const part of view.gems) {
        part.scale.setScalar(gem);
      }
    }
    for (const [id, view] of this.depositViews) {
      if (!alive.has(id)) {
        this.group.remove(view.root);
        if (view.fallback) {
          disposeFallback(view.root);
        }
        this.depositViews.delete(id);
      }
    }
  }

  private makeDeposit(deposit: DepositState): { root: THREE.Object3D; gems: THREE.Object3D[]; fallback: boolean } {
    const template = this.depositTemplates.get(deposit.kind);
    const y = heightAt(this.map, deposit.x, deposit.z);
    if (!template) {
      const mesh = new THREE.Mesh(
        new THREE.CylinderGeometry(1.2, 1.2, 0.4, 10),
        new THREE.MeshStandardMaterial({ color: deposit.kind === 'ore' ? 0xc0508a : 0x5a8fc8, roughness: 0.6 }),
      );
      mesh.position.set(deposit.x, y + 0.2, deposit.z);
      mesh.receiveShadow = true;
      return { root: mesh, gems: [], fallback: true };
    }
    const root = template.clone(true);
    root.name = `Deposit:${deposit.id}`;
    root.position.set(deposit.x, y, deposit.z);
    root.rotation.y = deposit.id * 2.39996;
    root.scale.setScalar(DEPOSIT_SCALE);
    const gems: THREE.Object3D[] = [];
    root.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.castShadow = this.shadows;
        object.receiveShadow = true;
        const mesh = object as THREE.Mesh<THREE.BufferGeometry, THREE.Material | THREE.Material[]>;
        const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
        if (material?.name === 'OreGem') {
          gems.push(object);
        }
      }
    });
    return { root, gems, fallback: false };
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

function disposeFallback(root: THREE.Object3D): void {
  if (root instanceof THREE.Mesh) {
    const mesh = root as THREE.Mesh<THREE.BufferGeometry, THREE.Material>;
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
}
