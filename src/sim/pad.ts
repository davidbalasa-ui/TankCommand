// Landing pad layout and traffic rules.
//
// A pad has three working spots, all derived from its position so nothing extra has to be saved:
//   - the landing circle at its centre, where deliveries come down one at a time;
//   - the exit edge, facing the map centre: new arrivals drive off the pad that way to a rally point;
//   - the dock edge, at right angles to the exit: miners and haulers unload there, one at a time,
//     and the others wait in a line behind it.
import { clampToMap } from './map';
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
  // Dock side: the exit direction turned a quarter to the left (toward +heading).
  const dx = -fz;
  const dz = fx;
  const rally = clampToMap(
    world.map,
    pad.x + fx * (half + PAD_RALLY_DISTANCE),
    pad.z + fz * (half + PAD_RALLY_DISTANCE),
    UNIT_RADIUS,
  );
  const dock = clampToMap(
    world.map,
    pad.x + dx * (half + UNIT_RADIUS + 0.4),
    pad.z + dz * (half + UNIT_RADIUS + 0.4),
    UNIT_RADIUS,
  );
  return {
    half,
    facing,
    exitX: pad.x + fx * half,
    exitZ: pad.z + fz * half,
    rallyX: rally.x,
    rallyZ: rally.z,
    dockX: dock.x,
    dockZ: dock.z,
    liftX: pad.x + dx * (half * 0.62),
    liftZ: pad.z + dz * (half * 0.62),
    dockDirX: dx,
    dockDirZ: dz,
  };
}

/** Waiting spot `index` (0 = first in line) behind the dock. */
export function padQueueSpot(
  world: WorldState,
  layout: PadLayout,
  index: number,
): { x: number; z: number } {
  const distance = PAD_QUEUE_SPACING * (index + 1);
  return clampToMap(
    world.map,
    layout.dockX + layout.dockDirX * distance,
    layout.dockZ + layout.dockDirZ * distance,
    UNIT_RADIUS,
  );
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

/** Workers heading to `pad`, in the order they joined its line (oldest first). */
export function padLine(world: WorldState, pad: StructureState): UnitState[] {
  return world.units
    .filter(
      (unit) =>
        unit.hp > 0 &&
        unit.job !== null &&
        unit.job.dockPadId === pad.id &&
        (unit.job.stage === 'toPad' || unit.job.stage === 'unloading'),
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
