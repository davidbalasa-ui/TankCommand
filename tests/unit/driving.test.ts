import { describe, expect, it } from 'vitest';
import { createWorld, step } from '../../src/sim/world';
import { UNIT_RADIUS } from '../../src/sim/tuning';
import type { Command } from '../../src/sim/commands';
import type { SimStructureType, StartUnit, WorldState } from '../../src/sim/types';
import { padType, testTypes } from './simHelpers';

// Step 2 of the overhaul: routes go round parked units, a blocked unit plans again, and units take
// turns at one-lane spots instead of pushing through each other.
const TANK = 'unit.test.tank';
const SEC = 20;

function flatWorld(units: StartUnit[], walls: Array<{ x: number; z: number }> = []): WorldState {
  const structures = new Map<string, SimStructureType>();
  // A plain 8 m block to build narrow gaps with.
  structures.set('structure.test.block', padType({ id: 'structure.test.block', kind: 'lab', footprint: { cellsX: 4, cellsZ: 4 } }));
  const world = createWorld(7, {
    unitTypes: testTypes(),
    structureTypes: structures,
    startUnits: units,
    startStructures: walls.map((wall) => ({ owner: 1, typeId: 'structure.test.block', ...wall })),
  });
  world.map.heights.fill(0);
  return world;
}

function move(ids: number[], x: number, z: number, tick = 1): Command {
  return { kind: 'move', unitIds: ids, x, z, tick, issuer: 1 };
}

function closestPair(world: WorldState): number {
  let best = Infinity;
  const ground = world.units.filter((unit) => !unit.air && unit.hp > 0);
  for (let i = 0; i < ground.length; i += 1) {
    for (let j = i + 1; j < ground.length; j += 1) {
      best = Math.min(best, Math.hypot(ground[i]!.x - ground[j]!.x, ground[i]!.z - ground[j]!.z));
    }
  }
  return best;
}

describe('[DRV] driving round units', () => {
  it('[DRV-01] a route goes round a line of parked tanks instead of shoving through them', () => {
    const wall: StartUnit[] = [-6, -2, 2, 6].map((z) => ({ owner: 1, typeId: TANK, x: 0, z: z * 0.9 }));
    let world = flatWorld([{ owner: 1, typeId: TANK, x: -25, z: 0 }, ...wall]);
    const mover = world.units[0]!;
    const before = world.units.slice(1).map((unit) => ({ id: unit.id, x: unit.x, z: unit.z }));
    world = step(world, [move([mover.id], 25, 0)]);
    let closest = Infinity;
    for (let i = 0; i < 30 * SEC; i += 1) {
      world = step(world, []);
      closest = Math.min(closest, closestPair(world));
    }
    const end = world.units.find((unit) => unit.id === mover.id)!;
    expect(Math.hypot(end.x - 25, end.z)).toBeLessThan(3);
    // Nobody in the line was pushed far out of place, and the mover never drove into them.
    for (const spot of before) {
      const unit = world.units.find((item) => item.id === spot.id)!;
      expect(Math.hypot(unit.x - spot.x, unit.z - spot.z), `tank ${spot.id}`).toBeLessThan(0.75);
    }
    expect(closest).toBeGreaterThan(UNIT_RADIUS * 2 - 0.4);
  });

  it('[DRV-02] a unit blocked for a second plans again round what is in its way', () => {
    let world = flatWorld([{ owner: 1, typeId: TANK, x: -25, z: 0 }]);
    const mover = world.units[0]!;
    world = step(world, [move([mover.id], 25, 0)]);
    // After the route is planned, a cluster parks across it.
    world.units.push(
      ...[-3, 0, 3].map((z, index) => ({ ...structuredClone(world.units[0]!), id: 900 + index, x: 0, z, order: { kind: 'idle' as const }, path: [], speed: 0 })),
    );
    for (let i = 0; i < 30 * SEC; i += 1) {
      world = step(world, []);
    }
    const end = world.units.find((unit) => unit.id === mover.id)!;
    expect(Math.hypot(end.x - 25, end.z)).toBeLessThan(3);
    for (const id of [900, 901, 902]) {
      const unit = world.units.find((item) => item.id === id)!;
      expect(Math.hypot(unit.x, unit.z - [-3, 0, 3][id - 900]!), `blocker ${id}`).toBeLessThan(3);
    }
  });

  it('[DRV-03] two tanks meeting in a one-lane gap take turns and both get through', () => {
    // Two blocks leave a gap one tank wide at x = 0.
    let world = flatWorld(
      [
        { owner: 1, typeId: TANK, x: -25, z: 0 },
        { owner: 1, typeId: TANK, x: 25, z: 0 },
      ],
      [
        { x: 0, z: 7 },
        { x: 0, z: -7 },
      ],
    );
    const [a, b] = world.units;
    world = step(world, [move([a!.id], 25, 0), move([b!.id], -25, 0)]);
    let closest = Infinity;
    for (let i = 0; i < 60 * SEC; i += 1) {
      world = step(world, []);
      closest = Math.min(closest, closestPair(world));
    }
    const endA = world.units.find((unit) => unit.id === a!.id)!;
    const endB = world.units.find((unit) => unit.id === b!.id)!;
    expect(Math.hypot(endA.x - 25, endA.z)).toBeLessThan(3);
    expect(Math.hypot(endB.x + 25, endB.z)).toBeLessThan(3);
    expect(closest).toBeGreaterThan(UNIT_RADIUS * 2 - 0.4);
  });
});
