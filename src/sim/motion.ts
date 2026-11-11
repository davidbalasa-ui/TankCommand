import {
  clampToMap,
  groundLineClear,
  isBlockedAt,
  mapFor,
  type MapDef,
} from './map';
import { goalTaken, steer } from './avoidance';
import { findPath } from './pathfinding';
import {
  STOP_DISTANCE,
  UNIT_RADIUS,
  WAYPOINT_REACHED,
} from './tuning';
import type { Point, SimUnitType, UnitState, WorldState } from './types';

const DEG_TO_RAD = Math.PI / 180;
const TURN_SPEED_FLOOR = 0.25;

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

export function unitMap(world: WorldState, unit: UnitState): MapDef {
  return mapFor(world.map, world.unitTypes.get(unit.typeId)?.movement ?? 'tracked');
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

export function computePath(
  world: WorldState,
  unit: UnitState,
  goalX: number,
  goalZ: number,
): Point[] | null {
  const path = findPath(unitMap(world, unit), unit.x, unit.z, goalX, goalZ);
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
  const map = mapFor(world.map, type.movement);
  const goalDistance = Math.hypot(goal.x - unit.x, goal.z - unit.z);
  if (
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

  let visible = -1;
  for (let index = unit.path.length - 1; index >= 0; index -= 1) {
    const point = unit.path[index];
    if (point && groundLineClear(map, unit.x, unit.z, point.x, point.z)) {
      visible = index;
      break;
    }
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

  const steering = steer(world, map, unit, type, Math.atan2(aim.z - unit.z, aim.x - unit.x), goalDistance);
  const bearing = steering.bearing;
  unit.heading = rotateTowards(unit.heading, bearing, type.turnDegPerSec * DEG_TO_RAD / 20);
  const error = Math.abs(angleDiff(bearing, unit.heading));

  const turnSpeed = type.topSpeed * Math.max(TURN_SPEED_FLOOR, 1 - error / Math.PI);
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
