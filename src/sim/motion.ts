import {
  clampToMap,
  groundLineClear,
  isBlockedAt,
  mapFor,
  type MapDef,
} from './map';
import { goalTaken, nearbyUnits, steer, unitRadius } from './avoidance';
import { cellKeyAt, findPath } from './pathfinding';
import { avoidsDeposits, insideObstacle, obstacleMap } from './obstacles';
import {
  STOP_DISTANCE,
  UNIT_RADIUS,
  WAYPOINT_REACHED,
} from './tuning';
import type { Point, SimUnitType, UnitState, WorldState } from './types';

const DEG_TO_RAD = Math.PI / 180;
const TURN_SPEED_FLOOR = 0.25;
/** Past this heading error a tracked vehicle stops and turns in place before driving on. */
const TRACKED_PIVOT_ANGLE = (75 * Math.PI) / 180;

export function angleDiff(a: number, b: number): number {
  let diff = a - b;
  while (diff > Math.PI) {
    diff -= Math.PI * 2;
  }
  while (diff < -Math.PI) {
    diff += Math.PI * 2;
  }
  return diff;
}

export function rotateTowards(current: number, target: number, maxStep: number): number {
  const diff = angleDiff(target, current);
  if (Math.abs(diff) <= maxStep) {
    return target;
  }
  return current + Math.sign(diff) * maxStep;
}

export function approach(current: number, target: number, step: number): number {
  if (current < target) {
    return Math.min(target, current + step);
  }
  return Math.max(target, current - step);
}

/** The ground as this unit sees it: terrain for its movement class plus solid buildings/sites. */
export function unitMap(world: WorldState, unit: UnitState): MapDef {
  const movement = world.unitTypes.get(unit.typeId)?.movement ?? 'tracked';
  return obstacleMap(world, movement, avoidsDeposits(world, unit));
}

export function canStand(world: WorldState, x: number, z: number): boolean {
  const half = world.map.size / 2;
  if (x < -half + UNIT_RADIUS || x > half - UNIT_RADIUS) {
    return false;
  }
  if (z < -half + UNIT_RADIUS || z > half - UNIT_RADIUS) {
    return false;
  }
  return !isBlockedAt(world.map, x, z);
}

/** A ground unit that is staying put: other units plan their routes round it. */
export function isParked(unit: UnitState): boolean {
  // A unit that has been stuck for half a second counts too: it is in the way, not passing through.
  // Units holding still to fight are left out: they move on again as soon as the fight shifts.
  if (unit.hp <= 0 || unit.air || unit.speed >= 0.3) {
    return false;
  }
  return unit.stuckTicks >= 10 || (unit.path.length === 0 && unit.order.kind === 'idle');
}

/** Room left round a parked unit's hull when routing past it. */
const PARKED_MARGIN = 0.6;
/** Parked units this close to the start or the goal are ignored (the unit is leaving, or arriving there). */
const PARKED_IGNORE_NEAR_GOAL = 4;

/**
 * Path-grid cells that other parked ground units sit in, for routing round them. Only units near
 * the straight line from start to goal count, which keeps the set (and the cost) small.
 */
export function parkedCells(world: WorldState, map: MapDef, unit: UnitState, goalX: number, goalZ: number): Set<number> {
  const cells = new Set<number>();
  if (unit.air || unit.job) {
    return cells;
  }
  const r = unitRadius(world, unit);
  const midX = (unit.x + goalX) / 2;
  const midZ = (unit.z + goalZ) / 2;
  const reach = Math.hypot(goalX - unit.x, goalZ - unit.z) / 2 + 20;
  for (const other of nearbyUnits(world, midX, midZ, reach)) {
    if (other === unit || !isParked(other)) {
      continue;
    }
    if (
      Math.hypot(other.x - goalX, other.z - goalZ) < PARKED_IGNORE_NEAR_GOAL ||
      Math.hypot(other.x - unit.x, other.z - unit.z) < r + unitRadius(world, other) + 0.5
    ) {
      continue;
    }
    const extent = r + unitRadius(world, other) + PARKED_MARGIN;
    const step = map.cellSize;
    for (let dx = -extent; dx <= extent + 1e-6; dx += step / 2) {
      for (let dz = -extent; dz <= extent + 1e-6; dz += step / 2) {
        if (dx * dx + dz * dz <= extent * extent) {
          cells.add(cellKeyAt(map, other.x + dx, other.z + dz));
        }
      }
    }
  }
  // Never penalise the cells the unit starts in or is heading for.
  cells.delete(cellKeyAt(map, unit.x, unit.z));
  cells.delete(cellKeyAt(map, goalX, goalZ));
  return cells;
}

