// Moving parts on models (miner drums, radar dishes, spinning crowns, wings). The art pipeline
// (tools/art/v2/motion.py) puts an `anim` entry in a pivot node's glTF extras, which GLTFLoader
// copies to node.userData.anim:
//
//   { type: 'spin',  axis: [x, y, z], speed: rad/s, when, busySpeed? }
//   { type: 'swing', axis: [x, y, z], amp: rad, speed: Hz, when, busySpeed? }
//   { type: 'scroll', speed: tiles/s, when }   (tank treads: slides the texture along U)
//
// Treads are matched to the ground instead of using `speed`: the game measures how many texture
// tiles one metre of the top run holds (and which way U runs) from the mesh, then moves the top
// run forward at exactly the unit's ground speed, so cleats never slip. `speed` is the fallback
// for a mesh it cannot measure.
//
// `when` is 'always' | 'mining' | 'working' | 'moving'. The axis is in the node's own space and
// each node already sits on its part's axis, so the part turns by rotating the node about that
// axis on top of its rest rotation. busySpeed replaces speed while the unit is working.
//
// A TurretPivot that carries an anim is a spinner, not an aimed turret.
//
// Firing parts (timed from the unit's shots; see fireUnit):
//
//   { type: 'recoil', axis, dist, attack, recover, delay, repeat?, every? }
//       slides back along -axis by dist * hit(tf - delay) (telescoping barrel sleeves)
//   { type: 'slide', axis, amp, speed, phase?, snap?, attack?, recover? }
//       offset = amp * sin(2 pi speed t + phase) + snap * hit(tf) metres along axis
//   { type: 'swing', ..., phase?, snap?, attack?, recover? }   adds snap * hit(tf) radians
//   { type: 'launch', axis, delay, travel, dur, reload }
//       a missile in its tube. Each shot fires the next loaded tube in turn (in delay order), at
//       once: the model's missile is hidden until tf >= reload, then sits back in its tube. The
//       game draws the missile in flight from that tube onto the sim's shot, so it really reaches
//       what it was fired at (the art's own 9 m fly-out vanished in mid-air).
//
// hit(x) = x / attack while x < attack, then (1 - (x - attack) / recover)^2 until 0. The art's
// delays describe a whole firing cycle (the scene's extras.fire `repeat` shots `every` seconds
// apart: a Lancer's lances in turn, a Javelin's four tubes); the sim fires one projectile per
// shot, so each projectile plays the parts whose delay falls on its place in that cycle, at once.
// 'flash' and 'flicker' parts are not played here (the game draws its own muzzle blasts).
//
// A scroll part does not move its node: it writes the texture offset to userData.uvScroll on each
// mesh under it, and the unit instancing (unitInstances.ts) passes that per instance to the
// shader, so every tank's treads run on their own.
import * as THREE from 'three';

export type PartMotionWhen = 'always' | 'mining' | 'working' | 'moving';

export interface PartMotionSpec {
  type: 'spin' | 'swing' | 'scroll' | 'slide' | 'recoil' | 'launch';
  axis: THREE.Vector3;
  speed: number;
  amp: number;
  when: PartMotionWhen;
  busySpeed: number | null;
  /** Firing timing, for recoil, launch and swing or slide parts with a snap. */
  fire: PartFireSpec | null;
  /** Swing and slide: starting phase (radians), so paired parts move out of step. */
  phase?: number;
}

/** How a part reacts to the unit firing. */
export interface PartFireSpec {
  /** recoil: distance (metres); swing: radians; slide: metres; launch: travel (metres). */
  snap: number;
  attack: number;
  recover: number;
  delay: number;
  repeat: number;
  every: number;
  /** launch only: flight time and when (seconds after the shot) the tube is filled again. */
  dur: number;
  reload: number;
}

/** The model's whole-body firing kick (glTF scene extras.fire). */
export interface FireKick {
  kick: number;
  slide: number;
  attack: number;
  recover: number;
  /** Shots in one firing cycle and the spacing of the art's delays between them. */
  repeat: number;
  every: number;
}

/** Per-unit firing state: when it last fired and where in its firing cycle it is. */
export interface UnitFiring {
  kick: FireKick | null;
  /** Seconds (renderer clock) of the last shot; -Infinity before the first. */
  shotAt: number;
  shots: number;
  /** True when barrels recoil on their own (the whole turret then stays put). */
  barrels: boolean;
}

