// Packed tower -> deployed structure, animated part by part.
//
// Tower models from tools/art/v2 carry their packed pose on each moving part (glTF extras, which
// GLTFLoader puts in userData): `packed: { p, r, s }` on Base, Carrier and TurretPivot, in the
// parent's glTF space. The node's own transform is the deployed pose. Carrier
// (`hideWhenDeployed`) is the folded hull: it shows only while unfolding. The packed unit model
// uses the same units, so the whole model also tweens from the size and centre the packed unit had
// to the structure's.
import * as THREE from 'three';

interface Pose {
  p: [number, number, number];
  q: [number, number, number, number];
  s: [number, number, number];
}

interface UnfoldPart {
  name: string;
  packed: Pose;
  deployed: Pose;
  hide: boolean;
}

/** Plain numbers only: Object3D.clone copies userData through JSON. */
export interface UnfoldData {
  parts: UnfoldPart[];
  /** Raw (glTF unit) bounds of the packed pose: centre x/z and lowest y. */
  packedCentre: [number, number, number];
  /** Raw bounds of the deployed pose without the Carrier. */
  deployedCentre: [number, number, number];
  /** Scale the template gives the inner model (1 / deployed footprint). */
  normScale: number;
}

function isTriple(value: unknown): value is [number, number, number] {
  return Array.isArray(value) && value.length === 3 && value.every((item) => typeof item === 'number');
}

function readPacked(object: THREE.Object3D): Pose | null {
  const packed: unknown = object.userData?.packed;
  if (!packed || typeof packed !== 'object') {
    return null;
  }
  const { p, r, s } = packed as { p?: unknown; r?: unknown; s?: unknown };
  if (!isTriple(p) || !isTriple(s) || !Array.isArray(r) || r.length !== 4) {
    return null;
  }
  return { p, q: r as [number, number, number, number], s };
}

function poseOf(object: THREE.Object3D): Pose {
  return {
    p: object.position.toArray(),
    q: object.quaternion.toArray(),
    s: object.scale.toArray(),
  };
}

function setPose(object: THREE.Object3D, pose: Pose): void {
  object.position.fromArray(pose.p);
  object.quaternion.fromArray(pose.q);
  object.scale.fromArray(pose.s);
}

function meshBounds(model: THREE.Object3D, skip: Set<THREE.Object3D>): THREE.Box3 {
  model.updateMatrixWorld(true);
  const bounds = new THREE.Box3();
  const part = new THREE.Box3();
  model.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) {
      return;
    }
    for (let node: THREE.Object3D | null = object; node; node = node.parent) {
      if (skip.has(node)) {
        return;
      }
    }
    part.setFromObject(object);
    bounds.union(part);
  });
  return bounds;
}

function centreOf(bounds: THREE.Box3): [number, number, number] {
  const centre = new THREE.Vector3();
  bounds.getCenter(centre);
  return [centre.x, bounds.min.y, centre.z];
}

/**
 * Read the fold data off a freshly loaded tower model (identity root transform). Leaves the model
 * in its deployed pose with hide-when-deployed parts hidden. Returns the deployed bounds to
 * normalise with (Carrier left out) and the fold data, or null for an ordinary model.
 */
export function readUnfold(model: THREE.Object3D): { data: Omit<UnfoldData, 'normScale'>; bounds: THREE.Box3 } | null {
  const parts: UnfoldPart[] = [];
  const nodes: THREE.Object3D[] = [];
  model.traverse((object) => {
    const packed = readPacked(object);
    if (packed && object.name) {
      parts.push({ name: object.name, packed, deployed: poseOf(object), hide: Boolean(object.userData?.hideWhenDeployed) });
      nodes.push(object);
    }
  });
  if (parts.length === 0) {
    return null;
  }
  const hidden = new Set(nodes.filter((_, index) => parts[index]?.hide));
  const deployedBounds = meshBounds(model, hidden);
  nodes.forEach((node, index) => setPose(node, parts[index]!.packed));
  const packedBounds = meshBounds(model, new Set());
  nodes.forEach((node, index) => {
    setPose(node, parts[index]!.deployed);
    if (parts[index]!.hide) {
      node.visible = false;
    }
  });
  model.updateMatrixWorld(true);
  if (deployedBounds.isEmpty() || packedBounds.isEmpty()) {
    return null;
  }
  return {
    data: { parts, packedCentre: centreOf(packedBounds), deployedCentre: centreOf(deployedBounds) },
    bounds: deployedBounds,
  };
}

