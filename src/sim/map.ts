import {
  DEFAULT_CELL_SIZE,
  DEFAULT_MAP_SIZE,
  MAX_SLOPE,
} from './tuning';

export type MovementClass = 'tracked' | 'hover' | 'air';

export interface LakeFeature {
  x: number;
  z: number;
  radius: number;
  depth: number;
}

export interface RiverFeature {
  x0: number;
  z0: number;
  x1: number;
  z1: number;
  width: number;
  depth: number;
  // Fractions along the river (0 to 1) that stay dry so ground units can cross.
  fords: Array<{ from: number; to: number }>;
}

/** A raised wall of ground from one point to another (a ridge line); leave gaps by splitting it. */
export interface RidgeFeature {
  x0: number;
  z0: number;
  x1: number;
  z1: number;
  /** Height at the crest, metres (negative digs a trench). */
  height: number;
  /** Half-width of the ridge at its base, metres. */
  width: number;
}

/** A round hill (positive height) or basin (negative). */
export interface HillFeature {
  x: number;
  z: number;
  radius: number;
  height: number;
}

/** Level ground for a base or landing site. */
export interface FlatFeature {
  x: number;
  z: number;
  radius: number;
  height?: number;
}

/**
 * Hand-shaped terrain for campaign maps. Absent = the classic skirmish terrain (seeded noise,
 * the diagonal centre ridge, rotational symmetry, four flat corners).
 */
export interface TerrainFeature {
  /** Noise seed for this map's hills; the world seed when absent. */
  seed?: number;
  /** Multiplier on the rolling noise (default 1). */
  roughness?: number;
  /** The skirmish maps' diagonal ridge (default true). */
  centreRidge?: boolean;
  /** Mirror the map so both sides start equal (default true). */
  symmetric?: boolean;
  ridges?: RidgeFeature[];
  hills?: HillFeature[];
  /** Replace the four default flat corners when given. */
  flats?: FlatFeature[];
}

export interface MapFeatures {
  waterLevel: number | null;
  lakes: LakeFeature[];
  rivers: RiverFeature[];
  terrain?: TerrainFeature;
}

export const NO_FEATURES: MapFeatures = { waterLevel: null, lakes: [], rivers: [] };

export interface MapDef {
  seed: number;
  size: number;
  cellSize: number;
  cols: number;
  rows: number;
  heights: Float32Array;
  waterLevel: number | null;
  // Which kind of unit this view of the map is for. Tracked when absent.
  movement?: MovementClass;
  // Buildings (and sites) as solid shapes; only on per-tick views made by obstacles.ts, never on
  // the world's own map.
  obstacles?: MapObstacles;
}

/** An axis-aligned box (half sizes hx, hz) or, when round, a circle of radius hx. */
export interface ObstacleShape {
  x: number;
  z: number;
  hx: number;
  hz: number;
  round: boolean;
}

export interface MapObstacles {
  shapes: ObstacleShape[];
  /** 1 where a cell centre is inside a shape, row-major (cz * cols + cx). */
  cells: Uint8Array;
}

function inObstacle(obstacles: MapObstacles, x: number, z: number): boolean {
  for (const shape of obstacles.shapes) {
    const dx = x - shape.x;
    const dz = z - shape.z;
    if (shape.round ? dx * dx + dz * dz < shape.hx * shape.hx : Math.abs(dx) < shape.hx && Math.abs(dz) < shape.hz) {
      return true;
    }
  }
  return false;
}

