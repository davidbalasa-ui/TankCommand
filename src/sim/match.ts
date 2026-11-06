import { isCompetitor, sideOf } from './diplomacy';
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

// Only human and AI sides count; neutral sides never decide victory. A team wins when every
// other team is eliminated. `winner` is the lowest player id of the winning team.
export function updateMatchResult(world: WorldState): void {
  if (world.result) {
    return;
  }
  const competitors = world.players.filter((player) => isCompetitor(sideOf(world, player)));
  if (competitors.length === 0) {
    return;
  }
  const aliveTeams = new Set<number>();
  const aliveByTeam = new Map<number, number>();
  for (const player of competitors) {
    if (sideAlive(world, player)) {
      const team = sideOf(world, player)?.team ?? player;
      aliveTeams.add(team);
      if (!aliveByTeam.has(team)) {
        aliveByTeam.set(team, player);
      }
    }
  }
  if (aliveTeams.size === 0) {
    world.result = { winner: null };
    return;
  }
  if (aliveTeams.size === 1) {
    const [team] = [...aliveTeams];
    world.result = { winner: team === undefined ? null : (aliveByTeam.get(team) ?? null) };
  }
}

export function recordUnitLost(world: WorldState, player: PlayerId): void {
  const stats = ensureSideStats(world, player);
  stats.unitsLost += 1;
}
