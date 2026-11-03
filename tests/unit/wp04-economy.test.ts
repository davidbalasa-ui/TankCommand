import { describe, expect, it } from 'vitest';
import { createWorld, step } from '../../src/sim/world';
import { Rng } from '../../src/sim/rng';
import type { Command } from '../../src/sim/commands';
import type {
  SimStructureType,
  SimUnitType,
  StartStructure,
  StartUnit,
} from '../../src/sim/types';
import {
  metalStationType,
  minerType,
  padType,
  scoutType,
  tugType,
} from './simHelpers';

function buildTypes(): {
  units: ReadonlyMap<string, SimUnitType>;
  structures: ReadonlyMap<string, SimStructureType>;
} {
  const units = new Map<string, SimUnitType>();
  for (const unit of [minerType(), tugType(), scoutType()]) {
    units.set(unit.id, unit);
  }
  const structures = new Map<string, SimStructureType>();
  for (const structure of [padType(), metalStationType()]) {
    structures.set(structure.id, structure);
  }
  return { units, structures };
}

function economyWorld(options: {
  startUnits: StartUnit[];
  startStructures?: StartStructure[];
  oreDeposit?: { x: number; z: number; amount: number };
  metalDeposit?: { x: number; z: number; amount: number };
  ore?: number;
  metal?: number;
}) {
  const { units, structures } = buildTypes();
  const deposits: Array<{ kind: 'ore' | 'metal'; x: number; z: number; amount: number }> = [];
  if (options.oreDeposit) {
    deposits.push({ kind: 'ore', ...options.oreDeposit });
  }
  if (options.metalDeposit) {
    deposits.push({ kind: 'metal', ...options.metalDeposit });
  }
  // Second live side keeps `world.result` null so subsequent `step` calls still
  // accept commands (see docs/decisions: a decided match ignores commands).
  // Without this the buy/cancel/mine cycle in [ECO-05] is dropped after tick 1.
  const startStructures: StartStructure[] = [
    ...(options.startStructures ?? [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
    ]),
    { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
  ];
  return createWorld(1, {
    unitTypes: units,
    structureTypes: structures,
    startUnits: options.startUnits,
    startStructures,
    deposits,
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
    startResources: [
      { player: 1, ore: options.ore ?? 0, metal: options.metal ?? 0 },
      { player: 2, ore: 0, metal: 0 },
    ],
  });
}

function stats(world: ReturnType<typeof economyWorld>) {
  return world.resources.find((item) => item.player === 1);
}

describe('economy', () => {
  it('[ECO-01] ore is credited only when load reaches a pad and in exact load-size chunks', () => {
    let world = economyWorld({
      startUnits: [{ owner: 1, typeId: 'unit.test.miner', x: -50, z: -46 }],
      oreDeposit: { x: -46, z: -50, amount: 100 },
    });
    const minerId = world.units[0]?.id ?? 0;
    const padId = world.structures[0]?.id ?? 0;
    world = step(world, [
      { kind: 'mine', unitIds: [minerId], depositId: 1, tick: 1, issuer: 1 },
    ]);
    let previous = stats(world)?.ore ?? 0;
    const deltas: number[] = [];
    for (let i = 0; i < 300; i += 1) {
      world = step(world, []);
      const current = stats(world)?.ore ?? previous;
      if (current > previous) {
        deltas.push(current - previous);
        const miner = world.units.find((unit) => unit.id === minerId);
        const pad = world.structures.find((structure) => structure.id === padId);
        expect(miner).toBeDefined();
        expect(pad).toBeDefined();
        if (miner && pad) {
          expect(Math.hypot(miner.x - pad.x, miner.z - pad.z)).toBeLessThanOrEqual(5);
        }
        previous = current;
      }
      if (deltas.length >= 2) {
        break;
      }
    }
    expect(deltas.length).toBeGreaterThanOrEqual(1);
    for (const delta of deltas) {
      expect(delta).toBe(5);
    }
  });

  it('[ECO-02] a finite deposit reaches zero, stays empty and reports it', () => {
    let world = economyWorld({
      startUnits: [{ owner: 1, typeId: 'unit.test.miner', x: -50, z: -46 }],
      oreDeposit: { x: -46, z: -50, amount: 3 },
    });
    const minerId = world.units[0]?.id ?? 0;
    world = step(world, [
      { kind: 'mine', unitIds: [minerId], depositId: 1, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 600; i += 1) {
      world = step(world, []);
      const deposit = world.deposits[0];
      const miner = world.units.find((unit) => unit.id === minerId);
      if (deposit && miner?.job?.stage === 'waiting' && deposit.amount === 0) {
        break;
      }
    }
    const deposit = world.deposits[0];
    const miner = world.units.find((unit) => unit.id === minerId);
    expect(deposit?.amount).toBe(0);
    expect(miner?.job?.stage).toBe('waiting');
    expect(stats(world)?.ore).toBe(3);
    expect(world.alerts.some((alert) => alert.kind === 'depositEmpty')).toBe(true);

    const before = stats(world)?.ore ?? 0;
    for (let i = 0; i < 100; i += 1) {
      world = step(world, []);
    }
    expect(world.deposits[0]?.amount).toBe(0);
    expect(stats(world)?.ore).toBe(before);
  });

  it('[ECO-03] metal is credited only at a pad and a destroyed tug loses its load', () => {
    let world = economyWorld({
      startUnits: [{ owner: 1, typeId: 'unit.test.tug', x: -50, z: -46 }],
      startStructures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 1, typeId: 'structure.test.metal_station', x: -46, z: -50 },
      ],
      metalDeposit: { x: -46, z: -50, amount: 100 },
    });
    const tugId = world.units[0]?.id ?? 0;
    const station = world.structures.find((item) => item.typeId === 'structure.test.metal_station');
    expect(station).toBeDefined();
    if (!station) {
      return;
    }
    world = step(world, [
      { kind: 'assign', unitIds: [tugId], stationId: station.id, tick: 1, issuer: 1 },
    ]);
    let previous = stats(world)?.metal ?? 0;
    const deltas: number[] = [];
    for (let i = 0; i < 500; i += 1) {
      world = step(world, []);
      const current = stats(world)?.metal ?? previous;
      if (current > previous) {
        deltas.push(current - previous);
        previous = current;
      }
      if (deltas.length >= 1) {
        break;
      }
    }
    expect(deltas).toEqual([2]);

    let lost = economyWorld({
      startUnits: [{ owner: 1, typeId: 'unit.test.tug', x: -50, z: -46 }],
      startStructures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 1, typeId: 'structure.test.metal_station', x: -46, z: -50 },
      ],
      metalDeposit: { x: -46, z: -50, amount: 100 },
    });
    const lostTugId = lost.units[0]?.id ?? 0;
    const lostStation = lost.structures.find((item) => item.typeId === 'structure.test.metal_station');
    expect(lostStation).toBeDefined();
    if (!lostStation) {
      return;
    }
    lost = step(lost, [
      { kind: 'assign', unitIds: [lostTugId], stationId: lostStation.id, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 300; i += 1) {
      lost = step(lost, []);
      const tug = lost.units.find((unit) => unit.id === lostTugId);
      if (tug?.job?.load && tug.job.stage === 'toPad') {
        break;
      }
    }
    const carrying = lost.units.find((unit) => unit.id === lostTugId);
    expect(carrying?.job?.load ?? 0).toBeGreaterThan(0);
    if (carrying) {
      carrying.hp = 0;
    }
    for (let i = 0; i < 100; i += 1) {
      lost = step(lost, []);
    }
    expect(lost.units.some((unit) => unit.id === lostTugId)).toBe(false);
    expect(lost.resources.find((item) => item.player === 1)?.metal).toBe(0);
  });

  it('[ECO-04] income stops entirely when every miner and tug is dead', () => {
    let world = economyWorld({
      startUnits: [{ owner: 1, typeId: 'unit.test.miner', x: -50, z: -46 }],
      oreDeposit: { x: -46, z: -50, amount: 100 },
    });
    const minerId = world.units[0]?.id ?? 0;
    world = step(world, [
      { kind: 'mine', unitIds: [minerId], depositId: 1, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < 200; i += 1) {
      world = step(world, []);
      if ((stats(world)?.ore ?? 0) > 0) {
        break;
      }
    }
    const miner = world.units.find((unit) => unit.id === minerId);
    expect(miner).toBeDefined();
    if (miner) {
      miner.hp = 0;
    }
    world = step(world, []);
    const stopped = stats(world)?.ore ?? 0;
    for (let i = 0; i < 300; i += 1) {
      world = step(world, []);
    }
    expect(stats(world)?.ore).toBe(stopped);
  });

  it('[ECO-05] resources never go negative under random commands', () => {
    const rng = new Rng(21);
    let world = economyWorld({
      startUnits: [
        { owner: 1, typeId: 'unit.test.miner', x: -50, z: -46 },
        { owner: 1, typeId: 'unit.test.tug', x: -50, z: -44 },
      ],
      startStructures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 1, typeId: 'structure.test.metal_station', x: -46, z: -50 },
      ],
      oreDeposit: { x: -46, z: -46, amount: 100 },
      metalDeposit: { x: -46, z: -50, amount: 100 },
      ore: 700,
      metal: 300,
    });
    const minerId = world.units[0]?.id ?? 0;
    const tugId = world.units[1]?.id ?? 0;
    const station = world.structures.find((item) => item.typeId === 'structure.test.metal_station');
    for (let tick = 0; tick < 800; tick += 1) {
      const commands: Command[] = [];
      if (tick % 10 === 0) {
        const roll = rng.int(0, 5);
        if (roll === 0) {
          commands.push({
            kind: 'buy',
            itemId: 'unit.test.scout',
            padId: world.structures[0]?.id ?? 1,
            tick: world.tick + 1,
            issuer: 1,
          });
        } else if (roll === 1 && world.dropQueue[0]) {
          commands.push({
            kind: 'cancel',
            orderId: world.dropQueue[0].id,
            tick: world.tick + 1,
            issuer: 1,
          });
        } else if (roll === 2) {
          commands.push({ kind: 'mine', unitIds: [minerId], depositId: 1, tick: world.tick + 1, issuer: 1 });
        } else if (roll === 3) {
          if (station) {
            commands.push({ kind: 'assign', unitIds: [tugId], stationId: station.id, tick: world.tick + 1, issuer: 1 });
          }
        } else {
          commands.push({ kind: 'salvage', unitIds: [minerId, tugId], tick: world.tick + 1, issuer: 1 });
        }
      }
      world = step(world, commands);
      const side = stats(world);
      expect(side?.ore ?? 0).toBeGreaterThanOrEqual(0);
      expect(side?.metal ?? 0).toBeGreaterThanOrEqual(0);
    }
  });

  it('[ECO-06] miner salvage refunds exactly the data-sheet percentage', () => {
    let world = economyWorld({
      startUnits: [{ owner: 1, typeId: 'unit.test.miner', x: -50, z: -46 }],
      ore: 0,
      metal: 0,
    });
    const miner = world.units[0];
    expect(miner).toBeDefined();
    if (!miner) {
      return;
    }
    world = step(world, [
      { kind: 'salvage', unitIds: [miner.id], tick: 1, issuer: 1 },
    ]);
    expect(world.units).toHaveLength(0);
    expect(stats(world)?.ore).toBe(40);
    expect(stats(world)?.metal).toBe(0);
  });
});
