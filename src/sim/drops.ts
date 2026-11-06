import { SIM_TICK_HZ } from './constants';
import { findNearestFreeSpot, addStructure, addUnit, placementValidity, unitCount } from './spawn';
import { addAlert, ensureSideStats } from './economy';
import { isItemUnlocked } from './research';
import {
  DROP_BEAM_TTL_SEC,
  UNIT_CAP,
} from './tuning';
import type { Command } from './commands';
import type {
  CommandOutcome,
  DropOrder,
  PendingKit,
  PlayerId,
  SimStructureType,
  SimUnitType,
  WorldState,
} from './types';

const DT = 1 / SIM_TICK_HZ;

type ResolvedItem =
  | { kind: 'unit'; unit: SimUnitType }
  | { kind: 'structure'; structure: SimStructureType };

type BuyReason =
  | 'ok'
  | 'unknownItem'
  | 'notInRoster'
  | 'padGone'
  | 'unaffordable'
  | 'locked'
  | 'cap';

export function setOutcome(
  world: WorldState,
  tick: number,
  kind: string,
  ok: boolean,
  reason: string,
): void {
  const outcome: CommandOutcome = { tick, kind, ok, reason };
  world.lastCommandOutcome = outcome;
}

function factionOf(world: WorldState, player: PlayerId): 'human' | 'alien' | null {
  return world.factions.find((entry) => entry.player === player)?.faction ?? null;
}

function resolveItem(
  world: WorldState,
  player: PlayerId,
  itemId: string,
): { item: ResolvedItem | null; reason: BuyReason } {
  const unit = world.unitTypes.get(itemId);
  const structure = world.structureTypes.get(itemId);
  if (!unit && !structure) {
    return { item: null, reason: 'unknownItem' };
  }
  const faction = factionOf(world, player);
  if (faction) {
    if (unit && unit.faction !== faction) {
      return { item: null, reason: 'notInRoster' };
    }
    if (!unit && structure && structure.faction !== faction) {
      return { item: null, reason: 'notInRoster' };
    }
  }
  if (unit && unit.deploysTo !== null) {
    return { item: null, reason: 'notInRoster' };
  }
  if (!isItemUnlocked(world, player, itemId)) {
    return { item: null, reason: 'locked' };
  }
  if (unit) {
    return { item: { kind: 'unit', unit }, reason: 'ok' };
  }
  if (structure) {
    return { item: { kind: 'structure', structure }, reason: 'ok' };
  }
  return { item: null, reason: 'unknownItem' };
}

function ownPad(world: WorldState, player: PlayerId, padId: number): boolean {
  const structure = world.structures.find(
    (item) => item.id === padId && item.owner === player && item.hp > 0,
  );
  if (!structure) {
    return false;
  }
  const type = world.structureTypes.get(structure.typeId);
  return type?.kind === 'pad';
}

function queuedUnits(world: WorldState, player: PlayerId): number {
  return world.dropQueue.filter(
    (order) => order.owner === player && order.itemKind === 'unit',
  ).length;
}

function itemCost(item: ResolvedItem): { ore: number; metal: number; deliverySec: number } {
  if (item.kind === 'unit') {
    return {
      ore: item.unit.oreCost,
      metal: item.unit.metalCost,
      deliverySec: item.unit.deliverySec,
    };
  }
  return {
    ore: item.structure.cost.ore,
    metal: item.structure.cost.metal,
    deliverySec: item.structure.deliverySec,
  };
}

function rejection(
  world: WorldState,
  player: PlayerId,
  itemId: string,
  padId: number,
): { item: ResolvedItem | null; reason: BuyReason } {
  const resolved = resolveItem(world, player, itemId);
  if (!resolved.item) {
    return resolved;
  }
  if (!ownPad(world, player, padId)) {
    return { item: resolved.item, reason: 'padGone' };
  }
  const stats = ensureSideStats(world, player);
  const cost = itemCost(resolved.item);
  if (stats.ore < cost.ore || stats.metal < cost.metal) {
    return { item: resolved.item, reason: 'unaffordable' };
  }
  if (
    resolved.item.kind === 'unit' &&
    unitCount(world, player) + queuedUnits(world, player) >= UNIT_CAP
  ) {
    return { item: resolved.item, reason: 'cap' };
  }
  return { item: resolved.item, reason: 'ok' };
}

export function buyRejectionReason(
  world: WorldState,
  player: PlayerId,
  itemId: string,
  padId: number,
): string | null {
  const result = rejection(world, player, itemId, padId);
  return result.reason === 'ok' ? null : result.reason;
}

export function applyBuyCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'buy' }>,
): void {
  const result = rejection(world, command.issuer, command.itemId, command.padId);
  if (!result.item || result.reason !== 'ok') {
    setOutcome(world, command.tick, 'buy', false, result.reason);
    return;
  }
  const stats = ensureSideStats(world, command.issuer);
  const item = result.item;
  const cost = itemCost(item);
  stats.ore -= cost.ore;
  stats.metal -= cost.metal;
  const order: DropOrder = {
    id: world.nextId,
    owner: command.issuer,
    itemId: command.itemId,
    itemKind: item.kind,
    padId: command.padId,
    remainingSec: cost.deliverySec,
    totalSec: cost.deliverySec,
    costOre: cost.ore,
    costMetal: cost.metal,
  };
  world.nextId += 1;
  world.dropQueue.push(order);
  setOutcome(world, command.tick, 'buy', true, 'ok');
}

