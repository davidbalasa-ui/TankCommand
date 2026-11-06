import { isHostile } from './diplomacy';
import { SIM_TICK_HZ } from './constants';
import { heightAt, lineOfSightClear } from './map';
import { setOutcome } from './drops';
import { unitTargetKind, weaponCanHit } from './air';
import { ensureSideStats } from './economy';
import { addStructure, addUnit, placementValidity, structureRadius } from './spawn';
import {
  MUZZLE_HEIGHT,
  RUBBLE_PADDING,
  RUBBLE_TTL_SEC,
  STRUCTURE_DAMAGE_CRITICAL,
  STRUCTURE_DAMAGE_HEAVY,
  STRUCTURE_DAMAGE_LIGHT,
  TARGET_HEIGHT,
  TURRET_ALIGN_TOLERANCE_DEG,
  UPGRADE_FIRE_RATE_FACTOR,
} from './tuning';
import type { Rng } from './rng';
import type { Command } from './commands';
import type { SimStructureType, StructureState, UnitState, WeaponStats, WorldState } from './types';

const DT = 1 / SIM_TICK_HZ;
const DEG_TO_RAD = Math.PI / 180;

export type DamageState = 'ok' | 'light' | 'heavy' | 'critical';

export type FireFn = (
  shooter: { owner: number; x: number; z: number },
  targetX: number,
  targetZ: number,
  weapon: WeaponStats,
  rng: Rng,
  targetStructureId?: number,
) => void;

export function damageState(hp: number, maxHp: number): DamageState {
  const ratio = maxHp > 0 ? hp / maxHp : 0;
  if (ratio <= STRUCTURE_DAMAGE_CRITICAL) {
    return 'critical';
  }
  if (ratio <= STRUCTURE_DAMAGE_HEAVY) {
    return 'heavy';
  }
  if (ratio <= STRUCTURE_DAMAGE_LIGHT) {
    return 'light';
  }
  return 'ok';
}

function normalizeAngle(angle: number): number {
  let value = angle;
  while (value > Math.PI) {
    value -= Math.PI * 2;
  }
  while (value < -Math.PI) {
    value += Math.PI * 2;
  }
  return value;
}

function ownStructure(
  world: WorldState,
  issuer: number,
  id: number,
): { structure: StructureState; type: SimStructureType } | null {
  const structure = world.structures.find((item) => item.id === id && item.owner === issuer && item.hp > 0);
  const type = structure ? world.structureTypes.get(structure.typeId) : undefined;
  return structure && type ? { structure, type } : null;
}

export function applyPackCommand(world: WorldState, command: Extract<Command, { kind: 'pack' }>): void {
  const own = ownStructure(world, command.issuer, command.structureId);
  if (!own) {
    setOutcome(world, command.tick, 'pack', false, 'unknownStructure');
    return;
  }
  if (own.type.packSec <= 0 || own.type.packedUnitId === null) {
    setOutcome(world, command.tick, 'pack', false, 'notPackable');
    return;
  }
  if (own.structure.work !== null) {
    setOutcome(world, command.tick, 'pack', false, 'busy');
    return;
  }
  own.structure.work = { kind: 'pack', left: own.type.packSec };
  setOutcome(world, command.tick, 'pack', true, 'ok');
}

export function applyDismantleCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'dismantle' }>,
): void {
  const own = ownStructure(world, command.issuer, command.structureId);
  if (!own) {
    setOutcome(world, command.tick, 'dismantle', false, 'unknownStructure');
    return;
  }
  if (own.type.kind === 'pad' && world.structures.filter(
    (item) => item.owner === command.issuer && item.hp > 0 && item.work?.kind !== 'dismantle' && world.structureTypes.get(item.typeId)?.kind === 'pad',
  ).length <= 1) {
    setOutcome(world, command.tick, 'dismantle', false, 'lastPad');
    return;
  }
  if (own.structure.work !== null) {
    setOutcome(world, command.tick, 'dismantle', false, 'busy');
    return;
  }
  own.structure.work = { kind: 'dismantle', left: own.type.dismantleSec };
  const running = own.structure.research
    ? world.researchTree.get(own.structure.research.nodeId)
    : undefined;
  if (running) {
    const stats = ensureSideStats(world, command.issuer);
    stats.ore += running.cost.ore;
    stats.metal += running.cost.metal;
  }
  own.structure.research = null;
  setOutcome(world, command.tick, 'dismantle', true, 'ok');
}