/** True when driving straight from a to b would pass through a parked ground unit (other than self). */
export function segmentHitsParked(world: WorldState, unit: UnitState, ax: number, az: number, bx: number, bz: number): boolean {
  const r = unitRadius(world, unit);
  const dx = bx - ax;
  const dz = bz - az;
  const length2 = dx * dx + dz * dz;
  if (length2 < 1e-6) {
    return false;
  }
  const midX = (ax + bx) / 2;
  const midZ = (az + bz) / 2;
  for (const other of nearbyUnits(world, midX, midZ, Math.sqrt(length2) / 2 + 4)) {
    if (other === unit || other.owner !== unit.owner || !isParked(other)) {
      continue;
    }
    const t = Math.max(0, Math.min(1, ((other.x - ax) * dx + (other.z - az) * dz) / length2));
    const px = ax + dx * t;
    const pz = az + dz * t;
    const clear = r + unitRadius(world, other);
    if (Math.hypot(other.x - px, other.z - pz) < clear && Math.hypot(other.x - bx, other.z - bz) > clear) {
      return true;
    }
  }
  return false;
}

export function computePath(
  world: WorldState,
  unit: UnitState,
  goalX: number,
  goalZ: number,
): Point[] | null {
  const map = unitMap(world, unit);
  const path = findPath(map, unit.x, unit.z, goalX, goalZ, parkedCells(world, map, unit, goalX, goalZ));
  if (!path || path.length === 0) {
    return null;
  }
  return path;
}

