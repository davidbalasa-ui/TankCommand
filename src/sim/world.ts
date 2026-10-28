import { Rng } from './rng';
import type { Command } from './commands';
import { SIM_TICK_HZ } from './constants';
import {
  clampToMap,
  generateMap,
  groundLineClear,
  heightAt,
  isBlockedAt,
  lineOfSightClear,
} from './map';
import { findPath } from './pathfinding';
import {
  ATTACK_REPATH_TICKS,
  FIRE_MOVE_SPEED_MAX,
  FORMATION_SPACING,
  MAX_AIM_ERROR,
  MAX_REPLANS,
  MOVE_EPS,
  MUZZLE_HEIGHT,
  PROJECTILE_TTL,
  STOP_DISTANCE,
  STUCK_TICKS,
  TARGET_HEIGHT,
  TURRET_ALIGN_TOLERANCE_DEG,
  UNIT_RADIUS,
  WAYPOINT_REACHED,
  WRECK_TTL_SEC,
} from './tuning';
import type {
  Order,
  PlayerId,
  Point,
  ProjectileState,
  SimUnitType,
  StartUnit,
  UnitState,
  WeaponStats,
  WorldResult,
  WorldState,
  WreckState,
} from './types';

const DT = 1 / SIM_TICK_HZ;
const DEG_TO_RAD = Math.PI / 180;
const TURN_SPEED_FLOOR = 0.25;

