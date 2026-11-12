import { describe, expect, it } from 'vitest';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { DEPOSIT_SOLID_RADIUS } from '../../src/sim/obstacles';
import type { Command } from '../../src/sim/commands';
import type { WorldState } from '../../src/sim/types';
import { labType, tankType } from './simHelpers';

const SEC = 20;

function flatWorld(options: Parameters<typeof createWorld>[1]): WorldState {
  const world = createWorld(5, options);
  world.map.heights.fill(0);
  return world;
}

function move(ids: number[], x: number, z: number): Command {
  return { kind: 'move', unitIds: ids, x, z, tick: 1, issuer: 1 };
}

describe('[OBS] solid buildings and sites', () => {
  it('[OBS-01] a tank told to drive through a building goes round it and arrives', () => {
    const lab = labType({ footprint: { cellsX: 3, cellsZ: 3 } });
    let world = flatWorld({
      unitTypes: new Map([['unit.test.tank', tankType()]]),
      structureTypes: new Map([[lab.id, lab]]),
      startUnits: [{ owner: 1, typeId: 'unit.test.tank', x: -20, z: 1 }],
      startStructures: [{ owner: 1, typeId: lab.id, x: 1, z: 1 }],
    });
    const id = world.units[0]!.id;
    world = step(world, [move([id], 20, 1)]);
    const half = 3; // 3 cells of 2 m
    for (let i = 0; i < 40 * SEC; i += 1) {
      world = step(world, []);
      const unit = world.units[0]!;
      const inside = Math.abs(unit.x - 1) < half && Math.abs(unit.z - 1) < half;
      expect(inside, `tick ${world.tick} at ${unit.x.toFixed(2)},${unit.z.toFixed(2)}`).toBe(false);
    }
    const unit = world.units[0]!;
    expect(Math.hypot(unit.x - 20, unit.z - 1)).toBeLessThan(2.5);
  });

  it('[OBS-02] fighting units keep out of an ore site; the order still ends', () => {
    let world = flatWorld({
      unitTypes: new Map([['unit.test.tank', tankType()]]),
      startUnits: [{ owner: 1, typeId: 'unit.test.tank', x: -20, z: 0 }],
      deposits: [{ kind: 'ore', x: 0, z: 0, amount: 500 }],
    });
    const id = world.units[0]!.id;
    // Straight at the middle of the site: it stops beside it instead of driving in.
    world = step(world, [move([id], 0, 0)]);
    for (let i = 0; i < 30 * SEC; i += 1) {
      world = step(world, []);
      const unit = world.units[0]!;
      expect(Math.hypot(unit.x, unit.z)).toBeGreaterThan(DEPOSIT_SOLID_RADIUS);
    }
    expect(world.units[0]!.order.kind).toBe('idle');
  });

  it('[OBS-03] a unit caught inside a new building slides out of it', () => {
    const lab = labType({ footprint: { cellsX: 2, cellsZ: 2 } });
    let world = flatWorld({
      unitTypes: new Map([['unit.test.tank', tankType()]]),
      structureTypes: new Map([[lab.id, lab]]),
      startUnits: [{ owner: 1, typeId: 'unit.test.tank', x: 0.5, z: 0.2 }],
      startStructures: [{ owner: 1, typeId: lab.id, x: 0, z: 0 }],
    });
    for (let i = 0; i < 10 * SEC; i += 1) {
      world = step(world, []);
    }
    const unit = world.units[0]!;
    expect(Math.abs(unit.x) >= 2 || Math.abs(unit.z) >= 2).toBe(true);
  });

  it('[OBS-04] driving round buildings is deterministic', () => {
    const lab = labType({ footprint: { cellsX: 3, cellsZ: 3 } });
    const make = (): WorldState =>
      flatWorld({
        unitTypes: new Map([['unit.test.tank', tankType()]]),
        structureTypes: new Map([[lab.id, lab]]),
        startUnits: [
          { owner: 1, typeId: 'unit.test.tank', x: -20, z: 0 },
          { owner: 1, typeId: 'unit.test.tank', x: -20, z: 4 },
        ],
        startStructures: [{ owner: 1, typeId: lab.id, x: 0, z: 1 }],
      });
    let a = make();
    let b = make();
    const ids = a.units.map((u) => u.id);
    a = step(a, [move(ids, 20, 2)]);
    b = step(b, [move(ids, 20, 2)]);
    for (let i = 0; i < 20 * SEC; i += 1) {
      a = step(a, []);
      b = step(b, []);
    }
    expect(hashWorld(a)).toBe(hashWorld(b));
  });
});
