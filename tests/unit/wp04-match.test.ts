import { describe, expect, it } from 'vitest';
import { createWorld, step } from '../../src/sim/world';
import type { SimStructureType, SimUnitType, StartStructure, StartUnit } from '../../src/sim/types';
import { minerType, padType, tankType } from './simHelpers';

function matchTypes(): {
  units: ReadonlyMap<string, SimUnitType>;
  structures: ReadonlyMap<string, SimStructureType>;
} {
  return {
    units: new Map([
      ['unit.test.tank', tankType()],
      ['unit.test.miner', minerType()],
    ]),
    structures: new Map([['structure.test.pad', padType({ hp: 40 })]]),
  };
}

function matchWorld(starts: StartUnit[], structures: StartStructure[]) {
  const types = matchTypes();
  return createWorld(1, {
    unitTypes: types.units,
    structureTypes: types.structures,
    startUnits: starts,
    startStructures: structures,
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'human' },
    ],
    startResources: [
      { player: 1, ore: 0, metal: 0 },
      { player: 2, ore: 0, metal: 0 },
    ],
  });
}

describe('match flow', () => {
  it('[MATCH-01] destroying the enemy pad and fighting units wins, losing yours loses', () => {
    let world = matchWorld(
      [{ owner: 1, typeId: 'unit.test.tank', x: -50, z: -50, turretHeading: 0 }],
      [
        { owner: 1, typeId: 'structure.test.pad', x: -55, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
      ],
    );
    const padId = world.structures.find((structure) => structure.owner === 2)?.id ?? 0;
    const tankId = world.units[0]?.id ?? 0;
    world = step(world, [
      { kind: 'attack', unitIds: [tankId], targetId: padId, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 4000 && !world.result; i += 1) {
      world = step(world, []);
    }
    expect(world.result).toEqual({ winner: 1 });

    let defeat = matchWorld(
      [{ owner: 1, typeId: 'unit.test.miner', x: -50, z: -50 }],
      [{ owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 }],
    );
    defeat = step(defeat, [
      { kind: 'mine', unitIds: [defeat.units[0]?.id ?? 0], depositId: 1, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 60 && !defeat.result; i += 1) {
      defeat = step(defeat, []);
    }
    expect(defeat.result).toEqual({ winner: 2 });
  });
});