export function applyDeployCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'deploy' }>,
): void {
  const unit = world.units.find(
    (item) => item.id === command.unitId && item.owner === command.issuer && item.hp > 0,
  );
  const type = unit ? world.unitTypes.get(unit.typeId) : undefined;
  if (!unit || !type || type.deploysTo === null) {
    setOutcome(world, command.tick, 'deploy', false, 'notDeployable');
    return;
  }
  const target = world.structureTypes.get(type.deploysTo);
  if (!target) {
    setOutcome(world, command.tick, 'deploy', false, 'notDeployable');
    return;
  }
  const validity = placementValidity(world, command.issuer, target, unit.x, unit.z, unit.id);
  if (!validity.valid) {
    setOutcome(world, command.tick, 'deploy', false, validity.reason);
    return;
  }
  unit.order = { kind: 'idle' };
  unit.path = [];
  unit.speed = 0;
  unit.transform = { left: type.deploySec };
  setOutcome(world, command.tick, 'deploy', true, 'ok');
}

function packStructure(world: WorldState, structure: StructureState, type: SimStructureType): void {
  const packedId = type.packedUnitId;
  const packedType = packedId ? world.unitTypes.get(packedId) : undefined;
  if (!packedId || !packedType) {
    structure.work = null;
    return;
  }
  const unit = addUnit(world, { owner: structure.owner, typeId: packedId, x: structure.x, z: structure.z });
  if (unit) {
    unit.hp = Math.max(1, (structure.hp / type.hp) * packedType.hp);
    unit.upgrades = [...structure.upgrades];
  }
  removeStructure(world, structure);
}

function removeStructure(world: WorldState, structure: StructureState): void {
  world.structures = world.structures.filter((item) => item.id !== structure.id);
}

function dismantleStructure(world: WorldState, structure: StructureState, type: SimStructureType): void {
  const stats = ensureSideStats(world, structure.owner);
  stats.ore += Math.floor((type.cost.ore * type.dismantleRefundPercent) / 100);
  stats.metal += Math.floor((type.cost.metal * type.dismantleRefundPercent) / 100);
  removeStructure(world, structure);
}

export function updateStructureWork(world: WorldState): void {
  for (const structure of world.structures) {
    if (!structure.work || structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type) {
      structure.work = null;
      continue;
    }
    structure.work.left = Math.max(0, structure.work.left - DT);
    if (structure.work.left > 0) {
      continue;
    }
    if (structure.work.kind === 'pack') {
      packStructure(world, structure, type);
    } else {
      dismantleStructure(world, structure, type);
    }
  }
}

export function updateDeploys(world: WorldState): void {
  for (const unit of world.units) {
    if (!unit.transform || unit.hp <= 0) {
      continue;
    }
    unit.speed = 0;
    unit.transform.left = Math.max(0, unit.transform.left - DT);
    if (unit.transform.left > 0) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
    const target = type?.deploysTo ? world.structureTypes.get(type.deploysTo) : undefined;
    if (!type || !target || !type.deploysTo) {
      unit.transform = null;
      continue;
    }
    const validity = placementValidity(world, unit.owner, target, unit.x, unit.z, unit.id);
    if (!validity.valid) {
      unit.transform = null;
      continue;
    }
    const structure = addStructure(world, {
      owner: unit.owner,
      typeId: type.deploysTo,
      x: unit.x,
      z: unit.z,
      depositId: validity.depositId,
    });
    if (structure) {
      structure.hp = Math.max(1, (unit.hp / type.hp) * target.hp);
      structure.upgrades = [...unit.upgrades];
    }
    world.units = world.units.filter((item) => item.id !== unit.id);
  }
}

