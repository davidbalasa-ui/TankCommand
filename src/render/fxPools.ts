// GPU pools for the battle effects. Every effect particle lives in one of a handful of instanced
// draws (soft camera-facing sprites, ground decals, stretched ribbons, lit debris chunks), so a
// big fight with hundreds of live particles still costs about six draw calls and no per-particle
// materials or meshes. Render-only: nothing here feeds back into the sim.
import * as THREE from 'three';

const SPRITE_VERTEX = /* glsl */ `
attribute vec3 aPos;
attribute vec4 aColor;
attribute vec3 aSizeRotSeed;
varying vec2 vUv;
varying vec4 vColor;
varying float vSeed;
void main() {
  vUv = uv;
  vColor = aColor;
  vSeed = aSizeRotSeed.z;
  vec4 mv = viewMatrix * vec4(aPos, 1.0);
  float c = cos(aSizeRotSeed.y);
  float s = sin(aSizeRotSeed.y);
  vec2 p = position.xy;
  mv.xy += vec2(c * p.x - s * p.y, s * p.x + c * p.y) * aSizeRotSeed.x;
  gl_Position = projectionMatrix * mv;
}`;

// Additive glow: a soft halo with a white-hot core.
const GLOW_FRAGMENT = /* glsl */ `
varying vec2 vUv;
varying vec4 vColor;
varying float vSeed;
void main() {
  float d = length(vUv * 2.0 - 1.0);
  if (d > 1.0) discard;
  float halo = 1.0 - d;
  halo *= halo;
  float core = 1.0 - smoothstep(0.0, 0.42, d);
  vec3 color = mix(vColor.rgb, vec3(1.0), core * 0.55);
  gl_FragColor = vec4(color, vColor.a * (halo + core * 0.6));
}`;

// Smoke and dust: soft round puffs with a cheap lumpy edge.
const SMOKE_FRAGMENT = /* glsl */ `
varying vec2 vUv;
varying vec4 vColor;
varying float vSeed;
void main() {
  vec2 q = vUv * 2.0 - 1.0;
  float d = length(q);
  float lump = 0.82 + 0.18 * sin(q.x * 5.0 + vSeed * 6.0) * sin(q.y * 4.0 + vSeed * 3.7);
  float a = 1.0 - smoothstep(0.25, 1.0, d / lump);
  if (a <= 0.01) discard;
  gl_FragColor = vec4(vColor.rgb * (0.85 + 0.25 * (1.0 - d)), vColor.a * a);
}`;

const DECAL_VERTEX = /* glsl */ `
attribute vec3 aPos;
attribute vec4 aColor;
attribute vec3 aSizeRotSeed;
varying vec2 vUv;
varying vec4 vColor;
varying float vSeed;
void main() {
  vUv = uv;
  vColor = aColor;
  vSeed = aSizeRotSeed.z;
  float c = cos(aSizeRotSeed.y);
  float s = sin(aSizeRotSeed.y);
  vec2 p = position.xy * aSizeRotSeed.x;
  vec3 world = aPos + vec3(c * p.x - s * p.y, 0.0, s * p.x + c * p.y);
  // Pulled 0.8 m towards the camera so grass tufts and coarse terrain never poke through it.
  vec4 mv = viewMatrix * vec4(world, 1.0);
  float dist = length(mv.xyz);
  mv.xyz *= max(0.0, 1.0 - 0.8 / max(dist, 1.0));
  gl_Position = projectionMatrix * mv;
}`;

// Ground decals. Seed 10 (tested as > 9.5: varyings interpolate inexactly) draws a thin ring (shock waves), otherwise a soft blotch (scorch, glow).
const DECAL_FRAGMENT = /* glsl */ `
varying vec2 vUv;
varying vec4 vColor;
varying float vSeed;
void main() {
  vec2 q = vUv * 2.0 - 1.0;
  float d = length(q);
  float a;
  if (vSeed > 9.5) {
    a = smoothstep(0.7, 0.93, d) * (1.0 - smoothstep(0.94, 1.0, d));
  } else {
    float ang = atan(q.y, q.x);
    float edge = 0.85 + 0.08 * sin(ang * 5.0 + vSeed * 9.0) + 0.05 * sin(ang * 11.0 + vSeed * 4.0);
    a = 1.0 - smoothstep(edge * 0.3, edge, d);
  }
  if (a <= 0.01) discard;
  gl_FragColor = vec4(vColor.rgb, vColor.a * a);
}`;

