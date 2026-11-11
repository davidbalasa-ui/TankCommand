import { setOutcome } from './drops';
import { SIM_TICK_HZ } from './constants';
import type { Command } from './commands';
import type { PlayerId, StructureState, UnitState, WeaponStats, WeaponTarget, WorldState } from './types';

const DT = 1 / SIM_TICK_HZ;
const LAND_DISTANCE = 1.5;
const FUEL_MARGIN = 1.25;
const DEFAULT_TARGETS: readonly WeaponTarget[] = ['ground', 'structure'];

export function isAirborne(unit: UnitState): boolean {
  return unit.air !== null && (unit.air.mode === 'flying' || unit.air.mode === 'returning');
}

/** What a weapon may hit: 'air' for airborne units, 'ground' for ground and parked ones. */
export function weaponCanHit(
  weapon: WeaponStats,
  target: 'airborne' | 'ground' | 'structure',
): boolean {
  const targets = weapon.targets ?? DEFAULT_TARGETS;
  const need = target === 'airborne' ? 'air' : target;
  return targets.includes(need);
}

export function unitTargetKind(unit: UnitState): 'airborne' | 'ground' {
  return isAirborne(unit) ? 'airborne' : 'ground';
}

function baseCapacity(world: WorldState, base: StructureState): number {
  return world.structureTypes.get(base.typeId)?.airCapacity ?? 0;
}

function housed(world: WorldState, base: StructureState): number {
  let count = 0;
  for (const unit of world.units) {
    if (unit.hp > 0 && unit.air?.homeId === base.id) {
      count += 1;
    }
  }
  return count;
}

export function airBases(world: WorldState, player: PlayerId): StructureState[] {
  return world.structures.filter(
    (s) => s.hp > 0 && s.owner === player && !s.work && baseCapacity(world, s) > 0,
  );
}

export function hasFreeAirSlot(world: WorldState, player: PlayerId): boolean {
  return airBases(world, player).some((b) => housed(world, b) < baseCapacity(world, b));
}

function nearestBase(world: WorldState, unit: UnitState, needFree: boolean): StructureState | null {
  let best: StructureState | null = null;
  let bestD = Number.POSITIVE_INFINITY;
  for (const base of airBases(world, unit.owner)) {
    if (needFree && housed(world, base) >= baseCapacity(world, base)) {
      continue;
    }
    const d = Math.hypot(base.x - unit.x, base.z - unit.z);
    if (d < bestD) {
      best = base;
      bestD = d;
    }
  }
  return best;
}

/** Call right after an aircraft is delivered: it parks at the nearest base with room. */
export function assignHome(world: WorldState, unit: UnitState): void {
  if (!unit.air) {
    return;
  }
  const base = nearestBase(world, unit, true);
  if (base) {
    unit.air.homeId = base.id;
    unit.x = base.x;
    unit.z = base.z;
  }
  unit.air.mode = 'parked';
}

/**
 * Call when an aircraft has just come down on a landing pad: it takes off at once and flies to
 * the nearest base with room, where it lands and parks.
 */
export function flyNewAircraftHome(world: WorldState, unit: UnitState): void {
  if (!unit.air) {
    return;
  }
  const base = nearestBase(world, unit, true);
  unit.air.homeId = base ? base.id : null;
  if (!base) {
    unit.air.mode = 'parked';
    return;
  }
  sendHome(world, unit);
}

export function applyAirCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'air' }>,
): void {
  let ok = false;
  for (const id of command.unitIds) {
    const unit = world.units.find((u) => u.id === id && u.owner === command.issuer && u.hp > 0);
    if (!unit?.air) {
      continue;
    }
    if (command.action === 'launch' && unit.air.mode === 'parked') {
      const home = world.structures.find((s) => s.id === unit.air?.homeId && s.hp > 0);
      if (home) {
        unit.air.mode = 'flying';
        unit.order = { kind: 'idle' };
        ok = true;
      }
    } else if (command.action === 'recall' && isAirborne(unit)) {
      sendHome(world, unit);
      ok = true;
    }
  }
  setOutcome(world, command.tick, 'air', ok, ok ? 'ok' : 'nothingToDo');
}

function sendHome(world: WorldState, unit: UnitState): void {
  const air = unit.air;
  if (!air) {
    return;
  }
  let home = world.structures.find((s) => s.id === air.homeId && s.hp > 0) ?? null;
  if (!home) {
    home = nearestBase(world, unit, false);
    air.homeId = home ? home.id : null;
  }
  if (!home) {
    return;
  }
  air.mode = 'returning';
  unit.order = { kind: 'move', x: home.x, z: home.z, queue: false };
  unit.path = [];
}

export function updateAir(world: WorldState): void {
  for (const unit of world.units) {
    const air = unit.air;
    const type = world.unitTypes.get(unit.typeId);
    if (!air || !type?.air || unit.hp <= 0) {
      continue;
    }
    if (air.mode === 'parked' || air.mode === 'rearming') {
      const homeAlive = world.structures.some((s) => s.id === air.homeId && s.hp > 0);
      if (!homeAlive) {
        const base = nearestBase(world, unit, true);
        air.homeId = base ? base.id : null;
        if (base) {
          unit.x = base.x;
          unit.z = base.z;
        }
      }
    }
    if (air.mode === 'parked') {
      continue;
    }
    if (air.mode === 'rearming') {
      air.rearmLeft = Math.max(0, air.rearmLeft - DT);
      if (air.rearmLeft <= 0) {
        air.ammo = type.air.ammo;
        air.fuelLeft = type.air.fuelSec;
        air.mode = 'parked';
      }
      continue;
    }
    air.fuelLeft -= DT;
    if (air.fuelLeft <= 0) {
      unit.hp = 0; // out of fuel away from base: crashes
      continue;
    }
    if (air.mode === 'flying') {
      const home = world.structures.find((s) => s.id === air.homeId && s.hp > 0);
      const distance = home ? Math.hypot(home.x - unit.x, home.z - unit.z) : 0;
      const needFuel = distance / Math.max(0.1, type.topSpeed) * FUEL_MARGIN + 1;
      const dry = type.weapon !== null && air.ammo <= 0;
      if (dry || air.fuelLeft <= needFuel) {
        sendHome(world, unit);
      }
      continue;
    }
    // returning: land when over the base
    const home = world.structures.find((s) => s.id === air.homeId && s.hp > 0);
    if (!home) {
      sendHome(world, unit);
      continue;
    }
    if (Math.hypot(home.x - unit.x, home.z - unit.z) <= LAND_DISTANCE) {
      unit.x = home.x;
      unit.z = home.z;
      unit.speed = 0;
      unit.order = { kind: 'idle' };
      unit.path = [];
      air.mode = 'rearming';
      air.rearmLeft = type.air.rearmSec;
    }
  }
}
