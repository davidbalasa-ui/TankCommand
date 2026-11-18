// Indirect-fire shells (Longbow, Mortar Beast) are drawn on a ballistic arc from the gun's muzzle
// down onto the point the sim's shot bursts at. The sim flies every shot on a near-flat line from
// the unit's centre; this is the view's own path for the shell, closed onto the same end point.

export interface ShellArc {
  fromX: number;
  fromY: number;
  fromZ: number;
  toX: number;
  toY: number;
  toZ: number;
  /** Height of the arc's top above the straight line between its ends, metres. */
  height: number;
}

/** The arc's top is this share of its ground length, within the limits below. */
const ARC_HEIGHT_PER_METRE = 0.32;
const ARC_MIN_HEIGHT = 1.5;
const ARC_MAX_HEIGHT = 9;
/** A muzzle further forward than this share of the aimed distance starts the arc no further. */
const MAX_START_SHARE = 0.6;

/**
 * Plan a shell's arc. `launch` is where the sim fired it (the unit's centre), `dirX/dirZ` its
 * flight direction on the ground, `aim` the distance to where it bursts and `endY` the height it
 * bursts at. `muzzle` is the barrel tip (null when the model has none). The start is kept behind the
 * end along the line of fire, so the shell never flies backwards, even at point-blank range.
 */
export function planShellArc(
  launch: { x: number; y: number; z: number },
  muzzle: { x: number; y: number; z: number } | null,
  dirX: number,
  dirZ: number,
  aim: number,
  endY: number,
): ShellArc {
  const length = Math.hypot(dirX, dirZ);
  const ux = length > 1e-9 ? dirX / length : 1;
  const uz = length > 1e-9 ? dirZ / length : 0;
  const from = muzzle ?? launch;
  const relX = from.x - launch.x;
  const relZ = from.z - launch.z;
  const forward = relX * ux + relZ * uz;
  const sideX = relX - forward * ux;
  const sideZ = relZ - forward * uz;
  const ahead = Math.min(Math.max(0, forward), Math.max(0, aim) * MAX_START_SHARE);
  const fromX = launch.x + ux * ahead + sideX;
  const fromZ = launch.z + uz * ahead + sideZ;
  const toX = launch.x + ux * Math.max(0, aim);
  const toZ = launch.z + uz * Math.max(0, aim);
  const ground = Math.hypot(toX - fromX, toZ - fromZ);
  // A high gun lobbing onto a near target still climbs first: half the drop goes on top.
  const drop = Math.max(0, from.y - endY);
  return {
    fromX,
    fromY: from.y,
    fromZ,
    toX,
    toY: endY,
    toZ,
    height: Math.min(ARC_MAX_HEIGHT, Math.max(ARC_MIN_HEIGHT + drop * 0.5, ground * ARC_HEIGHT_PER_METRE)),
  };
}

/** Where the shell is at `progress` (0 at the muzzle, 1 at the burst). */
export function shellArcPoint(arc: ShellArc, progress: number): { x: number; y: number; z: number } {
  const p = Math.min(1, Math.max(0, progress));
  return {
    x: arc.fromX + (arc.toX - arc.fromX) * p,
    y: arc.fromY + (arc.toY - arc.fromY) * p + 4 * arc.height * p * (1 - p),
    z: arc.fromZ + (arc.toZ - arc.fromZ) * p,
  };
}
