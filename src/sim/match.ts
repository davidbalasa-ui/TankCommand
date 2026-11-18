import { isCompetitor, sideOf } from './diplomacy';
import { crateOre, ensureSideStats, isFightingUnitType } from './economy';
import { isItemUnlocked } from './research';
import type { PlayerId, SimUnitType, WorldState } from './types';

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

/**
 * A side that still owns a pad but can never field a fighting unit again: no fighting units, nothing
 * on the way down or waiting to be placed, too little ore and metal (counting what dismantling its
 * other buildings and salvaging its workers would give back) to buy any fighting unit, and the map's
 * ore mined out so none can be earned. Skirmish counts such a side as eliminated (gameplay.md: "no
 * Landing Pads and no units able to fight or build a new pad"), so a mined-out map can't hang forever
 * on pads that will never field anything again. Missions keep the plain pad rule (sideAlive).
 */
export function sideStranded(world: WorldState, player: PlayerId): boolean {
  if (!oreMinedOut(world, player)) {
    return false;
  }
  const workers: SimUnitType[] = [];
  let carrying = false;
  for (const unit of world.units) {
    if (unit.owner !== player || unit.hp <= 0) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
    if (isFightingUnitType(type)) {
      return false;
    }
    if (type?.workerKind) {
      workers.push(type);
      carrying ||= (unit.job?.load ?? 0) > 0;
    }
  }
  if (
    carrying ||
    world.dropQueue.some((order) => order.owner === player) ||
    world.pendingKits.some((kit) => kit.owner === player)
  ) {
    return false;
  }
  const faction = world.factions.find((entry) => entry.player === player)?.faction;
  const stats = world.resources.find((entry) => entry.player === player);
  let ore = stats?.ore ?? 0;
  let metal = stats?.metal ?? 0;
  for (const structure of world.structures) {
    const type = structure.owner === player && structure.hp > 0 ? world.structureTypes.get(structure.typeId) : undefined;
    if (type && type.kind !== 'pad') {
      ore += Math.floor((type.cost.ore * type.dismantleRefundPercent) / 100);
      metal += Math.floor((type.cost.metal * type.dismantleRefundPercent) / 100);
    }
  }
  for (const type of workers) {
    ore += Math.floor((type.oreCost * type.salvageRefundPercent) / 100);
    metal += Math.floor((type.metalCost * type.salvageRefundPercent) / 100);
  }
  const affordable = (type: SimUnitType): boolean => type.oreCost <= ore && type.metalCost <= metal;
  const buyable = [...world.unitTypes.values()].filter(
    (type) => type.faction === faction && type.deploysTo === null && isItemUnlocked(world, player, type.id),
  );
  return !buyable.some((type) => isFightingUnitType(type) && affordable(type));
}

// While ore is left (its own crates included) a side may still dig its way back; a map made
// without ore (a scenario) never strands anyone.
function oreMinedOut(world: WorldState, player: PlayerId): boolean {
  const oreFields = world.deposits.filter((deposit) => deposit.kind === 'ore');
  return oreFields.length > 0 && oreFields.every((deposit) => deposit.amount <= 0 && crateOre(deposit, player) <= 0);
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
    if (sideAlive(world, player) && !sideStranded(world, player)) {
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
