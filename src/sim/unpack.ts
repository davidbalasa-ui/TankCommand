/**
 * Structures as vehicles (overhaul step 5). Every structure except the landing pad comes down at
 * the pad as a packed vehicle and drives out by itself to a suggested spot, where it unpacks:
 *
 * - a metal station heads for the nearest free metal site,
 * - a tower goes beside the pad on the side facing the enemy,
 * - anything else goes beside the pad, out of the way of the delivery lanes.
 *
 * The player can redirect it at any time: a move order on a packed vehicle becomes its new
 * unpack spot. If the spot is taken when it gets there, it looks for the nearest free one close
 * by; if there is none it stays packed and waits for orders.
 */
import { isHostile } from './diplomacy';
import { placementValidity, structureSize } from './spawn';
import type { SimStructureType, StructureState, UnitState, WorldState } from './types';

/** How close a packed vehicle has to get to its spot before it snaps there and unpacks. */
const ARRIVE_DISTANCE = 2.5;
/** How far round a taken spot it looks for another. */
const SEARCH_RADIUS = 18;
/** Gives up (stays packed) after this many failed tries to reach or use a spot. */
const MAX_TRIES = 4;

/** The packed vehicle type a structure lands as, or null (landing pads drop straight down). */
export function packedUnitFor(world: WorldState, structureTypeId: string): string | null {
  const type = world.structureTypes.get(structureTypeId);
  if (!type || type.kind === 'pad') {
    return null;
  }
  const ids = [...world.unitTypes.values()]
    .filter((unit) => unit.deploysTo === structureTypeId)
    .map((unit) => unit.id)
    .sort();
  return ids[0] ?? null;
}

export function deployTypeOf(world: WorldState, unit: UnitState): SimStructureType | null {
  const target = world.unitTypes.get(unit.typeId)?.deploysTo;
  return target ? (world.structureTypes.get(target) ?? null) : null;
}

/** Another packed vehicle of this side already heading for (about) this spot. */
function spotClaimed(world: WorldState, unit: UnitState, x: number, z: number, room: number): boolean {
  return world.units.some(
    (other) =>
      other.id !== unit.id &&
      other.owner === unit.owner &&
      other.hp > 0 &&
      other.deployTarget != null &&
      Math.hypot(other.deployTarget.x - x, other.deployTarget.z - z) < room,
  );
}

function usable(world: WorldState, unit: UnitState, type: SimStructureType, x: number, z: number): boolean {
  const size = structureSize(world, type);
  const room = Math.max(size.x, size.z) + 2;
  return placementValidity(world, unit.owner, type, x, z, unit.id).valid && !spotClaimed(world, unit, x, z, room);
}

/** The nearest free spot to (x, z), searching outward in rings; null when there is none. */
export function nearestFreeSpot(
  world: WorldState,
  unit: UnitState,
  type: SimStructureType,
  x: number,
  z: number,
  startAngle = 0,
): { x: number; z: number } | null {
  if (type.buildOnMetalDeposit) {
    return freeMetalSite(world, unit, type, x, z, SEARCH_RADIUS);
  }
  if (usable(world, unit, type, x, z)) {
    return { x, z };
  }
  for (let radius = 3; radius <= SEARCH_RADIUS; radius += 3) {
    const steps = Math.max(8, Math.round(radius * 2));
    for (let step = 0; step < steps; step += 1) {
      // Alternate either side of the preferred direction so the nearest good side wins.
      const k = Math.ceil(step / 2) * (step % 2 === 0 ? 1 : -1);
      const angle = startAngle + (k / steps) * Math.PI * 2;
      const px = x + Math.cos(angle) * radius;
      const pz = z + Math.sin(angle) * radius;
      if (usable(world, unit, type, px, pz)) {
        return { x: px, z: pz };
      }
    }
  }
  return null;
}

/** The nearest metal site with no station on it (and none on its way), within `range` of (x, z). */
function freeMetalSite(
  world: WorldState,
  unit: UnitState,
  type: SimStructureType,
  x: number,
  z: number,
  range: number,
): { x: number; z: number } | null {
  const sites = world.deposits
    .filter((deposit) => deposit.kind === 'metal' && deposit.amount > 0)
    .filter((deposit) => !world.structures.some((item) => item.hp > 0 && item.depositId === deposit.id))
    .filter((deposit) => Math.hypot(deposit.x - x, deposit.z - z) <= range)
    .sort((a, b) => Math.hypot(a.x - x, a.z - z) - Math.hypot(b.x - x, b.z - z) || a.id - b.id);
  const site = sites.find((deposit) => usable(world, unit, type, deposit.x, deposit.z));
  return site ? { x: site.x, z: site.z } : null;
}