/** Eased progress: slow start, slow finish. */
function ease(x: number): number {
  const t = Math.min(1, Math.max(0, x));
  return t * t * (3 - 2 * t);
}

const scratchA = new THREE.Quaternion();
const scratchB = new THREE.Quaternion();
const scratchYaw = new THREE.Quaternion();
const UP = new THREE.Vector3(0, 1, 0);
const offset = new THREE.Vector3();

export interface UnfoldStart {
  /** Inner-model scale (in the structure root's units) that matches the packed unit's size. */
  packedScale: number;
  /** Model yaw (rotation.y) the packed unit had. */
  yaw: number;
}

/**
 * Pose the model `t` of the way (0..1) from packed to deployed. `inner` is the template's model
 * (the root's only child). `pivotYaw` is the aim (rotation.y) the turret ends on; the pivot blends
 * into it so there is no snap when aiming takes over. Returns true once fully deployed.
 */
export function applyUnfold(
  inner: THREE.Object3D,
  data: UnfoldData,
  t: number,
  start: UnfoldStart,
  pivotYaw: number,
): boolean {
  const done = t >= 1;
  // The hull settles to the structure's size and facing first, then the parts fold out.
  const body = done ? 1 : ease(t / 0.4);
  const fold = done ? 1 : ease((t - 0.2) / 0.8);

  const k = start.packedScale + (data.normScale - start.packedScale) * body;
  const yaw = start.yaw * (1 - body);
  const cx = data.packedCentre[0] + (data.deployedCentre[0] - data.packedCentre[0]) * body;
  const cy = data.packedCentre[1] + (data.deployedCentre[1] - data.packedCentre[1]) * body;
  const cz = data.packedCentre[2] + (data.deployedCentre[2] - data.packedCentre[2]) * body;
  inner.scale.setScalar(k);
  inner.rotation.set(0, yaw, 0);
  offset.set(-cx * k, -cy * k, -cz * k).applyAxisAngle(UP, yaw);
  inner.position.copy(offset);

  for (const part of data.parts) {
    const node = inner.getObjectByName(part.name);
    if (!node) {
      continue;
    }
    if (part.hide) {
      node.visible = !done;
    }
    const isPivot = part.name === 'TurretPivot';
    scratchB.fromArray(part.deployed.q);
    if (isPivot) {
      // Aim relative to the model, which may still be turning to face north.
      scratchYaw.setFromAxisAngle(UP, pivotYaw - yaw);
      scratchB.multiply(scratchYaw);
    }
    if (done) {
      setPose(node, part.deployed);
      node.quaternion.copy(scratchB);
      continue;
    }
    scratchA.fromArray(part.packed.q);
    node.quaternion.slerpQuaternions(scratchA, scratchB, fold);
    node.position.set(
      part.packed.p[0] + (part.deployed.p[0] - part.packed.p[0]) * fold,
      part.packed.p[1] + (part.deployed.p[1] - part.packed.p[1]) * fold,
      part.packed.p[2] + (part.deployed.p[2] - part.packed.p[2]) * fold,
    );
    node.scale.set(
      part.packed.s[0] + (part.deployed.s[0] - part.packed.s[0]) * fold,
      part.packed.s[1] + (part.deployed.s[1] - part.packed.s[1]) * fold,
      part.packed.s[2] + (part.deployed.s[2] - part.packed.s[2]) * fold,
    );
  }
  return done;
}
