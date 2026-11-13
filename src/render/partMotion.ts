// Moving parts on models (miner drums, radar dishes, spinning crowns, wings). The art pipeline
// (tools/art/v2/motion.py) puts an `anim` entry in a pivot node's glTF extras, which GLTFLoader
// copies to node.userData.anim:
//
//   { type: 'spin',  axis: [x, y, z], speed: rad/s, when, busySpeed? }
//   { type: 'swing', axis: [x, y, z], amp: rad, speed: Hz, when, busySpeed? }
//   { type: 'scroll', speed: tiles/s, when }   (tank treads: slides the texture along U)
//
// `when` is 'always' | 'mining' | 'working' | 'moving'. The axis is in the node's own space and
// each node already sits on its part's axis, so the part turns by rotating the node about that
// axis on top of its rest rotation. busySpeed replaces speed while the unit is working.
//
// A TurretPivot that carries an anim is a spinner, not an aimed turret.
//
// A scroll part does not move its node: it writes the texture offset to userData.uvScroll on each
// mesh under it, and the unit instancing (unitInstances.ts) passes that per instance to the
// shader, so every tank's treads run on their own.
import * as THREE from 'three';

export type PartMotionWhen = 'always' | 'mining' | 'working' | 'moving';

export interface PartMotionSpec {
  type: 'spin' | 'swing' | 'scroll';
  axis: THREE.Vector3;
  speed: number;
  amp: number;
  when: PartMotionWhen;
  busySpeed: number | null;
}

export interface PartMotion {
  node: THREE.Object3D;
  spec: PartMotionSpec;
  rest: THREE.Quaternion;
  /** Spin angle so far, or swing phase (radians). */
  phase: number;
  /** 0..1: eases the part in and out as its condition starts and stops. */
  blend: number;
}

/** What the owning unit or structure is doing this frame. */
export interface PartMotionState {
  mining: boolean;
  working: boolean;
  moving: boolean;
  /** How fast it is going compared with its top speed (0..1); scales tread scroll. */
  pace?: number;
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
  const when = typeof item.when === 'string' && WHENS.has(item.when) ? (item.when as PartMotionWhen) : 'always';
  const busy = typeof item.busySpeed === 'number' && Number.isFinite(item.busySpeed) ? item.busySpeed : null;
  if (item.type === 'scroll') {
    if (typeof item.speed !== 'number' || !Number.isFinite(item.speed)) {
      return null;
    }
    return { type: 'scroll', axis: new THREE.Vector3(1, 0, 0), speed: item.speed, amp: 0, when, busySpeed: busy };
  }
  const axis = item.axis;
  if (
    (item.type !== 'spin' && item.type !== 'swing') ||
    !Array.isArray(axis) ||
    axis.length !== 3 ||
    !axis.every((value) => typeof value === 'number' && Number.isFinite(value)) ||
    typeof item.speed !== 'number' ||
    !Number.isFinite(item.speed)
  ) {
    return null;
  }
  const vector = new THREE.Vector3(axis[0] as number, axis[1] as number, axis[2] as number);
  if (vector.lengthSq() < 1e-8) {
    return null;
  }
  const amp = typeof item.amp === 'number' && Number.isFinite(item.amp) ? item.amp : 0;
  if (item.type === 'swing' && amp === 0) {
    return null;
  }
  return { type: item.type, axis: vector.normalize(), speed: item.speed, amp, when, busySpeed: busy };
}

/** Every moving part under a model, with its rest rotation. Call on the cloned model. */
export function collectPartMotions(root: THREE.Object3D): PartMotion[] {
  const out: PartMotion[] = [];
  root.traverse((node) => {
    const spec = readPartMotion(node.userData.anim);
    if (spec) {
      out.push({ node, spec, rest: node.quaternion.clone(), phase: 0, blend: spec.when === 'always' ? 1 : 0 });
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

/** Advances and poses every part. `dt` is real seconds since the last frame. */
export function updatePartMotions(parts: readonly PartMotion[], state: PartMotionState, dt: number): void {
  const step = Math.min(Math.max(dt, 0), 0.1);
  for (const part of parts) {
    const { spec } = part;
    const on = active(spec.when, state);
    part.blend = on ? Math.min(1, part.blend + step * EASE_PER_SEC) : Math.max(0, part.blend - step * EASE_PER_SEC);
    const speed = state.working && spec.busySpeed !== null ? spec.busySpeed : spec.speed;
    if (spec.type === 'scroll') {
      // Tiles per second, scaled by how fast the unit is actually going; wraps to stay precise.
      part.phase = (part.phase + speed * part.blend * (state.pace ?? 1) * step) % 1;
      const offset = part.phase;
      part.node.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.userData[UV_SCROLL] = offset;
        }
      });
      continue;
    }
    if (spec.type === 'spin') {
      // Spins up and winds down rather than snapping, and stops where it is.
      part.phase = (part.phase + speed * part.blend * step) % (Math.PI * 2);
      turn.setFromAxisAngle(spec.axis, part.phase);
    } else {
      // speed is in Hz; the swing settles back to rest as blend falls.
      part.phase = (part.phase + speed * Math.PI * 2 * step) % (Math.PI * 2);
      turn.setFromAxisAngle(spec.axis, Math.sin(part.phase) * spec.amp * part.blend);
    }
    part.node.quaternion.copy(part.rest).multiply(turn);
  }
}
