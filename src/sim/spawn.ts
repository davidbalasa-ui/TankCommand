import { clampToMap, heightAt, isBlockedAt } from './map';
import { canStand } from './motion';
import {
  DROP_SPAWN_RADIUS,
  DROP_SPAWN_TRIES,
  MAX_PLACEMENT_SLOPE,
  PLACEMENT_CLEARANCE,
  PLACEMENT_SAMPLE_STEPS,
  STRUCTURE_PICK_PADDING,
  UNIT_RADIUS,
} from './tuning';
import type {
  DepositState,
  PlayerId,
  SimStructureType,
  SimUnitType,
  StartStructure,
  StartUnit,
  StructureState,
  UnitState,
  WorldState,
} from './types';

export type PlacementReason =
  | 'ok'
  | 'outside'
  | 'blocked'
  | 'overlap'
  | 'steep'
  | 'rubble'
  | 'needsMetalDeposit';

export interface PlacementResult {
  valid: boolean;
  reason: PlacementReason;
  depositId: number | null;
}

export function structureSize(
  world: WorldState,
  type: SimStructureType,
): { x: number; z: number } {
  return {
    x: type.footprint.cellsX * world.map.cellSize,
    z: type.footprint.cellsZ * world.map.cellSize,
  };
}

export function structureRadius(world: WorldState, type: SimStructureType): number {
  const size = structureSize(world, type);
  return Math.max(size.x, size.z) / 2;
}

export function addUnit(world: WorldState, start: StartUnit): UnitState | null {
  const type = world.unitTypes.get(start.typeId);
  if (!type) {
    return null;
  }
  const position = clampToMap(world.map, start.x, start.z, UNIT_RADIUS);
  const id = world.nextId;
  world.nextId += 1;
  const heading = start.heading ?? 0;
  const build: UnitState = {
    id,
    owner: start.owner,
    typeId: start.typeId,
    x: position.x,
    z: position.z,
    heading,
    turretHeading: start.turretHeading ?? heading,
    hp: type.hp,
    order: { kind: 'idle' },
    stance: start.stance === 'hold' ? 'hold' : 'free',
    path: [],
    reloadLeft: 0,
    stuckTicks: 0,
    speed: 0,
    replans: 0,
    attackRepathTick: 0,
    job: null,
    upgrades: [],
    transform: null,
  };
  world.units.push(build);
  return build;
}

function findDepositUnder(
  world: WorldState,
  type: SimStructureType,
  x: number,
  z: number,
): DepositState | null {
  const size = structureSize(world, type);
  for (const deposit of world.deposits) {
    if (
      Math.abs(deposit.x - x) <= size.x / 2 &&
      Math.abs(deposit.z - z) <= size.z / 2 &&
      deposit.kind === 'metal'
    ) {
      return deposit;
    }
  }
  return null;
}

export function addStructure(world: WorldState, start: StartStructure): StructureState | null {
  const type = world.structureTypes.get(start.typeId);
  if (!type) {
    return null;
  }
  const position = clampToMap(world.map, start.x, start.z, structureRadius(world, type));
  const id = world.nextId;
  world.nextId += 1;
  const deposit =
    start.depositId === undefined || start.depositId === null
      ? findDepositUnder(world, type, position.x, position.z)
      : world.deposits.find((item) => item.id === start.depositId) ?? null;
  const structure: StructureState = {
    id,
    owner: start.owner,
    typeId: start.typeId,
    x: position.x,
    z: position.z,
    hp: type.hp,
    containers: 0,
    fill: 0,
    depositId: deposit?.id ?? null,
    upgrades: [],
    reloadLeft: 0,
    turretHeading: 0,
    work: null,
    research: null,
  };
  world.structures.push(structure);
  return structure;
}

