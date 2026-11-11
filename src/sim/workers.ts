import { SIM_TICK_HZ } from './constants';
import {
  DEPOSIT_REACH,
  PAD_REACH,
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
import type { SimUnitType, StructureState, UnitState, WorldState } from './types';

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

  if (job.stage === 'toPad') {
    const pad = nearestPad(world, unit.owner, unit.x, unit.z);
    if (!pad) {
      stopMoving(unit, type);
      return;
    }
    const arrived = moveWorkerTo(world, unit, type, pad.x, pad.z, PAD_REACH);
    if (!arrived) {
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

  if (job.stage === 'toPad') {
    const pad = nearestPad(world, unit.owner, unit.x, unit.z);
    if (!pad) {
      stopMoving(unit, type);
      return;
    }
    const arrived = moveWorkerTo(world, unit, type, pad.x, pad.z, PAD_REACH);
    if (!arrived) {
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
