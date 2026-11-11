import { SIM_TICK_HZ } from './constants';
import {
  CRATE_REACH,
  DEPOSIT_REACH,
  ORE_CRATE_SIZE,
  STATION_REACH,
} from './tuning';
import { approach, computePath, followPath } from './motion';
import {
  addAlert,
  crateOre,
  creditMetal,
  creditOre,
  findDeposit,
  minerAtDeposit,
  minerDiggingStep,
  nearestPad,
  structureTypeOf,
  takeCrateOre,
} from './economy';
import {
  PAD_CARGO_LIFT_SEC,
  PAD_DOCK_REACH,
  PAD_QUEUE_JOIN_DISTANCE,
  PAD_UNLOAD_SEC,
  padLayout,
  padLine,
  padQueueSpot,
} from './pad';
import type { DepositState, SimUnitType, StructureState, UnitState, WorkerJob, WorldState } from './types';

const DT = 1 / SIM_TICK_HZ;

function stopMoving(unit: UnitState, type: SimUnitType): void {
  unit.path = [];
  unit.speed = approach(unit.speed, 0, type.accel * DT);
}

function moveWorkerTo(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  x: number,
  z: number,
  reach: number,
): boolean {
  if (Math.hypot(unit.x - x, unit.z - z) <= reach) {
    stopMoving(unit, type);
    return true;
  }
  const last = unit.path[unit.path.length - 1];
  if (last && Math.hypot(last.x - x, last.z - z) > Math.max(reach, world.map.cellSize * 1.5)) {
    unit.path = []; // the destination moved (e.g. a place in the pad's delivery line)
  }
  if (unit.path.length === 0) {
    const path = computePath(world, unit, x, z);
    if (!path) {
      return false;
    }
    unit.path = path;
  }
  followPath(world, unit, type, { x, z });
  return Math.hypot(unit.x - x, unit.z - z) <= reach;
}

function reportEmpty(world: WorldState, unit: UnitState, depositId: number): void {
  const job = unit.job;
  if (!job || job.reportedEmpty) {
    return;
  }
  const deposit = findDeposit(world, depositId);
  const x = deposit?.x ?? unit.x;
  const z = deposit?.z ?? unit.z;
  addAlert(world, 'depositEmpty', unit.owner, x, z);
  job.reportedEmpty = true;
}

function ownPadById(world: WorldState, owner: number, id: number | null | undefined): StructureState | null {
  if (id === undefined || id === null) {
    return null;
  }
  const pad = world.structures.find((item) => item.id === id && item.owner === owner && item.hp > 0);
  return pad && structureTypeOf(world, pad)?.kind === 'pad' ? pad : null;
}

function leaveLine(job: WorkerJob): void {
  job.dockPadId = null;
  job.queuedAt = undefined;
  job.unloadLeft = undefined;
}

/**
 * Bring a loaded worker to a landing pad's dock and unload it. Workers line up behind the dock in
 * the order they arrived and unload one at a time; the cargo then lifts off the pad. Returns true
 * on the tick the load is handed over, which is when the caller credits it.
 */
function deliverAtPad(
  world: WorldState,
  unit: UnitState,
  type: SimUnitType,
  job: WorkerJob,
  cargo: 'ore' | 'metal',
): boolean {
  let pad = ownPadById(world, unit.owner, job.dockPadId);
  if (!pad) {
    pad = nearestPad(world, unit.owner, unit.x, unit.z);
    leaveLine(job);
    job.stage = 'toPad';
    if (!pad) {
      stopMoving(unit, type);
      return false;
    }
    job.dockPadId = pad.id;
  }
  const layout = padLayout(world, pad);

  if (job.stage === 'unloading') {
    stopMoving(unit, type);
    job.unloadLeft = Math.max(0, (job.unloadLeft ?? PAD_UNLOAD_SEC) - DT);
    if (job.unloadLeft > 0) {
      return false;
    }
    world.dropBeams.push({
      owner: unit.owner,
      x: layout.liftX,
      z: layout.liftZ,
      ttl: PAD_CARGO_LIFT_SEC,
      total: PAD_CARGO_LIFT_SEC,
      kind: cargo,
    });
    leaveLine(job);
    return true;
  }

  if (job.queuedAt === undefined) {
    if (Math.hypot(unit.x - layout.dockX, unit.z - layout.dockZ) > PAD_QUEUE_JOIN_DISTANCE) {
      moveWorkerTo(world, unit, type, layout.dockX, layout.dockZ, PAD_DOCK_REACH);
      return false;
    }
    job.queuedAt = world.tick;
  }
  const line = padLine(world, pad).filter(
    (item) => item.job?.stage === 'unloading' || item.job?.queuedAt !== undefined,
  );
  const place = line.indexOf(unit);
  if (place <= 0) {
    if (moveWorkerTo(world, unit, type, layout.dockX, layout.dockZ, PAD_DOCK_REACH)) {
      job.stage = 'unloading';
      job.unloadLeft = PAD_UNLOAD_SEC;
      stopMoving(unit, type);
    }
    return false;
  }
  const spot = padQueueSpot(world, layout, place - 1);
  moveWorkerTo(world, unit, type, spot.x, spot.z, PAD_DOCK_REACH);
  return false;
}