export function placementValidity(
  world: WorldState,
  _owner: PlayerId,
  type: SimStructureType,
  x: number,
  z: number,
  ignoreUnitId?: number,
): PlacementResult {
  const half = world.map.size / 2;
  const size = structureSize(world, type);
  if (
    x - size.x / 2 < -half ||
    x + size.x / 2 > half ||
    z - size.z / 2 < -half ||
    z + size.z / 2 > half
  ) {
    return { valid: false, reason: 'outside', depositId: null };
  }

  for (let iz = 0; iz < PLACEMENT_SAMPLE_STEPS; iz += 1) {
    for (let ix = 0; ix < PLACEMENT_SAMPLE_STEPS; ix += 1) {
      const sx = x - size.x / 2 + ((ix + 0.5) / PLACEMENT_SAMPLE_STEPS) * size.x;
      const sz = z - size.z / 2 + ((iz + 0.5) / PLACEMENT_SAMPLE_STEPS) * size.z;
      if (isBlockedAt(world.map, sx, sz)) {
        return { valid: false, reason: 'blocked', depositId: null };
      }
    }
  }

  let minHeight = Number.POSITIVE_INFINITY;
  let maxHeight = Number.NEGATIVE_INFINITY;
  for (const [cx, cz] of [
    [x - size.x / 2, z - size.z / 2],
    [x + size.x / 2, z - size.z / 2],
    [x - size.x / 2, z + size.z / 2],
    [x + size.x / 2, z + size.z / 2],
    [x, z],
  ] as const) {
    const height = heightAt(world.map, cx, cz);
    minHeight = Math.min(minHeight, height);
    maxHeight = Math.max(maxHeight, height);
  }
  if ((maxHeight - minHeight) / Math.max(size.x, size.z) > MAX_PLACEMENT_SLOPE) {
    return { valid: false, reason: 'steep', depositId: null };
  }

  for (const item of world.rubble) {
    if (Math.hypot(item.x - x, item.z - z) < item.radius + Math.max(size.x, size.z) / 2) {
      return { valid: false, reason: 'rubble', depositId: null };
    }
  }

  for (const structure of world.structures) {
    if (structure.hp <= 0) {
      continue;
    }
    const otherType = world.structureTypes.get(structure.typeId);
    if (!otherType) {
      continue;
    }
    const otherSize = structureSize(world, otherType);
    if (
      Math.abs(structure.x - x) < (size.x + otherSize.x) / 2 + PLACEMENT_CLEARANCE &&
      Math.abs(structure.z - z) < (size.z + otherSize.z) / 2 + PLACEMENT_CLEARANCE
    ) {
      return { valid: false, reason: 'overlap', depositId: null };
    }
  }

  const radius = Math.max(size.x, size.z) / 2;
  for (const unit of world.units) {
    if (unit.hp <= 0 || unit.id === ignoreUnitId) {
      continue;
    }
    if (Math.hypot(unit.x - x, unit.z - z) < radius + UNIT_RADIUS) {
      return { valid: false, reason: 'overlap', depositId: null };
    }
  }

  let metalDepositId: number | null = null;
  for (const deposit of world.deposits) {
    if (
      Math.abs(deposit.x - x) <= size.x / 2 + PLACEMENT_CLEARANCE &&
      Math.abs(deposit.z - z) <= size.z / 2 + PLACEMENT_CLEARANCE
    ) {
      if (type.buildOnMetalDeposit && deposit.kind === 'metal') {
        metalDepositId = deposit.id;
      } else if (!type.buildOnMetalDeposit) {
        return { valid: false, reason: 'overlap', depositId: null };
      }
    }
  }

  if (type.buildOnMetalDeposit && metalDepositId === null) {
    return { valid: false, reason: 'needsMetalDeposit', depositId: null };
  }

  return { valid: true, reason: 'ok', depositId: metalDepositId };
}

export function structureAtPoint(
  world: WorldState,
  x: number,
  z: number,
): StructureState | null {
  for (const structure of world.structures) {
    if (structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type) {
      continue;
    }
    const size = structureSize(world, type);
    if (
      Math.abs(x - structure.x) <= size.x / 2 + STRUCTURE_PICK_PADDING &&
      Math.abs(z - structure.z) <= size.z / 2 + STRUCTURE_PICK_PADDING
    ) {
      return structure;
    }
  }
  return null;
}

function clearOfStructures(world: WorldState, x: number, z: number): boolean {
  for (const structure of world.structures) {
    if (structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type) {
      continue;
    }
    if (Math.hypot(structure.x - x, structure.z - z) < structureRadius(world, type) + UNIT_RADIUS) {
      return false;
    }
  }
  return true;
}

function clearOfUnits(world: WorldState, x: number, z: number): boolean {
  for (const unit of world.units) {
    if (unit.hp <= 0) {
      continue;
    }
    if (Math.hypot(unit.x - x, unit.z - z) < UNIT_RADIUS * 2) {
      return false;
    }
  }
  return true;
}

export function findNearestFreeSpot(
  world: WorldState,
  x: number,
  z: number,
): { x: number; z: number } {
  for (let index = 0; index < DROP_SPAWN_TRIES; index += 1) {
    const angle = index * 2.399963229728653;
    const radius = DROP_SPAWN_RADIUS * Math.sqrt(index + 1);
    const candidate = clampToMap(
      world.map,
      x + Math.cos(angle) * radius,
      z + Math.sin(angle) * radius,
      UNIT_RADIUS,
    );
    if (
      canStand(world, candidate.x, candidate.z) &&
      clearOfStructures(world, candidate.x, candidate.z) &&
      clearOfUnits(world, candidate.x, candidate.z)
    ) {
      return candidate;
    }
  }
  return clampToMap(world.map, x, z, UNIT_RADIUS);
}

export function unitCount(world: WorldState, player: PlayerId): number {
  let count = 0;
  for (const unit of world.units) {
    if (unit.owner === player && unit.hp > 0) {
      count += 1;
    }
  }
  return count;
}

export function typeOfUnit(
  world: WorldState,
  unit: UnitState,
): SimUnitType | undefined {
  return world.unitTypes.get(unit.typeId);
}