export function followPath(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  goal: Point,
): void {
  let map = unitMap(world, unit);
  // Already inside a building or site (it was built or landed round the unit): drive out on
  // terrain rules only, so the unit is never frozen in place.
  if (insideObstacle(map, unit.x, unit.z)) {
    map = mapFor(world.map, type.movement);
  }
  const goalDistance = Math.hypot(goal.x - unit.x, goal.z - unit.z);
  // A goal inside a building or site can't be reached; the planned path stops beside it, and
  // reaching the end of that path counts as arriving.
  const pathEnd = unit.path[unit.path.length - 1];
  const besideBlockedGoal =
    unit.path.length <= 1 &&
    isBlockedAt(map, goal.x, goal.z) &&
    (!pathEnd || Math.hypot(pathEnd.x - unit.x, pathEnd.z - unit.z) <= WAYPOINT_REACHED);
  const moveOrder = unit.order.kind === 'move' || unit.order.kind === 'attackMove';
  if (besideBlockedGoal && !moveOrder) {
    // Attacking or working next to a building: hold here and keep the path, so the caller
    // doesn't re-plan every tick; it decides when it is in range.
    unit.speed = 0;
    return;
  }
  if (
    besideBlockedGoal ||
    goalDistance <= STOP_DISTANCE ||
    ((unit.order.kind === 'move' || unit.order.kind === 'attackMove') && goalTaken(world, unit, goal.x, goal.z, goalDistance))
  ) {
    unit.path = [];
    unit.speed = 0;
    if (unit.order.kind === 'move' || unit.order.kind === 'attackMove') {
      unit.order = { kind: 'idle' };
    }
    return;
  }

  while (unit.path.length > 1) {
    const first = unit.path[0];
    if (!first) {
      break;
    }
    if (Math.hypot(first.x - unit.x, first.z - unit.z) > WAYPOINT_REACHED) {
      break;
    }
    unit.path.shift();
  }

  // Aim for the furthest waypoint in clear line of sight, preferring one whose straight line does
  // not run through a parked friend. Waypoints before it are behind us now and are dropped, so a
  // unit never turns back to a point it has already passed.
  // Workers queue at pads and sites by their own rules; only units on a plain move weave round parked ones.
  // Units on the attack take the direct line and leave contact to local steering.
  const avoidParked = unit.job === null && unit.order.kind === 'move' && goalDistance > PARKED_IGNORE_NEAR_GOAL;
  let visible = -1;
  for (let index = unit.path.length - 1; index >= 0; index -= 1) {
    const point = unit.path[index];
    if (!point || !groundLineClear(map, unit.x, unit.z, point.x, point.z)) {
      continue;
    }
    if (index === 0 || !avoidParked || !segmentHitsParked(world, unit, unit.x, unit.z, point.x, point.z)) {
      visible = index;
      break;
    }
  }
  if (visible < 0 && unit.path.length > 0) {
    // No waypoint is in sight any more (the unit was pushed or slid off its line): plan again
    // from here rather than driving into whatever is in the way.
    const path = computePath(world, unit, goal.x, goal.z);
    if (path) {
      unit.path = path;
      const end = path[path.length - 1]!;
      if (unit.pathGoal) {
        unit.pathGoal = { x: unit.pathGoal.x, z: unit.pathGoal.z, endX: end.x, endZ: end.z };
      }
      const first = path[0]!;
      visible = groundLineClear(map, unit.x, unit.z, first.x, first.z) ? 0 : -1;
    }
  }
  // A queued order's path holds the player's waypoints, so it is kept whole.
  const queued = (unit.order.kind === 'move' || unit.order.kind === 'attackMove') && unit.order.queue;
  if (visible > 0 && !queued) {
    unit.path.splice(0, visible);
    visible = 0;
  }

  const aim = (visible >= 0 ? unit.path[visible] : unit.path[0]) ?? goal;

  let remaining = Math.hypot(aim.x - unit.x, aim.z - unit.z);
  let previous: Point = aim;
  for (let index = visible + 1; index < unit.path.length; index += 1) {
    const point = unit.path[index];
    if (!point) {
      continue;
    }
    remaining += Math.hypot(point.x - previous.x, point.z - previous.z);
    previous = point;
  }
  remaining += Math.hypot(goal.x - previous.x, goal.z - previous.z);

  const aimBearing = Math.atan2(aim.z - unit.z, aim.x - unit.x);
  const steering = steer(world, map, unit, type, aimBearing, goalDistance);
  const bearing = steering.bearing;
  unit.heading = rotateTowards(unit.heading, bearing, type.turnDegPerSec * DEG_TO_RAD / 20);
  const error = Math.abs(angleDiff(bearing, unit.heading));

  // Tracked vehicles pivot on the spot when the route turns sharply (judged against the route,
  // not avoidance swerves) and roll forward once roughly facing it; hover craft slide round.
  const turnFactor =
    type.movement === 'tracked' && Math.abs(angleDiff(aimBearing, unit.heading)) > TRACKED_PIVOT_ANGLE
      ? 0
      : Math.max(TURN_SPEED_FLOOR, 1 - error / Math.PI);
  const turnSpeed = type.topSpeed * turnFactor;
  const braking = Math.sqrt(2 * type.accel * Math.max(0, remaining - STOP_DISTANCE));
  const targetSpeed = Math.min(turnSpeed, braking, steering.speedCap);
  unit.speed = approach(unit.speed, targetSpeed, type.accel / 20);

  const step = unit.speed / 20;
  if (step <= 0) {
    return;
  }

  const stepX = Math.cos(unit.heading) * step;
  const stepZ = Math.sin(unit.heading) * step;
  let nextX = unit.x + stepX;
  let nextZ = unit.z + stepZ;
  if (isBlockedAt(map, nextX, nextZ)) {
    if (!isBlockedAt(map, unit.x + stepX, unit.z)) {
      nextX = unit.x + stepX;
      nextZ = unit.z;
    } else if (!isBlockedAt(map, unit.x, unit.z + stepZ)) {
      nextX = unit.x;
      nextZ = unit.z + stepZ;
    } else {
      unit.speed = 0;
      return;
    }
  }
  const clamped = clampToMap(map, nextX, nextZ, UNIT_RADIUS);
  if (isBlockedAt(map, clamped.x, clamped.z)) {
    unit.speed = 0;
    return;
  }
  unit.x = clamped.x;
  unit.z = clamped.z;
}