export interface PartMotion {
  node: THREE.Object3D;
  spec: PartMotionSpec;
  rest: THREE.Quaternion;
  /** Spin angle so far, or swing phase (radians). */
  phase: number;
  /** 0..1: eases the part in and out as its condition starts and stops. */
  blend: number;
  /** Scroll only: texture tiles per metre along +X on the top run (signed), or null if unknown. */
  tilesPerMetre: number | null;
  /** Rest position and scale (slide, recoil and launch move or hide the node). */
  restPos: THREE.Vector3;
  restScale: THREE.Vector3;
  /** The axis in the parent's space (the node's own axis turned by its rest rotation). */
  dir: THREE.Vector3;
  /** Renderer-clock seconds of the shot this part last answered, and its delays after it. */
  shotAt: number;
  offsets: number[];
  /** A firing part still moving (false once it has settled back at rest). */
  live: boolean;
}

/** What the owning unit or structure is doing this frame. */
export interface PartMotionState {
  mining: boolean;
  working: boolean;
  moving: boolean;
  /** How fast it is going compared with its top speed (0..1); scales the fallback scroll. */
  pace?: number;
  /** Ground speed in world units per second; drives tread scroll. */
  travel?: number;
  /** Renderer clock (seconds), for firing parts. */
  time?: number;
  /** Low quality: skip the small extras (snaps, sliding masts); barrels and missiles still play. */
  lite?: boolean;
}

/** userData key a scrolling mesh carries its texture offset (in tiles) under. */
export const UV_SCROLL = 'uvScroll';

const WHENS: ReadonlySet<string> = new Set(['always', 'mining', 'working', 'moving']);
/** How fast a part spins up or winds down (fraction of full speed per second). */
const EASE_PER_SEC = 2.5;

/** Reads a node's anim extras; null when it has none or it is malformed. */
export function readPartMotion(raw: unknown): PartMotionSpec | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const item = raw as Record<string, unknown>;
  // 'idle' motions (an aimed turret sweeping while it has no target) belong to the art viewer: in
  // the game the turret is aimed every frame, so such a part is left alone (and stays aimable).
  if (item.when === 'idle') {
    return null;
  }
  const when = typeof item.when === 'string' && WHENS.has(item.when) ? (item.when as PartMotionWhen) : 'always';
  const busy = typeof item.busySpeed === 'number' && Number.isFinite(item.busySpeed) ? item.busySpeed : null;
  if (item.type === 'scroll') {
    if (typeof item.speed !== 'number' || !Number.isFinite(item.speed)) {
      return null;
    }
    return { type: 'scroll', axis: new THREE.Vector3(1, 0, 0), speed: item.speed, amp: 0, when, busySpeed: busy, fire: null };
  }
  const type = item.type;
  if (type !== 'spin' && type !== 'swing' && type !== 'slide' && type !== 'recoil' && type !== 'launch') {
    return null;
  }
  const axis = item.axis;
  if (!Array.isArray(axis) || axis.length !== 3 || !axis.every((value) => typeof value === 'number' && Number.isFinite(value))) {
    return null;
  }
  const vector = new THREE.Vector3(axis[0] as number, axis[1] as number, axis[2] as number);
  if (vector.lengthSq() < 1e-8) {
    return null;
  }
  vector.normalize();
  if (type === 'recoil' || type === 'launch') {
    const size = num(type === 'recoil' ? item.dist : item.travel, type === 'recoil' ? 0 : 9);
    if (size === 0) {
      return null;
    }
    const fire: PartFireSpec = {
      snap: size,
      attack: Math.max(1e-3, num(item.attack, 0.04)),
      recover: Math.max(1e-3, num(item.recover, 0.45)),
      delay: Math.max(0, num(item.delay, 0)),
      repeat: Math.max(1, Math.round(num(item.repeat, 1))),
      every: Math.max(0, num(item.every, 0)),
      dur: Math.max(1e-3, num(item.dur, 0.45)),
      reload: num(item.reload, 2.4),
    };
    return { type, axis: vector, speed: 0, amp: 0, when: 'always', busySpeed: null, fire };
  }
  if (typeof item.speed !== 'number' || !Number.isFinite(item.speed)) {
    return null;
  }
  const amp = num(item.amp, 0);
  const snap = num(item.snap, 0);
  if (type !== 'spin' && amp === 0 && snap === 0) {
    return null;
  }
  const fire: PartFireSpec | null =
    type !== 'spin' && snap !== 0
      ? {
          snap,
          attack: Math.max(1e-3, num(item.attack, 0.04)),
          recover: Math.max(1e-3, num(item.recover, 0.45)),
          delay: 0,
          repeat: 1,
          every: 0,
          dur: 0,
          reload: 0,
        }
      : null;
  const phase = num(item.phase, 0);
  return { type, axis: vector, speed: item.speed, amp, when, busySpeed: busy, fire, ...(phase !== 0 ? { phase } : {}) };
}

