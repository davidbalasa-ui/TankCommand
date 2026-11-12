// Landing pad layout and traffic rules.
//
// A pad has three working spots, all derived from its position so nothing extra has to be saved:
//   - the landing circle at its centre, where deliveries come down one at a time;
//   - the exit edge, facing the map centre: new arrivals drive off the pad that way to a rally point;
//   - three dock spots, one off the middle of every edge except the exit: haulers unload at the
//     nearest free one, one at a time per dock, and the others wait in a line behind it.
//
// The pad deck is solid (see padShapes): units can only stand on the landing circle and the exit
// lane, so nothing drives across the pad's raised deck.
import { clampToMap } from './map';
import { canStand } from './motion';
import { UNIT_RADIUS } from './tuning';
import type { StructureState, UnitState, WorldState } from './types';

export const PAD_LAND_SEC = 2.5; // placeholder until Stage 0: descent onto the pad
export const PAD_CLEAR_TIMEOUT_SEC = 10; // placeholder until Stage 0: stop waiting for a stuck arrival
export const PAD_RALLY_DISTANCE = 7; // placeholder until Stage 0: how far past the exit edge arrivals park
export const PAD_UNLOAD_SEC = 1.5; // placeholder until Stage 0: cargo moves from worker to pad
export const PAD_CARGO_LIFT_SEC = 2.5; // placeholder until Stage 0: cargo lifts off (visual only)
export const PAD_DOCK_REACH = 1.6; // placeholder until Stage 0
export const PAD_QUEUE_SPACING = 5.5; // placeholder until Stage 0
export const PAD_QUEUE_JOIN_DISTANCE = 30; // placeholder until Stage 0: workers queue once this close
export const PAD_DOCK_WAIT_COST = 18; // placeholder until Stage 0: metres of extra drive one waiting worker is worth

/** One unloading spot off a pad edge, with its waiting line extending outward. */
export interface PadDock {
  x: number;
  z: number;
  dirX: number; // outward from the pad; the waiting line extends this way
  dirZ: number;
  liftX: number; // where on the deck the cargo lifts off from this dock
  liftZ: number;
  open: boolean; // false when the dock spot is off the map or on blocked ground
}

/** Half-width of the exit lane (unit centres), so the landing circle and lane stay drivable. */
export const PAD_LANE_HALF = 2;

export interface PadLayout {
  half: number;
  facing: number; // heading of the exit edge (0 = +x)
  exitX: number;
  exitZ: number;
  rallyX: number;
  rallyZ: number;
  dockX: number; // where a worker parks to unload, just off the dock edge
  dockZ: number;
  liftX: number; // the cargo lift on the pad, beside the dock edge
  liftZ: number;
  dockDirX: number; // outward along the dock side; the waiting line extends this way
  dockDirZ: number;
  docks: PadDock[]; // [0] = the dock above (left of the exit), [1] = right of the exit, [2] = back
}

/** Exit faces the map centre, snapped to the nearest axis so the pad sits square on the grid. */
export function padFacing(pad: { x: number; z: number }): number {
  const dx = -pad.x;
  const dz = -pad.z;
  if (Math.abs(dx) < 1e-6 && Math.abs(dz) < 1e-6) {
    return 0;
  }
  if (Math.abs(dx) >= Math.abs(dz)) {
    return dx >= 0 ? 0 : Math.PI;
  }
  return dz >= 0 ? Math.PI / 2 : -Math.PI / 2;
}

