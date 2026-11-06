import { Rng } from './rng';
import type { Command } from './commands';
import { SIM_TICK_HZ } from './constants';
import {
  clampToMap,
  generateMap,
  NO_FEATURES,
  type MapFeatures,
  mapFor,
  groundLineClear,
  heightAt,
  isBlockedAt,
  lineOfSightClear,
} from './map';
import { unitMap } from './motion';
import { applyAirCommand, assignHome, isAirborne, unitTargetKind, updateAir, weaponCanHit } from './air';
import { findPath } from './pathfinding';
import {
  ATTACK_MOVE_ENGAGE_FACTOR,
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
import {
  applyAssignCommand,
  applyMineCommand,
  applySalvageCommand,
  ensureSideStats,
  updateAlerts,
  updateMetalStations,
} from './economy';
import {
  applyBuyCommand,
  applyCancelCommand,
  applyPlaceKitCommand,
  updateDropQueues,
} from './drops';
import { updateMatchResult } from './match';
import { cloneMission, updateMission, type MissionState } from './triggers';
import { updateVision } from './vision';
import {
  buildRelations,
  defaultSide,
  isAllied,
  isHostile,
  provoke,
  setRelation,
  touchProvocation,
  updateDiplomacy,
} from './diplomacy';
import {
  applyCancelResearchCommand,
  applyResearchCommand,
  updateResearch,
} from './research';
import { applyUpgradeCommand, reloadSeconds, unitArmor, structureArmor } from './upgrades';
import { resolveRepairCommand, updateRepair } from './repair';
import {
  applyDeployCommand,
  applyDismantleCommand,
  applyPackCommand,
  collectRubble,
  updateDeploys,
  updateRubble,
  updateStructureWork,
  updateTurrets,
} from './structures';
import { updateWorkers } from './workers';
import { addStructure, addUnit } from './spawn';
import type {
  CommandOutcome,
  DepositDef,
  DepositState,
  DropBeamState,
  DropOrder,
  FactionAssignment,
  Order,
  PendingKit,
  PlayerId,
  Point,
  ProjectileState,
  ResearchNode,
  ResearchSideState,
  SideState,
  RelationState,
  VisionSideState,
  AiState,
  DiplomacyRelation,
  RubbleState,
  SideStats,
  SimAlert,
  SimStructureType,
  SimUnitType,
  StartResources,
  StartStructure,
  StartUnit,
  Stance,
  StructureState,
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
  structureTypes?: ReadonlyMap<string, SimStructureType>;
  researchTree?: ReadonlyMap<string, ResearchNode>;
  mapFeatures?: MapFeatures;
  mission?: MissionState | null;
  startUnits?: StartUnit[];
  startStructures?: StartStructure[];
  deposits?: DepositDef[];
  factions?: FactionAssignment[];
  fog?: boolean;
  sides?: SideState[];
  relations?: Array<{ a: PlayerId; b: PlayerId; relation: DiplomacyRelation }>;
  startResources?: StartResources[];
  size?: number;
  cellSize?: number;
}

interface TargetRef {
  id: number;
  x: number;
  z: number;
  kind: 'unit' | 'structure';
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
  if (order.kind === 'attackMove') {
    return { ...order };
  }
  if (order.kind === 'attack') {
    return { ...order };
  }
  return { kind: 'idle' };
}

function normalizeStance(stance: Stance | undefined): Stance {
  return stance === 'hold' ? 'hold' : 'free';
}

function cloneStructure(structure: StructureState): StructureState {
  return {
    ...structure,
    upgrades: [...structure.upgrades],
    work: structure.work ? { ...structure.work } : null,
    research: structure.research ? { ...structure.research } : null,
  };
}

function cloneVision(item: VisionSideState): VisionSideState {
  return {
    ...item,
    visibleUnits: [...item.visibleUnits],
    contacts: item.contacts.map((c) => ({ ...c })),
    ghosts: item.ghosts.map((g) => ({ ...g })),
  };
}

function cloneWorld(world: WorldState): WorldState {
  return {
    ...world,
    players: [...world.players],
    factions: world.factions.map((entry) => ({ ...entry })),
    sides: world.sides.map((side) => ({ ...side })),
    relations: world.relations.map((item) => ({ ...item })),
    rubble: world.rubble.map((item) => ({ ...item })),
    research: world.research.map((item) => ({ ...item, done: [...item.done] })),
    mission: world.mission ? cloneMission(world.mission) : null,
    vision: world.vision.map(cloneVision),
    aiStates: world.aiStates.map((item) => ({ ...item, groupIds: [...item.groupIds], lastPads: item.lastPads.map((p) => ({ ...p })) })),
    units: world.units.map((unit) => ({
      ...unit,
      order: cloneOrder(unit.order),
      path: unit.path.map((point) => ({ ...point })),
      job: unit.job ? { ...unit.job } : null,
      upgrades: [...unit.upgrades],
      transform: unit.transform ? { ...unit.transform } : null,
      air: unit.air ? { ...unit.air, patrol: unit.air.patrol ? { ...unit.air.patrol } : null } : null,
    })),
    structures: world.structures.map(cloneStructure),
    deposits: world.deposits.map((deposit) => ({ ...deposit })),
    pendingKits: world.pendingKits.map((kit) => ({ ...kit })),
    dropQueue: world.dropQueue.map((order) => ({ ...order })),
    dropBeams: world.dropBeams.map((beam) => ({ ...beam })),
    alerts: world.alerts.map((alert) => ({ ...alert })),
    resources: world.resources.map((stats) => ({ ...stats })),
    projectiles: world.projectiles.map((projectile) => ({ ...projectile })),
    wrecks: world.wrecks.map((wreck) => ({ ...wreck })),
    lastCommandOutcome: world.lastCommandOutcome ? { ...world.lastCommandOutcome } : null,
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

export function createWorld(seed: number, options: CreateWorldOptions = {}): WorldState {
  const unitTypes = options.unitTypes ?? new Map<string, SimUnitType>();
  const structureTypes = options.structureTypes ?? new Map<string, SimStructureType>();
  const mapFeatures = options.mapFeatures ?? NO_FEATURES;
  const map = generateMap(seed, options.size, options.cellSize, mapFeatures);
  const rng = new Rng(seed);
  const deposits: DepositState[] = (options.deposits ?? []).map((def, index) => ({
    id: index + 1,
    kind: def.kind,
    x: def.x,
    z: def.z,
    amount: def.amount,
    maxAmount: def.amount,
  }));
  const world: WorldState = {
    tick: 0,
    seed,
    rngState: rng.getState(),
    counter: 0,
    nextId: 1,
    players: [],
    factions: (options.factions ?? []).map((entry) => ({ ...entry })),
    fogEnabled: options.fog ?? true,
    aiStates: [],
    vision: [],
    sides: [],
    relations: [],
    map,
    mapFeatures,
    unitTypes,
    structureTypes,
    researchTree: options.researchTree ?? new Map<string, ResearchNode>(),
    units: [],
    structures: [],
    deposits,
    pendingKits: [],
    dropQueue: [],
    dropBeams: [],
    alerts: [],
    resources: (options.startResources ?? []).map((entry) => ({
      player: entry.player,
      ore: entry.ore,
      metal: entry.metal,
      oreGathered: 0,
      metalGathered: 0,
      unitsBuilt: 0,
      unitsLost: 0,
    })),
    projectiles: [],
    wrecks: [],
    rubble: [],
    research: [],
    lastCommandOutcome: null,
    result: null,
    mission: options.mission ? cloneMission(options.mission) : null,
  };

  const starts =
    options.startUnits ??
    (unitTypes.size > 0 && structureTypes.size === 0 ? defaultStartUnits() : []);
  for (const start of starts) {
    addUnit(world, start);
  }
  for (const start of options.startStructures ?? []) {
    addStructure(world, start);
  }
  for (const unit of world.units) {
    assignHome(world, unit);
  }
  for (const faction of world.factions) {
    ensureSideStats(world, faction.player);
  }
  const owners = new Set<PlayerId>();
  for (const unit of world.units) {
    owners.add(unit.owner);
  }
  for (const structure of world.structures) {
    owners.add(structure.owner);
  }
  for (const faction of world.factions) {
    owners.add(faction.player);
  }
  for (const side of options.sides ?? []) {
    owners.add(side.player);
  }
  world.players = [...owners].sort((a, b) => a - b);
  const given = new Map((options.sides ?? []).map((side) => [side.player, side]));
  world.sides = world.players.map((player) => ({ ...(given.get(player) ?? defaultSide(player)) }));
  buildRelations(world, options.relations ?? []);
  updateVision(world, true);
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
  const path = findPath(unitMap(world, unit), unit.x, unit.z, goalX, goalZ);
  if (!path || path.length === 0) {
    return null;
  }
  return path;
}

type MoveOrderKind = 'move' | 'attackMove';

function adoptPath(unit: UnitState, path: Point[], queue: boolean, kind: MoveOrderKind): void {
  unit.path = path;
  const final = path[path.length - 1];
  if (!final) {
    unit.order = { kind: 'idle' };
    unit.speed = 0;
    return;
  }
  unit.order =
    kind === 'move'
      ? { kind: 'move', x: final.x, z: final.z, queue }
      : { kind: 'attackMove', x: final.x, z: final.z, queue };
}

function planMove(
  world: WorldState,
  unit: UnitState,
  goalX: number,
  goalZ: number,
  queue: boolean,
  kind: MoveOrderKind,
): void {
  unit.stance = 'free';

  if (queue) {
    const tail = unit.path.length > 0 ? unit.path[unit.path.length - 1] : undefined;
    const pending =
      unit.order.kind === 'move' || unit.order.kind === 'attackMove'
        ? { x: unit.order.x, z: unit.order.z }
        : undefined;
    const anchor = tail ?? pending;
    if (anchor) {
      const appended = findPath(unitMap(world, unit), anchor.x, anchor.z, goalX, goalZ) ?? [
        { x: goalX, z: goalZ },
      ];
      const combined = [...unit.path, ...appended];
      const final = combined[combined.length - 1];
      if (final) {
        unit.path = combined;
        unit.order =
          kind === 'move'
            ? { kind: 'move', x: final.x, z: final.z, queue: true }
            : { kind: 'attackMove', x: final.x, z: final.z, queue: true };
        unit.replans = 0;
        unit.stuckTicks = 0;
        return;
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
  adoptPath(unit, path, false, kind);
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
    planMove(world, unit, goal.x, goal.z, command.queue ?? false, 'move');
  }
}

function applyAttackMoveCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'attackMove' }>,
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
    planMove(world, unit, goal.x, goal.z, command.queue ?? false, 'attackMove');
  }
}

function applyAttackCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'attack' }>,
): void {
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    unit.stance = 'free';
    unit.order = { kind: 'attack', targetId: command.targetId };
    unit.path = [];
    unit.speed = 0;
    unit.replans = 0;
    unit.stuckTicks = 0;
    unit.attackRepathTick = 0;
  }
}

function applyHoldCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'hold' }>,
): void {
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    unit.stance = 'hold';
    unit.order = { kind: 'idle' };
    unit.path = [];
    unit.speed = 0;
    unit.replans = 0;
    unit.stuckTicks = 0;
  }
}

function applyStopCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'stop' }>,
): void {
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    unit.stance = 'free';
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

function unitLineOfSightAt(world: WorldState, unit: UnitState, x: number, z: number): boolean {
  return lineOfSightClear(
    world.map,
    unit.x,
    unit.z,
    heightAt(world.map, unit.x, unit.z) + MUZZLE_HEIGHT,
    x,
    z,
    heightAt(world.map, x, z) + TARGET_HEIGHT,
  );
}

function nearestEnemyUnit(world: WorldState, unit: UnitState): UnitState | null {
  let best: UnitState | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const other of world.units) {
    if (other.hp <= 0 || !isHostile(world, unit.owner, other.owner)) {
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
): TargetRef | null {
  if (unit.order.kind === 'attack') {
    const id = unit.order.targetId;
    const foundUnit = world.units.find(
      (other) => other.id === id && other.hp > 0 && !isAllied(world, unit.owner, other.owner),
    );
    if (foundUnit) {
      return { id: foundUnit.id, x: foundUnit.x, z: foundUnit.z, kind: 'unit' };
    }
    const foundStructure = world.structures.find(
      (structure) => structure.id === id && structure.hp > 0 && !isAllied(world, unit.owner, structure.owner),
    );
    if (foundStructure) {
      return {
        id: foundStructure.id,
        x: foundStructure.x,
        z: foundStructure.z,
        kind: 'structure',
      };
    }
    const near = nearestEnemyUnit(world, unit);
    if (near) {
      return { id: near.id, x: near.x, z: near.z, kind: 'unit' };
    }
    return null;
  }

  const range =
    unit.order.kind === 'attackMove'
      ? type.sightRange * ATTACK_MOVE_ENGAGE_FACTOR
      : type.weapon?.range ?? type.sightRange;
  let best: TargetRef | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const other of world.units) {
    if (other.hp <= 0 || !isHostile(world, unit.owner, other.owner)) {
      continue;
    }
    if (type.weapon && !weaponCanHit(type.weapon, unitTargetKind(other))) {
      continue;
    }
    const distance = Math.hypot(other.x - unit.x, other.z - unit.z);
    if (distance <= range && distance < bestDistance) {
      best = { id: other.id, x: other.x, z: other.z, kind: 'unit' };
      bestDistance = distance;
    }
  }
  return best;
}

function isHoldingFirePosition(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  target: TargetRef | null,
): boolean {
  if (unit.order.kind !== 'attack' && unit.order.kind !== 'attackMove') {
    return false;
  }
  const weapon = type.weapon;
  if (!weapon || !target) {
    return false;
  }
  const distance = Math.hypot(target.x - unit.x, target.z - unit.z);
  return distance <= weapon.range && unitLineOfSightAt(world, unit, target.x, target.z);
}

function followPath(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  goal: Point,
): void {
  const map = mapFor(world.map, type.movement);
  const goalDistance = Math.hypot(goal.x - unit.x, goal.z - unit.z);
  if (goalDistance <= STOP_DISTANCE) {
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
  shooter: { owner: PlayerId; x: number; z: number },
  targetX: number,
  targetZ: number,
  weapon: WeaponStats,
  rng: Rng,
  targetStructureId?: number,
): void {
  const startY = heightAt(world.map, shooter.x, shooter.z) + MUZZLE_HEIGHT;
  const targetY = heightAt(world.map, targetX, targetZ) + TARGET_HEIGHT;
  const dx = targetX - shooter.x;
  const dz = targetZ - shooter.z;
  const distance = Math.hypot(dx, dz);
  if (distance < 0.001) {
    return;
  }
  const baseAngle = Math.atan2(dz, dx);
  const error = (1 - weapon.accuracy) * MAX_AIM_ERROR * (rng.next() * 2 - 1);
  const angle = baseAngle + error;
  const travelTime = distance / weapon.projectileSpeed;

  const projectile: ProjectileState = {
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
  };
  if (targetStructureId !== undefined) {
    projectile.targetStructureId = targetStructureId;
  }
  world.projectiles.push(projectile);
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

function structureRadius(world: WorldState, type: SimStructureType): number {
  return (
    (Math.max(type.footprint.cellsX, type.footprint.cellsZ) * world.map.cellSize) / 2
  );
}

function applySplash(
  world: WorldState,
  x: number,
  y: number,
  z: number,
  projectile: ProjectileState,
  directUnitId?: number,
  directStructureId?: number,
): void {
  const radius = Math.max(0.001, projectile.splashRadius);
  for (const unit of world.units) {
    if (unit.hp <= 0 || isAllied(world, projectile.owner, unit.owner)) {
      continue;
    }
    const unitY = heightAt(world.map, unit.x, unit.z) + TARGET_HEIGHT;
    const distance = Math.hypot(unit.x - x, unitY - y, unit.z - z);
    if (unit.id === directUnitId || distance <= radius + UNIT_RADIUS) {
      const type = world.unitTypes.get(unit.typeId);
      const armor = unitArmor(unit, type);
      const damage = Math.max(1, projectile.damage - armor);
      unit.hp = Math.max(0, unit.hp - damage);
      provoke(world, unit.owner, projectile.owner);
      touchProvocation(world, unit.owner, projectile.owner);
    }
  }
  // A shot fired at a unit must not splash a structure: the pad that sits next
  // to the target unit would otherwise eat every shot aimed at that unit and
  // the unit could never be damaged at all (see ProjectileState.targetStructureId).
  if (projectile.targetStructureId === undefined) {
    return;
  }
  for (const structure of world.structures) {
    if (structure.hp <= 0 || isAllied(world, projectile.owner, structure.owner)) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type) {
      continue;
    }
    const structY = heightAt(world.map, structure.x, structure.z) + TARGET_HEIGHT;
    const structureHitRadius = structureRadius(world, type);
    const distance = Math.hypot(structure.x - x, structY - y, structure.z - z);
    if (structure.id === directStructureId || distance <= radius + structureHitRadius) {
      const damage = Math.max(1, projectile.damage - structureArmor(structure.upgrades, type));
      structure.hp = Math.max(0, structure.hp - damage);
      provoke(world, structure.owner, projectile.owner);
      touchProvocation(world, structure.owner, projectile.owner);
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
    let hitStructure: StructureState | null = null;
    let hitT = Number.POSITIVE_INFINITY;
    for (const unit of world.units) {
      if (unit.hp <= 0 || isAllied(world, projectile.owner, unit.owner)) {
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
        hitStructure = null;
      }
    }
    if (projectile.targetStructureId !== undefined) {
      for (const structure of world.structures) {
        if (structure.hp <= 0 || isAllied(world, projectile.owner, structure.owner)) {
          continue;
        }
        const type = world.structureTypes.get(structure.typeId);
        if (!type) {
          continue;
        }
        const structY = heightAt(world.map, structure.x, structure.z) + TARGET_HEIGHT;
        const structRadius = structureRadius(world, type);
        const t = closestPointT(ox, oy, oz, nx, ny, nz, structure.x, structY, structure.z);
        const px = ox + (nx - ox) * t;
        const py = oy + (ny - oy) * t;
        const pz = oz + (nz - oz) * t;
        const distance = Math.hypot(px - structure.x, py - structY, pz - structure.z);
        if (distance <= structRadius && t < hitT) {
          hitT = t;
          hitUnit = null;
          hitStructure = structure;
        }
      }
    }

    if (hitUnit) {
      const hx = ox + (nx - ox) * hitT;
      const hy = oy + (ny - oy) * hitT;
      const hz = oz + (nz - oz) * hitT;
      applySplash(world, hx, hy, hz, projectile, hitUnit.id);
      continue;
    }
    if (hitStructure) {
      const hx = ox + (nx - ox) * hitT;
      const hy = oy + (ny - oy) * hitT;
      const hz = oz + (nz - oz) * hitT;
      applySplash(world, hx, hy, hz, projectile, undefined, hitStructure.id);
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
        if (!b || b.hp <= 0 || a.air || b.air) {
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
  target: TargetRef | null,
): void {
  if (unit.stance === 'hold') {
    unit.path = [];
    unit.speed = approach(unit.speed, 0, type.accel * DT);
    return;
  }

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
      adoptPath(unit, path, unit.order.queue, 'move');
    }
    if (unit.order.kind === 'move') {
      followPath(world, unit, type, { x: unit.order.x, z: unit.order.z });
    }
    return;
  }

  if (unit.order.kind === 'attackMove') {
    const weapon = type.weapon;
    const distance = target ? Math.hypot(target.x - unit.x, target.z - unit.z) : 0;
    const inRange =
      target !== null &&
      weapon !== null &&
      distance <= weapon.range &&
      unitLineOfSightAt(world, unit, target.x, target.z);
    if (inRange) {
      unit.path = [];
      unit.speed = approach(unit.speed, 0, type.accel * DT);
      return;
    }

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
      adoptPath(unit, path, unit.order.queue, 'attackMove');
    }
    if (unit.order.kind === 'attackMove') {
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
    const los = weapon ? unitLineOfSightAt(world, unit, target.x, target.z) : false;
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
    if (
      unit.order.kind !== 'move' &&
      unit.order.kind !== 'attackMove' &&
      unit.order.kind !== 'attack'
    ) {
      unit.stuckTicks = 0;
      unit.replans = 0;
      continue;
    }

    const type = world.unitTypes.get(unit.typeId);
    if (type) {
      const target = selectTarget(world, unit, type);
      if (isHoldingFirePosition(world, unit, type, target)) {
        unit.stuckTicks = 0;
        unit.replans = 0;
        continue;
      }
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
      const path = findPath(unitMap(world, unit), unit.x, unit.z, unit.order.x, unit.order.z);
      unit.path = path ?? [];
      const end = path && path.length > 0 ? path[path.length - 1] : undefined;
      if (end) {
        unit.order = { kind: 'move', x: end.x, z: end.z, queue: unit.order.queue };
      }
      continue;
    }

    if (unit.order.kind === 'attackMove') {
      const path = findPath(unitMap(world, unit), unit.x, unit.z, unit.order.x, unit.order.z);
      unit.path = path ?? [];
      const end = path && path.length > 0 ? path[path.length - 1] : undefined;
      if (end) {
        unit.order = { kind: 'attackMove', x: end.x, z: end.z, queue: unit.order.queue };
      }
      continue;
    }

    const liveTarget = type ? selectTarget(world, unit, type) : null;
    if (liveTarget) {
      unit.path = findPath(unitMap(world, unit), unit.x, unit.z, liveTarget.x, liveTarget.z) ?? [];
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

    // A worker with a job owns its speed, heading and path through
    // `updateWorkers`; the military tick must not touch it. Otherwise
    // `updateOrderPath` runs the idle deceleration on the same `unit.speed` the
    // worker step just raised, and the worker never crawls faster than one
    // `accel * DT` step per tick.
    if (unit.job) {
      continue;
    }
    // Deploying units stand still and can't fire; updateDeploys finishes the job.
    if (unit.transform) {
      unit.speed = 0;
      continue;
    }
    // Aircraft on the ground (parked or rearming) neither move nor shoot.
    if (unit.air && !isAirborne(unit)) {
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

    if (target && type.weapon && unit.reloadLeft <= 0 && (!unit.air || unit.air.ammo > 0)) {
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
        unitLineOfSightAt(world, unit, target.x, target.z);
      if (canFire) {
        fireProjectile(
          world,
          unit,
          target.x,
          target.z,
          weapon,
          rng,
          target.kind === 'structure' ? target.id : undefined,
        );
        unit.reloadLeft = reloadSeconds(unit, weapon.reloadSec);
        if (unit.air) {
          unit.air.ammo -= 1;
        }
      }
    }
  }

  separateUnits(world);
  updateStuckUnits(world, startPositions);
}

function cleanupDead(world: WorldState): void {
  const dead = world.units.filter((unit) => unit.hp <= 0);
  for (const unit of dead) {
    world.wrecks.push({ x: unit.x, z: unit.z, ttl: WRECK_TTL_SEC });
    const stats = ensureSideStats(world, unit.owner);
    stats.unitsLost += 1;
  }
  world.units = world.units.filter((unit) => unit.hp > 0);
  world.structures = world.structures.filter((structure) => structure.hp > 0);
}

function updateWrecks(world: WorldState): void {
  for (const wreck of world.wrecks) {
    wreck.ttl -= DT;
  }
  world.wrecks = world.wrecks.filter((wreck) => wreck.ttl > 0);
}

function updateDropBeams(world: WorldState): void {
  for (const beam of world.dropBeams) {
    beam.ttl -= DT;
  }
  world.dropBeams = world.dropBeams.filter((beam) => beam.ttl > 0);
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
      switch (command.kind) {
        case 'debug.addCounter':
          next.counter += command.amount;
          break;
        case 'move':
          applyMoveCommand(next, command);
          break;
        case 'attackMove':
          applyAttackMoveCommand(next, command);
          break;
        case 'attack':
          applyAttackCommand(next, command);
          break;
        case 'hold':
          applyHoldCommand(next, command);
          break;
        case 'stop':
          applyStopCommand(next, command);
          break;
        case 'buy':
          applyBuyCommand(next, command);
          break;
        case 'cancel':
          applyCancelCommand(next, command);
          break;
        case 'placeKit':
          applyPlaceKitCommand(next, command);
          break;
        case 'mine':
          applyMineCommand(next, command);
          break;
        case 'assign':
          applyAssignCommand(next, command);
          break;
        case 'salvage':
          applySalvageCommand(next, command);
          break;
        case 'diplomacy.set':
          setRelation(next, command.a, command.b, command.relation, command.oneWay === true);
          break;
        case 'pack':
          applyPackCommand(next, command);
          break;
        case 'deploy':
          applyDeployCommand(next, command);
          break;
        case 'dismantle':
          applyDismantleCommand(next, command);
          break;
        case 'research':
          applyResearchCommand(next, command);
          break;
        case 'cancelResearch':
          applyCancelResearchCommand(next, command);
          break;
        case 'upgrade':
          applyUpgradeCommand(next, command);
          break;
        case 'repair': {
          const resolved = resolveRepairCommand(next, command);
          if (resolved) {
            applyMoveCommand(next, {
              kind: 'move',
              tick: command.tick,
              issuer: command.issuer,
              unitIds: resolved.unitIds,
              x: resolved.x,
              z: resolved.z,
            });
          }
          break;
        }
        case 'air':
          applyAirCommand(next, command);
          break;
        case 'noop':
          break;
      }
    }
  }

  updateUnits(next, rng);
  updateAir(next);
  updateTurrets(next, rng, (shooter, x, z, weapon, shotRng, structureId) => {
    fireProjectile(next, shooter, x, z, weapon, shotRng, structureId);
  });
  updateStructureWork(next);
  updateDeploys(next);
  updateDiplomacy(next);
  updateRepair(next);
  updateResearch(next);
  updateWorkers(next);
  updateMetalStations(next);
  updateDropQueues(next);
  updateProjectiles(next);
  collectRubble(next);
  cleanupDead(next);
  updateWrecks(next);
  updateRubble(next);
  updateDropBeams(next);
  updateAlerts(next);
  if (next.mission) {
    updateMission(next, {
      attackMove: (target, side, unitIds, x, z) => {
        applyAttackMoveCommand(target, { kind: 'attackMove', tick: target.tick + 1, issuer: side, unitIds, x, z });
      },
    });
  } else {
    updateMatchResult(next);
  }

  next.tick = nextTick;
  updateVision(next);
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
      factions: world.factions,
      sides: world.sides,
      relations: world.relations,
      fogEnabled: world.fogEnabled,
      vision: world.vision,
      mapFeatures: world.mapFeatures,
      aiStates: world.aiStates,
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
        stance: unit.stance,
        path: unit.path,
        reloadLeft: unit.reloadLeft,
        stuckTicks: unit.stuckTicks,
        speed: unit.speed,
        replans: unit.replans,
        attackRepathTick: unit.attackRepathTick,
        job: unit.job,
        upgrades: unit.upgrades,
        transform: unit.transform,
        air: unit.air,
      })),
      structures: world.structures,
      deposits: world.deposits,
      pendingKits: world.pendingKits,
      dropQueue: world.dropQueue,
      dropBeams: world.dropBeams,
      alerts: world.alerts,
      resources: world.resources,
      projectiles: world.projectiles,
      wrecks: world.wrecks,
      rubble: world.rubble,
      research: world.research,
      lastCommandOutcome: world.lastCommandOutcome,
      result: world.result,
      mission: world.mission,
    }),
  );
}

