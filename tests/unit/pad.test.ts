import { describe, expect, it } from 'vitest';
import { createWorld, step } from '../../src/sim/world';
import { PAD_LAND_SEC, padLayout } from '../../src/sim/pad';
import type { SimStructureType, SimUnitType, StartUnit, WorldState } from '../../src/sim/types';
import { metalStationType, minerType, padType, scoutType, tugType } from './simHelpers';

const HZ = 20;

function padWorld(options: {
  units?: StartUnit[];
  ore?: number;
  oreDeposit?: { x: number; z: number; amount: number };
}): WorldState {
  const units = new Map<string, SimUnitType>();
  for (const unit of [minerType(), tugType(), scoutType()]) {
    units.set(unit.id, unit);
  }
  const structures = new Map<string, SimStructureType>();
  // A full-size pad: 6 x 6 cells, like the real ones.
  for (const structure of [padType({ footprint: { cellsX: 6, cellsZ: 6 } }), metalStationType()]) {
    structures.set(structure.id, structure);
  }
  return createWorld(1, {
    unitTypes: units,
    structureTypes: structures,
    startUnits: options.units ?? [],
    startStructures: [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
    ],
    deposits: options.oreDeposit ? [{ kind: 'ore', ...options.oreDeposit }] : [],
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
    startResources: [
      { player: 1, ore: options.ore ?? 1000, metal: 100 },
      { player: 2, ore: 0, metal: 0 },
    ],
  });
}

function myPad(world: WorldState) {
  const pad = world.structures.find((s) => s.owner === 1 && s.typeId === 'structure.test.pad');
  if (!pad) {
    throw new Error('no pad');
  }
  return pad;
}

