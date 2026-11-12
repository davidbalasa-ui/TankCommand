// Local avoidance for ground units (own side only; enemies are targets, not traffic). Deterministic: iteration follows world.units order and every
// tie is broken by unit id.
//
// Pathfinding plans around terrain only. On top of that, each moving unit looks ahead along the
// way it wants to go and, when another unit is in that corridor:
//   - head-on with a moving unit: both keep right, so they pass instead of meeting nose to nose;
//   - behind a unit going the same way: it follows at that unit's speed rather than ramming it;
//   - anything else: it steers round the near side of the obstacle, harder the closer it is;
//   - a parked friendly unit in the way steps aside to let it through.
// Overlaps that still happen are pushed apart afterwards by separateUnits, using each unit's own
// size.
import { isBlockedAt, type MapDef } from './map';
import { UNIT_RADIUS } from './tuning';
import type { SimUnitType, UnitState, WorldState } from './types';

const CELL = 8;
const MAX_RADIUS = UNIT_RADIUS * 1.5;
const LOOK_BASE = 2;
const LOOK_SECONDS = 0.8;
const CLEAR_MARGIN = 0.6;
const YIELD_SPEED = 3; // m/s a parked unit shuffles sideways
const TICK = 1 / 20;

export function unitRadius(world: WorldState, unit: UnitState): number {
  return world.unitTypes.get(unit.typeId)?.radius ?? UNIT_RADIUS;
}

interface Grid {
  world: WorldState;
  tick: number;
  cells: Map<number, UnitState[]>;
}

let cached: Grid | null = null;

function cellKey(cx: number, cz: number): number {
  return (cx + 4096) * 8192 + (cz + 4096);
}

/** Ground units bucketed by position, rebuilt once per tick (positions drift a little within it). */
function grid(world: WorldState): Grid {
  if (cached && cached.world === world && cached.tick === world.tick) {
    return cached;
  }
  const cells = new Map<number, UnitState[]>();
  for (const unit of world.units) {
    if (unit.hp <= 0 || unit.air) {
      continue;
    }
    const key = cellKey(Math.floor(unit.x / CELL), Math.floor(unit.z / CELL));
    const bucket = cells.get(key);
    if (bucket) {
      bucket.push(unit);
    } else {
      cells.set(key, [unit]);
    }
  }
  cached = { world, tick: world.tick, cells };
  return cached;
}

/** Ground units near (x, z), in world.units order. */
export function nearbyUnits(world: WorldState, x: number, z: number, range: number): UnitState[] {
  const { cells } = grid(world);
  const found: UnitState[] = [];
  const x0 = Math.floor((x - range) / CELL);
  const x1 = Math.floor((x + range) / CELL);
  const z0 = Math.floor((z - range) / CELL);
  const z1 = Math.floor((z + range) / CELL);
  for (let cx = x0; cx <= x1; cx += 1) {
    for (let cz = z0; cz <= z1; cz += 1) {
      const bucket = cells.get(cellKey(cx, cz));
      if (bucket) {
        found.push(...bucket);
      }
    }
  }
  // Buckets are visited in grid order; sort back to world order so results never depend on it.
  return found.length > 1 ? found.sort((a, b) => a.id - b.id) : found;
}

/** Drops the cached grid (after units are added or removed outside the tick). */
export function resetAvoidanceGrid(): void {
  cached = null;
}

function canParkAt(world: WorldState, map: MapDef, x: number, z: number, r: number): boolean {
  const half = world.map.size / 2;
  if (x < -half + r || x > half - r || z < -half + r || z > half - r) {
    return false;
  }
  return !isBlockedAt(map, x, z);
}

function isParkedFriend(unit: UnitState, other: UnitState): boolean {
  return (
    other.owner === unit.owner &&
    other.order.kind === 'idle' &&
    other.job === null &&
    other.transform === null &&
    other.speed < 0.1
  );
}

export interface Steering {
  bearing: number;
  /** Top speed allowed this tick (Infinity when nothing is in the way). */
  speedCap: number;
}

/**
 * Adjusts the bearing a unit wants to drive on so it goes round other ground units, and may slow
 * it to follow one. Parked friends in the corridor are nudged aside.
 */