export function updateWorkers(world: WorldState): void {
  for (const unit of world.units) {
    if (unit.hp <= 0) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
    if (!unit.job) {
      // Haulers look for work by themselves once they stand idle (fresh off the pad, say).
      if (type?.workerKind === 'tug' && unit.order.kind === 'idle' && unit.path.length === 0) {
        const job: WorkerJob = {
          kind: 'tug',
          targetId: -1,
          stage: 'waiting',
          load: 0,
          progress: 0,
          reportedEmpty: false,
        };
        if (retargetTug(world, unit, job)) {
          unit.job = job;
          unit.stance = 'free';
        }
      }
      continue;
    }
    if (!type) {
      unit.job = null;
      continue;
    }
    if (unit.job.kind === 'oreMiner') {
      updateMiner(world, unit, type);
    } else {
      updateTug(world, unit, type);
    }
  }
}

function updateMiner(world: WorldState, unit: UnitState, type: SimUnitType): void {
  const job = unit.job;
  if (!job || job.kind !== 'oreMiner') {
    return;
  }
  // Miners no longer deliver; one left on its way to the pad by an older save goes back to dig.
  if (job.stage === 'toPad' || job.stage === 'unloading' || job.stage === 'loading' || job.stage === 'toStation') {
    leaveLine(job);
    job.stage = 'toDeposit';
  }
  const deposit = findDeposit(world, job.targetId);
  if (!deposit || deposit.kind !== 'ore' || (deposit.amount < 1 && job.load <= 0)) {
    job.stage = 'waiting';
    reportEmpty(world, unit, job.targetId);
  }

  if (job.stage === 'waiting' || !deposit) {
    stopMoving(unit, type);
    return;
  }

  if (job.stage === 'toDeposit') {
    const arrived = moveWorkerTo(world, unit, type, deposit.x, deposit.z, DEPOSIT_REACH);
    if (arrived) {
      job.stage = 'digging';
      stopMoving(unit, type);
    }
    return;
  }

  if (job.stage === 'digging') {
    stopMoving(unit, type);
    if (minerAtDeposit(unit, deposit)) {
      minerDiggingStep(world, unit, type, deposit);
      if ((job.stage as string) === 'waiting') {
        reportEmpty(world, unit, job.targetId);
      }
    } else {
      job.stage = 'toDeposit';
    }
  }
}

// A station that has nothing to hand over now and never will again.
function stationDry(world: WorldState, station: StructureState): boolean {
  if (station.containers > 0) {
    return false;
  }
  const deposit = world.deposits.find((item) => item.id === station.depositId);
  return !deposit || deposit.amount <= 1e-6;
}

// An ore deposit has work for a side's haulers while crates are stacked there or one of its
// miners is still digging it.
function oreSiteMinedBy(world: WorldState, deposit: DepositState, owner: number): boolean {
  if (deposit.amount < 1) {
    return false;
  }
  return world.units.some(
    (unit) =>
      unit.owner === owner &&
      unit.hp > 0 &&
      unit.job?.kind === 'oreMiner' &&
      unit.job.targetId === deposit.id &&
      unit.job.stage !== 'waiting',
  );
}

function oreSiteDry(world: WorldState, deposit: DepositState, owner: number): boolean {
  return crateOre(deposit, owner) <= 1e-6 && !oreSiteMinedBy(world, deposit, owner);
}

function haulersOn(world: WorldState, self: UnitState, source: 'station' | 'deposit', id: number): number {
  let count = 0;
  for (const unit of world.units) {
    if (
      unit !== self &&
      unit.owner === self.owner &&
      unit.hp > 0 &&
      unit.job?.kind === 'tug' &&
      (unit.job.source ?? 'station') === source &&
      unit.job.targetId === id
    ) {
      count += 1;
    }
  }
  return count;
}

/**
 * Point an empty-handed hauler at the best place to collect from: an own metal station or an ore
 * deposit where own miners stack crates. Cargo waiting now counts in a site's favour, other
 * haulers already working it count against it, then distance decides.
 */
