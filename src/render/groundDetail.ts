// Ground detail for the battlefield terrain shader.
//
// Two textures feed it:
// - the ground detail texture (assets/textures/terrain_detail.jpg): fine grass blades, gravel and
//   fractured rock in its R, G and B channels, about 7 m per repeat. It is read twice, the second
//   time rotated and at a finer scale, so the repeat of either lookup never lines up into a grid.
// - a small generated noise texture (this file): large, slow patches across the field (lighter and
//   darker ground, lush and dry grass, bare earth showing through the grass). It repeats only every
//   NOISE_TILE metres, more than the width of a map, so its patches never visibly repeat.
//
// The same noise is available on the CPU (groundNoiseAt) so scattered plants can match the ground
// they stand on: drier grass on the dry patches.
import * as THREE from 'three';

/** Metres covered by one repeat of the broad noise (larger than any map). */
export const NOISE_TILE = 211;
const NOISE_SIZE = 256;

function lattice(ix: number, iz: number, period: number, seed: number): number {
  const x = ((ix % period) + period) % period;
  const z = ((iz % period) + period) % period;
  let h = Math.imul(x, 374761393) ^ Math.imul(z, 668265263) ^ Math.imul(seed, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** Smooth value noise in [0, 1] that wraps every `period` lattice cells. */
function periodicNoise(u: number, v: number, period: number, seed: number): number {
  const x = u * period;
  const z = v * period;
  const ix = Math.floor(x);
  const iz = Math.floor(z);
  const fx = x - ix;
  const fz = z - iz;
  const sx = fx * fx * (3 - 2 * fx);
  const sz = fz * fz * (3 - 2 * fz);
  const a = lattice(ix, iz, period, seed);
  const b = lattice(ix + 1, iz, period, seed);
  const c = lattice(ix, iz + 1, period, seed);
  const d = lattice(ix + 1, iz + 1, period, seed);
  return a + (b - a) * sx + (c - a) * sz + (a - b - c + d) * sx * sz;
}

function fbm(u: number, v: number, periods: readonly number[], seed: number): number {
  let sum = 0;
  let weight = 0;
  let amplitude = 1;
  periods.forEach((period, index) => {
    sum += periodicNoise(u, v, period, seed + index * 101) * amplitude;
    weight += amplitude;
    amplitude *= 0.55;
  });
  return sum / weight;
}

/** Stretches a noise value round 0.5 so the patches have clearer edges. */
function contrast(value: number, amount: number): number {
  return Math.min(1, Math.max(0, 0.5 + (value - 0.5) * amount));
}

export interface GroundNoise {
  /** Light and dark ground, patches about 15 to 50 m across. */
  light: number;
  /** Mid-scale variation, 6 to 13 m. */
  mid: number;
  /** Dry (1) or lush (0) grass, patches 35 to 70 m across. */
  dry: number;
  /** Bare earth showing through the grass where this is high. */
  bare: number;
}

/** The broad ground noise at a world position (u, v wrap every NOISE_TILE metres). */
export function groundNoiseAt(seed: number, x: number, z: number): GroundNoise {
  const u = x / NOISE_TILE;
  const v = z / NOISE_TILE;
  return {
    light: contrast(fbm(u, v, [4, 8, 16], seed + 1), 1.9),
    mid: contrast(fbm(u, v, [16, 32], seed + 2), 1.7),
    dry: contrast(fbm(u, v, [3, 6, 12], seed + 3), 2.1),
    bare: contrast(fbm(u, v, [12, 24, 48, 96], seed + 4), 2.0),
  };
}

let cached: { seed: number; texture: THREE.DataTexture } | null = null;

/** The broad noise as a small repeating texture (one per map seed; the last one is kept). */
export function groundNoiseTexture(seed: number): THREE.DataTexture {
  if (cached && cached.seed === seed) {
    return cached.texture;
  }
  cached?.texture.dispose();
  const data = new Uint8Array(NOISE_SIZE * NOISE_SIZE * 4);
  for (let iz = 0; iz < NOISE_SIZE; iz += 1) {
    for (let ix = 0; ix < NOISE_SIZE; ix += 1) {
      const n = groundNoiseAt(seed, ((ix + 0.5) / NOISE_SIZE) * NOISE_TILE, ((iz + 0.5) / NOISE_SIZE) * NOISE_TILE);
      const index = (iz * NOISE_SIZE + ix) * 4;
      data[index] = Math.round(n.light * 255);
      data[index + 1] = Math.round(n.mid * 255);
      data[index + 2] = Math.round(n.dry * 255);
      data[index + 3] = Math.round(n.bare * 255);
    }
  }
  const texture = new THREE.DataTexture(data, NOISE_SIZE, NOISE_SIZE, THREE.RGBAFormat);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  cached = { seed, texture };
  return texture;
}

/**
 * Fragment shader lines for the terrain's colour stage (a MeshStandardMaterial, for `vViewPosition`).
 * Needs `vFogXZ` (world xz), `vSurface` (grass, dirt and rock weights), `vWall` (world height and
 * the up component of the normal), `uDetail` (the detail texture) and `uGroundNoise`.
 * Three texture reads: the noise and the detail texture twice.
 */
export function groundDetailGlsl(detailTile: number): string {
  const tile = detailTile.toFixed(2);
  const noiseTile = NOISE_TILE.toFixed(1);
  return `
vec4 gN = texture2D(uGroundNoise, vFogXZ / ${noiseTile});
vec3 w = vSurface / max(0.001, vSurface.x + vSurface.y + vSurface.z);
// Fine detail: the texture at its own scale plus a rotated, finer copy. A slight sharpening bias
// keeps the blades and gravel crisp at low camera angles.
vec3 dA = texture2D(uDetail, vFogXZ / ${tile}, -0.5).rgb - 0.5;
// On steep faces the top-down projection smears into streaks, so the finer copy is projected
// sideways there instead (along the face, against height) and carries the detail alone.
float steep = 1.0 - smoothstep(0.58, 0.72, vWall.y);
vec2 flatUv = mat2(0.8, -0.6, 0.6, 0.8) * vFogXZ / ${(detailTile * 0.43).toFixed(2)} + vec2(0.31, 0.57);
vec2 wallUv = vec2(vFogXZ.x + vFogXZ.y, vWall.x * 1.3) / ${(detailTile * 0.6).toFixed(2)};
vec3 dB = texture2D(uDetail, mix(flatUv, wallUv, steep), -0.5).rgb - 0.5;
vec3 dF = dA * (0.85 - 0.3 * gN.g) + dB * (0.45 + 0.3 * gN.g);
dF = mix(dF, dB * 1.25, steep);
// Close to the camera the coarser copy is magnified and goes soft: lean on the finer one there.
float nearCam = 1.0 - smoothstep(6.0, 28.0, length(vViewPosition));
dF = mix(dF, dA * 0.45 + dB * 1.0, nearCam * 0.7);
// Bare earth breaking through the grass in small patches, with ragged grassy edges.
float bare = smoothstep(0.66, 0.92, gN.a + dA.r * 0.35 + dB.r * 0.2) * w.x * 0.8;
w = vec3(w.x - bare, w.y + bare, w.z);
float fine = dot(dF, w);
// Bare patches take the colour of earth (the vertex colour there is still grass).
vec3 earth = vec3(0.2, 0.145, 0.075) * (1.0 + dF.g * 1.4);
diffuseColor.rgb = mix(diffuseColor.rgb, earth, smoothstep(0.0, 0.6, bare) * 0.8);
// Lush and dry grass, then light and dark ground over everything.
vec3 dryTint = mix(vec3(0.87, 1.05, 0.84), vec3(1.08, 1.0, 0.76), gN.b);
diffuseColor.rgb *= mix(vec3(1.0), dryTint, w.x);
diffuseColor.rgb *= (1.0 + fine * (1.75 + nearCam * 0.5)) * (0.8 + gN.r * 0.4) * (0.94 + gN.g * 0.12);
`;
}

/**
 * The land past the map edge keeps its plain lit material (it can fill much of the screen), but
 * gets one read of the detail texture, so the ground does not turn flat and smooth at the edge.
 * Off until the detail texture has loaded; set `needsUpdate` on the material once it has.
 */
export function addOuterLandDetail(
  material: THREE.Material,
  detail: { value: THREE.Texture | null },
  detailTile: number,
): void {
  material.onBeforeCompile = (shader) => {
    if (!detail.value) {
      return;
    }
    shader.uniforms.uDetail = detail;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec3 surface;\nvarying vec3 vOutSurface;\nvarying vec2 vOutXZ;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvOutXZ = position.xz;\nvOutSurface = surface;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform sampler2D uDetail;\nvarying vec3 vOutSurface;\nvarying vec2 vOutXZ;')
      .replace(
        '#include <color_fragment>',
        `#include <color_fragment>
vec3 dO = texture2D(uDetail, vOutXZ / ${detailTile.toFixed(2)}).rgb - 0.5;
vec3 wO = vOutSurface / max(0.001, vOutSurface.x + vOutSurface.y + vOutSurface.z);
diffuseColor.rgb *= 1.0 + dot(dO, wO) * 1.5;`,
      );
  };
  material.customProgramCacheKey = () => (detail.value ? 'outerDetail' : 'outer');
}
