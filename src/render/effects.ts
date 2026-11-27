// Weapon, impact, explosion and fire effects. Render-only: nothing here feeds back into the sim.
//
// Every particle is drawn through a few shared instanced pools (fxPools.ts), so a big battle stays
// at about six effect draw calls. Epic over realistic: big muzzle blasts, fireballs that roll from
// white-hot to dark red, shock rings, flying debris, burning wrecks with smoke columns.
//
// Terran weapons burn orange (tracers, shells, missiles with smoke trails). Every Arcadian weapon
// fires gold energy: plasma orbs with a crackle of gold lightning around them, gold muzzle flares
// and gold lightning star-bursts where they hit. Special kinds keep their own looks:
//   laser        Terran fighter: cyan energy bolts.
//   bombs        Terran bomber: a dark finned bomb, a huge fireball, shock ring, debris and scorch.
//   lightning    Arcadian fighter: a jagged gold-white arc from the gun to the target.
//   ground_beam  Arcadian Disc: a thick gold beam that tears the ground open.
//   shard        The Shard (neutral crystal): a kinked white-violet lance, prism flash on impact.
//   spore        Third faction (sample): a slow pod that bursts into a lingering cloud.
import * as THREE from 'three';
import { SIM_TICK_HZ } from '../sim/constants';
import { MUZZLE_HEIGHT } from '../sim/tuning';
import { QuadPool, RibbonPool, decalPool, glowPool, haloPool, smokePool, tonguePool } from './fxPools';

type Rgb = readonly [number, number, number];