function structureLineOfSight(world: WorldState, from: StructureState, x: number, z: number): boolean {
  return lineOfSightClear(
    world.map,
    from.x,
    from.z,
    heightAt(world.map, from.x, from.z) + MUZZLE_HEIGHT,
    x,
    z,
    heightAt(world.map, x, z) + TARGET_HEIGHT,
  );
}

export function updateTurrets(world: WorldState, rng: Rng, fire: FireFn): void {
  for (const turret of world.structures) {
    if (turret.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(turret.typeId);
    const weapon = type?.weapon;
    if (!type || !weapon) {
      continue;
    }
    turret.reloadLeft = Math.max(0, turret.reloadLeft - DT);
    if (turret.work) {
      continue;
    }
    let best: { id: number; x: number; z: number; structure: boolean } | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const unit of world.units) {
      if (unit.hp <= 0 || !isHostile(world, turret.owner, unit.owner)) {
        continue;
      }
      if (!weaponCanHit(weapon, unitTargetKind(unit))) {
        continue;
      }
      const distance = Math.hypot(unit.x - turret.x, unit.z - turret.z);
      if (distance <= weapon.range && distance < bestDistance && structureLineOfSight(world, turret, unit.x, unit.z)) {
        best = { id: unit.id, x: unit.x, z: unit.z, structure: false };
        bestDistance = distance;
      }
    }
    if (!best) {
      for (const other of world.structures) {
        if (other.hp <= 0 || !isHostile(world, turret.owner, other.owner)) {
          continue;
        }
        const distance = Math.hypot(other.x - turret.x, other.z - turret.z);
        if (distance <= weapon.range && distance < bestDistance && structureLineOfSight(world, turret, other.x, other.z)) {
          best = { id: other.id, x: other.x, z: other.z, structure: true };
          bestDistance = distance;
        }
      }
    }
    if (!best) {
      continue;
    }
    const bearing = Math.atan2(best.z - turret.z, best.x - turret.x);
    const maxStep = type.turretTurnDegPerSec * DEG_TO_RAD * DT;
    const diff = normalizeAngle(bearing - turret.turretHeading);
    turret.turretHeading =
      Math.abs(diff) <= maxStep ? bearing : turret.turretHeading + Math.sign(diff) * maxStep;
    const aligned = Math.abs(normalizeAngle(bearing - turret.turretHeading)) <= TURRET_ALIGN_TOLERANCE_DEG * DEG_TO_RAD + 0.000001;
    if (turret.reloadLeft > 0 || !aligned) {
      continue;
    }
    fire(turret, best.x, best.z, weapon, rng, best.structure ? best.id : undefined);
    turret.reloadLeft = turret.upgrades.includes('fireRate')
      ? weapon.reloadSec * UPGRADE_FIRE_RATE_FACTOR
      : weapon.reloadSec;
  }
}

// Call before structures with hp <= 0 are removed. Only destroyed structures leave rubble; packed,
// dismantled and deployed ones are removed directly and never reach here.
export function collectRubble(world: WorldState): void {
  for (const structure of world.structures) {
    if (structure.hp > 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type) {
      continue;
    }
    world.rubble.push({
      x: structure.x,
      z: structure.z,
      radius: structureRadius(world, type) + RUBBLE_PADDING,
      ttl: RUBBLE_TTL_SEC,
    });
  }
}

export function updateRubble(world: WorldState): void {
  for (const item of world.rubble) {
    item.ttl -= DT;
  }
  world.rubble = world.rubble.filter((item) => item.ttl > 0);
}

export function isPackedUnit(unit: UnitState, world: WorldState): boolean {
  return world.unitTypes.get(unit.typeId)?.deploysTo != null;
}