export function worldToPayload(world: WorldState): unknown {
  const unitTypes = [...world.unitTypes.entries()]
    .map(([id, type]) => ({ id, type }))
    .sort((a, b) => a.id.localeCompare(b.id));
  const structureTypes = [...world.structureTypes.entries()]
    .map(([id, type]) => ({ id, type }))
    .sort((a, b) => a.id.localeCompare(b.id));
  return {
    tick: world.tick,
    seed: world.seed,
    rngState: world.rngState,
    counter: world.counter,
    nextId: world.nextId,
    players: [...world.players],
    factions: world.factions.map((entry) => ({ ...entry })),
    sides: world.sides.map((side) => ({ ...side })),
    relations: world.relations.map((item) => ({ ...item })),
    mission: world.mission ? cloneMission(world.mission) : null,
    mapSpec: { size: world.map.size, cellSize: world.map.cellSize, features: world.mapFeatures },
    fogEnabled: world.fogEnabled,
    vision: world.vision.map(cloneVision),
    aiStates: world.aiStates.map((item) => ({ ...item, groupIds: [...item.groupIds], lastPads: item.lastPads.map((p) => ({ ...p })) })),
    units: world.units.map((unit) => ({
      ...unit,
      order: cloneOrder(unit.order),
      path: unit.path.map((point) => ({ ...point })),
      job: unit.job ? { ...unit.job } : null,
      upgrades: [...unit.upgrades],
      transform: unit.transform ? { ...unit.transform } : null,
      air: unit.air ? { ...unit.air, patrol: unit.air.patrol ? { ...unit.air.patrol } : null } : null,
    })),
    structures: world.structures.map(cloneStructure),
    deposits: world.deposits.map((deposit) => ({ ...deposit })),
    pendingKits: world.pendingKits.map((kit) => ({ ...kit })),
    dropQueue: world.dropQueue.map((order) => ({ ...order })),
    dropBeams: world.dropBeams.map((beam) => ({ ...beam })),
    alerts: world.alerts.map((alert) => ({ ...alert })),
    resources: world.resources.map((stats) => ({ ...stats })),
    projectiles: world.projectiles.map((projectile) => ({ ...projectile })),
    wrecks: world.wrecks.map((wreck) => ({ ...wreck })),
    rubble: world.rubble.map((item) => ({ ...item })),
    research: world.research.map((side) => ({ ...side, done: [...side.done] })),
    lastCommandOutcome: world.lastCommandOutcome ? { ...world.lastCommandOutcome } : null,
    result: world.result ? { winner: world.result.winner } : null,
    unitTypes,
    structureTypes,
    researchTree: [...world.researchTree.values()].sort((a, b) => a.id.localeCompare(b.id)),
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

  const mission: MissionState | null = isRecord(input.mission)
    ? cloneMission(input.mission as unknown as MissionState)
    : null;
  const spec = isRecord(input.mapSpec) ? input.mapSpec : null;
  const mapFeatures: MapFeatures =
    spec && isRecord(spec.features) ? (spec.features as unknown as MapFeatures) : NO_FEATURES;
  const map = generateMap(
    seed,
    spec && typeof spec.size === 'number' ? spec.size : undefined,
    spec && typeof spec.cellSize === 'number' ? spec.cellSize : undefined,
    mapFeatures,
  );
  const unitTypes = new Map<string, SimUnitType>();
  if (Array.isArray(input.unitTypes)) {
    for (const entry of input.unitTypes) {
      if (!isRecord(entry) || typeof entry.id !== 'string' || !isRecord(entry.type)) {
        continue;
      }
      unitTypes.set(entry.id, entry.type as unknown as SimUnitType);
    }
  }
  const structureTypes = new Map<string, SimStructureType>();
  if (Array.isArray(input.structureTypes)) {
    for (const entry of input.structureTypes) {
      if (!isRecord(entry) || typeof entry.id !== 'string' || !isRecord(entry.type)) {
        continue;
      }
      structureTypes.set(entry.id, entry.type as unknown as SimStructureType);
    }
  }

  const units: UnitState[] = Array.isArray(input.units)
    ? (input.units as UnitState[]).map((unit) => ({
        ...unit,
        stance: normalizeStance(unit.stance),
        job: unit.job ?? null,
        upgrades: Array.isArray(unit.upgrades) ? [...unit.upgrades] : [],
        transform: unit.transform ?? null,
        air: unit.air ?? null,
      }))
    : [];
  const structures: StructureState[] = Array.isArray(input.structures)
    ? (input.structures as StructureState[]).map((structure) => ({
        ...structure,
        upgrades: Array.isArray(structure.upgrades) ? [...structure.upgrades] : [],
        reloadLeft: structure.reloadLeft ?? 0,
        turretHeading: structure.turretHeading ?? 0,
        work: structure.work ?? null,
        research: structure.research ?? null,
      }))
    : [];
  const researchTree = new Map<string, ResearchNode>();
  if (Array.isArray(input.researchTree)) {
    for (const node of input.researchTree as ResearchNode[]) {
      researchTree.set(node.id, node);
    }
  }
  const rubble: RubbleState[] = Array.isArray(input.rubble) ? (input.rubble as RubbleState[]) : [];
  const research: ResearchSideState[] = Array.isArray(input.research)
    ? (input.research as ResearchSideState[])
    : [];
  const deposits: DepositState[] = Array.isArray(input.deposits)
    ? (input.deposits as DepositState[])
    : [];
  const pendingKits: PendingKit[] = Array.isArray(input.pendingKits)
    ? (input.pendingKits as PendingKit[])
    : [];
  const dropQueue: DropOrder[] = Array.isArray(input.dropQueue)
    ? (input.dropQueue as DropOrder[])
    : [];
  const dropBeams: DropBeamState[] = Array.isArray(input.dropBeams)
    ? (input.dropBeams as DropBeamState[])
    : [];
  const alerts: SimAlert[] = Array.isArray(input.alerts)
    ? (input.alerts as SimAlert[])
    : [];
  const resources: SideStats[] = Array.isArray(input.resources)
    ? (input.resources as SideStats[])
    : [];
  const factions: FactionAssignment[] = Array.isArray(input.factions)
    ? (input.factions as FactionAssignment[])
    : [];
  const vision: VisionSideState[] = Array.isArray(input.vision)
    ? (input.vision as VisionSideState[])
    : [];
  const fogEnabled = input.fogEnabled !== false;
  const aiStates: AiState[] = Array.isArray(input.aiStates) ? (input.aiStates as AiState[]) : [];
  const projectiles: ProjectileState[] = Array.isArray(input.projectiles)
    ? (input.projectiles as ProjectileState[])
    : [];
  const wrecks: WreckState[] = Array.isArray(input.wrecks)
    ? (input.wrecks as WreckState[])
    : [];
  const players: PlayerId[] = Array.isArray(input.players)
    ? input.players.filter((player): player is number => typeof player === 'number')
    : [];

  const sides: SideState[] =
    Array.isArray(input.sides) && input.sides.length > 0
      ? (input.sides as SideState[])
      : players.map((player) => defaultSide(player));
  const relations: RelationState[] = Array.isArray(input.relations)
    ? (input.relations as RelationState[])
    : [];

  let result: WorldResult | null = null;
  if (isRecord(input.result)) {
    const winner = input.result.winner;
    if (winner === null || typeof winner === 'number') {
      result = { winner };
    }
  }

  let lastCommandOutcome: CommandOutcome | null = null;
  if (isRecord(input.lastCommandOutcome)) {
    const outcome = input.lastCommandOutcome;
    if (
      typeof outcome.tick === 'number' &&
      typeof outcome.kind === 'string' &&
      typeof outcome.ok === 'boolean' &&
      typeof outcome.reason === 'string'
    ) {
      lastCommandOutcome = {
        tick: outcome.tick,
        kind: outcome.kind,
        ok: outcome.ok,
        reason: outcome.reason,
      };
    }
  }

  return {
    tick,
    seed,
    rngState,
    counter,
    nextId,
    players,
    factions,
    fogEnabled,
    aiStates,
    vision,
    sides,
    relations,
    map,
    mapFeatures,
    unitTypes,
    structureTypes,
    researchTree,
    units,
    structures,
    deposits,
    pendingKits,
    dropQueue,
    dropBeams,
    alerts,
    resources,
    projectiles,
    wrecks,
    rubble,
    research,
    lastCommandOutcome,
    result,
    mission,
  };
}
