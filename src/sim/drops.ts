import { flyNewAircraftHome, hasFreeAirSlot } from './air';
import { missionAllows } from './triggers';
import { PAD_CLEAR_TIMEOUT_SEC, PAD_LAND_SEC, padLayout, padOccupied, padRallySpot } from './pad';
import { SIM_TICK_HZ } from './constants';
import { addStructure, addUnit, placementValidity, unitCount } from './spawn';
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
  StructureState,
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
  | 'notInMission'
  | 'cap'
  | 'noAirBase';

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
  if ((unit && unit.deploysTo !== null) || (!unit && structure && !structure.buyable)) {
    return { item: null, reason: 'notInRoster' };
  }
  if (!missionAllows(world, player, itemId)) {
    return { item: null, reason: 'notInMission' };
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
  if (resolved.item.kind === 'unit' && resolved.item.unit.air && !hasFreeAirSlot(world, player)) {
    return { item: resolved.item, reason: 'noAirBase' };
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
  if (order.landingSec !== undefined) {
    setOutcome(world, command.tick, 'cancel', false, 'landing');
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

export function addBeam(world: WorldState, owner: PlayerId, x: number, z: number): void {
  world.dropBeams.push({ owner, x, z, ttl: DROP_BEAM_TTL_SEC });
}

// The descent is over: the delivery is on the pad.
function touchDown(
  world: WorldState,
  player: PlayerId,
  pad: StructureState,
  item: ResolvedItem,
): boolean {
  if (item.kind === 'unit') {
    if (unitCount(world, player) >= UNIT_CAP) {
      return false;
    }
    const layout = padLayout(world, pad);
    const spawned = addUnit(world, {
      owner: player,
      typeId: item.unit.id,
      x: pad.x,
      z: pad.z,
      heading: layout.facing,
    });
    if (!spawned) {
      return false;
    }
    if (spawned.air) {
      flyNewAircraftHome(world, spawned);
    } else {
      // Park beside earlier arrivals rather than on top of them.
      const spot = padRallySpot(world, pad, spawned.id);
      spawned.order = { kind: 'move', x: spot.x, z: spot.z, queue: false };
    }
    pad.padUnitId = spawned.id;
    pad.padClearLeft = PAD_CLEAR_TIMEOUT_SEC;
    const stats = ensureSideStats(world, player);
    stats.unitsBuilt += 1;
    addBeam(world, player, pad.x, pad.z);
    addAlert(world, 'dropArrived', player, pad.x, pad.z);
    return true;
  }
  const kit: PendingKit = {
    id: world.nextId,
    owner: player,
    structureTypeId: item.structure.id,
  };
  world.nextId += 1;
  world.pendingKits.push(kit);
  addBeam(world, player, pad.x, pad.z);
  addAlert(world, 'dropArrived', player, pad.x, pad.z);
  return true;
}

// Deliveries come down one at a time per side, in the order they were bought. When an order's
// timer runs out it waits for its pad to be clear, then descends onto the pad's landing circle
// (PAD_LAND_SEC). A unit then drives off the exit edge to the rally point; the pad stays busy
// until it has left, so arrivals never stack up on top of each other.
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
    let pad = world.structures.find(
      (structure) => structure.id === first.padId && structure.owner === player && structure.hp > 0,
    );
    if (!pad) {
      const replacement = firstOwnPad(world, player);
      if (replacement === null) {
        first.landingSec = undefined;
        continue;
      }
      first.padId = replacement;
      first.landingSec = undefined;
      pad = world.structures.find((structure) => structure.id === replacement);
      if (!pad) {
        continue;
      }
    }

    if (first.landingSec === undefined) {
      first.remainingSec = Math.max(0, first.remainingSec - DT);
      if (first.remainingSec > 0) {
        continue;
      }
      const ready = resolveItem(world, player, first.itemId).item;
      if (!ready) {
        world.dropQueue = world.dropQueue.filter((order) => order.id !== first.id);
        continue;
      }
      if (padOccupied(world, pad)) {
        continue;
      }
      if (ready.kind === 'unit' && unitCount(world, player) >= UNIT_CAP) {
        continue;
      }
      first.landingSec = 0;
      continue;
    }

    first.landingSec = Math.min(PAD_LAND_SEC, first.landingSec + DT);
    if (first.landingSec < PAD_LAND_SEC) {
      continue;
    }
    const item = resolveItem(world, player, first.itemId).item;
    if (!item) {
      world.dropQueue = world.dropQueue.filter((order) => order.id !== first.id);
      continue;
    }
    if (!touchDown(world, player, pad, item)) {
      continue;
    }
    world.dropQueue = world.dropQueue.filter((order) => order.id !== first.id);
  }
}

export function itemName(world: WorldState, itemId: string): string {
  return world.unitTypes.get(itemId)?.id ?? world.structureTypes.get(itemId)?.name ?? itemId;
}