// The same terrain seen by a unit of another movement class.
export function mapFor(map: MapDef, movement: MovementClass): MapDef {
  return (map.movement ?? 'tracked') === movement ? map : { ...map, movement };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function smooth(t: number): number {
  return t * t * (3 - 2 * t);
}

function hash2(ix: number, iz: number, seed: number): number {
  let h = Math.imul(ix, 374761393) ^ Math.imul(iz, 668265263) ^ Math.imul(seed, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

function valueNoise(x: number, z: number, seed: number): number {
  const x0 = Math.floor(x);
  const z0 = Math.floor(z);
  const fx = x - x0;
  const fz = z - z0;
  const u = smooth(fx);
  const v = smooth(fz);
  const a = hash2(x0, z0, seed);
  const b = hash2(x0 + 1, z0, seed);
  const c = hash2(x0, z0 + 1, seed);
  const d = hash2(x0 + 1, z0 + 1, seed);
  const top = a + (b - a) * u;
  const bottom = c + (d - c) * u;
  return top + (bottom - top) * v;
}

function heightAtVertex(map: MapDef, ix: number, iz: number): number {
  const stride = map.cols + 1;
  return map.heights[iz * stride + ix] ?? 0;
}

function setHeight(map: MapDef, ix: number, iz: number, value: number): void {
  const stride = map.cols + 1;
  map.heights[iz * stride + ix] = value;
}

function flattenCircle(
  map: MapDef,
  centerX: number,
  centerZ: number,
  inner: number,
  outer: number,
  target: number,
): void {
  const half = map.size / 2;
  for (let iz = 0; iz <= map.rows; iz += 1) {
    const z = -half + iz * map.cellSize;
    for (let ix = 0; ix <= map.cols; ix += 1) {
      const x = -half + ix * map.cellSize;
      const distance = Math.hypot(x - centerX, z - centerZ);
      if (distance <= inner) {
        setHeight(map, ix, iz, target);
      } else if (distance < outer) {
        const t = (distance - inner) / (outer - inner);
        const blend = smooth(t);
        const current = heightAtVertex(map, ix, iz);
        setHeight(map, ix, iz, current * blend + target * (1 - blend));
      }
    }
  }
}

export function generateMap(
  seed: number,
  size = DEFAULT_MAP_SIZE,
  cellSize = DEFAULT_CELL_SIZE,
  features: MapFeatures = NO_FEATURES,
): MapDef {
  const cols = Math.max(1, Math.round(size / cellSize));
  const rows = cols;
  const stride = cols + 1;
  const map: MapDef = {
    seed,
    size: cols * cellSize,
    cellSize,
    cols,
    rows,
    heights: new Float32Array(stride * stride),
    waterLevel: features.waterLevel,
  };

  const half = map.size / 2;
  const terrain = features.terrain;
  const noiseSeed = terrain?.seed ?? seed;
  const roughness = terrain?.roughness ?? 1;

  for (let iz = 0; iz <= rows; iz += 1) {
    const z = -half + iz * cellSize;
    for (let ix = 0; ix <= cols; ix += 1) {
      const x = -half + ix * cellSize;
      const octave1 = valueNoise(x * 0.035, z * 0.035, noiseSeed) * 2.4;
      const octave2 = valueNoise(x * 0.09, z * 0.09, noiseSeed + 17) * 1.1;
      const octave3 = valueNoise(x * 0.19, z * 0.19, noiseSeed + 43) * 0.45;
      let h = (octave1 + octave2 + octave3) * roughness;

      if (terrain?.centreRidge ?? true) {
        const ridgeDistance = Math.abs(x + z);
        const ridgeAlong = Math.abs(x - z);
        if (ridgeAlong < 70) {
          h += Math.max(0, 1 - ridgeDistance / 6) * 9;
        }
      }
      for (const ridge of terrain?.ridges ?? []) {
        const dx = ridge.x1 - ridge.x0;
        const dz = ridge.z1 - ridge.z0;
        const lengthSq = dx * dx + dz * dz;
        const t = lengthSq === 0 ? 0 : clamp(((x - ridge.x0) * dx + (z - ridge.z0) * dz) / lengthSq, 0, 1);
        const d = Math.hypot(x - (ridge.x0 + dx * t), z - (ridge.z0 + dz * t));
        if (d < ridge.width) {
          h += smooth(1 - d / ridge.width) * ridge.height;
        }
      }
      for (const hill of terrain?.hills ?? []) {
        const d = Math.hypot(x - hill.x, z - hill.z);
        if (d < hill.radius) {
          h += smooth(1 - d / hill.radius) * hill.height;
        }
      }

      const edgeDistance = Math.min(ix, iz, cols - ix, rows - iz) * cellSize;
      if (edgeDistance < 6) {
        h *= edgeDistance / 6;
      }

      setHeight(map, ix, iz, h);
    }
  }

  // Rotationally symmetric terrain so both start positions are equally good.
  for (let iz = 0; iz <= rows && (terrain?.symmetric ?? true); iz += 1) {
    for (let ix = 0; ix <= cols; ix += 1) {
      const mirrorIx = cols - ix;
      const mirrorIz = rows - iz;
      if (iz * stride + ix < mirrorIz * stride + mirrorIx) {
        const average =
          ((map.heights[iz * stride + ix] ?? 0) + (map.heights[mirrorIz * stride + mirrorIx] ?? 0)) / 2;
        setHeight(map, ix, iz, average);
        setHeight(map, mirrorIx, mirrorIz, average);
      }
    }
  }

  if (terrain?.flats) {
    for (const flat of terrain.flats) {
      flattenCircle(map, flat.x, flat.z, flat.radius, flat.radius * 1.7, flat.height ?? 0);
    }
  } else {
    flattenCircle(map, -50, -50, 14, 24, 0);
    flattenCircle(map, 50, 50, 14, 24, 0);
    flattenCircle(map, 50, -50, 14, 24, 0);
    flattenCircle(map, -50, 50, 14, 24, 0);
    flattenCircle(map, 20, -20, 6, 10, 0);
  }

  carveWater(map, features);

  return map;
}

function carveWater(map: MapDef, features: MapFeatures): void {
  if (features.waterLevel === null) {
    return;
  }
  const level = features.waterLevel;
  const half = map.size / 2;
  const stride = map.cols + 1;
  for (let iz = 0; iz <= map.rows; iz += 1) {
    for (let ix = 0; ix <= map.cols; ix += 1) {
      const x = -half + ix * map.cellSize;
      const z = -half + iz * map.cellSize;
      let target = Number.POSITIVE_INFINITY;
      let strength = 0;
      for (const lake of features.lakes) {
        const d = Math.hypot(x - lake.x, z - lake.z);
        if (d < lake.radius) {
          const falloff = smooth(1 - d / lake.radius);
          if (falloff > strength) {
            strength = falloff;
            target = level - lake.depth;
          }
        }
      }
      for (const river of features.rivers) {
        const dx = river.x1 - river.x0;
        const dz = river.z1 - river.z0;
        const lengthSq = dx * dx + dz * dz;
        const t = lengthSq === 0 ? 0 : clamp(((x - river.x0) * dx + (z - river.z0) * dz) / lengthSq, 0, 1);
        if (river.fords.some((ford) => t >= ford.from && t <= ford.to)) {
          continue;
        }
        const d = Math.hypot(x - (river.x0 + dx * t), z - (river.z0 + dz * t));
        if (d < river.width) {
          const falloff = smooth(1 - d / river.width);
          if (falloff > strength) {
            strength = falloff;
            target = level - river.depth;
          }
        }
      }
      if (strength > 0) {
        const index = iz * stride + ix;
        const current = map.heights[index] ?? 0;
        map.heights[index] = current + (target - current) * strength;
      }
    }
  }
}

export function isWaterAt(map: MapDef, x: number, z: number): boolean {
  return map.waterLevel !== null && heightAt(map, x, z) < map.waterLevel;
}

export function heightAt(map: MapDef, x: number, z: number): number {
  const half = map.size / 2;
  const gx = clamp((x + half) / map.cellSize, 0, map.cols);
  const gz = clamp((z + half) / map.cellSize, 0, map.rows);
  const ix = Math.min(map.cols - 1, Math.floor(gx));
  const iz = Math.min(map.rows - 1, Math.floor(gz));
  const fx = gx - ix;
  const fz = gz - iz;

  const h00 = heightAtVertex(map, ix, iz);
  const h10 = heightAtVertex(map, Math.min(map.cols, ix + 1), iz);
  const h01 = heightAtVertex(map, ix, Math.min(map.rows, iz + 1));
  const h11 = heightAtVertex(map, Math.min(map.cols, ix + 1), Math.min(map.rows, iz + 1));

  const top = h00 + (h10 - h00) * fx;
  const bottom = h01 + (h11 - h01) * fx;
  return top + (bottom - top) * fz;
}

export function slopeAt(map: MapDef, x: number, z: number): number {
  const half = map.size / 2;
  const cx = clamp(Math.floor((x + half) / map.cellSize), 0, map.cols - 1);
  const cz = clamp(Math.floor((z + half) / map.cellSize), 0, map.rows - 1);
  const h00 = heightAtVertex(map, cx, cz);
  const h10 = heightAtVertex(map, cx + 1, cz);
  const h01 = heightAtVertex(map, cx, cz + 1);
  const h11 = heightAtVertex(map, cx + 1, cz + 1);

  const s1 = Math.abs(h10 - h00) / map.cellSize;
  const s2 = Math.abs(h11 - h01) / map.cellSize;
  const s3 = Math.abs(h01 - h00) / map.cellSize;
  const s4 = Math.abs(h11 - h10) / map.cellSize;
  return Math.max(s1, s2, s3, s4);
}

export function isBlockedAt(map: MapDef, x: number, z: number): boolean {
  const half = map.size / 2;
  if (x < -half || x > half || z < -half || z > half) {
    return true;
  }
  const movement = map.movement ?? 'tracked';
  if (movement === 'air') {
    return false;
  }
  if (map.obstacles && inObstacle(map.obstacles, x, z)) {
    return true;
  }
  if (movement === 'tracked' && isWaterAt(map, x, z)) {
    return true;
  }
  return slopeAt(map, x, z) > MAX_SLOPE;
}

// Terrain never changes during a match, so each map's blocked cells are worked out once per
// movement class (0 = unknown, 1 = open, 2 = blocked) and kept with its height array.
const terrainCellCache = new WeakMap<Float32Array, Map<MovementClass, Uint8Array>>();

function terrainCells(map: MapDef, movement: MovementClass): Uint8Array {
  let byMovement = terrainCellCache.get(map.heights);
  if (!byMovement) {
    byMovement = new Map();
    terrainCellCache.set(map.heights, byMovement);
  }
  let cells = byMovement.get(movement);
  if (!cells || cells.length !== map.cols * map.rows) {
    cells = new Uint8Array(map.cols * map.rows);
    byMovement.set(movement, cells);
  }
  return cells;
}

export function isBlockedCell(map: MapDef, cx: number, cz: number): boolean {
  if (cx < 0 || cz < 0 || cx >= map.cols || cz >= map.rows) {
    return true;
  }
  const movement = map.movement ?? 'tracked';
  if (movement === 'air') {
    return false;
  }
  const index = cz * map.cols + cx;
  if (map.obstacles && map.obstacles.cells[index] === 1) {
    return true;
  }
  const cache = terrainCells(map, movement);
  const known = cache[index];
  if (known !== undefined && known !== 0) {
    return known === 2;
  }
  const blocked = terrainCellBlocked(map, movement, cx, cz);
  cache[index] = blocked ? 2 : 1;
  return blocked;
}

function terrainCellBlocked(map: MapDef, movement: MovementClass, cx: number, cz: number): boolean {
  const h00 = heightAtVertex(map, cx, cz);
  const h10 = heightAtVertex(map, cx + 1, cz);
  const h01 = heightAtVertex(map, cx, cz + 1);
  const h11 = heightAtVertex(map, cx + 1, cz + 1);
  if (movement === 'tracked' && map.waterLevel !== null && (h00 + h10 + h01 + h11) / 4 < map.waterLevel) {
    return true;
  }

  const s1 = Math.abs(h10 - h00) / map.cellSize;
  const s2 = Math.abs(h11 - h01) / map.cellSize;
  const s3 = Math.abs(h01 - h00) / map.cellSize;
  const s4 = Math.abs(h11 - h10) / map.cellSize;
  return Math.max(s1, s2, s3, s4) > MAX_SLOPE;
}

export function cellCenter(map: MapDef, cx: number, cz: number): { x: number; z: number } {
  const half = map.size / 2;
  return {
    x: -half + (cx + 0.5) * map.cellSize,
    z: -half + (cz + 0.5) * map.cellSize,
  };
}

export function worldToCell(
  map: MapDef,
  x: number,
  z: number,
): { cx: number; cz: number } {
  const half = map.size / 2;
  return {
    cx: clamp(Math.floor((x + half) / map.cellSize), 0, map.cols - 1),
    cz: clamp(Math.floor((z + half) / map.cellSize), 0, map.rows - 1),
  };
}

export function clampToMap(
  map: MapDef,
  x: number,
  z: number,
  margin = 0,
): { x: number; z: number } {
  const half = map.size / 2;
  const limit = Math.max(0, half - margin);
  return {
    x: clamp(x, -limit, limit),
    z: clamp(z, -limit, limit),
  };
}

export function groundLineClear(
  map: MapDef,
  fromX: number,
  fromZ: number,
  toX: number,
  toZ: number,
): boolean {
  const distance = Math.hypot(toX - fromX, toZ - fromZ);
  const samples = Math.max(1, Math.ceil(distance / (map.cellSize / 2)));
  for (let i = 1; i < samples; i += 1) {
    const t = i / samples;
    const x = fromX + (toX - fromX) * t;
    const z = fromZ + (toZ - fromZ) * t;
    if (isBlockedAt(map, x, z)) {
      return false;
    }
  }
  return true;
}

export function lineOfSightClear(
  map: MapDef,
  fromX: number,
  fromZ: number,
  fromY: number,
  toX: number,
  toZ: number,
  toY: number,
): boolean {
  const distance = Math.hypot(toX - fromX, toZ - fromZ);
  const samples = Math.max(1, Math.ceil(distance / (map.cellSize / 2)));
  for (let i = 1; i < samples; i += 1) {
    const t = i / samples;
    const x = fromX + (toX - fromX) * t;
    const z = fromZ + (toZ - fromZ) * t;
    const y = fromY + (toY - fromY) * t;
    const terrain = heightAt(map, x, z);
    if (terrain > y + 0.01) {
      return false;
    }
  }
  return true;
}