describe('[PAD] landing pad traffic', () => {
  it('[PAD-01] the exit faces the map centre and the dock is on a side edge', () => {
    const world = padWorld({});
    const pad = myPad(world);
    const layout = padLayout(world, pad);
    expect(layout.half).toBe(6);
    // (-50,-50): centre is +x/+z; ties pick the x axis.
    expect(layout.facing).toBe(0);
    expect(layout.rallyX).toBeGreaterThan(pad.x + layout.half);
    expect(Math.abs(layout.dockX - pad.x)).toBeLessThan(1e-9);
    expect(layout.dockZ).toBeGreaterThan(pad.z + layout.half);
  });

  it('[PAD-02] deliveries come down one at a time, in order, and each clears the pad first', () => {
    let world = padWorld({});
    const padId = myPad(world).id;
    const commands = [1, 2, 3].map((n) => ({
      kind: 'buy' as const,
      itemId: 'unit.test.scout',
      padId,
      tick: n,
      issuer: 1,
    }));
    for (const command of commands) {
      world = step(world, [command]);
    }
    const orderIds = world.dropQueue.map((order) => order.id);
    expect(orderIds).toHaveLength(3);

    const arrivals: number[] = [];
    let maxLanding = 0;
    for (let i = 0; i < 40 * HZ; i += 1) {
      world = step(world, []);
      const landing = world.dropQueue.filter((order) => order.landingSec !== undefined).length;
      maxLanding = Math.max(maxLanding, landing);
      const pad = myPad(world);
      for (const unit of world.units) {
        if (unit.owner === 1 && !arrivals.includes(unit.id)) {
          arrivals.push(unit.id);
          // Each arrival touches down on the landing circle and heads for the exit side.
          expect(Math.hypot(unit.x - pad.x, unit.z - pad.z)).toBeLessThan(0.01);
          expect(unit.order.kind).toBe('move');
          // Nothing else is sitting on the pad when it lands.
          const others = world.units.filter(
            (other) =>
              other.id !== unit.id &&
              Math.max(Math.abs(other.x - pad.x), Math.abs(other.z - pad.z)) < 6,
          );
          expect(others).toHaveLength(0);
        }
      }
      if (arrivals.length === 3 && world.dropQueue.length === 0) {
        break;
      }
    }
    expect(maxLanding).toBe(1);
    expect(arrivals).toHaveLength(3);
    // Spawn order follows buy order (ids grow monotonically).
    expect([...arrivals].sort((a, b) => a - b)).toEqual(arrivals);
    // They drove off the exit edge toward the rally point.
    const pad = myPad(world);
    const layout = padLayout(world, pad);
    for (let i = 0; i < 10 * HZ; i += 1) {
      world = step(world, []);
    }
    for (const id of arrivals) {
      const unit = world.units.find((item) => item.id === id);
      expect(unit).toBeDefined();
      if (unit) {
        expect(unit.x).toBeGreaterThan(pad.x + layout.half - 1);
      }
    }
  });

  it('[PAD-03] a delivery cannot be cancelled once it is coming down', () => {
    let world = padWorld({});
    const padId = myPad(world).id;
    world = step(world, [{ kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 }]);
    for (let i = 0; i < 10; i += 1) {
      world = step(world, []);
    }
    const order = world.dropQueue[0];
    expect(order?.landingSec).toBeGreaterThan(0);
    expect(order?.landingSec ?? 0).toBeLessThan(PAD_LAND_SEC);
    world = step(world, [{ kind: 'cancel', orderId: order?.id ?? 0, tick: world.tick + 1, issuer: 1 }]);
    expect(world.lastCommandOutcome?.reason).toBe('landing');
    expect(world.dropQueue).toHaveLength(1);
  });

  it('[PAD-04] workers unload at the delivery spots, one at a time per spot, in the order they arrive', () => {
    // Two miners fill crates; three haulers carry them to the pad's dock.
    const units: StartUnit[] = [0, 1, 2, 3, 4].map((i) => ({
      owner: 1,
      typeId: i < 2 ? 'unit.test.miner' : 'unit.test.tug',
      x: -50 + i * 3,
      z: -30,
    }));
    let world = padWorld({ units, oreDeposit: { x: -44, z: -26, amount: 1000 } });
    const miners = world.units.filter((unit) => unit.typeId === 'unit.test.miner').map((unit) => unit.id);
    const tugs = world.units.filter((unit) => unit.typeId === 'unit.test.tug').map((unit) => unit.id);
    world = step(world, [
      { kind: 'mine', unitIds: miners, depositId: 1, tick: 1, issuer: 1 },
      { kind: 'haul', unitIds: tugs, depositId: 1, tick: 1, issuer: 1 },
    ]);
    const layout = padLayout(world, myPad(world));
    let maxUnloading = 0;
    const docksUsed = new Set<number>();
    const credits: number[] = [];
    let previous = world.resources.find((r) => r.player === 1)?.ore ?? 0;
    for (let i = 0; i < 90 * HZ; i += 1) {
      world = step(world, []);
      const unloading = world.units.filter((unit) => unit.job?.stage === 'unloading');
      for (const side of [0, 1, 2]) {
        const atSide = unloading.filter((unit) => (unit.job?.dockSide ?? 0) === side);
        maxUnloading = Math.max(maxUnloading, atSide.length);
      }
      for (const unit of unloading) {
        const side = unit.job?.dockSide ?? 0;
        docksUsed.add(side);
        const dock = layout.docks[side]!;
        expect(dock.open).toBe(true);
        expect(Math.hypot(unit.x - dock.x, unit.z - dock.z)).toBeLessThanOrEqual(1.7);
      }
      const ore = world.resources.find((r) => r.player === 1)?.ore ?? previous;
      if (ore > previous) {
        credits.push(world.tick);
        previous = ore;
      }
      if (credits.length >= 6) {
        break;
      }
    }
    expect(maxUnloading).toBe(1);
    expect(docksUsed.size).toBeGreaterThanOrEqual(1);
    expect(credits.length).toBeGreaterThanOrEqual(6);
    // A cargo pod lifts off the dock for every load.
    expect(world.dropBeams.some((beam) => beam.kind === 'ore')).toBe(true);
  });

  it('[PAD-05] the pad has a delivery spot off every edge except the exit, and a worker takes a shorter line', () => {
    const world = padWorld({});
    const pad = myPad(world);
    const layout = padLayout(world, pad);
    expect(layout.docks).toHaveLength(3);
    const exitDir = { x: Math.cos(layout.facing), z: Math.sin(layout.facing) };
    for (const dock of layout.docks) {
      expect(dock.open).toBe(true);
      // Outside the pad, off the middle of an edge, and never on the exit edge.
      expect(Math.max(Math.abs(dock.x - pad.x), Math.abs(dock.z - pad.z))).toBeGreaterThan(layout.half);
      expect(dock.dirX * exitDir.x + dock.dirZ * exitDir.z).toBeLessThan(0.5);
    }
    const sides = new Set(layout.docks.map((dock) => `${dock.dirX},${dock.dirZ}`));
    expect(sides.size).toBe(3);
  });

  it('[PAD-06] the pad deck is solid: units drive round it, and only the landing circle and exit lane are open', () => {
    // A scout west of the pad ordered to a spot east of it, straight across the deck.
    const pad0 = { x: -50, z: -50 };
    let world = padWorld({ units: [{ owner: 1, typeId: 'unit.test.scout', x: pad0.x - 14, z: pad0.z }] });
    const pad = myPad(world);
    const layout = padLayout(world, pad);
    const scout = world.units[0]!;
    world = step(world, [
      { kind: 'move', unitIds: [scout.id], x: pad.x + 14, z: pad.z + 2, queue: false, tick: 1, issuer: 1 },
    ]);
    const lane = 2;
    for (let i = 0; i < 40 * HZ; i += 1) {
      world = step(world, []);
      const unit = world.units.find((item) => item.id === scout.id)!;
      const u = (unit.x - pad.x) * Math.cos(layout.facing) + (unit.z - pad.z) * Math.sin(layout.facing);
      const v = -(unit.x - pad.x) * Math.sin(layout.facing) + (unit.z - pad.z) * Math.cos(layout.facing);
      const onDeck = Math.abs(u) < layout.half && Math.abs(v) < layout.half;
      if (onDeck) {
        // Only the landing circle and the lane out of it are drivable.
        expect(Math.abs(v)).toBeLessThan(lane + 0.2);
        expect(u).toBeGreaterThan(-lane - 0.2);
      }
    }
    const unit = world.units.find((item) => item.id === scout.id)!;
    expect(Math.hypot(unit.x - (pad.x + 14), unit.z - (pad.z + 2))).toBeLessThan(3);
  });
});