export function padLayout(world: WorldState, pad: StructureState): PadLayout {
  const type = world.structureTypes.get(pad.typeId);
  const cells = type ? Math.max(type.footprint.cellsX, type.footprint.cellsZ) : 1;
  const half = (cells * world.map.cellSize) / 2;
  const facing = padFacing(pad);
  const fx = Math.round(Math.cos(facing));
  const fz = Math.round(Math.sin(facing));
  const rally = clampToMap(
    world.map,
    pad.x + fx * (half + PAD_RALLY_DISTANCE),
    pad.z + fz * (half + PAD_RALLY_DISTANCE),
    UNIT_RADIUS,
  );
  // Dock sides: left of the exit (a quarter turn toward +heading), right of it, and the back.
  const sides: Array<[number, number]> = [
    [-fz, fx],
    [fz, -fx],
    [-fx, -fz],
  ];
  const docks = sides.map(([dx, dz]): PadDock => {
    const wantX = pad.x + dx * (half + UNIT_RADIUS + 0.4);
    const wantZ = pad.z + dz * (half + UNIT_RADIUS + 0.4);
    const spot = clampToMap(world.map, wantX, wantZ, UNIT_RADIUS);
    const moved = Math.hypot(spot.x - wantX, spot.z - wantZ) > 0.5;
    return {
      x: spot.x,
      z: spot.z,
      dirX: dx,
      dirZ: dz,
      liftX: pad.x + dx * (half * 0.62),
      liftZ: pad.z + dz * (half * 0.62),
      open: !moved && canStand(world, spot.x, spot.z) && !underBuilding(world, spot.x, spot.z),
    };
  });
  // Dock 0 is the fallback: treat it as open if every dock is shut, so a worker always has one.
  if (!docks.some((dock) => dock.open)) {
    docks[0]!.open = true;
  }
  const first = docks[0]!;
  return {
    half,
    facing,
    exitX: pad.x + fx * half,
    exitZ: pad.z + fz * half,
    rallyX: rally.x,
    rallyZ: rally.z,
    dockX: first.x,
    dockZ: first.z,
    liftX: first.liftX,
    liftZ: first.liftZ,
    dockDirX: first.dirX,
    dockDirZ: first.dirZ,
    docks,
  };
}

/** True when a standing building (not a pad) covers this spot, hull included. */
function underBuilding(world: WorldState, x: number, z: number): boolean {
  for (const structure of world.structures) {
    if (structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type || type.kind === 'pad') {
      continue;
    }
    const hx = (type.footprint.cellsX * world.map.cellSize) / 2 + UNIT_RADIUS;
    const hz = (type.footprint.cellsZ * world.map.cellSize) / 2 + UNIT_RADIUS;
    if (Math.abs(structure.x - x) < hx && Math.abs(structure.z - z) < hz) {
      return true;
    }
  }
  return false;
}

/**
 * The solid parts of a pad, as obstacle rectangles already widened by `margin`: the whole square
 * except the landing circle at the centre and the exit lane leading off it.
 */
export function padShapes(
  pad: { x: number; z: number },
  half: number,
  margin: number,
): Array<{ x: number; z: number; hx: number; hz: number }> {
  const facing = padFacing(pad);
  const fx = Math.round(Math.cos(facing));
  const fz = Math.round(Math.sin(facing));
  const outer = half + margin;
  const lane = PAD_LANE_HALF;
  // In the pad's frame: u along the exit, v across it.
  const rects: Array<{ u0: number; u1: number; v0: number; v1: number }> = [
    { u0: -outer, u1: -lane, v0: -outer, v1: outer }, // back block, behind the landing circle
    { u0: -lane, u1: outer, v0: lane, v1: outer }, // side block, one side of the lane
    { u0: -lane, u1: outer, v0: -outer, v1: -lane }, // side block, the other side
  ];
  return rects.map((rect) => {
    const cu = (rect.u0 + rect.u1) / 2;
    const cv = (rect.v0 + rect.v1) / 2;
    const hu = (rect.u1 - rect.u0) / 2;
    const hv = (rect.v1 - rect.v0) / 2;
    // u axis = (fx, fz); v axis = (-fz, fx). Both are along world axes, so the box stays square.
    const alongX = fx !== 0;
    return {
      x: pad.x + fx * cu - fz * cv,
      z: pad.z + fz * cu + fx * cv,
      hx: alongX ? hu : hv,
      hz: alongX ? hv : hu,
    };
  });
}

