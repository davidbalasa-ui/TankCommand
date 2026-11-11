import { SIM_TICK_HZ } from './constants';
import {
  DEPOSIT_REACH,
  STATION_REACH,
} from './tuning';
import { approach, computePath, followPath } from './motion';
import {
  addAlert,
  creditMetal,
  creditOre,
  findDeposit,
  minerAtDeposit,
  minerDiggingStep,
  nearestPad,
  structureTypeOf,
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
import type { SimUnitType, StructureState, UnitState, WorkerJob, WorldState } from './types';

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
    if (unit.hp <= 0 || !unit.job) {
      continue;
    }
    const type = world.unitTypes.get(unit.typeId);
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
  const deposit = findDeposit(world, job.targetId);
  if (!deposit || deposit.kind !== 'ore') {
    if (job.load > 0) {
      job.stage = 'toPad';
    } else {
      job.stage = 'waiting';
      reportEmpty(world, unit, job.targetId);
    }
  }

  if (deposit && deposit.kind === 'ore' && deposit.amount <= 0 && job.load <= 0) {
    job.stage = 'waiting';
    reportEmpty(world, unit, job.targetId);
  }

  if (job.stage === 'waiting') {
    stopMoving(unit, type);
    return;
  }

  if (job.stage === 'toDeposit' && deposit) {
    const arrived = moveWorkerTo(world, unit, type, deposit.x, deposit.z, DEPOSIT_REACH);
    if (arrived) {
      job.stage = 'digging';
      stopMoving(unit, type);
    }
    return;
  }

  if (job.stage === 'digging' && deposit) {
    stopMoving(unit, type);
    if (minerAtDeposit(unit, deposit)) {
      minerDiggingStep(world, unit, type, deposit);
    } else {
      job.stage = 'toDeposit';
    }
    return;
  }

  if (job.stage === 'toPad' || job.stage === 'unloading') {
    if (!deliverAtPad(world, unit, type, job, 'ore')) {
      return;
    }
    creditOre(world, unit.owner, job.load);
    job.load = 0;
    job.progress = 0;
    stopMoving(unit, type);
    const after = findDeposit(world, job.targetId);
    if (after && after.kind === 'ore' && after.amount > 0) {
      job.stage = 'toDeposit';
    } else {
      job.stage = 'waiting';
      job.reportedEmpty = false;
      reportEmpty(world, unit, job.targetId);
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

// Move an empty-handed tug to the nearest own station that still has or will have metal.
function retargetTug(world: WorldState, unit: UnitState, job: { targetId: number; stage: string }): boolean {
  let best: StructureState | null = null;
  let bestD = Number.POSITIVE_INFINITY;
  for (const candidate of world.structures) {
    if (candidate.owner !== unit.owner || candidate.hp <= 0 || candidate.id === job.targetId) {
      continue;
    }
    if (structureTypeOf(world, candidate)?.kind !== 'metalStation' || stationDry(world, candidate)) {
      continue;
    }
    const d = Math.hypot(candidate.x - unit.x, candidate.z - unit.z);
    if (d < bestD || (d === bestD && best !== null && candidate.id < best.id)) {
      best = candidate;
      bestD = d;
    }
  }
  if (!best) {
    return false;
  }
  job.targetId = best.id;
  job.stage = 'toStation';
  return true;
}

function updateTug(world: WorldState, unit: UnitState, type: SimUnitType): void {
  const job = unit.job;
  if (!job || job.kind !== 'tug') {
    return;
  }
  const station = world.structures.find(
    (structure) => structure.id === job.targetId && structure.hp > 0,
  );
  const stationType = station ? structureTypeOf(world, station) : undefined;

  if (job.stage === 'waiting') {
    stopMoving(unit, type);
    if (job.load <= 0 && (!station || stationDry(world, station))) {
      retargetTug(world, unit, job);
    }
    return;
  }

  if (job.stage === 'toStation') {
    if (!station || !stationType || stationType.kind !== 'metalStation') {
      if (job.load > 0) {
        job.stage = 'toPad';
      } else {
        job.stage = 'waiting';
      }
      return;
    }
    const arrived = moveWorkerTo(world, unit, type, station.x, station.z, STATION_REACH);
    if (arrived) {
      job.stage = 'loading';
      stopMoving(unit, type);
    }
    return;
  }

  if (job.stage === 'loading') {
    stopMoving(unit, type);
    if (!station || !stationType || stationType.kind !== 'metalStation') {
      job.stage = job.load > 0 ? 'toPad' : 'waiting';
      return;
    }
    if (job.load <= 0 && station.containers > 0) {
      station.containers -= 1;
      job.load = stationType.containerSize;
      job.stage = 'toPad';
    } else if (job.load <= 0 && stationDry(world, station)) {
      retargetTug(world, unit, job);
    }
    return;
  }

  if (job.stage === 'toPad' || job.stage === 'unloading') {
    if (!deliverAtPad(world, unit, type, job, 'metal')) {
      return;
    }
    creditMetal(world, unit.owner, job.load);
    job.load = 0;
    stopMoving(unit, type);
    const aliveStation = world.structures.find(
      (structure) => structure.id === job.targetId && structure.hp > 0,
    );
    if (aliveStation) {
      job.stage = 'toStation';
    } else {
      job.stage = 'waiting';
    }
  }
}