export function applyCancelCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'cancel' }>,
): void {
  const order = world.dropQueue.find(
    (item) => item.id === command.orderId && item.owner === command.issuer,
  );
  if (!order) {
    setOutcome(world, command.tick, 'cancel', false, 'unknownOrder');
    return;
  }
  const stats = ensureSideStats(world, command.issuer);
  stats.ore += order.costOre;
  stats.metal += order.costMetal;
  world.dropQueue = world.dropQueue.filter((item) => item.id !== order.id);
  setOutcome(world, command.tick, 'cancel', true, 'ok');
}

export function applyPlaceKitCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'placeKit' }>,
): void {
  const kit = world.pendingKits.find(
    (item) => item.id === command.kitId && item.owner === command.issuer,
  );
  if (!kit) {
    setOutcome(world, command.tick, 'placeKit', false, 'unknownKit');
    return;
  }
  const type = world.structureTypes.get(kit.structureTypeId);
  if (!type) {
    setOutcome(world, command.tick, 'placeKit', false, 'unknownStructure');
    return;
  }
  const validity = placementValidity(world, command.issuer, type, command.x, command.z);
  if (!validity.valid) {
    setOutcome(world, command.tick, 'placeKit', false, validity.reason);
    return;
  }
  let x = command.x;
  let z = command.z;
  if (type.buildOnMetalDeposit && validity.depositId !== null) {
    const deposit = world.deposits.find((item) => item.id === validity.depositId);
    if (deposit) {
      x = deposit.x;
      z = deposit.z;
    }
  }
  const structure = addStructure(world, {
    owner: command.issuer,
    typeId: kit.structureTypeId,
    x,
    z,
    depositId: validity.depositId,
  });
  if (!structure) {
    setOutcome(world, command.tick, 'placeKit', false, 'unknownStructure');
    return;
  }
  world.pendingKits = world.pendingKits.filter((item) => item.id !== kit.id);
  setOutcome(world, command.tick, 'placeKit', true, 'ok');
}

function firstOwnPad(world: WorldState, player: PlayerId): number | null {
  let best: number | null = null;
  for (const structure of world.structures) {
    if (structure.owner !== player || structure.hp <= 0) {
      continue;
    }
    const type = world.structureTypes.get(structure.typeId);
    if (!type || type.kind !== 'pad') {
      continue;
    }
    if (best === null || structure.id < best) {
      best = structure.id;
    }
  }
  return best;
}

function addBeam(world: WorldState, owner: PlayerId, x: number, z: number): void {
  world.dropBeams.push({ owner, x, z, ttl: DROP_BEAM_TTL_SEC });
}

export function updateDropQueues(world: WorldState): void {
  const players = [...world.players].sort((a, b) => a - b);
  for (const player of players) {
    const waiting = world.dropQueue
      .filter((order) => order.owner === player)
      .sort((a, b) => a.id - b.id);
    const first = waiting[0];
    if (!first) {
      continue;
    }
    const pad = world.structures.find(
      (structure) => structure.id === first.padId && structure.owner === player && structure.hp > 0,
    );
    const replacement = pad ? null : firstOwnPad(world, player);
    if (!pad && replacement === null) {
      continue;
    }
    if (!pad && replacement !== null) {
      first.padId = replacement;
    }
    first.remainingSec = Math.max(0, first.remainingSec - DT);
    if (first.remainingSec > 0) {
      continue;
    }

    const item = resolveItem(world, player, first.itemId).item;
    if (!item) {
      world.dropQueue = world.dropQueue.filter((order) => order.id !== first.id);
      continue;
    }
    const padStructure = world.structures.find((structure) => structure.id === first.padId);
    if (!padStructure) {
      continue;
    }
    if (item.kind === 'unit') {
      if (unitCount(world, player) >= UNIT_CAP) {
        continue;
      }
      const spot = findNearestFreeSpot(world, padStructure.x, padStructure.z);
      const spawned = addUnit(world, {
        owner: player,
        typeId: item.unit.id,
        x: spot.x,
        z: spot.z,
        heading: 0,
      });
      if (!spawned) {
        continue;
      }
      const stats = ensureSideStats(world, player);
      stats.unitsBuilt += 1;
      addBeam(world, player, spot.x, spot.z);
      addAlert(world, 'dropArrived', player, spot.x, spot.z);
      world.dropQueue = world.dropQueue.filter((order) => order.id !== first.id);
      continue;
    }

    const kit: PendingKit = {
      id: world.nextId,
      owner: player,
      structureTypeId: item.structure.id,
    };
    world.nextId += 1;
    world.pendingKits.push(kit);
    addBeam(world, player, padStructure.x, padStructure.z);
    addAlert(world, 'dropArrived', player, padStructure.x, padStructure.z);
    world.dropQueue = world.dropQueue.filter((order) => order.id !== first.id);
  }
}

export function itemName(world: WorldState, itemId: string): string {
  return world.unitTypes.get(itemId)?.id ?? world.structureTypes.get(itemId)?.name ?? itemId;
}