function rgb(hex: number): Rgb {
  return [((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255];
}

const WHITE: Rgb = [1, 1, 1];
const HOT: Rgb = [1, 0.93, 0.72];
const FIRE: Rgb = [1, 0.55, 0.12];
const EMBER: Rgb = [0.55, 0.12, 0.03];
const GOLD: Rgb = [1, 0.72, 0.18];
const GOLD_HOT: Rgb = [1, 0.95, 0.75];
const CYAN: Rgb = [0.2, 0.84, 1];
const VIOLET: Rgb = [0.6, 0.36, 1];
const SMOKE: Rgb = [0.2, 0.18, 0.16];
const SMOKE_LIGHT: Rgb = [0.42, 0.38, 0.34];
const DUST: Rgb = [0.5, 0.44, 0.36];
const SCORCH: Rgb = [0.03, 0.025, 0.02];
const SPORE: Rgb = [0.66, 0.74, 0.29];
// Terran muzzle blast palette (tools/art/v2/viewer/blast.js).
const HALO: Rgb = [0.45, 0.88, 1];
const WHITE_HOT: Rgb = [0.88, 0.98, 1];
const BLAST_CYAN: Rgb = [0.1, 0.5, 1];
const BLAST_ORANGE: Rgb = [1, 0.58, 0.2];
const SPARK: Rgb = [1, 0.9, 0.6];
const BLAST_SMOKE: Rgb = [0.54, 0.57, 0.62];
const BLAST_SMOKE_HOT: Rgb = [0.68, 0.72, 0.78];
const BLAST_DUST: Rgb = [0.7, 0.62, 0.48];

/**
 * Where each Terran gun's muzzle sits on its model: metres forward of the unit's centre and metres
 * above the ground (the sim fires every shot from the centre at MUZZLE_HEIGHT).
 */
const MUZZLE_AT: Record<string, readonly [number, number]> = {
  autocannon: [1.9, 1.2],
  cannon: [2.4, 1.3],
  heavy_cannon: [3, 1.5],
  shell: [2.6, 3.4],
  missile: [0.6, 1.7],
};

/** Visual size per weapon kind (1 = a light tank's cannon). */
const WEAPON_SCALE: Record<string, number> = {
  autocannon: 0.65,
  cannon: 1,
  heavy_cannon: 1.45,
  missile: 1.1,
  shell: 1.6,
  laser: 0.8,
  bombs: 2.2,
  lightning: 0.9,
  ground_beam: 2,
  shard: 1.2,
  spore: 1.3,
};


type Layer = 0 | 1 | 2 | 3 | 4; // glow, smoke, scorch decal, glowing decal, alpha-blended halo
type Fade = 0 | 1 | 2; // 0 fade out, 1 fade in then out (smoke), 2 hold then fade (decals)

interface Particle {
  layer: Layer;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  gravity: number;
  drag: number;
  age: number;
  life: number;
  size0: number;
  size1: number;
  c0: Rgb;
  c1: Rgb;
  alpha: number;
  fade: Fade;
  rot: number;
  spin: number;
  seed: number;
  /** Drawn at least once: even a very short particle shows for one frame at any frame rate. */
  drawn: boolean;
}

interface Ribbon {
  ax: number;
  ay: number;
  az: number;
  bx: number;
  by: number;
  bz: number;
  c: Rgb;
  alpha: number;
  width: number;
  age: number;
  life: number;
  drawn: boolean;
  /** Alpha-blended flame tongue / spark streak instead of an additive tracer. */
  soft?: boolean;
}

interface Chunk {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  rx: number;
  ry: number;
  spin: number;
  size: number;
  age: number;
  life: number;
  ground: number;
  glow: boolean;
}

/** A fire-and-smoke source at a fixed spot (a wreck, a ruined building). */
export interface Burner {
  x: number;
  y: number;
  z: number;
  size: number;
  age: number;
  fireSec: number;
  smokeSec: number;
  alive: boolean;
  acc: number;
}

interface Tracked {
  kind: string | undefined;
  alien: boolean;
  scale: number;
  prev: THREE.Vector3 | null;
  frames: number;
}

const MAX_BURNERS = 28;
const rand = (a: number, b: number): number => a + Math.random() * (b - a);

export class Effects {
  private readonly glow: QuadPool;
  private readonly smoke: QuadPool;
  private readonly scorch: QuadPool;
  private readonly groundGlow: QuadPool;
  private readonly ribbons: RibbonPool;
  private readonly halo: QuadPool;
  private readonly tongues: RibbonPool;
  private readonly chunkMesh: THREE.InstancedMesh;
  private readonly particles: Particle[] = [];
  private readonly spare: Particle[] = [];
  private readonly ribbonList: Ribbon[] = [];
  private readonly chunks: Chunk[] = [];
  private readonly burners: Burner[] = [];
  private readonly delayed: Array<{ at: number; run: () => void }> = [];
  private readonly tracked = new Map<THREE.Object3D, Tracked>();
  private readonly bombGeometry = new THREE.CapsuleGeometry(0.22, 0.7, 3, 8).rotateX(Math.PI / 2);
  private readonly bombMaterial = new THREE.MeshStandardMaterial({ color: 0x23272c, metalness: 0.7, roughness: 0.45 });
  /** A small missile pointing along +Z: body, nose cone and four tail fins in one geometry. */
  private readonly missileGeometry = buildMissileGeometry();
  private readonly missileMaterial = new THREE.MeshStandardMaterial({ color: 0xc9ccd0, metalness: 0.55, roughness: 0.4 });
  private readonly missileMaterialAlien = new THREE.MeshStandardMaterial({ color: 0xc9a457, metalness: 0.8, roughness: 0.3, emissive: 0x3a2a08 });
  private readonly chunkGeometry = new THREE.DodecahedronGeometry(1, 0);
  private readonly chunkMaterial = new THREE.MeshStandardMaterial({ color: 0x2e2822, roughness: 0.95, flatShading: true });
  private readonly matrix = new THREE.Matrix4();
  private readonly quat = new THREE.Quaternion();
  private readonly euler = new THREE.Euler();
  private readonly vec = new THREE.Vector3();
  private readonly vec2 = new THREE.Vector3();
  private readonly scaleVec = new THREE.Vector3();
  private time = 0;
  /** 1 = full detail; lower values thin the optional particles (set from the quality level). */
  private detail = 1;

  constructor(private readonly scene: THREE.Scene) {
    this.glow = glowPool(scene, 2400);
    this.smoke = smokePool(scene, 900);
    this.scorch = decalPool(scene, 160, false);
    this.groundGlow = decalPool(scene, 160, true);
    this.ribbons = new RibbonPool(scene, 2400);
    this.halo = haloPool(scene, 900);
    this.tongues = tonguePool(scene, 900);
    this.chunkMesh = new THREE.InstancedMesh(this.chunkGeometry, this.chunkMaterial, 260);
    this.chunkMesh.count = 0;
    this.chunkMesh.frustumCulled = false;
    this.chunkMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    scene.add(this.chunkMesh);
    if (__TEST_HOOK__ && typeof window !== 'undefined') {
      (window as unknown as { __TC_FX__?: Effects }).__TC_FX__ = this;
    }
  }

  get count(): number {
    return this.particles.length + this.ribbonList.length + this.chunks.length;
  }

  /** 0 (lowest quality) .. 1 (full): scales how many optional particles big effects spawn. */
  setDetail(detail: number): void {
    this.detail = Math.min(1, Math.max(0.3, detail));
  }

  // ---- projectiles ---------------------------------------------------------------------
  /**
   * An object for a projectile in flight. The caller positions and aims it (+Z forward); its look
   * is drawn into the shared pools each frame, so only bombs carry a real mesh.
   */
  projectileMesh(kind: string | undefined, human: boolean): THREE.Object3D {
    const group = new THREE.Group();
    if (kind === 'bombs') {
      const bomb = new THREE.Mesh(this.bombGeometry, this.bombMaterial);
      bomb.castShadow = true;
      group.add(bomb);
    }
    if (kind === 'missile') {
      const missile = new THREE.Mesh(this.missileGeometry, human ? this.missileMaterial : this.missileMaterialAlien);
      group.add(missile);
    }
    this.tracked.set(group, { kind, alien: !human, scale: WEAPON_SCALE[kind ?? ''] ?? 1, prev: null, frames: 0 });
    return group;
  }

  disposeProjectileMesh(object: THREE.Object3D): void {
    this.tracked.delete(object);
  }

  private drawProjectile(object: THREE.Object3D, info: Tracked): void {
    const p = object.position;
    const s = info.scale;
    const forward = this.vec.set(0, 0, 1).applyQuaternion(object.quaternion);
    const kind = info.kind;
    info.frames += 1;
    if (kind === 'bombs') {
      this.flash(p.x - forward.x * 0.5, p.y - forward.y * 0.5, p.z - forward.z * 0.5, 0.35, FIRE, 0.9);
      return;
    }
    if (kind === 'lightning' || kind === 'ground_beam') {
      this.flash(p.x, p.y, p.z, kind === 'lightning' ? 0.5 : 1.1, GOLD_HOT, 1);
      return;
    }
    if (kind === 'shard') {
      this.flash(p.x, p.y, p.z, 0.45, [0.95, 0.92, 1], 1);
      return;
    }
    if (kind === 'spore') {
      this.frameSprite(1, p.x, p.y, p.z, 0.55, SPORE, 0.95);
      this.flash(p.x, p.y, p.z, 0.5, SPORE, 0.5);
      return;
    }
    if (kind === 'laser') {
      this.streak(p, forward, 2.6, CYAN, 0.24, 1);
      this.flash(p.x, p.y, p.z, 0.45, CYAN, 0.8);
      return;
    }
    if (info.alien) {
      // Gold plasma orb with a short trail and a crackle of gold lightning around it.
      this.flash(p.x, p.y, p.z, 0.42 * s, GOLD_HOT, 1);
      this.flash(p.x, p.y, p.z, 1.05 * s, GOLD, 0.55);
      this.streak(p, forward, 1.4 * s, GOLD, 0.22 * s, 0.75);
      if (Math.random() < 0.7) {
        const r = 0.55 * s;
        this.arc(
          p.x + rand(-r, r),
          p.y + rand(-r, r),
          p.z + rand(-r, r),
          p.x + rand(-r, r),
          p.y + rand(-r, r),
          p.z + rand(-r, r),
          GOLD_HOT,
          0.034,
          3,
          0.25 * s,
          0.07,
        );
      }
      if (kind === 'missile' && info.frames % 2 === 0) {
        this.spawn(0, p.x, p.y, p.z, -forward.x * 2, -forward.y * 2, -forward.z * 2, 0.25, 0.55 * s, 0.1, GOLD, EMBER, 0.6, 0);
      }
      return;
    }
    if (kind === 'missile') {
      // Exhaust: a short flame out of the tail with a hot core, smoke puffs behind.
      const tail = this.vec2.copy(p).addScaledVector(forward, -0.55);
      this.streak(tail, forward, 0.9, FIRE, 0.2, 1);
      this.flash(tail.x, tail.y, tail.z, 0.5, FIRE, 0.95);
      this.flash(tail.x, tail.y, tail.z, 0.22, HOT, 1);
      if (info.frames % 2 === 0 && this.optional(1) > 0) {
        this.spawn(1, p.x - forward.x * 0.6, p.y, p.z - forward.z * 0.6, rand(-0.3, 0.3), 0.6, rand(-0.3, 0.3), 1.1, 0.35, 1.3, SMOKE_LIGHT, SMOKE_LIGHT, 0.45, 1);
      }
      return;
    }
    if (kind === 'shell') {
      this.flash(p.x, p.y, p.z, 0.6, HOT, 1);
      this.flash(p.x, p.y, p.z, 1.2, FIRE, 0.5);
      this.streak(p, forward, 2.4, FIRE, 0.22, 0.8);
      return;
    }
    // Tank cannon and autocannon: a bright tracer with a hot head.
    this.streak(p, forward, 1.3 + s * 1.1, [1, 0.82, 0.45], 0.13 * s + 0.06, 1);
    this.flash(p.x, p.y, p.z, 0.3 * s, HOT, 0.9);
  }

  /** A tracer ribbon behind a point along its direction of travel, for this frame only. */
  private streak(p: THREE.Vector3, forward: THREE.Vector3, length: number, color: Rgb, width: number, alpha: number): void {
    this.ribbonList.push({
      ax: p.x - forward.x * length,
      ay: p.y - forward.y * length,
      az: p.z - forward.z * length,
      bx: p.x,
      by: p.y,
      bz: p.z,
      c: color,
      alpha,
      width,
      age: 0,
      life: 0.025,
      drawn: false,
    });
  }

  // ---- arcs, beams, lances -------------------------------------------------------------
  /** A jagged arc from a to b (Arcadian lightning). Short-lived, so calling it every frame crackles. */
  lightning(a: THREE.Vector3, b: THREE.Vector3, color = 0xffe7a0, ttl = 0.05, segments = 9, jitter = 0.5): void {
    this.arc(a.x, a.y, a.z, b.x, b.y, b.z, rgb(color), ttl, segments, jitter, 0.2);
  }

  private arc(
    ax: number,
    ay: number,
    az: number,
    bx: number,
    by: number,
    bz: number,
    color: Rgb,
    ttl: number,
    segments: number,
    jitter: number,
    width: number,
  ): void {
    const dx = bx - ax;
    const dz = bz - az;
    const flat = Math.hypot(dx, dz) || 1;
    const sx = -dz / flat;
    const sz = dx / flat;
    let px = ax;
    let py = ay;
    let pz = az;
    for (let i = 1; i <= segments; i += 1) {
      const t = i / segments;
      let nx = ax + (bx - ax) * t;
      let ny = ay + (by - ay) * t;
      let nz = az + (bz - az) * t;
      if (i < segments) {
        const amount = jitter * Math.sin(Math.PI * t);
        const k = (Math.random() * 2 - 1) * amount;
        nx += sx * k;
        nz += sz * k;
        ny += (Math.random() * 2 - 1) * amount * 0.7;
      }
      this.ribbonList.push({ ax: px, ay: py, az: pz, bx: nx, by: ny, bz: nz, c: color, alpha: 1, width, age: 0, life: ttl, drawn: false });
      px = nx;
      py = ny;
      pz = nz;
    }
  }

  /** Short gold arcs flickering over an Arcadian hull: the cheap idle "charged" look. */
  arcAround(x: number, y: number, z: number, radius: number): void {
    const a = Math.random() * Math.PI * 2;
    const b = a + rand(0.8, 2.2);
    const h = rand(-0.2, 0.35) * radius;
    this.arc(
      x + Math.cos(a) * radius,
      y + h,
      z + Math.sin(a) * radius,
      x + Math.cos(b) * radius * 0.8,
      y + h + rand(-0.3, 0.3) * radius,
      z + Math.sin(b) * radius * 0.8,
      GOLD_HOT,
      0.07,
      4,
      0.3 * radius,
      0.08,
    );
  }

  /**
   * The Shard's lance: a few straight segments with sharp angular kinks (crystalline, never curvy).
   * `seed` fixes the kinks so they hold still between re-rolls; `strength` scales the brightness.
   */
  shardLance(a: THREE.Vector3, b: THREE.Vector3, strength: number, ttl: number, seed: number): void {
    const dx = b.x - a.x;
    const dz = b.z - a.z;
    const length = Math.hypot(dx, b.y - a.y, dz);
    if (length < 0.01) {
      return;
    }
    const flat = Math.hypot(dx, dz) || 1;
    const segments = length > 12 ? 4 : 3;
    let px = a.x;
    let py = a.y;
    let pz = a.z;
    for (let i = 1; i <= segments; i += 1) {
      const t = i / segments;
      let nx = a.x + dx * t;
      let ny = a.y + (b.y - a.y) * t;
      let nz = a.z + dz * t;
      if (i < segments) {
        const r = Math.sin(seed * 12.9898 + i * 78.233) * 43758.5453;
        const kink = (r - Math.floor(r)) * 2 - 1;
        const amount = kink * Math.min(1.1, length * 0.06);
        nx += (-dz / flat) * amount;
        nz += (dx / flat) * amount;
        ny += kink * 0.25;
      }
      const color: Rgb = strength >= 1 ? [0.75, 0.6, 1] : VIOLET;
      this.ribbonList.push({ ax: px, ay: py, az: pz, bx: nx, by: ny, bz: nz, c: color, alpha: Math.min(1, strength), width: strength >= 1 ? 0.2 : 0.14, age: 0, life: ttl, drawn: false });
      px = nx;
      py = ny;
      pz = nz;
    }
  }

  /** A straight beam from a to b (the Disc's ground beam) with a white core and a gold sheath. */
  beam(a: THREE.Vector3, b: THREE.Vector3, width: number, ttl = 0.05): void {
    const flicker = 0.85 + Math.random() * 0.3;
    this.ribbonList.push({ ax: a.x, ay: a.y, az: a.z, bx: b.x, by: b.y, bz: b.z, c: GOLD, alpha: 0.8, width: width * flicker, age: 0, life: ttl, drawn: false });
    this.ribbonList.push({ ax: a.x, ay: a.y, az: a.z, bx: b.x, by: b.y, bz: b.z, c: GOLD_HOT, alpha: 1, width: width * 0.4 * flicker, age: 0, life: ttl, drawn: false });
    if (Math.random() < 0.5) {
      this.arc(a.x, a.y, a.z, b.x, b.y, b.z, GOLD_HOT, 0.05, 6, width * 1.2, 0.08);
    }
  }

  // ---- muzzle flashes ------------------------------------------------------------------
  /** The blast where a shot leaves the gun. `dirX/dirZ` aim the flame (optional). */
  muzzle(
    x: number,
    y: number,
    z: number,
    kind: string | undefined,
    alien = false,
    dirX = 0,
    dirZ = 0,
    at: { x: number; y: number; z: number } | null = null,
  ): void {
    const s = WEAPON_SCALE[kind ?? ''] ?? 1;
    const len = Math.hypot(dirX, dirZ);
    const fx = len > 1e-6 ? dirX / len : 0;
    const fz = len > 1e-6 ? dirZ / len : 0;
    if (kind === 'laser') {
      this.spawn(0, x, y, z, 0, 0, 0, 0.1, 0.5, 1.2, WHITE, CYAN, 1, 0);
      return;
    }
    if (kind === 'bombs' || kind === 'spore' || kind === 'shard') {
      return;
    }
    if (alien || kind === 'lightning' || kind === 'ground_beam') {
      // Gold flare, a quick gold ring and a few arcs licking forward out of the gun.
      this.spawn(0, x, y, z, 0, 0, 0, 0.12, 0.7 * s, 1.6 * s, GOLD_HOT, GOLD, 1, 0);
      this.spawn(0, x + fx * 0.5 * s, y, z + fz * 0.5 * s, fx * 3, 0, fz * 3, 0.16, 0.5 * s, 1.1 * s, GOLD, GOLD, 0.7, 0);
      const arcs = this.optional(kind === 'ground_beam' ? 4 : 2);
      for (let i = 0; i < arcs; i += 1) {
        const reach = rand(0.9, 1.8) * s;
        this.arc(x, y, z, x + fx * reach + rand(-0.5, 0.5) * s, y + rand(-0.3, 0.5) * s, z + fz * reach + rand(-0.5, 0.5) * s, GOLD_HOT, 0.06, 3, 0.35 * s, 0.07);
      }
      this.sparks(x, y, z, this.optional(3), GOLD, 4 * s, fx, fz);
      return;
    }
    // The sim fires from the shooter's centre at a fixed height and the renderer first sees the shot
    // a tick later: step back to the shooter and out to roughly where each gun's muzzle sits.
    const [reach, height] = MUZZLE_AT[kind ?? ''] ?? [1.2, 1.5];
    if (at) {
      // The renderer found the gun's own muzzle on the model.
      this.terranBlast(at.x, at.y, at.z, kind, s, fx, fz, reach);
      return;
    }
    const back = len / SIM_TICK_HZ;
    this.terranBlast(x + fx * (reach - back), y - MUZZLE_HEIGHT + height, z + fz * (reach - back), kind, s, fx, fz, reach);
  }

  /**
   * Terran gun blast (look developed in tools/art/v2/viewer/blast.js): a white-hot bloom in a cyan
   * halo, a short plasma tongue, side jets from the muzzle brake, orange spark streaks, an orange-hot
   * muzzle that cools, then grey-blue smoke that rolls forward, slows and rises while the bore keeps
   * venting; heavy guns also blow dust off the ground. Saturated colours are alpha-blended (they read
   * as cyan and orange over any ground); only the white-hot core is additive.
   * Cost per shot (high / low quality): light gun ~23 / 12 sprites, autocannon ~14 / 8, artillery ~44 / 20.
   */
  private terranBlast(x: number, y: number, z: number, kind: string | undefined, scale: number, fx: number, fz: number, reach0: number): void {
    const missile = kind === 'missile';
    const quick = kind === 'autocannon';
    // Gun size in metres and heaviness (0 light tank .. 1 artillery), from the weapon's visual scale.
    const S = 0.36 * Math.pow(scale, 0.9);
    const H = Math.min(1, Math.max(0, (scale - 1) / 0.6));
    // Light guns get a relatively punchier flash (it has to read at game zoom), heavy ones mass instead.
    const P = 1 + 0.25 * (1 - H);
    const T = quick ? 0.7 : 1; // autocannon: shorter, snappier
    const rich = this.detail >= 0.6; // the cosmetic extras drop out on low quality
    // Side vector (horizontal, perpendicular to the shot).
    const sx = -fz;
    const sz = fx;
    const at = (d: number): [number, number, number] => [x + fx * d, y, z + fz * d];

    // White-hot core (additive) inside a cyan halo (alpha-blended) and a cyan inner glow.
    const [cx, cy, cz] = at(0.45 * S);
    this.spawn(4, cx, cy, cz, 0, 0, 0, 0.1 * T, S * (2.5 + 0.6 * H) * P, S * (2.9 + 0.7 * H) * P, HALO, HALO, 0.6, 0);
    this.spawn(0, cx, cy, cz, 0, 0, 0, 0.1 * T, S * (1.75 + 0.5 * H) * P, S * (1.9 + 0.5 * H) * P, BLAST_CYAN, BLAST_CYAN, 0.7, 0);
    this.spawn(0, cx, cy, cz, 0, 0, 0, 0.1 * T, S * (0.85 + 0.3 * H) * P, S * (0.9 + 0.3 * H) * P, WHITE, WHITE, 1, 0);

    // Plasma tongue down the barrel line: cyan sheath (alpha) and white-hot inner tongue (additive).
    const reach = S * (missile ? 1.6 : 3 + 0.8 * Math.random() + 0.8 * H) * P;
    const [bx, by, bz] = at(-0.2 * S);
    const [tx, ty, tz] = at(-0.2 * S + reach);
    this.ribbonList.push({ ax: bx, ay: by, az: bz, bx: tx, by: ty, bz: tz, c: HALO, alpha: 0.8, width: S * (1.3 + 0.3 * H) * P, age: 0, life: 0.1 * T, drawn: false, soft: true });
    const [ix, iy, iz] = at(-0.2 * S + reach * 0.7);
    this.ribbonList.push({ ax: bx, ay: by, az: bz, bx: ix, by: iy, bz: iz, c: WHITE_HOT, alpha: 0.95, width: S * 0.55 * P, age: 0, life: 0.1 * T, drawn: false, soft: true });

    // Telescoping barrels snap back as they fire: for a few frames plasma keeps pouring out of the
    // retracting tip, so the bloom never floats ahead of a collapsed barrel.
    if (!missile && !quick) {
      const [rx, ry, rz] = at(-reach0 * 0.55);
      this.ribbonList.push({ ax: rx, ay: ry - 0.1, az: rz, bx: cx, by: cy, bz: cz, c: HALO, alpha: 0.7, width: S * 0.6 * P, age: 0, life: 0.09, drawn: false, soft: true });
      this.ribbonList.push({ ax: rx, ay: ry - 0.1, az: rz, bx: cx, by: cy, bz: cz, c: WHITE_HOT, alpha: 0.8, width: S * 0.25 * P, age: 0, life: 0.07, drawn: false, soft: true });
    }

    // Muzzle-brake side jets.
    if (rich && !missile) {
      for (const side of [-1, 1]) {
        const jx = sx * side + fx * 0.45;
        const jz = sz * side + fz * 0.45;
        this.spawn(4, x, y, z, jx * 20 * S, 0, jz * 20 * S, 0.08 * T, 0.5 * S, 0.8 * S, BLAST_CYAN, HALO, 0.8, 0, 10);
      }
      // A faint pressure wisp swelling round the bloom.
      this.spawn(4, cx, cy, cz, 0, 0, 0, 0.16, 0.8 * S, (2.5 + 0.5 * H) * S, HALO, HALO, 0.12, 0);
    }

    // Spark streaks thrown forward (alpha-blended orange: additive orange on grass goes yellow).
    const sparks = missile ? 0 : this.optional(Math.round((quick ? 3 : 6) + 5 * H));
    for (let i = 0; i < sparks; i += 1) {
      const spread = (Math.random() - 0.5) * 1.2;
      const dx = fx + sx * spread;
      const dz = fz + sz * spread;
      const n = Math.hypot(dx, dz) || 1;
      const lift = (Math.random() - 0.3) * 1.2;
      const d0 = S * rand(0.8, 2);
      const d1 = d0 + S * rand(1.2, 2.6) * (1 + 0.5 * H);
      this.ribbonList.push({
        ax: x + (dx / n) * d0, ay: y + lift * d0 * 0.5, az: z + (dz / n) * d0,
        bx: x + (dx / n) * d1, by: y + lift * d1 * 0.5 - 0.1, bz: z + (dz / n) * d1,
        c: i % 3 === 0 ? SPARK : BLAST_ORANGE, alpha: 1, width: 0.13 * S, age: 0, life: rand(0.12, 0.24), drawn: false, soft: true,
      });
    }

    // The muzzle stays orange-hot for a moment.
    this.spawn(4, x, y, z, 0, 0, 0, 0.35 * T, 0.7 * S, 0.35 * S, BLAST_ORANGE, EMBER, 0.85, 0);

    // Smoke: puffs pushed forward at a spread of speeds, dragging to a stop and rising.
    const puffs = this.optional(Math.round((quick ? 2 : missile ? 6 : 5) + 3 * H));
    for (let i = 0; i < puffs; i += 1) {
      const f = (i + 0.5) / Math.max(1, puffs);
      const v = (0.6 + 13 * Math.pow(f, 1.5) * rand(0.75, 1.25)) * S * (1 - 0.45 * H) * (missile ? 0.5 : 1);
      const spread = rand(-0.35, 0.35);
      const [px, py, pz] = at(0.3 * S);
      this.spawn(1, px, py, pz, (fx + sx * spread) * v, rand(0.3, 0.8) * S * 2, (fz + sz * spread) * v, (1.2 + 0.8 * H) * T * rand(0.75, 1.25), 0.45 * S, (1.8 + 0.6 * H) * S * rand(0.7, 1.3), BLAST_SMOKE_HOT, BLAST_SMOKE, 0.7 - 0.12 * H, 1, 3.5);
    }
    // The hot bore keeps venting slow puffs, so the plume stays joined to the gun as it drifts off.
    const vents = this.optional(Math.round((quick ? 0 : 1) + 6 * H));
    for (let i = 0; i < vents; i += 1) {
      this.later(0.06 + i * (0.07 + 0.05 * H), () => {
        const [vx, vy, vz] = at(0.5 * S);
        this.spawn(1, vx, vy, vz, fx * rand(0.8, 2) * S + rand(-0.2, 0.2), rand(0.4, 0.9) * S * 2, fz * rand(0.8, 2) * S + rand(-0.2, 0.2), (1 + H) * rand(0.8, 1.2), 0.55 * S, (1.5 + 0.4 * H) * S, BLAST_SMOKE, BLAST_SMOKE, (0.45 + 0.05 * H) * (1 - (0.5 * i) / Math.max(1, vents)), 1, 1);
      });
    }

    if (H >= 0.5) {
      // Heavy guns and artillery: the pressure wave blows dust off the ground under the barrel.
      const gy = y - 0.8;
      this.decal(2, x - fx * 0.8, gy, z - fz * 0.8, 0.8 * S, (2 + 3.5 * H) * S, BLAST_DUST, 0.22 * H, 1.1, 1);
      const dust = this.optional(Math.round(2 + 4 * H));
      for (let i = 0; i < dust; i += 1) {
        const ang = ((i + 0.5) / dust - 0.5) * 3.6 + rand(-0.2, 0.2);
        const c = Math.cos(ang);
        const sn = Math.sin(ang);
        const dx = fx * c - sx * sn;
        const dz = fz * c - sz * sn;
        const v = rand(4, 7) * S * 4 * (0.55 + 0.45 * c);
        this.spawn(1, x - fx * 0.6, gy + 0.3, z - fz * 0.6, dx * v, 0.3, dz * v, rand(1.2, 2), 0.7 * S, (1.6 + 1.4 * H) * S, BLAST_DUST, BLAST_DUST, 0.3 * H, 1, 4);
      }
    }
  }

  // ---- impacts -------------------------------------------------------------------------
  /** Impact effect for a projectile that just ended at (x, y, z) on ground height gy. */
  impact(kind: string | undefined, x: number, y: number, z: number, gy: number, splash: number, alien = false): void {
    const s = WEAPON_SCALE[kind ?? ''] ?? 1;
    if (kind === 'laser') {
      this.spawn(0, x, y, z, 0, 0, 0, 0.2, 0.5, 1.4, WHITE, CYAN, 1, 0);
      this.sparks(x, y, z, this.optional(6), CYAN, 6);
      return;
    }
    if (kind === 'shard') {
      this.spawn(0, x, y, z, 0, 0, 0, 0.18, 0.6, 1.4, WHITE, VIOLET, 1, 0);
      for (let i = 0; i < 6; i += 1) {
        const angle = (i / 6) * Math.PI * 2;
        this.ribbonList.push({
          ax: x,
          ay: y,
          az: z,
          bx: x + Math.cos(angle) * 0.9,
          by: y + 0.35 * ((i % 2) * 2 - 1),
          bz: z + Math.sin(angle) * 0.9,
          c: i % 2 ? WHITE : VIOLET,
          alpha: 0.9,
          width: 0.08,
          age: 0,
          life: 0.16,
          drawn: false,
        });
      }
      return;
    }
    if (kind === 'spore') {
      this.cloud(x, gy + 0.8, z, Math.max(2.5, splash));
      return;
    }
    if (kind === 'bombs') {
      this.explosion(x, gy + 0.6, z, gy, Math.max(2.2, splash) * 0.9, false, false);
      return;
    }
    if (kind === 'ground_beam') {
      const size = Math.max(3, splash);
      this.explosion(x, gy + 0.8, z, gy, size * 0.8, true, false);
      // An eruption column: the beam punches the ground and throws fire straight up.
      for (let i = 0; i < 4; i += 1) {
        this.spawn(0, x + rand(-0.4, 0.4), gy + i * size * 0.3, z + rand(-0.4, 0.4), 0, rand(4, 7), 0, rand(0.4, 0.6), size * 0.35, size * 0.6, GOLD_HOT, FIRE, 0.8, 0);
      }
      return;
    }
    if (kind === 'lightning') {
      this.spawn(0, x, y, z, 0, 0, 0, 0.2, 0.6, 1.6, GOLD_HOT, GOLD, 1, 0);
      this.goldStar(x, y, z, 0.9, 3);
      this.sparks(x, y, z, this.optional(8), GOLD, 7);
      return;
    }
    const size = s * (1 + Math.min(1.5, splash) * 0.5);
    const onGround = y - gy < 1.2;
    if (alien) {
      this.spawn(0, x, y, z, 0, 0, 0, 0.14, 0.6 * size, 1.9 * size, WHITE, GOLD, 1, 0);
      this.spawn(0, x, y, z, 0, 0, 0, 0.3, 0.9 * size, 1.8 * size, GOLD, EMBER, 0.6, 0);
      this.goldStar(x, y, z, 1.1 * size, size >= 1.3 ? 6 : 4);
      this.sparks(x, y, z, this.optional(Math.round(6 * size)), GOLD, 6 * size);
      if (onGround) {
        this.decal(3, x, gy + 0.32, z, 0.3 * size, 0.9 * size, GOLD, 0.35, 0.5, 0);
        if (size >= 1.3) {
          this.decal(2, x, gy + 0.3, z, size * 0.9, size * 0.9, SCORCH, 0.6, 8, Math.random() * 9);
          this.decal(3, x, gy + 0.34, z, 0.2 * size, 2 * size, GOLD_HOT, 0.6, 0.3, 10);
        }
      }
      return;
    }
    // Terran shells: a fireball that rolls from white-hot to dark red, sparks and dirt.
    this.spawn(0, x, y, z, 0, 0, 0, 0.1, 0.6 * size, 1.6 * size, WHITE, HOT, 1, 0);
    const balls = size >= 1.3 ? 4 : 2;
    for (let i = 0; i < balls; i += 1) {
      this.spawn(0, x + rand(-0.3, 0.3) * size, y + rand(0, 0.4) * size, z + rand(-0.3, 0.3) * size, rand(-1, 1), rand(1, 2.5), rand(-1, 1), rand(0.3, 0.5), 0.5 * size, 1.3 * size, HOT, EMBER, 0.95, 0);
    }
    this.sparks(x, y, z, this.optional(Math.round(5 * size)), [1, 0.75, 0.35], 7 * size);
    if (onGround) {
      for (let i = 0; i < this.optional(size >= 1.3 ? 3 : 1); i += 1) {
        this.spawn(1, x + rand(-0.5, 0.5), gy + 0.4, z + rand(-0.5, 0.5), rand(-1, 1), rand(1, 2), rand(-1, 1), rand(0.9, 1.5), 0.5 * size, 1.6 * size, DUST, SMOKE, 0.45, 1);
      }
      if (size >= 1.3) {
        this.debris(x, gy, z, this.optional(3), 0.07 * size, 6 * size, false);
        this.decal(2, x, gy + 0.3, z, size * 0.85, size * 0.85, SCORCH, 0.6, 9, Math.random() * 9);
        this.decal(3, x, gy + 0.34, z, 0.2 * size, 2 * size, FIRE, 0.5, 0.3, 10);
      }
    }
  }

  /** Lightning radiating out from a point: the Arcadian hit signature. */
  private goldStar(x: number, y: number, z: number, reach: number, count: number): void {
    for (let i = 0; i < count; i += 1) {
      const a = (i / count) * Math.PI * 2 + rand(-0.4, 0.4);
      const r = reach * rand(0.7, 1.3);
      this.arc(x, y, z, x + Math.cos(a) * r, y + rand(-0.4, 0.8) * reach, z + Math.sin(a) * r, GOLD_HOT, 0.1, 3, 0.3 * reach, 0.08);
    }
  }

  // ---- big explosions --------------------------------------------------------------------
  /**
   * A vehicle blowing up: flash, rolling fireballs, a shock ring, debris, embers, a smoke column
   * and a scorch mark. Arcadian hulls burst in gold lightning first. `size` ~ 1 for a light tank.
   */
  unitDeath(x: number, y: number, z: number, gy: number, size: number, alien: boolean, air: boolean): void {
    this.explosion(x, y + 0.6 * size, z, gy, 1.5 * size, alien, air);
    // A second, bigger blast a moment later: the ammunition going up.
    this.later(0.22, () => {
      this.spawn(0, x + rand(-0.6, 0.6), y + size, z + rand(-0.6, 0.6), 0, 2, 0, 0.55, 1.2 * size, 2.8 * size, HOT, EMBER, 0.9, 0);
      this.sparks(x, y + size, z, this.optional(10), [1, 0.7, 0.3], 9 * size);
      if (alien) {
        this.goldStar(x, y + size, z, 2 * size, 5);
      }
    });
    if (air) {
      // The airframe breaks up and burning pieces rain down.
      this.debris(x, y, z, this.optional(6), 0.1 * size, 5, true, gy);
    }
  }

  /** A building going up: several blasts across its footprint over a second and a half. */
  structureDeath(x: number, gy: number, z: number, width: number, alien: boolean): void {
    const size = Math.max(1.5, width * 0.45);
    this.explosion(x, gy + 1, z, gy, size * 1.4, alien, false);
    for (let i = 1; i <= 4; i += 1) {
      this.later(i * 0.3 + rand(0, 0.15), () => {
        const ox = rand(-0.5, 0.5) * width;
        const oz = rand(-0.5, 0.5) * width;
        this.explosion(x + ox, gy + rand(0.6, 2), z + oz, gy, size * rand(0.7, 1.1), alien, false);
      });
    }
  }

  private explosion(x: number, y: number, z: number, gy: number, size: number, alien: boolean, air: boolean): void {
    const hot = alien ? GOLD_HOT : HOT;
    const outer = alien ? GOLD : FIRE;
    this.spawn(0, x, y, z, 0, 0, 0, 0.16, 1.2 * size, 2.7 * size, WHITE, hot, 1, 0);
    if (alien) {
      this.goldStar(x, y, z, 2.2 * size, 7);
    }
    const balls = Math.max(3, this.optional(7));
    for (let i = 0; i < balls; i += 1) {
      const a = Math.random() * Math.PI * 2;
      const r = rand(0.1, 0.7) * size;
      this.spawn(
        0,
        x + Math.cos(a) * r,
        y + rand(-0.2, 0.6) * size,
        z + Math.sin(a) * r,
        Math.cos(a) * rand(1, 3) * size,
        rand(1.5, 4) * size,
        Math.sin(a) * rand(1, 3) * size,
        rand(0.55, 0.95),
        rand(0.6, 0.9) * size,
        rand(1.6, 2.3) * size,
        hot,
        alien ? [0.6, 0.25, 0.04] : EMBER,
        0.95,
        0,
        0.9,
      );
    }
    this.sparks(x, y, z, this.optional(Math.round(12 * Math.min(2, size))), alien ? GOLD : [1, 0.7, 0.3], 10 * Math.min(2, size));
    const smokes = this.optional(Math.round(4 + 2 * size));
    for (let i = 0; i < smokes; i += 1) {
      this.spawn(
        1,
        x + rand(-0.6, 0.6) * size,
        y + rand(0, 0.8) * size,
        z + rand(-0.6, 0.6) * size,
        rand(-0.8, 0.8),
        rand(1.2, 2.6),
        rand(-0.8, 0.8),
        rand(2.2, 3.6),
        0.8 * size,
        2.6 * size,
        SMOKE,
        SMOKE_LIGHT,
        0.55,
        1,
        0.4,
      );
    }
    if (!air || y - gy < 2) {
      this.decal(3, x, gy + 0.35, z, 0.4 * size, 3.2 * size, outer, 0.7, 0.4, 10);
      this.decal(3, x, gy + 0.32, z, size * 0.9, size * 0.9, outer, 0.4, 1.2, Math.random() * 9);
      this.decal(2, x, gy + 0.3, z, size * 1.5, size * 1.6, SCORCH, 0.75, 20, Math.random() * 9);
      this.debris(x, gy, z, this.optional(Math.round(5 + 2 * size)), 0.08 * size, 8 * Math.min(1.6, size), true);
      for (let i = 0; i < this.optional(4); i += 1) {
        this.spawn(1, x + rand(-1, 1) * size, gy + 0.3, z + rand(-1, 1) * size, rand(-3, 3), rand(0.3, 0.8), rand(-3, 3), rand(1.2, 2), 0.6 * size, 2 * size, DUST, DUST, 0.4, 1, 1.5);
      }
    }
  }

  /** A packed tower unfolding into its structure: a dust ring for Terran builds, gold for Arcadian. */
  deploy(x: number, gy: number, z: number, size: number, alien: boolean): void {
    if (alien) {
      this.decal(3, x, gy + 0.2, z, 0.2 * size, 1.4 * size, GOLD, 0.8, 0.8, 10);
      this.spawn(0, x, gy + 0.6, z, 0, 0, 0, 0.5, 0.4 * size, 0.9 * size, GOLD_HOT, GOLD, 0.6, 0);
      this.goldStar(x, gy + 0.6, z, size * 0.7, 5);
      this.sparks(x, gy + 0.5, z, this.optional(10), GOLD, 5);
    } else {
      this.decal(3, x, gy + 0.15, z, 0.2 * size, 1.4 * size, FIRE, 0.5, 0.6, 10);
      for (let i = 0; i < this.optional(5); i += 1) {
        this.spawn(1, x + rand(-0.5, 0.5) * size, gy + 0.3, z + rand(-0.5, 0.5) * size, rand(-2, 2), 0.5, rand(-2, 2), rand(1, 1.6), 0.3 * size, 0.8 * size, DUST, DUST, 0.45, 1, 1.5);
      }
      this.debris(x, gy, z, this.optional(6), 0.07, 5, false);
    }
  }

  // ---- fire sources ------------------------------------------------------------------------
  /** Flames for `fireSec`, then smoke until `smokeSec`. Stop it early with `burner.alive = false`. */
  addBurner(x: number, y: number, z: number, size: number, fireSec: number, smokeSec: number): Burner {
    const burner: Burner = { x, y, z, size, age: 0, fireSec, smokeSec, alive: true, acc: 0 };
    this.burners.push(burner);
    if (this.burners.length > MAX_BURNERS) {
      const oldest = this.burners.shift();
      if (oldest) {
        oldest.alive = false;
      }
    }
    return burner;
  }

  private updateBurner(b: Burner, dt: number): void {
    b.age += dt;
    const burning = b.age < b.fireSec;
    // Fire licks up at about 9 flames a second; smoke thins out over the smoke time.
    const smokeLeft = 1 - Math.max(0, b.age - b.fireSec) / Math.max(0.1, b.smokeSec - b.fireSec);
    const rate = (burning ? 12 : 0) + 4 * Math.max(0, smokeLeft);
    b.acc += rate * dt * this.detail;
    const s = b.size;
    if (burning) {
      // A warm glow under the flames so a burning wreck reads from far away.
      const flicker = 0.8 + Math.random() * 0.4;
      this.frameSprite(0, b.x, b.y - 0.3 * s, b.z, 2.2 * s * flicker, FIRE, 0.28 * Math.min(1, (b.fireSec - b.age) / 2));
    }
    while (b.acc >= 1) {
      b.acc -= 1;
      if (burning && Math.random() < 12 / rate) {
        const fade = b.age > b.fireSec * 0.6 ? 0.6 : 1;
        this.spawn(0, b.x + rand(-0.45, 0.45) * s, b.y + rand(0, 0.3) * s, b.z + rand(-0.45, 0.45) * s, rand(-0.3, 0.3), rand(1.6, 2.6) * Math.sqrt(s), rand(-0.3, 0.3), rand(0.5, 0.8), rand(0.55, 0.9) * s * fade, 0.2 * s, HOT, [0.9, 0.25, 0.04], 0.95, 0);
      } else {
        this.spawn(1, b.x + rand(-0.3, 0.3) * s, b.y + 0.6 * s, b.z + rand(-0.3, 0.3) * s, rand(0.2, 0.7), rand(1.4, 2.2), rand(-0.2, 0.3), rand(2.6, 3.6), 0.45 * s, 2.2 * s, SMOKE, SMOKE_LIGHT, 0.5 * Math.max(0.35, smokeLeft), 1, 0.3);
      }
    }
  }

  // ---- particle helpers ----------------------------------------------------------------------
  /** How many of `count` optional particles to spawn, thinned by detail and by how busy the pools are. */
  private optional(count: number): number {
    const live = this.particles.length;
    const busy = live < 900 ? 1 : live > 2000 ? 0.15 : 1 - ((live - 900) / 1100) * 0.85;
    return Math.round(count * this.detail * busy);
  }

  private later(delay: number, run: () => void): void {
    this.delayed.push({ at: this.time + delay, run });
  }

  private flash(x: number, y: number, z: number, size: number, color: Rgb, alpha: number): void {
    this.frameSprite(0, x, y, z, size, color, alpha);
  }

  /** A sprite drawn for this frame only (projectile heads and glows). */
  private frameSprite(layer: Layer, x: number, y: number, z: number, size: number, color: Rgb, alpha: number): void {
    this.spawn(layer, x, y, z, 0, 0, 0, 0.025, size, size, color, color, alpha, 0);
  }

  private spawn(
    layer: Layer,
    x: number,
    y: number,
    z: number,
    vx: number,
    vy: number,
    vz: number,
    life: number,
    size0: number,
    size1: number,
    c0: Rgb,
    c1: Rgb,
    alpha: number,
    fade: Fade,
    drag = 1.5,
  ): void {
    const p = this.spare.pop() ?? ({} as Particle);
    p.layer = layer;
    p.x = x;
    p.y = y;
    p.z = z;
    p.vx = vx;
    p.vy = vy;
    p.vz = vz;
    p.gravity = 0;
    p.drag = drag;
    p.age = 0;
    p.life = life;
    p.size0 = size0;
    p.size1 = size1;
    p.c0 = c0;
    p.c1 = c1;
    p.alpha = alpha;
    p.fade = fade;
    p.rot = Math.random() * Math.PI * 2;
    p.spin = layer === 1 ? rand(-0.6, 0.6) : rand(-2, 2);
    p.seed = Math.random() * 9;
    p.drawn = false;
    this.particles.push(p);
  }

  private decal(layer: 2 | 3, x: number, y: number, z: number, size0: number, size1: number, color: Rgb, alpha: number, life: number, seed: number): void {
    this.spawn(layer, x, y, z, 0, 0, 0, life, size0, size1, color, color, alpha, layer === 2 ? 2 : 0, 0);
    const last = this.particles[this.particles.length - 1];
    if (last) {
      last.seed = seed;
      last.spin = 0;
    }
  }

  private sparks(x: number, y: number, z: number, count: number, color: Rgb, speed: number, biasX = 0, biasZ = 0): void {
    for (let i = 0; i < count; i += 1) {
      const a = Math.random() * Math.PI * 2;
      const up = Math.random() * 0.8 + 0.2;
      this.spawn(0, x, y, z, Math.cos(a) * speed * (1 - up * 0.5) + biasX * speed, up * speed, Math.sin(a) * speed * (1 - up * 0.5) + biasZ * speed, rand(0.25, 0.5), 0.12, 0.05, WHITE, color, 1, 0, 0.5);
      const last = this.particles[this.particles.length - 1];
      if (last) {
        last.gravity = 14;
      }
    }
  }

  private debris(x: number, gy: number, z: number, count: number, size: number, speed: number, glowing: boolean, fromY?: number): void {
    for (let i = 0; i < count && this.chunks.length < 240; i += 1) {
      const a = Math.random() * Math.PI * 2;
      const up = 0.55 + Math.random() * 0.45;
      this.chunks.push({
        x: x + rand(-0.5, 0.5),
        y: (fromY ?? gy) + 0.3,
        z: z + rand(-0.5, 0.5),
        vx: Math.cos(a) * speed * (1 - up * 0.6),
        vy: up * speed,
        vz: Math.sin(a) * speed * (1 - up * 0.6),
        rx: Math.random() * 6,
        ry: Math.random() * 6,
        spin: rand(6, 14),
        size: size * rand(0.6, 1.5),
        age: 0,
        life: rand(1, 1.6),
        ground: gy,
        glow: glowing && i % 3 === 0,
      });
    }
  }

  private cloud(x: number, y: number, z: number, radius: number): void {
    for (let i = 0; i < 9; i += 1) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * radius * 0.6;
      this.spawn(1, x + Math.cos(a) * r, y + Math.random() * radius * 0.5, z + Math.sin(a) * r, 0, 0.3, 0, rand(3, 4.5), radius * rand(0.3, 0.55), radius * 0.9, i % 3 === 0 ? [0.89, 0.94, 0.54] : SPORE, SPORE, 0.45, 1, 0.2);
    }
    this.spawn(0, x, y, z, 0, 0, 0, 0.4, radius * 0.4, radius * 0.8, [0.95, 1, 0.7], SPORE, 0.6, 0);
  }

  // ---- per frame ---------------------------------------------------------------------------
  update(dt: number): void {
    this.time += dt;
    this.glow.begin();
    this.smoke.begin();
    this.scorch.begin();
    this.groundGlow.begin();
    this.halo.begin();
    for (let i = this.delayed.length - 1; i >= 0; i -= 1) {
      const job = this.delayed[i];
      if (job && job.at <= this.time) {
        this.delayed.splice(i, 1);
        job.run();
      }
    }
    for (const [object, info] of this.tracked) {
      this.drawProjectile(object, info);
    }
    for (let i = this.burners.length - 1; i >= 0; i -= 1) {
      const b = this.burners[i];
      if (!b) {
        continue;
      }
      if (!b.alive || b.age >= b.smokeSec) {
        b.alive = false;
        this.burners.splice(i, 1);
        continue;
      }
      this.updateBurner(b, dt);
    }

    const pools = [this.glow, this.smoke, this.scorch, this.groundGlow, this.halo];
    let write = 0;
    for (let i = 0; i < this.particles.length; i += 1) {
      const p = this.particles[i];
      if (!p) {
        continue;
      }
      p.age += dt;
      if (p.age >= p.life && p.drawn) {
        this.spare.push(p);
        continue;
      }
      const t = Math.min(0.999, p.age / p.life);
      p.drawn = true;
      this.particles[write] = p;
      write += 1;
      const damp = Math.max(0, 1 - p.drag * dt);
      p.vx *= damp;
      p.vz *= damp;
      p.vy = p.vy * damp - p.gravity * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.z += p.vz * dt;
      p.rot += p.spin * dt;
      const eased = 1 - (1 - t) * (1 - t);
      const size = p.size0 + (p.size1 - p.size0) * eased;
      const ct = Math.sqrt(t);
      const r = p.c0[0] + (p.c1[0] - p.c0[0]) * ct;
      const g = p.c0[1] + (p.c1[1] - p.c0[1]) * ct;
      const b = p.c0[2] + (p.c1[2] - p.c0[2]) * ct;
      let a: number;
      if (p.fade === 1) {
        a = p.alpha * Math.min(1, t * 6) * (1 - t);
      } else if (p.fade === 2) {
        a = p.alpha * Math.min(1, (1 - t) * 3);
      } else {
        a = p.alpha * (1 - t);
      }
      pools[p.layer]?.push(p.x, p.y, p.z, r, g, b, a, size, p.rot, p.seed);
    }
    this.particles.length = write;

    this.ribbons.begin();
    this.tongues.begin();
    let keep = 0;
    for (let i = 0; i < this.ribbonList.length; i += 1) {
      const q = this.ribbonList[i];
      if (!q) {
        continue;
      }
      if (q.drawn && q.age > q.life) {
        continue;
      }
      this.ribbonList[keep] = q;
      keep += 1;
      const fade = Math.max(0.15, 1 - q.age / q.life);
      q.age += dt;
      q.drawn = true;
      (q.soft ? this.tongues : this.ribbons).push(q.ax, q.ay, q.az, q.bx, q.by, q.bz, q.c[0], q.c[1], q.c[2], q.alpha * fade, q.width);
    }
    this.ribbonList.length = keep;

    let rocks = 0;
    let kept = 0;
    for (let i = 0; i < this.chunks.length; i += 1) {
      const c = this.chunks[i];
      if (!c) {
        continue;
      }
      c.age += dt;
      if (c.age >= c.life) {
        continue;
      }
      this.chunks[kept] = c;
      kept += 1;
      c.vy -= 24 * dt;
      c.x += c.vx * dt;
      c.y += c.vy * dt;
      c.z += c.vz * dt;
      c.rx += c.spin * dt;
      c.ry += c.spin * 0.7 * dt;
      if (c.y < c.ground + 0.08) {
        c.y = c.ground + 0.08;
        c.vx *= 0.4;
        c.vz *= 0.4;
        c.vy = Math.abs(c.vy) * 0.25;
        c.spin *= 0.5;
      }
      const shrink = c.age > c.life * 0.75 ? 1 - (c.age - c.life * 0.75) / (c.life * 0.25) : 1;
      this.euler.set(c.rx, c.ry, 0);
      this.quat.setFromEuler(this.euler);
      this.scaleVec.setScalar(c.size * shrink);
      this.matrix.compose(this.vec.set(c.x, c.y, c.z), this.quat, this.scaleVec);
      if (c.glow) {
        // Burning pieces: a glowing ember with a short fiery trail.
        const heat = 1 - c.age / c.life;
        this.glow.push(c.x, c.y, c.z, 1, 0.55, 0.15, 0.9 * heat, c.size * 2.6 * shrink, 0, 0);
        if (c.y > c.ground + 0.2 && Math.random() < 0.35) {
          this.spawn(0, c.x, c.y, c.z, 0, 0.5, 0, 0.3, c.size * 2, c.size * 0.8, FIRE, EMBER, 0.5 * heat, 0);
        }
      } else if (rocks < this.chunkMesh.instanceMatrix.count) {
        this.chunkMesh.setMatrixAt(rocks, this.matrix);
        rocks += 1;
      }
    }
    this.chunks.length = kept;
    this.chunkMesh.count = rocks;
    if (rocks > 0) {
      this.chunkMesh.instanceMatrix.needsUpdate = true;
    }

    for (const pool of pools) {
      pool.end();
    }
    this.ribbons.end();
    this.tongues.end();
  }

  dispose(): void {
    for (const pool of [this.glow, this.smoke, this.scorch, this.groundGlow, this.halo]) {
      pool.dispose(this.scene);
    }
    this.ribbons.dispose(this.scene);
    this.tongues.dispose(this.scene);
    this.scene.remove(this.chunkMesh);
    this.chunkMesh.dispose();
    this.particles.length = 0;
    this.ribbonList.length = 0;
    this.chunks.length = 0;
    this.burners.length = 0;
    this.delayed.length = 0;
    this.tracked.clear();
    for (const g of [this.chunkGeometry, this.bombGeometry, this.missileGeometry]) {
      g.dispose();
    }
    for (const m of [this.chunkMaterial, this.bombMaterial, this.missileMaterial, this.missileMaterialAlien]) {
      m.dispose();
    }
  }
}

/** Missile body along +Z (about 1.1 m): cylinder, nose cone and four tail fins, merged. */
function buildMissileGeometry(): THREE.BufferGeometry {
  const parts: THREE.BufferGeometry[] = [];
  const body = new THREE.CylinderGeometry(0.075, 0.075, 0.8, 8).rotateX(Math.PI / 2);
  parts.push(body);
  const nose = new THREE.ConeGeometry(0.075, 0.3, 8).rotateX(Math.PI / 2).translate(0, 0, 0.55);
  parts.push(nose);
  for (let i = 0; i < 4; i += 1) {
    const fin = new THREE.BoxGeometry(0.02, 0.16, 0.18).translate(0, 0.11, -0.32).rotateZ((i * Math.PI) / 2);
    parts.push(fin);
  }
  const merged = mergeSimple(parts);
  for (const part of parts) {
    part.dispose();
  }
  return merged;
}

/** Merges non-indexed copies of simple geometries (position + normal only). */
function mergeSimple(parts: THREE.BufferGeometry[]): THREE.BufferGeometry {
  const positions: number[] = [];
  const normals: number[] = [];
  for (const part of parts) {
    const flat = part.index ? part.toNonIndexed() : part;
    const position = flat.getAttribute('position');
    const normal = flat.getAttribute('normal');
    for (let i = 0; i < position.count; i += 1) {
      positions.push(position.getX(i), position.getY(i), position.getZ(i));
      normals.push(normal.getX(i), normal.getY(i), normal.getZ(i));
    }
    if (flat !== part) {
      flat.dispose();
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  return geometry;
}