export function steer(
  world: WorldState,
  map: MapDef,
  unit: UnitState,
  type: SimUnitType,
  bearing: number,
  goalDistance: number,
): Steering {
  if (unit.air) {
    return { bearing, speedCap: Infinity };
  }
  const r = type.radius ?? UNIT_RADIUS;
  const look = Math.min(goalDistance + r, r + LOOK_BASE + Math.max(unit.speed, 2) * LOOK_SECONDS);
  const fx = Math.cos(bearing);
  const fz = Math.sin(bearing);
  let best: UnitState | null = null;
  let bestAlong = Infinity;
  let bestLateral = 0;
  let bestRadius = UNIT_RADIUS;
  for (const other of nearbyUnits(world, unit.x, unit.z, look + MAX_RADIUS)) {
    // Enemies are targets, not traffic: steering round them would pull attackers off their line.
    // Contact with them is still resolved by separateUnits.
    if (other === unit || other.hp <= 0 || other.air || other.owner !== unit.owner) {
      continue;
    }
    const ro = unitRadius(world, other);
    const dx = other.x - unit.x;
    const dz = other.z - unit.z;
    const along = dx * fx + dz * fz;
    // Keep tracking a unit until we are past it, so we do not swing back into it while alongside.
    if (along <= -ro * 0.5 || along > look + ro) {
      continue;
    }
    const lateral = -dx * fz + dz * fx; // > 0: the other unit is on our left
    if (Math.abs(lateral) >= r + ro + CLEAR_MARGIN) {
      continue;
    }
    // A friend driving the same way beside us is formation, not an obstacle.
    if (along < r + ro && other.speed > 0.3 && Math.cos(other.heading - bearing) > 0.6) {
      continue;
    }
    if (along < bestAlong) {
      best = other;
      bestAlong = along;
      bestLateral = lateral;
      bestRadius = ro;
    }
  }
  if (!best) {
    return { bearing, speedCap: Infinity };
  }

  const clearance = r + bestRadius + CLEAR_MARGIN;
  const gap = bestAlong - r - bestRadius;
  const facing = Math.cos(best.heading - bearing);
  const moving = best.speed > 0.3;

  // Same way, ahead of us: queue behind it instead of shunting it.
  if (moving && facing > 0.6 && Math.abs(bestLateral) < (r + bestRadius) * 0.8) {
    // Close the gap gently; never crawl so slowly that the stuck check gives up on the order.
    const cap = Math.max(1.5, best.speed + Math.max(0, gap - 0.3) * 3);
    return { bearing, speedCap: cap };
  }

  if (isParkedFriend(unit, best)) {
    // Shuffle the parked unit off our line, to whichever side it already leans.
    const away = bestLateral >= 0 ? 1 : -1;
    const step = YIELD_SPEED * TICK;
    const nx = best.x + -fz * away * step;
    const nz = best.z + fx * away * step;
    if (canParkAt(world, map, nx, nz, bestRadius)) {
      best.x = nx;
      best.z = nz;
    }
  }

  // Head-on and roughly in line: both keep right. Otherwise pass on the side away from the obstacle.
  let side: number;
  if (moving && facing < -0.3 && Math.abs(bestLateral) < clearance * 0.5) {
    side = -1;
  } else if (Math.abs(bestLateral) > 0.05) {
    side = bestLateral > 0 ? -1 : 1;
  } else {
    side = unit.id < best.id ? 1 : -1;
  }
  // Aim for a full clearance of sideways offset by the time we draw level with it. Left is +lateral.
  const offsetNow = -side * bestLateral; // how far it already sits on the side we pass it on
  const need = Math.max(0, clearance - offsetNow);
  let turn = side * Math.min(1.2, Math.atan2(need, Math.max(bestAlong, r)));
  // Do not steer into terrain: if that side is blocked a few metres out, try the other side.
  const probe = r + 2;
  const tx = unit.x + Math.cos(bearing + turn) * probe;
  const tz = unit.z + Math.sin(bearing + turn) * probe;
  if (isBlockedAt(map, tx, tz)) {
    turn = -turn;
  }
  const speedCap = gap < 0.3 ? Math.max(1.5, type.topSpeed * 0.5) : Infinity;
  return { bearing: bearing + turn, speedCap };
}

/**
 * True when the goal is already taken by one of our own units that is not moving, and we are as
 * close as we can get. Stops a crowd fighting for one spot.
 */
export function goalTaken(world: WorldState, unit: UnitState, goalX: number, goalZ: number, goalDistance: number): boolean {
  const r = unitRadius(world, unit);
  if (unit.air || goalDistance > r * 3) {
    return false;
  }
  for (const other of nearbyUnits(world, goalX, goalZ, r + MAX_RADIUS)) {
    // Only our own side's parked units count: an enemy on the spot is something to fight, not a reason to stop.
    if (other === unit || other.hp <= 0 || other.owner !== unit.owner || other.speed > 0.3) {
      continue;
    }
    const ro = unitRadius(world, other);
    if (Math.hypot(other.x - goalX, other.z - goalZ) < r + ro - 0.2) {
      return true;
    }
  }
  return false;
}

/** Pushes overlapping ground units apart, each by its own size. */
export function separateUnits(world: WorldState, canStand: (x: number, z: number) => boolean): void {
  resetAvoidanceGrid();
  for (let iteration = 0; iteration < 8; iteration += 1) {
    let moved = false;
    for (const a of world.units) {
      if (a.hp <= 0 || a.air) {
        continue;
      }
      const ra = unitRadius(world, a);
      for (const b of nearbyUnits(world, a.x, a.z, ra + MAX_RADIUS)) {
        if (b.id <= a.id || b.hp <= 0 || b.air) {
          continue;
        }
        const minimum = ra + unitRadius(world, b);
        let dx = b.x - a.x;
        let dz = b.z - a.z;
        let distance = Math.hypot(dx, dz);
        if (distance >= minimum - 0.001) {
          continue;
        }
        if (distance < 0.0001) {
          const angle = (((a.id * 13 + b.id * 7) % 360) * Math.PI) / 180;
          dx = Math.cos(angle);
          dz = Math.sin(angle);
          distance = 1;
        }
        const push = (minimum - distance) / 2;
        const ux = dx / distance;
        const uz = dz / distance;
        const aCan = canStand(a.x - ux * push, a.z - uz * push);
        const bCan = canStand(b.x + ux * push, b.z + uz * push);
        if (aCan && bCan) {
          a.x -= ux * push;
          a.z -= uz * push;
          b.x += ux * push;
          b.z += uz * push;
          moved = true;
        } else if (aCan) {
          a.x -= ux * push * 2;
          a.z -= uz * push * 2;
          moved = true;
        } else if (bCan) {
          b.x += ux * push * 2;
          b.z += uz * push * 2;
          moved = true;
        }
      }
    }
    resetAvoidanceGrid();
    if (!moved) {
      break;
    }
  }
}