function num(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

/** Reads the glTF scene's extras.fire (the whole-body kick); null when it has none. */
export function readFireKick(raw: unknown): FireKick | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const item = raw as Record<string, unknown>;
  const kick = num(item.kick, 0);
  const slide = num(item.slide, 0);
  if (kick === 0 && slide === 0) {
    return null;
  }
  return {
    kick,
    slide,
    attack: Math.max(1e-3, num(item.attack, 0.05)),
    recover: Math.max(1e-3, num(item.recover, 0.6)),
    repeat: Math.max(1, Math.round(num(item.repeat, 1))),
    every: Math.max(0, num(item.every, 0)),
  };
}

/** Firing state for a unit model: its kick (scene extras on the model or the root) and parts. */
export function createUnitFiring(root: THREE.Object3D, parts: readonly PartMotion[]): UnitFiring {
  let kick = readFireKick(root.userData.fire);
  for (const child of root.children) {
    kick ??= readFireKick(child.userData.fire);
  }
  return { kick, shotAt: -Infinity, shots: 0, barrels: parts.some((part) => part.spec.type === 'recoil') };
}

/** The art's hit envelope: a linear rise over `attack`, then a squared fall over `recover`. */
export function fireHit(x: number, attack: number, recover: number): number {
  if (x < 0) {
    return 0;
  }
  if (x < attack) {
    return x / attack;
  }
  const r = 1 - (x - attack) / recover;
  return r > 0 ? r * r : 0;
}

/** The whole-body kick envelope: a rise over attack, then exp(-4u) cos(6u) (0 once settled). */
export function fireKickEnvelope(kick: FireKick, tf: number): number {
  if (tf < 0) {
    return 0;
  }
  if (tf < kick.attack) {
    return tf / kick.attack;
  }
  const u = (tf - kick.attack) / kick.recover;
  return u > 2 ? 0 : Math.exp(-4 * u) * Math.cos(6 * u);
}

/**
 * The unit fired one shot at `now` (renderer clock, seconds): each firing part that belongs to
 * this shot's place in the art's firing cycle starts its hit.
 */
export function fireUnit(firing: UnitFiring, parts: readonly PartMotion[], now: number): THREE.Object3D | null {
  const repeat = firing.kick?.repeat ?? 1;
  const every = firing.kick?.every ?? 0;
  const slot = firing.shots % repeat;
  const launched = nextTube(parts, firing.shots, now);
  firing.shots += 1;
  firing.shotAt = now;
  if (launched) {
    launched.shotAt = now;
    launched.offsets = [0];
    launched.live = true;
  }
  for (const part of parts) {
    const fire = part.spec.fire;
    if (!fire || part.spec.type === 'launch') {
      continue;
    }
    const offsets: number[] = [];
    if (part.spec.type === 'swing' || part.spec.type === 'slide') {
      // Snaps (lids, claws, pod nods) answer every shot.
      offsets.push(0);
    } else {
      for (let i = 0; i < fire.repeat; i += 1) {
        const at = fire.delay + i * fire.every;
        if (repeat > 1 && every > 0) {
          const place = Math.round(at / every);
          if (place % repeat === slot) {
            offsets.push(Math.max(0, at - place * every));
          }
        } else {
          offsets.push(at);
        }
      }
    }
    if (offsets.length > 0) {
      part.shotAt = now;
      part.offsets = offsets;
      part.live = true;
    }
  }
  return launched?.node ?? null;
}

/** The tube this shot's missile leaves from: the next loaded one in delay order (or null). */
function nextTube(parts: readonly PartMotion[], shot: number, now: number): PartMotion | null {
  const tubes = parts
    .filter((part) => part.spec.type === 'launch' && part.spec.fire)
    .sort((a, b) => (a.spec.fire?.delay ?? 0) - (b.spec.fire?.delay ?? 0));
  if (tubes.length === 0) {
    return null;
  }
  for (let i = 0; i < tubes.length; i += 1) {
    const tube = tubes[(shot + i) % tubes.length] as PartMotion;
    const reload = tube.spec.fire?.reload ?? 0;
    if (!tube.live || now - tube.shotAt >= reload) {
      return tube;
    }
  }
  // Every tube is still reloading: fire the one in turn anyway.
  return tubes[shot % tubes.length] as PartMotion;
}

