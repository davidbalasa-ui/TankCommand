import { ensureSideStats, isFightingUnitType } from './economy';
import type { PlayerId, WorldState } from './types';

export function sideAlive(world: WorldState, player: PlayerId): boolean {
  for (const structure of world.structures) {
    if (structure.owner !== player || structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (type?.kind === 'pad') {
      return true;
    }
  }
  for (const unit of world.units) {
    if (unit.owner !== player || unit.hp <= 0) {
      continue;
    }
    if (isFightingUnitType(world.unitTypes.get(unit.typeId))) {
      return true;
    }
  }
  for (const kit of world.pendingKits) {
    if (kit.owner !== player) {
      continue;
    }
    const type = world.structureTypes.get(kit.structureTypeId);
    if (type?.kind === 'pad') {
      return true;
    }
  }
  return false;
}

export function updateMatchResult(world: WorldState): void {
  if (world.result || world.players.length === 0) {
    return;
  }
  const alive = world.players.filter((player) => sideAlive(world, player));
  if (alive.length === 0) {
    world.result = { winner: null };
    return;
  }
  if (alive.length === 1) {
    world.result = { winner: alive[0] ?? null };
  }
}

export function recordUnitLost(world: WorldState, player: PlayerId): void {
  const stats = ensureSideStats(world, player);
  stats.unitsLost += 1;
}
