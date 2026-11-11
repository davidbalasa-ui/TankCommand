import { describe, expect, it } from 'vitest';
import { createWorld, step, hashWorld } from '../../src/sim/world';
import { encodeSave, decodeSave } from '../../src/platform/saves';
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
import { PAD_LAND_SEC } from '../../src/sim/pad';

// Test pads deliver in 0.2 s, then the delivery spends PAD_LAND_SEC coming down onto the pad.
const DELIVERY_TICKS = Math.ceil((0.2 + PAD_LAND_SEC) * 20) + 4;

function types(): {
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

function world(options: {
  ore?: number;
  metal?: number;
  pad?: boolean;
  units?: StartUnit[];
  structures?: StartStructure[];
  oreDeposit?: { x: number; z: number; amount: number };
  metalDeposit?: { x: number; z: number; amount: number };
}) {
  const maps = types();
  const deposits: Array<{ kind: 'ore' | 'metal'; x: number; z: number; amount: number }> = [];
  if (options.oreDeposit) {
    deposits.push({ kind: 'ore', ...options.oreDeposit });
  }
  if (options.metalDeposit) {
    deposits.push({ kind: 'metal', ...options.metalDeposit });
  }
  // Both sides get a pad. The single-player world is decided on tick 1 (see
  // docs/decisions: commands are ignored once `world.result` is set), which
  // would silently drop the `cancel` at tick 2 and the `placeKit` at tick 12
  // in the multi-step commands below.
  const structures = options.structures ?? [
    ...(options.pad === false ? [] : [{ owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 }]),
    { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
  ];
  return createWorld(1, {
    unitTypes: maps.units,
    structureTypes: maps.structures,
    startUnits: options.units ?? [],
    startStructures: structures,
    deposits,
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
    startResources: [
      { player: 1, ore: options.ore ?? 500, metal: options.metal ?? 100 },
      { player: 2, ore: 0, metal: 0 },
    ],
  });
}

function initialPad(worldState: ReturnType<typeof world>): number {
  return (
    worldState.structures.find(
      (structure) => structure.typeId === 'structure.test.pad' && structure.owner === 1,
    )?.id ?? 0
  );
}

describe('drops', () => {
  it('[DROP-01] buying deducts full cost and refuses unknown, unaffordable, over-cap and no-pad orders', () => {
    let buy = world({ ore: 500, metal: 100 });
    const padId = initialPad(buy);
    buy = step(buy, [
      { kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 },
    ]);
    expect(buy.dropQueue).toHaveLength(1);
    expect(buy.resources[0]?.ore).toBe(450);
    expect(buy.lastCommandOutcome?.ok).toBe(true);

    const unknown = step(world({}), [
      { kind: 'buy', itemId: 'unit.nope', padId: initialPad(world({})), tick: 1, issuer: 1 },
    ]);
    expect(unknown.lastCommandOutcome?.reason).toBe('unknownItem');

    const unaffordable = step(world({ ore: 0, metal: 0 }), [
      { kind: 'buy', itemId: 'unit.test.scout', padId: initialPad(world({ ore: 0, metal: 0 })), tick: 1, issuer: 1 },
    ]);
    expect(unaffordable.lastCommandOutcome?.reason).toBe('unaffordable');

    const noPad = step(world({ pad: false }), [
      { kind: 'buy', itemId: 'unit.test.scout', padId: 1, tick: 1, issuer: 1 },
    ]);
    expect(noPad.lastCommandOutcome?.reason).toBe('padGone');

    const manyUnits: StartUnit[] = [];
    for (let i = 0; i < 200; i += 1) {
      manyUnits.push({
        owner: 1,
        typeId: 'unit.test.scout',
        x: -70 + (i % 20) * 2,
        z: -70 + Math.floor(i / 20) * 2,
      });
    }
    const capped = world({ units: manyUnits, ore: 500 });
    const cappedPad = initialPad(capped);
    const afterCap = step(capped, [
      { kind: 'buy', itemId: 'unit.test.scout', padId: cappedPad, tick: 1, issuer: 1 },
    ]);
    expect(afterCap.lastCommandOutcome?.reason).toBe('cap');
    expect(afterCap.resources[0]?.ore).toBe(500);
  });

  it('[DROP-02] cancel refunds in full before delivery and delivered items cannot be cancelled', () => {
    const base = world({ ore: 500 });
    const padId = initialPad(base);
    let cancelled = step(base, [
      { kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 },
    ]);
    const orderId = cancelled.dropQueue[0]?.id ?? 0;
    expect(cancelled.resources[0]?.ore).toBe(450);
    cancelled = step(cancelled, [
      { kind: 'cancel', orderId, tick: 2, issuer: 1 },
    ]);
    expect(cancelled.dropQueue).toHaveLength(0);
    expect(cancelled.resources[0]?.ore).toBe(500);
    expect(cancelled.lastCommandOutcome?.ok).toBe(true);

    let delivered = step(base, [
      { kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < DELIVERY_TICKS; i += 1) {
      delivered = step(delivered, []);
    }
    expect(delivered.dropQueue).toHaveLength(0);
    const deliveredId = orderId;
    delivered = step(delivered, [
      { kind: 'cancel', orderId: deliveredId, tick: delivered.tick + 1, issuer: 1 },
    ]);
    expect(delivered.lastCommandOutcome?.ok).toBe(false);
    expect(delivered.resources[0]?.ore).toBe(450);
  });

  it('[DROP-03] units deliver beside the chosen pad after delivery time and wait with no pad', () => {
    const base = world({ ore: 500 });
    const padId = initialPad(base);
    const pad = base.structures.find((structure) => structure.id === padId);
    expect(pad).toBeDefined();
    if (!pad) {
      return;
    }
    let delivered = step(base, [
      { kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < DELIVERY_TICKS; i += 1) {
      delivered = step(delivered, []);
    }
    const unit = delivered.units.find((item) => item.typeId === 'unit.test.scout');
    expect(unit).toBeDefined();
    if (unit) {
      expect(Math.hypot(unit.x - pad.x, unit.z - pad.z)).toBeLessThan(20);
    }

    let waiting = step(base, [
      { kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 },
    ]);
    const waitingPad = waiting.structures.find((structure) => structure.id === padId);
    expect(waitingPad).toBeDefined();
    if (waitingPad) {
      waitingPad.hp = 0;
    }
    for (let i = 0; i < 20; i += 1) {
      waiting = step(waiting, []);
    }
    expect(waiting.dropQueue).toHaveLength(1);
    expect(waiting.units.some((item) => item.typeId === 'unit.test.scout')).toBe(false);
  });

  it('[DROP-04] kits only place on valid ground and metal stations only on metal deposits', () => {
    const base = world({
      ore: 1000,
      metal: 500,
      oreDeposit: { x: -42, z: -48, amount: 100 },
      metalDeposit: { x: -58, z: -52, amount: 100 },
    });
    const padId = initialPad(base);
    let buying = step(base, [
      { kind: 'buy', itemId: 'structure.test.pad', padId, tick: 1, issuer: 1 },
    ]);
    for (let i = 0; i < DELIVERY_TICKS; i += 1) {
      buying = step(buying, []);
    }
    expect(buying.pendingKits).toHaveLength(1);
    const kitId = buying.pendingKits[0]?.id ?? 0;
    const outside = step(buying, [
      { kind: 'placeKit', kitId, x: 1000, z: 1000, tick: buying.tick + 1, issuer: 1 },
    ]);
    expect(outside.lastCommandOutcome?.reason).toBe('outside');
    expect(outside.pendingKits).toHaveLength(1);
    const valid = step(buying, [
      { kind: 'placeKit', kitId, x: -42, z: -42, tick: buying.tick + 1, issuer: 1 },
    ]);
    expect(valid.lastCommandOutcome?.ok).toBe(true);
    expect(valid.pendingKits).toHaveLength(0);
    expect(
      valid.structures.filter(
        (structure) => structure.typeId === 'structure.test.pad' && structure.owner === 1,
      ),
    ).toHaveLength(2);

    let stationWorld = step(valid, [
      { kind: 'buy', itemId: 'structure.test.metal_station', padId, tick: valid.tick + 1, issuer: 1 },
    ]);
    for (let i = 0; i < DELIVERY_TICKS; i += 1) {
      stationWorld = step(stationWorld, []);
    }
    const stationKit = stationWorld.pendingKits[0]?.id ?? 0;
    // Clear ground that is NOT a metal deposit: `(-56, -46)` sits inside the
    // start disc (flat, unblocked) and is more than a footprint+clearance away
    // from the Landing Pad placed at `(-42, -42)` above, so the only rule this
    // placement can fail is the metal-deposit rule. `(-42, -42)` would overlap
    // that pad and be reported as `'overlap'` instead.
    const wrongGround = step(stationWorld, [
      { kind: 'placeKit', kitId: stationKit, x: -56, z: -46, tick: stationWorld.tick + 1, issuer: 1 },
    ]);
    expect(wrongGround.lastCommandOutcome?.reason).toBe('needsMetalDeposit');
    const onDeposit = step(stationWorld, [
      { kind: 'placeKit', kitId: stationKit, x: -58, z: -52, tick: stationWorld.tick + 1, issuer: 1 },
    ]);
    expect(onDeposit.lastCommandOutcome?.ok).toBe(true);
    expect(onDeposit.structures.some((structure) => structure.typeId === 'structure.test.metal_station')).toBe(true);
  });

  it('[DET-02] economy and drops survive save/load mid-delivery with the same hash', () => {
    const base = world({ ore: 500, pad: true });
    const padId = initialPad(base);
    let first = step(base, [
      { kind: 'buy', itemId: 'unit.test.scout', padId, tick: 1, issuer: 1 },
    ]);
    // Save mid-descent: the order is already coming down onto the pad.
    for (let i = 0; i < 20; i += 1) {
      first = step(first, []);
    }
    expect(first.dropQueue[0]?.landingSec).toBeGreaterThan(0);
    const text = encodeSave(first, {
      gameVersion: 'test',
      savedAtIso: '2026-11-17T00:00:00.000Z',
    });
    const decoded = decodeSave(text);
    expect(decoded.ok).toBe(true);
    if (!decoded.ok) {
      return;
    }
    let resumed = decoded.world;
    let uninterrupted = first;
    for (let i = 0; i < DELIVERY_TICKS; i += 1) {
      resumed = step(resumed, []);
      uninterrupted = step(uninterrupted, []);
    }
    expect(hashWorld(resumed)).toBe(hashWorld(uninterrupted));
    expect(resumed.dropQueue).toHaveLength(0);
  });
});
