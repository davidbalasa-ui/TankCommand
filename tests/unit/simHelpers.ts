import { createWorld, defaultStartUnits } from '../../src/sim/world';
import type { SimUnitType, StartUnit, WorldState } from '../../src/sim/types';

export function tankType(overrides: Partial<SimUnitType> = {}): SimUnitType {
  return {
    id: 'unit.test.tank',
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
