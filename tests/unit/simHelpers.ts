import { createWorld, defaultStartUnits } from '../../src/sim/world';
import type {
  SimStructureType,
  SimUnitType,
  StartUnit,
  WorldState,
} from '../../src/sim/types';

export function tankType(overrides: Partial<SimUnitType> = {}): SimUnitType {
  return {
    id: 'unit.test.tank',
    faction: 'human',
    role: 'tank',
    hp: 220,
    armor: 4,
    topSpeed: 8,
    accel: 4,
    turnDegPerSec: 90,
    turretTurnDegPerSec: 120,
    fireOnMove: false,
    sightRange: 14,
    weapon: {
      damage: 30,
      range: 12,
      reloadSec: 2.5,
      projectileSpeed: 40,
      accuracy: 1,
      splashRadius: 0.5,
    },
    oreCost: 100,
    metalCost: 50,
    deliverySec: 1,
    workerKind: null,
    miningRatePerSec: 0,
    carryCapacity: 0,
    salvageRefundPercent: 0,
    ...overrides,
  };
}

export function minerType(overrides: Partial<SimUnitType> = {}): SimUnitType {
  return tankType({
    id: 'unit.test.miner',
    role: 'worker',
    hp: 100,
    armor: 0,
    topSpeed: 8,
    accel: 4,
    turnDegPerSec: 120,
    turretTurnDegPerSec: 0,
    sightRange: 10,
    weapon: null,
    oreCost: 80,
    metalCost: 0,
    deliverySec: 1,
    workerKind: 'oreMiner',
    miningRatePerSec: 20,
    carryCapacity: 5,
    salvageRefundPercent: 50,
    ...overrides,
  });
}

export function tugType(overrides: Partial<SimUnitType> = {}): SimUnitType {
  return tankType({
    id: 'unit.test.tug',
    role: 'worker',
    hp: 100,
    armor: 0,
    topSpeed: 8,
    accel: 4,
    turnDegPerSec: 120,
    turretTurnDegPerSec: 0,
    sightRange: 10,
    weapon: null,
    oreCost: 70,
    metalCost: 20,
    deliverySec: 1,
    workerKind: 'tug',
    miningRatePerSec: 0,
    carryCapacity: 2,
    salvageRefundPercent: 50,
    ...overrides,
  });
}

export function scoutType(overrides: Partial<SimUnitType> = {}): SimUnitType {
  return tankType({
    id: 'unit.test.scout',
    role: 'scout',
    hp: 80,
    armor: 1,
    topSpeed: 11,
    accel: 6,
    turnDegPerSec: 150,
    turretTurnDegPerSec: 180,
    weapon: {
      damage: 10,
      range: 8,
      reloadSec: 1.2,
      projectileSpeed: 55,
      accuracy: 1,
      splashRadius: 0,
    },
    oreCost: 50,
    metalCost: 0,
    deliverySec: 0.2,
    workerKind: null,
    miningRatePerSec: 0,
    carryCapacity: 0,
    salvageRefundPercent: 0,
    ...overrides,
  });
}

export function padType(overrides: Partial<SimStructureType> = {}): SimStructureType {
  return {
    id: 'structure.test.pad',
    name: 'Test Pad',
    faction: 'human',
    kind: 'pad',
    cost: { ore: 100, metal: 0 },
    deliverySec: 0.2,
    hp: 200,
    armor: 0,
    footprint: { cellsX: 2, cellsZ: 2 },
    sightRange: 10,
    modelId: 'pad',
    buildOnMetalDeposit: false,
    metalRatePerSec: 0,
    containerSize: 1,
    maxContainers: 1,
    ...overrides,
  };
}

export function metalStationType(overrides: Partial<SimStructureType> = {}): SimStructureType {
  return {
    id: 'structure.test.metal_station',
    name: 'Test Metal Station',
    faction: 'human',
    kind: 'metalStation',
    cost: { ore: 100, metal: 20 },
    deliverySec: 0.2,
    hp: 100,
    armor: 0,
    footprint: { cellsX: 2, cellsZ: 2 },
    sightRange: 10,
    modelId: 'metal',
    buildOnMetalDeposit: true,
    metalRatePerSec: 20,
    containerSize: 2,
    maxContainers: 5,
    ...overrides,
  };
}

export function testTypes(overrides: Partial<SimUnitType> = {}): ReadonlyMap<string, SimUnitType> {
  return new Map([['unit.test.tank', tankType(overrides)]]);
}

export function worldWithTypes(
  seed: number,
  startUnits: StartUnit[],
  types: SimUnitType[],
): WorldState {
  return createWorld(seed, {
    unitTypes: new Map(types.map((type) => [type.id, type])),
    startUnits,
  });
}

export function dummyType(overrides: Partial<SimUnitType> = {}): SimUnitType {
  return tankType({
    id: 'unit.test.dummy',
    hp: 1_000_000,
    armor: 0,
    topSpeed: 0,
    accel: 0,
    turnDegPerSec: 0,
    turretTurnDegPerSec: 0,
    sightRange: 1,
    weapon: null,
    ...overrides,
  });
}

export function makeWorld(
  seed: number,
  startUnits: StartUnit[],
  typeOverrides: Partial<SimUnitType> = {},
): WorldState {
  return createWorld(seed, {
    unitTypes: testTypes(typeOverrides),
    startUnits,
  });
}

export function makeSkirmishWorld(seed = 1): WorldState {
  return createWorld(seed, {
    unitTypes: new Map([['unit.human.light_tank', tankType({ id: 'unit.human.light_tank' })]]),
    startUnits: defaultStartUnits(),
  });
}

export function angleDiff(a: number, b: number): number {
  let diff = a - b;
  while (diff > Math.PI) {
    diff -= Math.PI * 2;
  }
  while (diff < -Math.PI) {
    diff += Math.PI * 2;
  }
  return diff;
}