const RIBBON_VERTEX = /* glsl */ `
attribute vec3 aStart;
attribute vec3 aEnd;
attribute vec4 aColor;
attribute float aWidth;
varying vec2 vUv;
varying vec4 vColor;
void main() {
  vUv = position.xy;
  vColor = aColor;
  vec4 a = viewMatrix * vec4(aStart, 1.0);
  vec4 b = viewMatrix * vec4(aEnd, 1.0);
  vec4 p = mix(a, b, position.x);
  vec2 dir = b.xy - a.xy;
  float len = length(dir);
  dir = len > 1e-5 ? dir / len : vec2(1.0, 0.0);
  vec2 side = vec2(-dir.y, dir.x);
  p.xy += side * position.y * aWidth + dir * (position.x * 2.0 - 1.0) * aWidth * 0.5;
  gl_Position = projectionMatrix * p;
}`;

const RIBBON_FRAGMENT = /* glsl */ `
varying vec2 vUv;
varying vec4 vColor;
void main() {
  float across = abs(vUv.y);
  float soft = 1.0 - across;
  float core = 1.0 - smoothstep(0.0, 0.38, across);
  vec3 color = mix(vColor.rgb, vec3(1.0), core * 0.7);
  gl_FragColor = vec4(color, vColor.a * (soft * soft * 0.8 + core * 0.6));
}`;

/** A pool of sprite-like quads with per-instance position, colour+alpha and size/rotation/seed. */
export class QuadPool {
  readonly mesh: THREE.Mesh;
  private readonly geometry: THREE.InstancedBufferGeometry;
  private readonly pos: THREE.InstancedBufferAttribute;
  private readonly color: THREE.InstancedBufferAttribute;
  private readonly params: THREE.InstancedBufferAttribute;
  private count = 0;

  constructor(
    scene: THREE.Scene,
    readonly capacity: number,
    vertex: string,
    fragment: string,
    blending: THREE.Blending,
    renderOrder: number,
  ) {
    const base = new THREE.PlaneGeometry(2, 2);
    this.geometry = new THREE.InstancedBufferGeometry();
    this.geometry.index = base.index;
    this.geometry.setAttribute('position', base.getAttribute('position'));
    this.geometry.setAttribute('uv', base.getAttribute('uv'));
    this.pos = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.color = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 4), 4).setUsage(THREE.DynamicDrawUsage);
    this.params = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.geometry.setAttribute('aPos', this.pos);
    this.geometry.setAttribute('aColor', this.color);
    this.geometry.setAttribute('aSizeRotSeed', this.params);
    this.geometry.instanceCount = 0;
    const material = new THREE.ShaderMaterial({
      vertexShader: vertex,
      fragmentShader: fragment,
      transparent: true,
      depthWrite: false,
      blending,
      side: THREE.DoubleSide,
    });
    if (vertex === DECAL_VERTEX) {
      // Ground decals sit on a terrain mesh that is coarser than the height samples: pull them
      // towards the camera so they never z-fight with it.
      material.polygonOffset = true;
      material.polygonOffsetFactor = -4;
      material.polygonOffsetUnits = -8;
    }
    this.mesh = new THREE.Mesh(this.geometry, material);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = renderOrder;
    scene.add(this.mesh);
  }

  begin(): void {
    this.count = 0;
  }

  get full(): boolean {
    return this.count >= this.capacity;
  }

  push(x: number, y: number, z: number, r: number, g: number, b: number, a: number, size: number, rot: number, seed: number): void {
    if (this.count >= this.capacity || a <= 0.003) {
      return;
    }
    const i = this.count;
    const p = this.pos.array as Float32Array;
    const c = this.color.array as Float32Array;
    const s = this.params.array as Float32Array;
    p[i * 3] = x;
    p[i * 3 + 1] = y;
    p[i * 3 + 2] = z;
    c[i * 4] = r;
    c[i * 4 + 1] = g;
    c[i * 4 + 2] = b;
    c[i * 4 + 3] = a;
    s[i * 3] = size;
    s[i * 3 + 1] = rot;
    s[i * 3 + 2] = seed;
    this.count += 1;
  }

  end(): void {
    this.geometry.instanceCount = this.count;
    for (const attribute of [this.pos, this.color, this.params]) {
      attribute.clearUpdateRanges();
      if (this.count > 0) {
        attribute.addUpdateRange(0, this.count * attribute.itemSize);
        attribute.needsUpdate = true;
      }
    }
  }

  dispose(scene: THREE.Scene): void {
    scene.remove(this.mesh);
    this.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
  }
}