export interface CreateWorldOptions {
  unitTypes?: ReadonlyMap<string, SimUnitType>;
  startUnits?: StartUnit[];
  size?: number;
  cellSize?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function angleDiff(a: number, b: number): number {
  let diff = a - b;
  while (diff > Math.PI) {
    diff -= Math.PI * 2;
  }
  while (diff < -Math.PI) {
    diff += Math.PI * 2;
  }
  return diff;
}

function rotateTowards(current: number, target: number, maxStep: number): number {
  const diff = angleDiff(target, current);
  if (Math.abs(diff) <= maxStep) {
    return target;
  }
  return current + Math.sign(diff) * maxStep;
}

function approach(current: number, target: number, step: number): number {
  if (current < target) {
    return Math.min(target, current + step);
  }
  return Math.max(target, current - step);
}

function cloneOrder(order: Order): Order {
  if (order.kind === 'move') {
    return { ...order };
  }
  if (order.kind === 'attack') {
    return { ...order };
  }
  return { kind: 'idle' };
}

function cloneWorld(world: WorldState): WorldState {
  return {
    ...world,
    players: [...world.players],
    units: world.units.map((unit) => ({
      ...unit,
      order: cloneOrder(unit.order),
      path: unit.path.map((point) => ({ ...point })),
    })),
    projectiles: world.projectiles.map((projectile) => ({ ...projectile })),
    wrecks: world.wrecks.map((wreck) => ({ ...wreck })),
    result: world.result ? { winner: world.result.winner } : null,
  };
}

export function formationOffsets(count: number): Point[] {
  const points: Point[] = [];
  if (count <= 0) {
    return points;
  }
  points.push({ x: 0, z: 0 });
  let index = 1;
  while (points.length < count) {
    const angle = index * 2.399963229728653;
    const radius = FORMATION_SPACING * Math.sqrt(index);
    points.push({ x: Math.cos(angle) * radius, z: Math.sin(angle) * radius });
    index += 1;
  }
  return points;
}

export function defaultStartUnits(): StartUnit[] {
  const playerOne = formationOffsets(4).map((offset) => ({
    owner: 1,
    typeId: 'unit.human.light_tank',
    x: -50 + offset.x,
    z: -50 + offset.z,
    heading: Math.PI / 4,
  }));
  const playerTwoHeading = Math.atan2(-100, -100);
  const playerTwo = formationOffsets(4).map((offset) => ({
    owner: 2,
    typeId: 'unit.human.light_tank',
    x: 50 + offset.x,
    z: 50 + offset.z,
    heading: playerTwoHeading,
  }));
  return [...playerOne, ...playerTwo];
}

function addUnit(world: WorldState, start: StartUnit): void {
  const type = world.unitTypes.get(start.typeId);
  if (!type) {
    return;
  }
  const position = clampToMap(world.map, start.x, start.z, UNIT_RADIUS);
  const id = world.nextId;
  world.nextId += 1;
  const heading = start.heading ?? 0;
  const turretHeading = start.turretHeading ?? heading;
  world.units.push({
    id,
    owner: start.owner,
    typeId: start.typeId,
    x: position.x,
    z: position.z,
    heading,
    turretHeading,
    hp: type.hp,
    order: { kind: 'idle' },
    path: [],
    reloadLeft: 0,
    stuckTicks: 0,
    speed: 0,
    replans: 0,
    attackRepathTick: 0,
  });
}

export function createWorld(seed: number, options: CreateWorldOptions = {}): WorldState {
  const unitTypes = options.unitTypes ?? new Map<string, SimUnitType>();
  const map = generateMap(seed, options.size, options.cellSize);
  const rng = new Rng(seed);
  const world: WorldState = {
    tick: 0,
    seed,
    rngState: rng.getState(),
    counter: 0,
    nextId: 1,
    players: [],
    map,
    unitTypes,
    units: [],
    projectiles: [],
    wrecks: [],
    result: null,
  };

  const starts = options.startUnits ?? (unitTypes.size > 0 ? defaultStartUnits() : []);
  for (const start of starts) {
    addUnit(world, start);
  }
  world.players = [...new Set(world.units.map((unit) => unit.owner))].sort((a, b) => a - b);
  return world;
}

function ownedUnits(world: WorldState, issuer: PlayerId, ids: readonly number[]): UnitState[] {
  const set = new Set(ids);
  return world.units.filter(
    (unit) => set.has(unit.id) && unit.owner === issuer && unit.hp > 0,
  );
}

function computePath(
  world: WorldState,
  unit: UnitState,
  goalX: number,
  goalZ: number,
): Point[] | null {
  const path = findPath(world.map, unit.x, unit.z, goalX, goalZ);
  if (!path || path.length === 0) {
    return null;
  }
  return path;
}

function adoptPath(unit: UnitState, path: Point[], queue: boolean): void {
  unit.path = path;
  const final = path[path.length - 1];
  if (!final) {
    unit.order = { kind: 'idle' };
    unit.speed = 0;
    return;
  }
  unit.order = { kind: 'move', x: final.x, z: final.z, queue };
}

function planMove(
  world: WorldState,
  unit: UnitState,
  goalX: number,
  goalZ: number,
  queue: boolean,
): void {
  if (queue && unit.order.kind === 'move' && unit.path.length > 0) {
    const last = unit.path[unit.path.length - 1];
    if (last) {
      const appended = findPath(world.map, last.x, last.z, goalX, goalZ);
      if (appended && appended.length > 0) {
        const combined = [...unit.path, ...appended];
        const final = combined[combined.length - 1];
        if (final) {
          unit.path = combined;
          unit.order = { kind: 'move', x: final.x, z: final.z, queue: true };
          unit.replans = 0;
          unit.stuckTicks = 0;
          return;
        }
      }
    }
  }

  const path = computePath(world, unit, goalX, goalZ);
  if (!path) {
    unit.path = [];
    unit.order = { kind: 'idle' };
    unit.speed = 0;
    unit.stuckTicks = 0;
    unit.replans = 0;
    return;
  }
  adoptPath(unit, path, false);
  unit.replans = 0;
  unit.stuckTicks = 0;
}

function applyMoveCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'move' }>,
): void {
  const units = ownedUnits(world, command.issuer, command.unitIds);
  if (units.length === 0) {
    return;
  }
  const clamped = clampToMap(world.map, command.x, command.z, UNIT_RADIUS);
  const offsets = formationOffsets(units.length);
  for (let i = 0; i < units.length; i += 1) {
    const unit = units[i];
    const offset = offsets[i];
    if (!unit || !offset) {
      continue;
    }
    const goal = clampToMap(
      world.map,
      clamped.x + offset.x,
      clamped.z + offset.z,
      UNIT_RADIUS,
    );
    planMove(world, unit, goal.x, goal.z, command.queue ?? false);
  }
}

function applyAttackCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'attack' }>,
): void {
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    unit.order = { kind: 'attack', targetId: command.targetId };
    unit.path = [];
    unit.speed = 0;
    unit.replans = 0;
    unit.stuckTicks = 0;
    unit.attackRepathTick = 0;
  }
}

function applyStopCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'stop' }>,
): void {
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    unit.order = { kind: 'idle' };
    unit.path = [];
    unit.speed = 0;
    unit.replans = 0;
    unit.stuckTicks = 0;
  }
}

function canStand(world: WorldState, x: number, z: number): boolean {
  const half = world.map.size / 2;
  if (x < -half + UNIT_RADIUS || x > half - UNIT_RADIUS) {
    return false;
  }
  if (z < -half + UNIT_RADIUS || z > half - UNIT_RADIUS) {
    return false;
  }
  return !isBlockedAt(world.map, x, z);
}

function unitLineOfSight(world: WorldState, a: UnitState, b: UnitState): boolean {
  return lineOfSightClear(
    world.map,
    a.x,
    a.z,
    heightAt(world.map, a.x, a.z) + MUZZLE_HEIGHT,
    b.x,
    b.z,
    heightAt(world.map, b.x, b.z) + TARGET_HEIGHT,
  );
}

function nearestEnemy(world: WorldState, unit: UnitState): UnitState | null {
  let best: UnitState | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const other of world.units) {
    if (other.hp <= 0 || other.owner === unit.owner) {
      continue;
    }
    const distance = Math.hypot(other.x - unit.x, other.z - unit.z);
    if (distance < bestDistance) {
      best = other;
      bestDistance = distance;
    }
  }
  return best;
}

function selectTarget(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
): UnitState | null {
  if (unit.order.kind === 'attack') {
    const targetId = unit.order.targetId;
    const explicit = world.units.find(
      (other) => other.id === targetId && other.hp > 0 && other.owner !== unit.owner,
    );
    if (explicit) {
      return explicit;
    }
    // The ordered target is gone. Keep the order alive against the nearest
    // survivor instead of dropping to idle: an idle unit only auto-engages
    // inside its weapon range, so a squad that had stopped at the edge of range
    // would sit outside every survivor and the skirmish could never resolve.
    return nearestEnemy(world, unit);
  }

  const range = type.weapon?.range ?? type.sightRange;
  let best: UnitState | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const other of world.units) {
    if (other.hp <= 0 || other.owner === unit.owner) {
      continue;
    }
    const distance = Math.hypot(other.x - unit.x, other.z - unit.z);
    if (distance <= range && distance < bestDistance) {
      best = other;
      bestDistance = distance;
    }
  }
  return best;
}

/**
 * True when an attack order is standing still on purpose: the selected target is
 * inside weapon range with clear line of sight, so `updateOrderPath` deliberately
 * clears the path and brakes to a halt to shoot.
 *
 * The stuck rule must ignore these units. Otherwise a perfectly placed firing
 * tank counts "moved less than MOVE_EPS" every tick, burns through MAX_REPLANS,
 * and has its attack order cancelled to idle — after which it only auto-engages
 * inside weapon range and will never close on the survivors, so the skirmish
 * can never reach a result.
 */
function isHoldingFirePosition(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
): boolean {
  if (unit.order.kind !== 'attack') {
    return false;
  }
  const weapon = type.weapon;
  if (!weapon) {
    return false;
  }
  const target = selectTarget(world, unit, type);
  if (!target) {
    return false;
  }
  const distance = Math.hypot(target.x - unit.x, target.z - unit.z);
  return distance <= weapon.range && unitLineOfSight(world, unit, target);
}

