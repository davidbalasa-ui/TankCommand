import { SIM_TICK_HZ } from './constants';
import { heightAt } from './map';
import {
  ALERT_TTL_SEC,
  DEPOSIT_REACH,
  ORE_CRATE_SIZE,
  ORE_MAX_CRATES,
  UNIT_CAP,
} from './tuning';
import type { Command } from './commands';
import type {
  AlertKind,
  CommandOutcome,
  DepositState,
  PlayerId,
  SimStructureType,
  SideStats,
  SimUnitType,
  StructureState,
  UnitState,
  WorldState,
} from './types';

const DT = 1 / SIM_TICK_HZ;

function outcome(world: WorldState, tick: number, kind: string, ok: boolean, reason: string): void {
  const result: CommandOutcome = { tick, kind, ok, reason };
  world.lastCommandOutcome = result;
}

export function ensureSideStats(world: WorldState, player: PlayerId): SideStats {
  const existing = world.resources.find((stats) => stats.player === player);
  if (existing) {
    return existing;
  }
  const created: SideStats = {
    player,
    ore: 0,
    metal: 0,
    oreGathered: 0,
    metalGathered: 0,
    unitsBuilt: 0,
    unitsLost: 0,
  };
  world.resources.push(created);
  world.resources.sort((a, b) => a.player - b.player);
  return created;
}

export function sideStats(world: WorldState, player: PlayerId): SideStats | undefined {
  return world.resources.find((stats) => stats.player === player);
}

export function creditOre(world: WorldState, player: PlayerId, amount: number): void {
  if (amount <= 0) {
    return;
  }
  const stats = ensureSideStats(world, player);
  stats.ore += amount;
  stats.oreGathered += amount;
}

export function creditMetal(world: WorldState, player: PlayerId, amount: number): void {
  if (amount <= 0) {
    return;
  }
  const stats = ensureSideStats(world, player);
  stats.metal += amount;
  stats.metalGathered += amount;
}

export function addAlert(
  world: WorldState,
  kind: AlertKind,
  owner: PlayerId,
  x: number,
  z: number,
): void {
  world.alerts.push({ kind, owner, x, z, ttl: ALERT_TTL_SEC });
  if (world.alerts.length > 64) {
    world.alerts.splice(0, world.alerts.length - 64);
  }
}

export function updateAlerts(world: WorldState): void {
  for (const alert of world.alerts) {
    alert.ttl -= DT;
  }
  world.alerts = world.alerts.filter((alert) => alert.ttl > 0);
}

export function structureTypeOf(
  world: WorldState,
  structure: StructureState,
): SimStructureType | undefined {
  return world.structureTypes.get(structure.typeId);
}

export function nearestPad(
  world: WorldState,
  owner: PlayerId,
  x: number,
  z: number,
): StructureState | null {
  let best: StructureState | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const structure of world.structures) {
    if (structure.owner !== owner || structure.hp <= 0) {
      continue;
    }
    const type = structureTypeOf(world, structure);
    if (!type || type.kind !== 'pad') {
      continue;
    }
    const distance = Math.hypot(structure.x - x, structure.z - z);
    if (distance < bestDistance) {
      best = structure;
      bestDistance = distance;
    }
  }
  return best;
}

export function cloneDeposit(deposit: DepositState): DepositState {
  return deposit.crates
    ? { ...deposit, crates: deposit.crates.map((pile) => ({ ...pile })) }
    : { ...deposit };
}

/** Ore a side has packed into crates beside this deposit. */
export function crateOre(deposit: DepositState, owner: PlayerId): number {
  return deposit.crates?.find((pile) => pile.owner === owner)?.ore ?? 0;
}

/** Number of crates to show for a side's pile (a part-filled crate counts). */
export function crateCount(deposit: DepositState, owner: PlayerId): number {
  return Math.ceil(crateOre(deposit, owner) / ORE_CRATE_SIZE - 1e-6);
}

export function crateRoom(deposit: DepositState, owner: PlayerId): number {
  return Math.max(0, ORE_MAX_CRATES * ORE_CRATE_SIZE - crateOre(deposit, owner));
}

function addCrateOre(deposit: DepositState, owner: PlayerId, ore: number): void {
  const crates = deposit.crates ?? (deposit.crates = []);
  const pile = crates.find((item) => item.owner === owner);
  if (pile) {
    pile.ore += ore;
  } else {
    crates.push({ owner, ore });
    crates.sort((a, b) => a.owner - b.owner);
  }
}