/** Waiting spot `index` (0 = first in line) behind dock `dock` (default the first). */
export function padQueueSpot(
  world: WorldState,
  layout: PadLayout,
  index: number,
  dock = 0,
): { x: number; z: number } {
  const spot = layout.docks[dock] ?? layout.docks[0]!;
  const distance = PAD_QUEUE_SPACING * (index + 1);
  return clampToMap(world.map, spot.x + spot.dirX * distance, spot.z + spot.dirZ * distance, UNIT_RADIUS);
}

/** True while a fresh arrival still sits on the pad, so the next delivery has to wait. */
export function padOccupied(world: WorldState, pad: StructureState): boolean {
  const id = pad.padUnitId;
  if (id === undefined || id === null) {
    return false;
  }
  return (pad.padClearLeft ?? 0) > 0;
}

/** Ticks a pad's "arrival still on the pad" state. */
export function updatePadClearing(world: WorldState, dt: number): void {
  for (const pad of world.structures) {
    const id = pad.padUnitId;
    if (id === undefined || id === null) {
      continue;
    }
    const unit = world.units.find((item) => item.id === id);
    const half = padLayout(world, pad).half;
    const off =
      !unit ||
      unit.hp <= 0 ||
      pad.hp <= 0 ||
      Math.max(Math.abs(unit.x - pad.x), Math.abs(unit.z - pad.z)) > half + UNIT_RADIUS * 0.5;
    pad.padClearLeft = Math.max(0, (pad.padClearLeft ?? 0) - dt);
    if (off || pad.padClearLeft <= 0) {
      pad.padUnitId = null;
      pad.padClearLeft = 0;
    }
  }
}

/**
 * Workers heading to `pad`, in the order they joined its line (oldest first). With `dock`, only
 * the line at that dock (workers that have not picked a dock yet count as dock 0).
 */
export function padLine(world: WorldState, pad: StructureState, dock?: number): UnitState[] {
  return world.units
    .filter(
      (unit) =>
        unit.hp > 0 &&
        unit.job !== null &&
        unit.job.dockPadId === pad.id &&
        (unit.job.stage === 'toPad' || unit.job.stage === 'unloading') &&
        (dock === undefined || (unit.job.dockSide ?? 0) === dock),
    )
    .sort((a, b) => {
      const ua = a.job?.stage === 'unloading' ? 0 : 1;
      const ub = b.job?.stage === 'unloading' ? 0 : 1;
      if (ua !== ub) {
        return ua - ub;
      }
      const qa = a.job?.queuedAt ?? 0;
      const qb = b.job?.queuedAt ?? 0;
      return qa - qb || a.id - b.id;
    });
}

/**
 * Where a fresh arrival parks: the rally point past the exit edge, or the nearest free slot in a
 * grid of rows laid out in the pad's own frame (alternating left and right), so arrivals line up
 * neatly beside each other the same way for every pad orientation.
 */
export function padRallySpot(world: WorldState, pad: StructureState, selfId: number): { x: number; z: number } {
  const layout = padLayout(world, pad);
  const fx = Math.round(Math.cos(layout.facing));
  const fz = Math.round(Math.sin(layout.facing));
  const free = (x: number, z: number): boolean =>
    canStand(world, x, z) &&
    !world.units.some(
      (other) => other.id !== selfId && other.hp > 0 && Math.hypot(other.x - x, other.z - z) < UNIT_RADIUS * 2,
    );
  for (let i = 0; i < 30; i += 1) {
    const row = Math.floor(i / 5);
    const col = i % 5;
    const lateral = (col === 0 ? 0 : Math.ceil(col / 2) * (col % 2 === 1 ? 1 : -1)) * UNIT_RADIUS * 2.4;
    const forward = row * UNIT_RADIUS * 2.8;
    const spot = clampToMap(
      world.map,
      layout.rallyX + fx * forward - fz * lateral,
      layout.rallyZ + fz * forward + fx * lateral,
      UNIT_RADIUS,
    );
    if (free(spot.x, spot.z)) {
      return spot;
    }
  }
  return { x: layout.rallyX, z: layout.rallyZ };
}