/** Camera-facing ribbons between two points (tracers, lightning segments, beams). */
export class RibbonPool {
  readonly mesh: THREE.Mesh;
  private readonly geometry: THREE.InstancedBufferGeometry;
  private readonly start: THREE.InstancedBufferAttribute;
  private readonly finish: THREE.InstancedBufferAttribute;
  private readonly color: THREE.InstancedBufferAttribute;
  private readonly width: THREE.InstancedBufferAttribute;
  private count = 0;

  constructor(scene: THREE.Scene, readonly capacity: number) {
    this.geometry = new THREE.InstancedBufferGeometry();
    // x: 0 at the start, 1 at the end; y: -1..1 across.
    this.geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, -1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0], 3));
    this.geometry.setIndex([0, 1, 2, 0, 2, 3]);
    this.start = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.finish = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3).setUsage(THREE.DynamicDrawUsage);
    this.color = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 4), 4).setUsage(THREE.DynamicDrawUsage);
    this.width = new THREE.InstancedBufferAttribute(new Float32Array(capacity), 1).setUsage(THREE.DynamicDrawUsage);
    this.geometry.setAttribute('aStart', this.start);
    this.geometry.setAttribute('aEnd', this.finish);
    this.geometry.setAttribute('aColor', this.color);
    this.geometry.setAttribute('aWidth', this.width);
    this.geometry.instanceCount = 0;
    const material = new THREE.ShaderMaterial({
      vertexShader: RIBBON_VERTEX,
      fragmentShader: RIBBON_FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(this.geometry, material);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 6;
    scene.add(this.mesh);
  }

  begin(): void {
    this.count = 0;
  }

  push(ax: number, ay: number, az: number, bx: number, by: number, bz: number, r: number, g: number, b: number, a: number, width: number): void {
    if (this.count >= this.capacity || a <= 0.003) {
      return;
    }
    const i = this.count;
    const s = this.start.array as Float32Array;
    const e = this.finish.array as Float32Array;
    const c = this.color.array as Float32Array;
    const w = this.width.array as Float32Array;
    s[i * 3] = ax;
    s[i * 3 + 1] = ay;
    s[i * 3 + 2] = az;
    e[i * 3] = bx;
    e[i * 3 + 1] = by;
    e[i * 3 + 2] = bz;
    c[i * 4] = r;
    c[i * 4 + 1] = g;
    c[i * 4 + 2] = b;
    c[i * 4 + 3] = a;
    w[i] = width;
    this.count += 1;
  }

  end(): void {
    this.geometry.instanceCount = this.count;
    for (const attribute of [this.start, this.finish, this.color, this.width]) {
      attribute.clearUpdateRanges();
      if (this.count > 0) {
        attribute.addUpdateRange(0, this.count * attribute.itemSize);
        attribute.needsUpdate = true;
      }
    }
  }

  dispose(scene: THREE.Scene): void {
    scene.remove(this.mesh);
    this.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
  }
}

export function glowPool(scene: THREE.Scene, capacity: number): QuadPool {
  return new QuadPool(scene, capacity, SPRITE_VERTEX, GLOW_FRAGMENT, THREE.AdditiveBlending, 7);
}

export function smokePool(scene: THREE.Scene, capacity: number): QuadPool {
  return new QuadPool(scene, capacity, SPRITE_VERTEX, SMOKE_FRAGMENT, THREE.NormalBlending, 5);
}

export function decalPool(scene: THREE.Scene, capacity: number, additive: boolean): QuadPool {
  return new QuadPool(
    scene,
    capacity,
    DECAL_VERTEX,
    DECAL_FRAGMENT,
    additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    additive ? 2 : 1,
  );
}