/** Every moving part under a model, with its rest rotation. Call on the cloned model. */
export function collectPartMotions(root: THREE.Object3D): PartMotion[] {
  const out: PartMotion[] = [];
  root.traverse((node) => {
    const spec = readPartMotion(node.userData.anim);
    if (spec) {
      out.push({
        node,
        spec,
        rest: node.quaternion.clone(),
        phase: spec.phase ?? 0,
        blend: spec.when === 'always' ? 1 : 0,
        tilesPerMetre: spec.type === 'scroll' ? treadTilesPerMetre(node) : null,
        restPos: node.position.clone(),
        restScale: node.scale.clone(),
        dir: spec.axis.clone().applyQuaternion(node.quaternion),
        shotAt: -Infinity,
        offsets: [],
        live: false,
      });
      if (spec.type === 'scroll') {
        node.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.userData[UV_SCROLL] = 0;
          }
        });
      }
    }
  });
  return out;
}

const densityCache = new WeakMap<THREE.BufferGeometry, number | null>();

/**
 * Texture tiles per metre along the node's +X (forward) on the top run of a tread mesh: the median
 * dU/dX over triangles lying wholly on the top run. Signed, so it also says which way U runs.
 */
export function treadTilesPerMetre(node: THREE.Object3D): number | null {
  let found: number | null = null;
  node.traverse((child) => {
    if (found !== null || !(child instanceof THREE.Mesh)) {
      return;
    }
    const geometry = child.geometry as THREE.BufferGeometry;
    if (!densityCache.has(geometry)) {
      densityCache.set(geometry, measureTopRun(geometry));
    }
    const value = densityCache.get(geometry) ?? null;
    if (value !== null) {
      // Into the node's frame (a child mesh may be scaled under the node).
      const scale = child === node ? 1 : child.scale.x;
      found = value / (scale || 1);
    }
  });
  return found;
}

function measureTopRun(geometry: THREE.BufferGeometry): number | null {
  const position = geometry.getAttribute('position');
  const uv = geometry.getAttribute('uv');
  if (!position || !uv) {
    return null;
  }
  let minY = Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < position.count; i += 1) {
    minY = Math.min(minY, position.getY(i));
    maxY = Math.max(maxY, position.getY(i));
  }
  const cut = maxY - Math.max(0.05, (maxY - minY) * 0.08);
  const index = geometry.getIndex();
  const count = index ? index.count : position.count;
  const ratios: number[] = [];
  for (let t = 0; t + 2 < count; t += 3) {
    const v = [0, 1, 2].map((k) => (index ? index.getX(t + k) : t + k));
    if (!v.every((i) => position.getY(i) >= cut)) {
      continue;
    }
    // The edge running most along X gives dU/dX for this triangle.
    let best: [number, number] | null = null;
    for (const [a, b] of [[v[0], v[1]], [v[1], v[2]], [v[0], v[2]]] as Array<[number, number]>) {
      const dx = position.getX(b) - position.getX(a);
      if (!best || Math.abs(dx) > Math.abs(best[0])) {
        best = [dx, uv.getX(b) - uv.getX(a)];
      }
    }
    if (best && Math.abs(best[0]) > 1e-4) {
      ratios.push(best[1] / best[0]);
    }
  }
  if (ratios.length === 0) {
    return null;
  }
  ratios.sort((a, b) => a - b);
  const median = ratios[Math.floor(ratios.length / 2)] ?? 0;
  return Math.abs(median) > 1e-4 ? median : null;
}

const worldScale = new THREE.Vector3();

/** True when this model's TurretPivot is a spinner (so it must not be aimed). */
export function pivotIsSpinner(parts: readonly PartMotion[]): boolean {
  return parts.some((part) => part.node.name === 'TurretPivot' && part.spec.type !== 'scroll');
}

function active(when: PartMotionWhen, state: PartMotionState): boolean {
  switch (when) {
    case 'always':
      return true;
    case 'mining':
      return state.mining;
    case 'working':
      return state.working;
    case 'moving':
      return state.moving;
  }
}