/** Where a freshly landed packed vehicle should unpack, or null when nowhere suits. */
export function suggestDeploySpot(
  world: WorldState,
  unit: UnitState,
  pad: StructureState,
): { x: number; z: number } | null {
  const type = deployTypeOf(world, unit);
  const padType = world.structureTypes.get(pad.typeId);
  if (!type || !padType) {
    return null;
  }
  if (type.buildOnMetalDeposit) {
    return freeMetalSite(world, unit, type, pad.x, pad.z, Number.POSITIVE_INFINITY);
  }
  // Face the nearest enemy building (or the middle of the map when none is left).
  const enemy = world.structures
    .filter((item) => item.hp > 0 && isHostile(world, unit.owner, item.owner))
    .sort((a, b) => Math.hypot(a.x - pad.x, a.z - pad.z) - Math.hypot(b.x - pad.x, b.z - pad.z) || a.id - b.id)[0];
  const toward = enemy ? Math.atan2(enemy.z - pad.z, enemy.x - pad.x) : Math.atan2(-pad.z, -pad.x);
  const padSize = structureSize(world, padType);
  const size = structureSize(world, type);
  const away = Math.max(padSize.x, padSize.z) / 2 + Math.max(size.x, size.z) / 2 + 6;
  // Towers stand toward the enemy; everything else beside the pad, alternating sides.
  const angle = type.kind === 'turret' ? toward : toward + (unit.id % 2 === 0 ? Math.PI / 2 : -Math.PI / 2);
  return nearestFreeSpot(world, unit, type, pad.x + Math.cos(angle) * away, pad.z + Math.sin(angle) * away, angle);
}

/** Sends a packed vehicle to unpack at (x, z): it drives there, then unpacks. */
export function setDeployTarget(unit: UnitState, x: number, z: number): void {
  unit.deployTarget = { x, z, tries: 0 };
  unit.order = { kind: 'move', x, z, queue: false };
  unit.path = [];
  unit.replans = 0;
  unit.stuckTicks = 0;
}

/**
 * Packed vehicles with a spot: once there, snap onto it and start unpacking (updateDeploys
 * finishes the job). A taken spot is swapped for the nearest free one; a vehicle that can't get
 * anywhere gives up and waits, packed, for orders.
 */
export function updateAutoDeploy(world: WorldState): void {
  for (const unit of world.units) {
    const target = unit.deployTarget;
    if (!target || unit.hp <= 0 || unit.transform) {
      continue;
    }
    const type = deployTypeOf(world, unit);
    const unitType = world.unitTypes.get(unit.typeId);
    if (!type || !unitType) {
      unit.deployTarget = null;
      continue;
    }
    const distance = Math.hypot(unit.x - target.x, unit.z - target.z);
    if (distance <= ARRIVE_DISTANCE) {
      if (placementValidity(world, unit.owner, type, target.x, target.z, unit.id).valid) {
        unit.x = target.x;
        unit.z = target.z;
        unit.order = { kind: 'idle' };
        unit.path = [];
        unit.speed = 0;
        unit.transform = { left: unitType.deploySec };
        unit.deployTarget = null;
        continue;
      }
      retarget(world, unit, type, target.x, target.z);
      continue;
    }
    if (unit.order.kind === 'idle') {
      // Stopped short (blocked, or the route ran out): try again, then settle for a spot nearby.
      target.tries += 1;
      if (target.tries > MAX_TRIES) {
        retarget(world, unit, type, unit.x, unit.z);
      } else {
        unit.order = { kind: 'move', x: target.x, z: target.z, queue: false };
        unit.path = [];
      }
    }
  }
}

function retarget(world: WorldState, unit: UnitState, type: SimStructureType, x: number, z: number): void {
  const tries = (unit.deployTarget?.tries ?? 0) + 1;
  const spot = tries > MAX_TRIES * 2 ? null : nearestFreeSpot(world, unit, type, x, z);
  if (!spot) {
    unit.deployTarget = null;
    unit.order = { kind: 'idle' };
    unit.path = [];
    return;
  }
  setDeployTarget(unit, spot.x, spot.z);
  if (unit.deployTarget) {
    unit.deployTarget.tries = tries;
  }
}

export function isPackedOnTheWay(unit: UnitState): boolean {
  return unit.deployTarget != null || unit.transform != null;
}