function followPath(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  goal: Point,
): void {
  const map = world.map;
  const goalDistance = Math.hypot(goal.x - unit.x, goal.z - unit.z);
  if (goalDistance <= STOP_DISTANCE) {
    unit.path = [];
    unit.speed = 0;
    if (unit.order.kind === 'move') {
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

  const steer = (visible >= 0 ? unit.path[visible] : unit.path[0]) ?? goal;

  let remaining = Math.hypot(steer.x - unit.x, steer.z - unit.z);
  let previous: Point = steer;
  for (let index = visible + 1; index < unit.path.length; index += 1) {
    const point = unit.path[index];
    if (!point) {
      continue;
    }
    remaining += Math.hypot(point.x - previous.x, point.z - previous.z);
    previous = point;
  }
  remaining += Math.hypot(goal.x - previous.x, goal.z - previous.z);

  const bearing = Math.atan2(steer.z - unit.z, steer.x - unit.x);
  unit.heading = rotateTowards(unit.heading, bearing, type.turnDegPerSec * DEG_TO_RAD * DT);
  const error = Math.abs(angleDiff(bearing, unit.heading));

  const turnSpeed = type.topSpeed * Math.max(TURN_SPEED_FLOOR, 1 - error / Math.PI);
  const braking = Math.sqrt(2 * type.accel * Math.max(0, remaining - STOP_DISTANCE));
  const targetSpeed = Math.min(turnSpeed, braking);
  unit.speed = approach(unit.speed, targetSpeed, type.accel * DT);

  const step = unit.speed * DT;
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

function fireProjectile(
  world: WorldState,
  shooter: UnitState,
  target: UnitState,
  weapon: WeaponStats,
  rng: Rng,
): void {
  const startY = heightAt(world.map, shooter.x, shooter.z) + MUZZLE_HEIGHT;
  const targetY = heightAt(world.map, target.x, target.z) + TARGET_HEIGHT;
  const dx = target.x - shooter.x;
  const dz = target.z - shooter.z;
  const distance = Math.hypot(dx, dz);
  if (distance < 0.001) {
    return;
  }
  const baseAngle = Math.atan2(dz, dx);
  const error = (1 - weapon.accuracy) * MAX_AIM_ERROR * (rng.next() * 2 - 1);
  const angle = baseAngle + error;
  const travelTime = distance / weapon.projectileSpeed;

  world.projectiles.push({
    id: world.nextId,
    owner: shooter.owner,
    x: shooter.x,
    y: startY,
    z: shooter.z,
    vx: Math.cos(angle) * weapon.projectileSpeed,
    vy: (targetY - startY) / travelTime,
    vz: Math.sin(angle) * weapon.projectileSpeed,
    damage: weapon.damage,
    ttl: PROJECTILE_TTL,
    splashRadius: weapon.splashRadius,
  });
  world.nextId += 1;
}

function closestPointT(
  ax: number,
  ay: number,
  az: number,
  bx: number,
  by: number,
  bz: number,
  px: number,
  py: number,
  pz: number,
): number {
  const dx = bx - ax;
  const dy = by - ay;
  const dz = bz - az;
  const lengthSq = dx * dx + dy * dy + dz * dz;
  if (lengthSq <= 0.000001) {
    return 0;
  }
  const t = ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / lengthSq;
  return Math.min(1, Math.max(0, t));
}

function applySplash(
  world: WorldState,
  x: number,
  y: number,
  z: number,
  projectile: ProjectileState,
  directUnitId?: number,
): void {
  const radius = Math.max(0.001, projectile.splashRadius);
  for (const unit of world.units) {
    if (unit.hp <= 0) {
      continue;
    }
    const unitY = heightAt(world.map, unit.x, unit.z) + TARGET_HEIGHT;
    const distance = Math.hypot(unit.x - x, unitY - y, unit.z - z);
    if (unit.id === directUnitId || distance <= radius + UNIT_RADIUS) {
      const type = world.unitTypes.get(unit.typeId);
      const armor = type?.armor ?? 0;
      const damage = Math.max(1, projectile.damage - armor);
      unit.hp = Math.max(0, unit.hp - damage);
    }
  }
}

function updateProjectiles(world: WorldState): void {
  const remaining: ProjectileState[] = [];
  for (const projectile of world.projectiles) {
    projectile.ttl -= DT;
    if (projectile.ttl <= 0) {
      applySplash(world, projectile.x, projectile.y, projectile.z, projectile);
      continue;
    }

    const ox = projectile.x;
    const oy = projectile.y;
    const oz = projectile.z;
    const nx = projectile.x + projectile.vx * DT;
    const ny = projectile.y + projectile.vy * DT;
    const nz = projectile.z + projectile.vz * DT;

    let hitUnit: UnitState | null = null;
    let hitT = Number.POSITIVE_INFINITY;
    for (const unit of world.units) {
      if (unit.hp <= 0 || unit.owner === projectile.owner) {
        continue;
      }
      const unitY = heightAt(world.map, unit.x, unit.z) + TARGET_HEIGHT;
      const t = closestPointT(ox, oy, oz, nx, ny, nz, unit.x, unitY, unit.z);
      const px = ox + (nx - ox) * t;
      const py = oy + (ny - oy) * t;
      const pz = oz + (nz - oz) * t;
      const distance = Math.hypot(px - unit.x, py - unitY, pz - unit.z);
      if (distance <= UNIT_RADIUS && t < hitT) {
        hitT = t;
        hitUnit = unit;
      }
    }

    if (hitUnit) {
      const hx = ox + (nx - ox) * hitT;
      const hy = oy + (ny - oy) * hitT;
      const hz = oz + (nz - oz) * hitT;
      applySplash(world, hx, hy, hz, projectile, hitUnit.id);
      continue;
    }

    const half = world.map.size / 2;
    const outside = nx < -half || nx > half || nz < -half || nz > half;
    if (outside || ny <= heightAt(world.map, nx, nz)) {
      applySplash(world, nx, ny, nz, projectile);
      continue;
    }

    projectile.x = nx;
    projectile.y = ny;
    projectile.z = nz;
    remaining.push(projectile);
  }
  world.projectiles = remaining;
}

function separateUnits(world: WorldState): void {
  const minimum = UNIT_RADIUS * 2;
  for (let iteration = 0; iteration < 8; iteration += 1) {
    let moved = false;
    for (let i = 0; i < world.units.length; i += 1) {
      const a = world.units[i];
      if (!a || a.hp <= 0) {
        continue;
      }
      for (let j = i + 1; j < world.units.length; j += 1) {
        const b = world.units[j];
        if (!b || b.hp <= 0) {
          continue;
        }
        let dx = b.x - a.x;
        let dz = b.z - a.z;
        let distance = Math.hypot(dx, dz);
        if (distance >= minimum - 0.001) {
          continue;
        }
        if (distance < 0.0001) {
          const angle = ((a.id * 13 + b.id * 7) % 360) * DEG_TO_RAD;
          dx = Math.cos(angle);
          dz = Math.sin(angle);
          distance = 1;
        }
        const push = (minimum - distance) / 2;
        const ax = a.x - (dx / distance) * push;
        const az = a.z - (dz / distance) * push;
        const bx = b.x + (dx / distance) * push;
        const bz = b.z + (dz / distance) * push;
        const aCan = canStand(world, ax, az);
        const bCan = canStand(world, bx, bz);
        if (aCan && bCan) {
          a.x = ax;
          a.z = az;
          b.x = bx;
          b.z = bz;
          moved = true;
        } else if (aCan) {
          a.x = a.x - (dx / distance) * push * 2;
          a.z = a.z - (dz / distance) * push * 2;
          moved = true;
        } else if (bCan) {
          b.x = b.x + (dx / distance) * push * 2;
          b.z = b.z + (dz / distance) * push * 2;
          moved = true;
        }
      }
    }
    if (!moved) {
      break;
    }
  }
}

function updateOrderPath(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  target: UnitState | null,
): void {
  if (unit.order.kind === 'move') {
    if (Math.hypot(unit.order.x - unit.x, unit.order.z - unit.z) <= STOP_DISTANCE) {
      unit.order = { kind: 'idle' };
      unit.path = [];
      unit.speed = 0;
      return;
    }
    if (unit.path.length === 0) {
      const path = computePath(world, unit, unit.order.x, unit.order.z);
      if (!path) {
        unit.order = { kind: 'idle' };
        unit.speed = 0;
        return;
      }
      adoptPath(unit, path, false);
    }
    if (unit.order.kind === 'move') {
      followPath(world, unit, type, { x: unit.order.x, z: unit.order.z });
    }
    return;
  }

  if (unit.order.kind === 'attack') {
    if (!target) {
      unit.order = { kind: 'idle' };
      unit.path = [];
      unit.speed = 0;
      return;
    }
    const weapon = type.weapon;
    const distance = Math.hypot(target.x - unit.x, target.z - unit.z);
    const inRange = weapon ? distance <= weapon.range : false;
    const los = weapon ? unitLineOfSight(world, unit, target) : false;
    if (inRange && los) {
      unit.path = [];
      unit.speed = approach(unit.speed, 0, type.accel * DT);
      return;
    }
    if (unit.attackRepathTick <= 0 || unit.path.length === 0) {
      const path = computePath(world, unit, target.x, target.z);
      unit.path = path ?? [];
      unit.attackRepathTick = ATTACK_REPATH_TICKS;
    }
    unit.attackRepathTick -= 1;
    followPath(world, unit, type, { x: target.x, z: target.z });
    return;
  }

  unit.speed = approach(unit.speed, 0, type.accel * DT);
}

function updateStuckUnits(world: WorldState, startPositions: ReadonlyMap<number, Point>): void {
  for (const unit of world.units) {
    if (unit.hp <= 0) {
      continue;
    }
    const start = startPositions.get(unit.id);
    if (!start) {
      continue;
    }
    if (unit.order.kind !== 'move' && unit.order.kind !== 'attack') {
      unit.stuckTicks = 0;
      unit.replans = 0;
      continue;
    }

    const type = world.unitTypes.get(unit.typeId);
    if (type && isHoldingFirePosition(world, unit, type)) {
      // Deliberately stationary to shoot: no path is wanted, so this is not a
      // stuck unit and it must keep its order.
      unit.stuckTicks = 0;
      unit.replans = 0;
      continue;
    }

    const moved = Math.hypot(unit.x - start.x, unit.z - start.z);
    if (moved < MOVE_EPS) {
      unit.stuckTicks += 1;
    } else {
      unit.stuckTicks = 0;
    }
    if (unit.stuckTicks < STUCK_TICKS) {
      continue;
    }

    unit.stuckTicks = 0;
    unit.replans += 1;
    unit.speed = 0;
    if (unit.replans >= MAX_REPLANS) {
      unit.order = { kind: 'idle' };
      unit.path = [];
      continue;
    }

    if (unit.order.kind === 'move') {
      const path = findPath(world.map, unit.x, unit.z, unit.order.x, unit.order.z);
      unit.path = path ?? [];
      const end = path && path.length > 0 ? path[path.length - 1] : undefined;
      if (end) {
        unit.order = { kind: 'move', x: end.x, z: end.z, queue: false };
      }
      continue;
    }

    const liveTarget = type ? selectTarget(world, unit, type) : null;
    if (liveTarget) {
      unit.path = findPath(world.map, unit.x, unit.z, liveTarget.x, liveTarget.z) ?? [];
    } else {
      unit.order = { kind: 'idle' };
      unit.path = [];
    }
  }
}

function updateUnits(world: WorldState, rng: Rng): void {
  const startPositions = new Map<number, Point>();
  for (const unit of world.units) {
    startPositions.set(unit.id, { x: unit.x, z: unit.z });
  }

  for (const unit of world.units) {
    if (unit.hp <= 0) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
    if (!type) {
      unit.speed = 0;
      continue;
    }

    unit.reloadLeft = Math.max(0, unit.reloadLeft - DT);
    const target = selectTarget(world, unit, type);

    if (target) {
      const bearing = Math.atan2(target.z - unit.z, target.x - unit.x);
      unit.turretHeading = rotateTowards(
        unit.turretHeading,
        bearing,
        type.turretTurnDegPerSec * DEG_TO_RAD * DT,
      );
    }

    updateOrderPath(world, unit, type, target);

    if (target && type.weapon && unit.reloadLeft <= 0) {
      const weapon = type.weapon;
      const distance = Math.hypot(target.x - unit.x, target.z - unit.z);
      const bearing = Math.atan2(target.z - unit.z, target.x - unit.x);
      const aligned =
        Math.abs(angleDiff(unit.turretHeading, bearing)) <=
        TURRET_ALIGN_TOLERANCE_DEG * DEG_TO_RAD + 0.000001;
      const canFire =
        aligned &&
        distance <= weapon.range &&
        (type.fireOnMove || unit.speed <= FIRE_MOVE_SPEED_MAX) &&
        unitLineOfSight(world, unit, target);
      if (canFire) {
        fireProjectile(world, unit, target, weapon, rng);
        unit.reloadLeft = weapon.reloadSec;
      }
    }
  }

  separateUnits(world);
  updateStuckUnits(world, startPositions);
}

function cleanupDead(world: WorldState): void {
  const dead = world.units.filter((unit) => unit.hp <= 0);
  if (dead.length === 0) {
    return;
  }
  for (const unit of dead) {
    world.wrecks.push({ x: unit.x, z: unit.z, ttl: WRECK_TTL_SEC });
  }
  world.units = world.units.filter((unit) => unit.hp > 0);
}

function updateWrecks(world: WorldState): void {
  for (const wreck of world.wrecks) {
    wreck.ttl -= DT;
  }
  world.wrecks = world.wrecks.filter((wreck) => wreck.ttl > 0);
}

function updateResult(world: WorldState): void {
  if (world.result || world.players.length === 0) {
    return;
  }
  const aliveOwners = new Set(world.units.map((unit) => unit.owner));
  const alive = world.players.filter((player) => aliveOwners.has(player));
  if (alive.length === 0) {
    world.result = { winner: null };
  } else if (alive.length === 1) {
    world.result = { winner: alive[0] ?? null };
  }
}

export function step(world: WorldState, commands: readonly Command[]): WorldState {
  const next = cloneWorld(world);
  const nextTick = next.tick + 1;
  const rng = new Rng(next.seed);
  rng.setState(next.rngState);

  if (!world.result) {
    for (const command of commands) {
      if (command.tick !== nextTick) {
        continue;
      }
      if (command.kind === 'debug.addCounter') {
        next.counter += command.amount;
      } else if (command.kind === 'move') {
        applyMoveCommand(next, command);
      } else if (command.kind === 'attack') {
        applyAttackCommand(next, command);
      } else if (command.kind === 'stop') {
        applyStopCommand(next, command);
      }
    }
  }

  updateUnits(next, rng);
  updateProjectiles(next);
  cleanupDead(next);
  updateWrecks(next);
  updateResult(next);

  next.tick = nextTick;
  next.rngState = rng.getState();
  next.counter += rng.int(0, 3);
  return next;
}

export function snapshot(world: WorldState): Readonly<WorldState> {
  return Object.freeze({ ...world });
}

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(',')}]`;
  }
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record).sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}

export function fnv1aHex(input: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i) & 0xff;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}

export function hashWorld(world: WorldState): string {
  return fnv1aHex(
    canonicalJson({
      tick: world.tick,
      seed: world.seed,
      rngState: world.rngState,
      counter: world.counter,
      nextId: world.nextId,
      players: world.players,
      units: world.units.map((unit) => ({
        id: unit.id,
        owner: unit.owner,
        typeId: unit.typeId,
        x: unit.x,
        z: unit.z,
        heading: unit.heading,
        turretHeading: unit.turretHeading,
        hp: unit.hp,
        order: unit.order,
        path: unit.path,
        reloadLeft: unit.reloadLeft,
        stuckTicks: unit.stuckTicks,
        speed: unit.speed,
        replans: unit.replans,
        attackRepathTick: unit.attackRepathTick,
      })),
      projectiles: world.projectiles,
      wrecks: world.wrecks,
      result: world.result,
    }),
  );
}

export function worldToPayload(world: WorldState): unknown {
  const unitTypes = [...world.unitTypes.entries()]
    .map(([id, type]) => ({ id, type }))
    .sort((a, b) => a.id.localeCompare(b.id));
  return {
    tick: world.tick,
    seed: world.seed,
    rngState: world.rngState,
    counter: world.counter,
    nextId: world.nextId,
    players: [...world.players],
    units: world.units.map((unit) => ({
      ...unit,
      order: cloneOrder(unit.order),
      path: unit.path.map((point) => ({ ...point })),
    })),
    projectiles: world.projectiles.map((projectile) => ({ ...projectile })),
    wrecks: world.wrecks.map((wreck) => ({ ...wreck })),
    result: world.result ? { winner: world.result.winner } : null,
    unitTypes,
  };
}

export function payloadToWorld(input: unknown): WorldState | null {
  if (!isRecord(input)) {
    return null;
  }
  const tick = input.tick;
  const seed = input.seed;
  const rngState = input.rngState;
  const counter = input.counter;
  const nextId = input.nextId;
  if (
    typeof tick !== 'number' ||
    !Number.isInteger(tick) ||
    typeof seed !== 'number' ||
    !Number.isFinite(seed) ||
    typeof rngState !== 'number' ||
    !Number.isFinite(rngState) ||
    typeof counter !== 'number' ||
    !Number.isFinite(counter) ||
    typeof nextId !== 'number' ||
    !Number.isInteger(nextId)
  ) {
    return null;
  }

  const map = generateMap(seed);
  const unitTypes = new Map<string, SimUnitType>();
  if (Array.isArray(input.unitTypes)) {
    for (const entry of input.unitTypes) {
      if (!isRecord(entry) || typeof entry.id !== 'string' || !isRecord(entry.type)) {
        continue;
      }
      unitTypes.set(entry.id, entry.type as unknown as SimUnitType);
    }
  }

  const units: UnitState[] = Array.isArray(input.units) ? (input.units as UnitState[]) : [];
  const projectiles: ProjectileState[] = Array.isArray(input.projectiles)
    ? (input.projectiles as ProjectileState[])
    : [];
  const wrecks: WreckState[] = Array.isArray(input.wrecks) ? (input.wrecks as WreckState[]) : [];
  const players: PlayerId[] = Array.isArray(input.players)
    ? input.players.filter((player): player is number => typeof player === 'number')
    : [];

  let result: WorldResult | null = null;
  if (isRecord(input.result)) {
    const winner = input.result.winner;
    if (winner === null || typeof winner === 'number') {
      result = { winner };
    }
  }

  return {
    tick,
    seed,
    rngState,
    counter,
    nextId,
    players,
    map,
    unitTypes,
    units,
    projectiles,
    wrecks,
    result,
  };
}
