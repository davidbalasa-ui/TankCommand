import { describe, expect, it } from 'vitest';
import { createWorld, step } from '../../src/sim/world';
import { hullHalfExtents } from '../../src/sim/avoidance';
import type { Command } from '../../src/sim/commands';
import type { SimStructureType, SimUnitType, StartUnit, WorldState } from '../../src/sim/types';
import { makeWorld, packedTurretUnit, padType, tankType, turretType } from './simHelpers';

type Untimed = Command extends infer C ? (C extends Command ? Omit<C, 'tick'> : never) : never;

function run(world: WorldState, commands: Untimed[], ticks: number): WorldState {
  let state = world;
  const stamped = commands.map((command) => ({ ...command, tick: world.tick + 1 }) as Command);
  for (let i = 0; i < ticks; i += 1) {
    state = step(state, i === 0 ? stamped : []);
  }
  return state;
}

const SEC = 20;

function withStructures(units: StartUnit[], structures: Array<{ owner: number; typeId: string; x: number; z: number }>): WorldState {
  const unitTypes = new Map<string, SimUnitType>();
  for (const type of [tankType(), packedTurretUnit()]) {
    unitTypes.set(type.id, type);
  }
  const structureTypes = new Map<string, SimStructureType>();
  for (const type of [padType(), turretType()]) {
    structureTypes.set(type.id, type);
  }
  return createWorld(1, {
    unitTypes,
    structureTypes,
    startUnits: units,
    startStructures: structures,
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
  });
}

describe('playtest fixes', () => {
  it('[ORD-06] patrol goes back and forth until another order', () => {
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -40, z: 0, heading: 0 },
      // A far-off enemy so the match is not over.
      { owner: 2, typeId: 'unit.test.tank', x: 80, z: 80, heading: 0 },
    ]);
    expect(world.result).toBeNull();
    const id = world.units[0]!.id;
    world = run(world, [{ issuer: 1, kind: 'patrol', unitIds: [id], x: -10, z: 0 }], 1);
    let reachedB = false;
    let backAtA = false;
    for (let i = 0; i < 60 * SEC && !backAtA; i += 1) {
      world = step(world, []);
      const unit = world.units.find((item) => item.id === id)!;
      if (unit.x > -14) {
        reachedB = true;
      }
      if (reachedB && unit.x < -36) {
        backAtA = true;
      }
    }
    expect(reachedB).toBe(true);
    expect(backAtA).toBe(true);
    expect(world.units.find((item) => item.id === id)?.patrol).not.toBeNull();
    world = run(world, [{ issuer: 1, kind: 'stop', unitIds: [id] }], 2);
    const stopped = world.units.find((item) => item.id === id)!;
    expect(stopped.patrol ?? null).toBeNull();
    expect(stopped.order.kind).toBe('idle');
  });

  it('[ORD-07] deploying packed vehicles parked side by side unpacks every one', () => {
    let world = withStructures(
      [
        { owner: 1, typeId: 'unit.test.packed_turret', x: -20, z: 10, heading: 0 },
        { owner: 1, typeId: 'unit.test.packed_turret', x: -20, z: 13, heading: 0 },
        { owner: 1, typeId: 'unit.test.packed_turret', x: -17, z: 11, heading: 0 },
      ],
      [
        { owner: 1, typeId: 'structure.test.pad', x: -60, z: -60 },
        { owner: 2, typeId: 'structure.test.pad', x: 60, z: 60 },
      ],
    );
    const ids = world.units.map((unit) => unit.id);
    world = run(
      world,
      ids.map((unitId) => ({ issuer: 1, kind: 'deploy', unitId }) as Untimed),
      30 * SEC,
    );
    expect(world.structures.filter((item) => item.typeId === 'structure.test.turret')).toHaveLength(3);
  });

  it('[ORD-08] a column of tanks keeps its hulls apart and parked tanks stay out of buildings', () => {
    let world = makeWorld(1, [
      { owner: 1, typeId: 'unit.test.tank', x: -30, z: 0, heading: 0 },
      { owner: 1, typeId: 'unit.test.tank', x: -27, z: 0, heading: 0 },
    ]);
    world = run(world, [], 2 * SEC);
    const [a, b] = world.units;
    const length = hullHalfExtents(world, a!).length + hullHalfExtents(world, b!).length;
    expect(Math.hypot(a!.x - b!.x, a!.z - b!.z)).toBeGreaterThan(length - 0.2);

    // A tank parked nose-on against a turret slides back until its hull is clear of the footprint.
    let base = withStructures(
      [{ owner: 1, typeId: 'unit.test.tank', x: -18.5, z: 0, heading: 0 }],
      [
        { owner: 1, typeId: 'structure.test.pad', x: -60, z: -60 },
        { owner: 2, typeId: 'structure.test.pad', x: 60, z: 60 },
        { owner: 1, typeId: 'structure.test.turret', x: -15, z: 0 },
      ],
    );
    base = run(base, [], 3 * SEC);
    const tank = base.units[0]!;
    const half = (turretType().footprint.cellsX * base.map.cellSize) / 2;
    expect(-15 - tank.x).toBeGreaterThanOrEqual(half + hullHalfExtents(base, tank).length - 0.05);
  });
});