/** Take up to `max` ore (whole crates first) from a side's pile. Returns what was taken. */
export function takeCrateOre(deposit: DepositState, owner: PlayerId, max: number): number {
  const pile = deposit.crates?.find((item) => item.owner === owner);
  if (!pile || pile.ore <= 1e-6) {
    return 0;
  }
  const taken = Math.min(pile.ore, max);
  pile.ore -= taken;
  if (pile.ore <= 1e-6 && deposit.crates) {
    deposit.crates = deposit.crates.filter((item) => item !== pile);
    if (deposit.crates.length === 0) {
      delete deposit.crates;
    }
  }
  return taken;
}

export function findDeposit(world: WorldState, id: number): DepositState | undefined {
  return world.deposits.find((deposit) => deposit.id === id);
}

export function isFightingUnitType(type: SimUnitType | undefined): boolean {
  return type !== undefined && type.weapon !== null && type.weapon.damage > 0;
}

export function updateMetalStations(world: WorldState): void {
  for (const structure of world.structures) {
    if (structure.hp <= 0) {
      continue;
    }
    const type = structureTypeOf(world, structure);
    if (!type || type.kind !== 'metalStation' || type.metalRatePerSec <= 0) {
      continue;
    }
    if (type.containerSize <= 0 || type.maxContainers <= 0) {
      continue;
    }
    const deposit =
      structure.depositId === null
        ? undefined
        : world.deposits.find((item) => item.id === structure.depositId);
    if (!deposit || deposit.kind !== 'metal' || deposit.amount <= 0) {
      continue;
    }
    const totalCapacity = type.maxContainers * type.containerSize;
    const current = structure.containers * type.containerSize + structure.fill;
    const room = totalCapacity - current;
    if (room <= 0) {
      continue;
    }
    const extracted = Math.min(type.metalRatePerSec * DT, deposit.amount, room);
    deposit.amount = Math.max(0, deposit.amount - extracted);
    structure.fill += extracted;
    while (
      structure.fill + 0.000001 >= type.containerSize &&
      structure.containers < type.maxContainers
    ) {
      structure.fill -= type.containerSize;
      structure.containers += 1;
    }
  }
}

function ownedUnits(world: WorldState, issuer: PlayerId, ids: readonly number[]): UnitState[] {
  const set = new Set(ids);
  return world.units.filter(
    (unit) => set.has(unit.id) && unit.owner === issuer && unit.hp > 0,
  );
}

export function applyMineCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'mine' }>,
): void {
  const deposit = findDeposit(world, command.depositId);
  if (!deposit) {
    outcome(world, command.tick, 'mine', false, 'depositMissing');
    return;
  }
  let applied = false;
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    const type = world.unitTypes.get(unit.typeId);
    if (!type || type.workerKind !== 'oreMiner') {
      continue;
    }
    const load = unit.job?.kind === 'oreMiner' ? unit.job.load : 0;
    const progress = unit.job?.kind === 'oreMiner' ? unit.job.progress : 0;
    unit.job = {
      kind: 'oreMiner',
      targetId: deposit.id,
      stage: 'toDeposit',
      load,
      progress,
      reportedEmpty: false,
    };
    unit.order = { kind: 'idle' };
    unit.path = [];
    unit.speed = 0;
    unit.stance = 'free';
    applied = true;
  }
  outcome(world, command.tick, 'mine', applied, applied ? 'ok' : 'noMiner');
}

export function applyAssignCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'assign' }>,
): void {
  const station = world.structures.find(
    (structure) => structure.id === command.stationId && structure.owner === command.issuer,
  );
  const stationType = station ? structureTypeOf(world, station) : undefined;
  if (!station || !stationType || stationType.kind !== 'metalStation' || station.hp <= 0) {
    outcome(world, command.tick, 'assign', false, 'stationMissing');
    return;
  }
  let applied = false;
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    const type = world.unitTypes.get(unit.typeId);
    if (!type || type.workerKind !== 'tug') {
      continue;
    }
    const load = unit.job?.kind === 'tug' ? unit.job.load : 0;
    unit.job = {
      kind: 'tug',
      targetId: station.id,
      source: 'station',
      stage: load > 0 ? 'toPad' : 'toStation',
      load,
      cargo: unit.job?.kind === 'tug' ? unit.job.cargo : undefined,
      progress: 0,
      reportedEmpty: false,
    };
    unit.order = { kind: 'idle' };
    unit.path = [];
    unit.speed = 0;
    unit.stance = 'free';
    applied = true;
  }
  outcome(world, command.tick, 'assign', applied, applied ? 'ok' : 'noTug');
}

