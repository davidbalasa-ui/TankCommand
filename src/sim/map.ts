import {
  DEFAULT_CELL_SIZE,
  DEFAULT_MAP_SIZE,
  MAX_SLOPE,
} from './tuning';

export interface MapDef {
  seed: number;
  size: number;
  cellSize: number;
  cols: number;
  rows: number;
  heights: Float32Array;
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
  };

  const half = map.size / 2;

  for (let iz = 0; iz <= rows; iz += 1) {
    const z = -half + iz * cellSize;
    for (let ix = 0; ix <= cols; ix += 1) {
      const x = -half + ix * cellSize;
      const octave1 = valueNoise(x * 0.035, z * 0.035, seed) * 2.4;
      const octave2 = valueNoise(x * 0.09, z * 0.09, seed + 17) * 1.1;
      const octave3 = valueNoise(x * 0.19, z * 0.19, seed + 43) * 0.45;
      let h = octave1 + octave2 + octave3;

      const ridgeDistance = Math.abs(x + z);
      const ridgeAlong = Math.abs(x - z);
      if (ridgeAlong < 70) {
        h += Math.max(0, 1 - ridgeDistance / 6) * 9;
      }

      const edgeDistance = Math.min(ix, iz, cols - ix, rows - iz) * cellSize;
      if (edgeDistance < 6) {
        h *= edgeDistance / 6;
      }

      setHeight(map, ix, iz, h);
    }
  }

  flattenCircle(map, -50, -50, 14, 24, 0);
  flattenCircle(map, 50, 50, 14, 24, 0);
  flattenCircle(map, 20, -20, 6, 10, 0);

  return map;
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
  return slopeAt(map, x, z) > MAX_SLOPE;
}

export function isBlockedCell(map: MapDef, cx: number, cz: number): boolean {
  if (cx < 0 || cz < 0 || cx >= map.cols || cz >= map.rows) {
    return true;
  }
  const h00 = heightAtVertex(map, cx, cz);
  const h10 = heightAtVertex(map, cx + 1, cz);
  const h01 = heightAtVertex(map, cx, cz + 1);
  const h11 = heightAtVertex(map, cx + 1, cz + 1);

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