const turn = new THREE.Quaternion();

/** The strongest of a part's hits at time `now` (0 when it has none running). */
function partHit(part: PartMotion, fire: PartFireSpec, now: number): number {
  const tf = now - part.shotAt;
  let most = 0;
  for (const offset of part.offsets) {
    most = Math.max(most, fireHit(tf - offset, fire.attack, fire.recover));
  }
  return most;
}

/** Poses a recoil or launch part; returns false once it is back at rest and need not be posed. */
function poseFiringPart(part: PartMotion, fire: PartFireSpec, now: number): boolean {
  const { node } = part;
  if (part.spec.type === 'recoil') {
    const hit = partHit(part, fire, now);
    node.position.copy(part.restPos).addScaledVector(part.dir, -fire.snap * hit);
    // Settled once every hit is past its attack and back to 0.
    const last = Math.max(...part.offsets) + fire.attack;
    return hit > 0 || now - part.shotAt < last;
  }
  // launch
  const tf = now - part.shotAt;
  const x = tf - (part.offsets[0] ?? 0);
  if (x < 0 || tf >= fire.reload) {
    node.position.copy(part.restPos);
    node.scale.copy(part.restScale);
    return tf < fire.reload;
  }
  // Gone from the tube until it is reloaded (a zero scale draws nothing in the instanced batch):
  // the game draws the missile in flight from here on.
  node.position.copy(part.restPos);
  node.scale.setScalar(0);
  return true;
}

/** Advances and poses every part. `dt` is real seconds since the last frame. */
export function updatePartMotions(parts: readonly PartMotion[], state: PartMotionState, dt: number): void {
  const step = Math.min(Math.max(dt, 0), 0.1);
  const now = state.time ?? 0;
  for (const part of parts) {
    const { spec } = part;
    if (spec.type === 'recoil' || spec.type === 'launch') {
      if (part.live && spec.fire) {
        part.live = poseFiringPart(part, spec.fire, now);
      }
      continue;
    }
    const on = active(spec.when, state);
    part.blend = on ? Math.min(1, part.blend + step * EASE_PER_SEC) : Math.max(0, part.blend - step * EASE_PER_SEC);
    const speed = state.working && spec.busySpeed !== null ? spec.busySpeed : spec.speed;
    if (spec.type === 'scroll') {
      let rate: number;
      if (part.tilesPerMetre !== null && state.travel !== undefined) {
        // The top run moves forward (+X) at ground speed relative to the hull. Sampling at
        // u + offset moves the pattern toward lower U, hence the minus sign.
        part.node.getWorldScale(worldScale);
        const metres = on ? state.travel / (worldScale.x || 1) : 0;
        rate = -part.tilesPerMetre * metres;
      } else {
        rate = speed * part.blend * (state.pace ?? 1);
      }
      // Wraps to stay precise.
      part.phase = (part.phase + rate * step) % 1;
      const offset = part.phase;
      part.node.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.userData[UV_SCROLL] = offset;
        }
      });
      continue;
    }
    // A snap (lids kicking open, a pod nodding) on top of the idle motion; skipped on low quality.
    let snap = 0;
    if (part.live && spec.fire) {
      snap = state.lite ? 0 : spec.fire.snap * partHit(part, spec.fire, now);
      part.live = snap !== 0 || now - part.shotAt < spec.fire.attack;
    }
    if (spec.type === 'slide') {
      if (state.lite && !part.live && part.node.position.equals(part.restPos)) {
        continue;
      }
      part.phase = (part.phase + speed * Math.PI * 2 * step) % (Math.PI * 2);
      const idle = state.lite ? 0 : Math.sin(part.phase) * spec.amp * part.blend;
      part.node.position.copy(part.restPos).addScaledVector(part.dir, idle + snap);
      continue;
    }
    if (spec.type === 'spin') {
      // Spins up and winds down rather than snapping, and stops where it is.
      part.phase = (part.phase + speed * part.blend * step) % (Math.PI * 2);
      turn.setFromAxisAngle(spec.axis, part.phase);
    } else {
      // speed is in Hz; the swing settles back to rest as blend falls.
      part.phase = (part.phase + speed * Math.PI * 2 * step) % (Math.PI * 2);
      turn.setFromAxisAngle(spec.axis, Math.sin(part.phase) * spec.amp * part.blend + snap);
    }
    part.node.quaternion.copy(part.rest).multiply(turn);
  }
}