/** Send haulers to collect the ore crates miners stack beside a deposit. */
export function applyHaulCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'haul' }>,
): void {
  const deposit = findDeposit(world, command.depositId);
  if (!deposit || deposit.kind !== 'ore') {
    outcome(world, command.tick, 'haul', false, 'depositMissing');
    return;
  }
  let applied = false;
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    const type = world.unitTypes.get(unit.typeId);
    if (!type || type.workerKind !== 'tug') {
      continue;
    }
    const load = unit.job?.kind === 'tug' ? unit.job.load : 0;
    unit.job = {
      kind: 'tug',
      targetId: deposit.id,
      source: 'deposit',
      stage: load > 0 ? 'toPad' : 'toStation',
      load,
      cargo: unit.job?.kind === 'tug' ? unit.job.cargo : undefined,
      progress: 0,
      reportedEmpty: false,
    };
    unit.order = { kind: 'idle' };
    unit.path = [];
    unit.speed = 0;
    unit.stance = 'free';
    applied = true;
  }
  outcome(world, command.tick, 'haul', applied, applied ? 'ok' : 'noTug');
}

export function applySalvageCommand(
  world: WorldState,
  command: Extract<Command, { kind: 'salvage' }>,
): void {
  const salvaged: UnitState[] = [];
  for (const unit of ownedUnits(world, command.issuer, command.unitIds)) {
    const type = world.unitTypes.get(unit.typeId);
    if (!type || !type.workerKind || type.salvageRefundPercent <= 0) {
      continue;
    }
    const stats = ensureSideStats(world, command.issuer);
    stats.ore += Math.floor((type.oreCost * type.salvageRefundPercent) / 100);
    stats.metal += Math.floor((type.metalCost * type.salvageRefundPercent) / 100);
    salvaged.push(unit);
  }
  if (salvaged.length === 0) {
    outcome(world, command.tick, 'salvage', false, 'noWorker');
    return;
  }
  const ids = new Set(salvaged.map((unit) => unit.id));
  world.units = world.units.filter((unit) => !ids.has(unit.id));
  outcome(world, command.tick, 'salvage', true, 'ok');
}

/**
 * One tick of a miner at its deposit: it grinds ore into its hopper and packs every full hopper
 * load into a crate beside the deposit. Miners never drive to the pad; haulers collect the crates.
 * With its side's crate stack full the miner stops until a hauler takes one.
 */
export function minerDiggingStep(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  deposit: DepositState,
): void {
  const job = unit.job;
  if (!job || job.kind !== 'oreMiner' || job.stage !== 'digging') {
    return;
  }
  const hopper = Math.max(ORE_CRATE_SIZE, type.carryCapacity);
  const space = Math.max(0, hopper - job.load);
  if (space > 0 && deposit.amount > 0) {
    job.progress += type.miningRatePerSec * DT;
    const move = Math.min(Math.floor(job.progress), space, Math.floor(deposit.amount));
    if (move > 0) {
      job.progress -= move;
      job.load += move;
      deposit.amount = Math.max(0, deposit.amount - move);
    }
  } else {
    job.progress = Math.min(job.progress, 1);
  }
  // Pack whole crates; once the deposit is spent, the last part-filled load goes in too.
  const exhausted = deposit.amount < 1;
  while (job.load > 0) {
    const crate = exhausted ? Math.min(job.load, ORE_CRATE_SIZE) : ORE_CRATE_SIZE;
    if (job.load + 1e-6 < crate || crateRoom(deposit, unit.owner) + 1e-6 < crate) {
      break;
    }
    job.load -= crate;
    addCrateOre(deposit, unit.owner, crate);
  }
  if (exhausted && job.load <= 0) {
    job.load = 0;
    job.stage = 'waiting';
    unit.path = [];
    unit.speed = 0;
  }
}

export function minerAtDeposit(unit: UnitState, deposit: DepositState): boolean {
  return Math.hypot(unit.x - deposit.x, unit.z - deposit.z) <= DEPOSIT_REACH;
}

export function unitCap(): number {
  return UNIT_CAP;
}

export function unitCanStandHeight(world: WorldState, x: number, z: number): number {
  return heightAt(world.map, x, z);
}