function retargetTug(world: WorldState, unit: UnitState, job: WorkerJob): boolean {
  let best: { source: 'station' | 'deposit'; id: number; score: number } | null = null;
  const consider = (source: 'station' | 'deposit', id: number, x: number, z: number, ready: boolean): void => {
    const others = haulersOn(world, unit, source, id);
    // An unserved metal station counts extra: its containers stop filling once they are full.
    const score =
      Math.hypot(x - unit.x, z - unit.z) +
      others * 30 -
      (ready ? 20 : 0) -
      (source === 'station' && others === 0 ? 40 : 0);
    if (!best || score < best.score - 1e-9) {
      best = { source, id, score };
    }
  };
  for (const candidate of world.structures) {
    if (candidate.owner !== unit.owner || candidate.hp <= 0) {
      continue;
    }
    if (structureTypeOf(world, candidate)?.kind !== 'metalStation' || stationDry(world, candidate)) {
      continue;
    }
    consider('station', candidate.id, candidate.x, candidate.z, candidate.containers > 0);
  }
  for (const deposit of world.deposits) {
    if (deposit.kind !== 'ore' || oreSiteDry(world, deposit, unit.owner)) {
      continue;
    }
    consider('deposit', deposit.id, deposit.x, deposit.z, crateOre(deposit, unit.owner) > 1e-6);
  }
  const pick = best as { source: 'station' | 'deposit'; id: number } | null;
  if (!pick) {
    return false;
  }
  job.source = pick.source;
  job.targetId = pick.id;
  job.stage = 'toStation';
  return true;
}

interface TugSource {
  x: number;
  z: number;
  reach: number;
  dry: boolean;
  station?: StructureState;
  containerSize?: number;
  deposit?: DepositState;
}

function tugSource(world: WorldState, unit: UnitState, job: WorkerJob): TugSource | null {
  if (job.source === 'deposit') {
    const deposit = findDeposit(world, job.targetId);
    if (!deposit || deposit.kind !== 'ore') {
      return null;
    }
    return {
      x: deposit.x,
      z: deposit.z,
      reach: CRATE_REACH,
      dry: oreSiteDry(world, deposit, unit.owner),
      deposit,
    };
  }
  const station = world.structures.find(
    (structure) => structure.id === job.targetId && structure.hp > 0 && structure.owner === unit.owner,
  );
  const stationType = station ? structureTypeOf(world, station) : undefined;
  if (!station || !stationType || stationType.kind !== 'metalStation') {
    return null;
  }
  return {
    x: station.x,
    z: station.z,
    reach: STATION_REACH,
    dry: stationDry(world, station),
    station,
    containerSize: stationType.containerSize,
  };
}

function updateTug(world: WorldState, unit: UnitState, type: SimUnitType): void {
  const job = unit.job;
  if (!job || job.kind !== 'tug') {
    return;
  }
  if (job.load > 0 && (job.stage === 'waiting' || job.stage === 'toStation' || job.stage === 'loading')) {
    job.stage = 'toPad';
  }
  const source = tugSource(world, unit, job);

  if (job.stage === 'waiting') {
    stopMoving(unit, type);
    if (!source || source.dry) {
      retargetTug(world, unit, job);
    } else {
      job.stage = 'toStation';
    }
    return;
  }

  if (job.stage === 'toStation' || job.stage === 'loading') {
    if (!source || source.dry) {
      if (!retargetTug(world, unit, job)) {
        job.stage = 'waiting';
        stopMoving(unit, type);
      }
      return;
    }
    if (job.stage === 'toStation') {
      if (moveWorkerTo(world, unit, type, source.x, source.z, source.reach)) {
        job.stage = 'loading';
        stopMoving(unit, type);
      }
      return;
    }
    stopMoving(unit, type);
    // Load as many containers or crates as the hauler holds (at least one) and leave at once.
    if (source.station && source.station.containers > 0) {
      const size = source.containerSize ?? 0;
      const fits = Math.max(1, Math.floor(type.carryCapacity / Math.max(1, size)));
      const count = Math.min(fits, source.station.containers);
      source.station.containers -= count;
      job.load = count * size;
      job.cargo = 'metal';
      job.stage = 'toPad';
    } else if (source.deposit) {
      const taken = takeCrateOre(source.deposit, unit.owner, Math.max(ORE_CRATE_SIZE, type.carryCapacity));
      if (taken > 0) {
        job.load = taken;
        job.cargo = 'ore';
        job.stage = 'toPad';
      }
    }
    return;
  }

  if (job.stage === 'toPad' || job.stage === 'unloading') {
    const cargo = job.cargo ?? (job.source === 'deposit' ? 'ore' : 'metal');
    if (!deliverAtPad(world, unit, type, job, cargo)) {
      return;
    }
    if (cargo === 'ore') {
      creditOre(world, unit.owner, job.load);
    } else {
      creditMetal(world, unit.owner, job.load);
    }
    job.load = 0;
    job.cargo = undefined;
    stopMoving(unit, type);
    job.stage = 'waiting';
    const back = tugSource(world, unit, job);
    if (back && !back.dry) {
      job.stage = 'toStation';
    } else {
      retargetTug(world, unit, job);
    }
  }
}
