// The land around the battlefield. The playable map no longer ends in a cliff over an empty plain:
// the ground carries on past the edge, rises into rolling hills and fades into the haze, so the
// battlefield reads as a valley in a larger world. Nothing out here is playable; the map edge
// keeps its marker and the camera target stays inside it.
//
// The mesh is a set of rings pushed out from the map's edge vertices (so the first ring meets the
// terrain exactly, with no seam), spaced further apart the further out they go.
import * as THREE from 'three';
import { heightAt, type MapDef } from '../sim/map';

/** How far out the rings go, in metres from the map edge. */
const RING_OFFSETS = [0, 1, 2, 3.5, 5.5, 8, 11, 15, 20, 26, 34, 44, 56, 72, 92, 118, 150, 190, 240, 300, 370];
/** Corner rounding of the ring shape, as a fraction of the map size. */
const CORNER_ROUND = 0.18;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function lattice(ix: number, iz: number, seed: number): number {
  let h = Math.imul(ix, 374761393) ^ Math.imul(iz, 668265263) ^ Math.imul(seed, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** Smooth value noise in [0, 1]. */
function valueNoise(x: number, z: number, seed: number): number {
  const ix = Math.floor(x);
  const iz = Math.floor(z);
  const fx = x - ix;
  const fz = z - iz;
  const u = fx * fx * (3 - 2 * fx);
  const v = fz * fz * (3 - 2 * fz);
  const a = lattice(ix, iz, seed);
  const b = lattice(ix + 1, iz, seed);
  const c = lattice(ix, iz + 1, seed);
  const d = lattice(ix + 1, iz + 1, seed);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

function hills(x: number, z: number, seed: number): number {
  return (
    valueNoise(x / 46, z / 46, seed) * 0.6 +
    valueNoise(x / 19, z / 19, seed + 7) * 0.28 +
    valueNoise(x / 8, z / 8, seed + 13) * 0.12
  );
}

/** Straight-line distance from (x, z) to the playable square (0 inside it). */
export function distanceOutside(map: MapDef, x: number, z: number): number {
  const half = map.size / 2;
  const dx = Math.max(0, Math.abs(x) - half);
  const dz = Math.max(0, Math.abs(z) - half);
  return Math.hypot(dx, dz);
}

/** Ground height anywhere: the map's own terrain inside it, the surrounding hills outside. */
export function groundHeightAt(map: MapDef, x: number, z: number): number {
  const half = map.size / 2;
  const d = distanceOutside(map, x, z);
  const edge = heightAt(map, clamp(x, -half, half), clamp(z, -half, half));
  if (d <= 0) {
    return edge;
  }
  // Hold the edge height for a few metres, then rise into hills that grow taller further out.
  const s = smoothstep(3, map.size * 0.3, d);
  const amplitude = 7 + 26 * smoothstep(map.size * 0.15, map.size * 1.1, d);
  const seed = Math.round(map.size * 13 + map.cols);
  const rolling = hills(x, z, seed) * amplitude;
  return edge * (1 - s) + (edge * 0.4 + rolling) * s;
}

export interface OuterLandColors {
  grass: THREE.Color;
  dry: THREE.Color;
  rock: THREE.Color;
  haze: THREE.Color;
}

/**
 * Builds the surrounding land as one mesh with vertex colours: grass near the edge, drier and
 * rockier on the hills, fading into the haze toward the horizon.
 */
export function buildOuterLandGeometry(map: MapDef, colors: OuterLandColors): THREE.BufferGeometry {
  const half = map.size / 2;
  // The edge loop, one vertex per terrain vertex, going round the map.
  const loop: Array<{ x: number; z: number }> = [];
  for (let ix = 0; ix <= map.cols; ix += 1) {
    loop.push({ x: -half + ix * map.cellSize, z: -half });
  }
  for (let iz = 1; iz <= map.rows; iz += 1) {
    loop.push({ x: half, z: -half + iz * map.cellSize });
  }
  for (let ix = map.cols - 1; ix >= 0; ix -= 1) {
    loop.push({ x: -half + ix * map.cellSize, z: half });
  }
  for (let iz = map.rows - 1; iz >= 1; iz -= 1) {
    loop.push({ x: -half, z: -half + iz * map.cellSize });
  }
  const round = map.size * CORNER_ROUND;
  const normals = loop.map((p) => {
    const ix = clamp(p.x, -half + round, half - round);
    const iz = clamp(p.z, -half + round, half - round);
    const nx = p.x - ix;
    const nz = p.z - iz;
    const length = Math.hypot(nx, nz) || 1;
    return { x: nx / length, z: nz / length };
  });

  const count = loop.length;
  const positions = new Float32Array(count * RING_OFFSETS.length * 3);
  const vertexColors = new Float32Array(count * RING_OFFSETS.length * 3);
  // Grass, dirt and rock weights, as the battlefield terrain uses them for its ground detail.
  const surface = new Float32Array(count * RING_OFFSETS.length * 3);
  const color = new THREE.Color();
  const sample = (x: number, z: number): number => groundHeightAt(map, x, z);
  RING_OFFSETS.forEach((offset, ring) => {
    for (let i = 0; i < count; i += 1) {
      const p = loop[i] ?? { x: 0, z: 0 };
      const n = normals[i] ?? { x: 0, z: 0 };
      const x = p.x + n.x * offset;
      const z = p.z + n.z * offset;
      const y = ring === 0 ? heightAt(map, p.x, p.z) : sample(x, z);
      const index = ring * count + i;
      positions[index * 3] = x;
      positions[index * 3 + 1] = y;
      positions[index * 3 + 2] = z;

      // Steeper and higher ground turns dry, then rocky; distance fades it into the haze.
      const slope = Math.abs(sample(x + 1.5, z) - sample(x - 1.5, z)) + Math.abs(sample(x, z + 1.5) - sample(x, z - 1.5));
      const dirt = clamp(slope / 3, 0, 1) * 0.7;
      const rock = smoothstep(10, 26, y) * 0.65;
      color.copy(colors.grass);
      color.lerp(colors.dry, dirt);
      color.lerp(colors.rock, rock);
      surface[index * 3] = Math.max(0, 1 - dirt - rock);
      surface[index * 3 + 1] = dirt;
      surface[index * 3 + 2] = rock;
      // A little darker than the battlefield, so the playable ground stands out.
      color.multiplyScalar(1 - 0.18 * smoothstep(0, 14, offset));
      color.lerp(colors.haze, smoothstep(map.size * 0.25, map.size * 2.2, offset) * 0.92);
      vertexColors[index * 3] = color.r;
      vertexColors[index * 3 + 1] = color.g;
      vertexColors[index * 3 + 2] = color.b;
    }
  });

  const indices: number[] = [];
  for (let ring = 0; ring + 1 < RING_OFFSETS.length; ring += 1) {
    for (let i = 0; i < count; i += 1) {
      const a = ring * count + i;
      const b = ring * count + ((i + 1) % count);
      const c = (ring + 1) * count + i;
      const d = (ring + 1) * count + ((i + 1) % count);
      // The loop runs clockwise seen from above (x right, z down), so this winding faces up.
      indices.push(a, b, c, b, d, c);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(vertexColors, 3));
  geometry.setAttribute('surface', new THREE.BufferAttribute(surface, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

/** The draped band that marks the playable edge: a soft line lying on the ground. */
export function buildEdgeBandGeometry(map: MapDef, width = 1.4, lift = 0.15): THREE.BufferGeometry {
  const half = map.size / 2;
  const positions: number[] = [];
  // RGBA per vertex: the outer side is solid, the inner side fades out.
  const rgba: number[] = [];
  const indices: number[] = [];
  // Each side runs from corner to corner; the band lies just inside the edge.
  const sides: Array<{ from: [number, number]; to: [number, number]; inward: [number, number] }> = [
    { from: [-half, -half], to: [half, -half], inward: [0, 1] },
    { from: [half, -half], to: [half, half], inward: [-1, 0] },
    { from: [half, half], to: [-half, half], inward: [0, -1] },
    { from: [-half, half], to: [-half, -half], inward: [1, 0] },
  ];
  for (const side of sides) {
    const steps = Math.max(1, Math.round(map.size / map.cellSize));
    const start = positions.length / 3;
    for (let s = 0; s <= steps; s += 1) {
      const t = s / steps;
      const x = side.from[0] + (side.to[0] - side.from[0]) * t;
      const z = side.from[1] + (side.to[1] - side.from[1]) * t;
      const ix = x + side.inward[0] * width;
      const iz = z + side.inward[1] * width;
      positions.push(x, heightAt(map, x, z) + lift, z);
      positions.push(ix, heightAt(map, ix, iz) + lift, iz);
      rgba.push(0.86, 0.93, 1, 0.32, 0.86, 0.93, 1, 0);
    }
    for (let s = 0; s < steps; s += 1) {
      const a = start + s * 2;
      indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(rgba, 4));
  geometry.setIndex(indices);
  return geometry;
}
