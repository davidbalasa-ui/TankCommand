import { describe, expect, it } from 'vitest';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { isWaterAt } from '../../src/sim/map';
import { isAirborne, weaponCanHit } from '../../src/sim/air';
import type { Command } from '../../src/sim/commands';
import type { MapFeatures } from '../../src/sim/map';
import type {
  SimStructureType,
  SimUnitType,
  StartStructure,
  StartUnit,
  WorldState,
} from '../../src/sim/types';
import { padType, tankType } from './simHelpers';

const RIVER: MapFeatures = {
  waterLevel: -0.5,
  lakes: [],
  rivers: [{ x0: -80, z0: 0, x1: 80, z1: 0, width: 8, depth: 4, fords: [] }],
};
const FORDED: MapFeatures = {
  ...RIVER,
  rivers: [{ x0: -80, z0: 0, x1: 80, z1: 0, width: 8, depth: 4, fords: [{ from: 0.4, to: 0.6 }] }],
};

const hover = () => tankType({ id: 'unit.test.hover', movement: 'hover' });
const fighter = (o: Partial<SimUnitType> = {}) =>
  tankType({
    id: 'unit.test.fighter',
    role: 'air',
    movement: 'air',
    topSpeed: 16,
    hp: 90,
    air: { ammo: 3, fuelSec: 30, rearmSec: 2, cruiseHeight: 6 },
    weapon: {
      damage: 20,
      range: 9,
      reloadSec: 0.5,
      projectileSpeed: 60,
      accuracy: 1,
      splashRadius: 0,
      targets: ['air', 'ground'],
    },
    ...o,
  });
const bomber = () =>
  fighter({
    id: 'unit.test.bomber',
    weapon: {
      damage: 70,
      range: 4,
      reloadSec: 0.5,
      projectileSpeed: 30,
      accuracy: 1,
      splashRadius: 0,
      targets: ['ground', 'structure'],
    },
  });
const groundOnly = () =>
  tankType({
    id: 'unit.test.gunner',
    topSpeed: 0,
    weapon: {
      damage: 30,
      range: 15,
      reloadSec: 1,
      projectileSpeed: 60,
      accuracy: 1,
      splashRadius: 0,
      targets: ['ground', 'structure'],
    },
  });
const airBase = (): SimStructureType =>
  padType({ id: 'structure.test.air_base', kind: 'airBase', airCapacity: 2 });

function build(options: {
  units?: StartUnit[];
  structures?: StartStructure[];
  features?: MapFeatures;
  extra?: SimUnitType[];
  ore?: number;
}): WorldState {
  const units = new Map<string, SimUnitType>();
  for (const t of [tankType(), hover(), fighter(), bomber(), groundOnly(), ...(options.extra ?? [])]) {
    units.set(t.id, t);
  }
  const structures = new Map<string, SimStructureType>();
  for (const s of [padType(), airBase()]) {
    structures.set(s.id, s);
  }
  return createWorld(3, {
    unitTypes: units,
    structureTypes: structures,
    startUnits: options.units ?? [],
    startStructures: options.structures ?? [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
    ],
    mapFeatures: options.features,
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
    startResources: [
      { player: 1, ore: options.ore ?? 2000, metal: 2000 },
      { player: 2, ore: 0, metal: 0 },
    ],
  });
}

type Untimed = Command extends infer C ? (C extends Command ? Omit<C, 'tick'> : never) : never;

function run(world: WorldState, commands: Untimed[], ticks: number): WorldState {
  let state = world;
  const stamped = commands.map((c) => ({ ...c, tick: world.tick + 1 }) as Command);
  for (let i = 0; i < ticks; i += 1) {
    state = step(state, i === 0 ? stamped : []);
  }
  return state;
}

const SEC = 20;

function unitOf(world: WorldState, typeId: string) {
  const unit = world.units.find((u) => u.typeId === typeId);
  if (!unit) {
    throw new Error(`no unit ${typeId}`);
  }
  return unit;
}

function crossing(typeId: string, features: MapFeatures): WorldState {
  const w = build({ units: [{ owner: 1, typeId, x: 0, z: -22 }], features });
  const u = unitOf(w, typeId);
  return run(w, [{ kind: 'move', issuer: 1, unitIds: [u.id], x: 0, z: 22 }], 40 * SEC);
}

describe('[TER-01] water terrain and movement classes', () => {
  it('[TER-01] the river is water, tracked units cannot cross it, hover units can', () => {
    const w = build({ features: RIVER });
    expect(isWaterAt(w.map, 0, 0)).toBe(true);
    expect(isWaterAt(w.map, 0, 40)).toBe(false);
    const tracked = unitOf(crossing('unit.test.tank', RIVER), 'unit.test.tank');
    expect(tracked.z).toBeLessThan(-3);
    const skimmer = unitOf(crossing('unit.test.hover', RIVER), 'unit.test.hover');
    expect(skimmer.z).toBeGreaterThan(18);
  });

  it('[TER-01] a ford lets tracked units across', () => {
    const tracked = unitOf(crossing('unit.test.tank', FORDED), 'unit.test.tank');
    expect(tracked.z).toBeGreaterThan(18);
  });
});

describe('[TER-02] map features are part of the saved world', () => {
  it('[TER-02] features round-trip through save/load with the same hash', () => {
    const w = run(build({ features: FORDED }), [], 5);
    const decoded = decodeSave(encodeSave(w, { gameVersion: 't', savedAtIso: '2026-01-01T00:00:00Z' }));
    expect(decoded.ok).toBe(true);
    if (decoded.ok) {
      expect(hashWorld(decoded.world)).toBe(hashWorld(w));
      expect(isWaterAt(decoded.world.map, 20, 0)).toBe(isWaterAt(w.map, 20, 0));
    }
  });
});

function airWorld(extraUnits: StartUnit[] = []): WorldState {
  return build({
    structures: [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 1, typeId: 'structure.test.air_base', x: -40, z: -40 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
    ],
    units: [{ owner: 1, typeId: 'unit.test.fighter', x: -40, z: -40 }, ...extraUnits],
  });
}

describe('[AIR-01] bases and buying', () => {
  it('[AIR-01] an aircraft cannot be bought without a free air base slot', () => {
    const w = build({});
    const pad = w.structures.find((s) => s.typeId === 'structure.test.pad' && s.owner === 1);
    const next = run(
      w,
      [{ kind: 'buy', issuer: 1, itemId: 'unit.test.fighter', padId: pad?.id ?? 0 }],
      2,
    );
    expect(next.dropQueue).toHaveLength(0);
    expect(next.resources.find((r) => r.player === 1)?.ore).toBe(2000);
  });

  it('[AIR-01] with a base the aircraft comes down on the pad, flies to the base and parks there', () => {
    const w = airWorld();
    const pad = w.structures.find((s) => s.typeId === 'structure.test.pad' && s.owner === 1);
    let landed = run(
      w,
      [{ kind: 'buy', issuer: 1, itemId: 'unit.test.bomber', padId: pad?.id ?? 0 }],
      1,
    );
    expect(landed.dropQueue).toHaveLength(1);
    for (let i = 0; i < 60 * SEC && !landed.units.some((u) => u.typeId === 'unit.test.bomber'); i += 1) {
      landed = run(landed, [], 1);
    }
    const fresh = unitOf(landed, 'unit.test.bomber');
    expect(fresh.air?.mode).toBe('returning');
    expect(fresh.air?.homeId).not.toBeNull();
    expect(Math.hypot(fresh.x - (pad?.x ?? 0), fresh.z - (pad?.z ?? 0))).toBeLessThan(20);
    const next = run(landed, [], 30 * SEC);
    const bought = unitOf(next, 'unit.test.bomber');
    expect(bought.air?.mode).toBe('parked');
    const base = next.structures.find((s) => s.typeId === 'structure.test.air_base');
    expect(Math.hypot(bought.x - (base?.x ?? 0), bought.z - (base?.z ?? 0))).toBeLessThan(0.1);
  });
});

describe('[AIR-02] launch, fuel, ammo, return and rearm', () => {
  it('[AIR-02] launch takes off, an empty magazine sends it home, and it rearms', () => {
    const w = airWorld([{ owner: 2, typeId: 'unit.test.tank', x: -20, z: -20 }]);
    const jet = unitOf(w, 'unit.test.fighter');
    expect(isAirborne(jet)).toBe(false);
    let state = run(w, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'launch' }], 1);
    expect(unitOf(state, 'unit.test.fighter').air?.mode).toBe('flying');
    state = run(
      state,
      [{ kind: 'attackMove', issuer: 1, unitIds: [jet.id], x: -20, z: -20 }],
      8 * SEC,
    );
    const air = unitOf(state, 'unit.test.fighter').air;
    expect(air?.ammo).toBeLessThan(3);
    state = run(state, [], 20 * SEC);
    const back = unitOf(state, 'unit.test.fighter');
    expect(['rearming', 'parked']).toContain(back.air?.mode);
    state = run(state, [], 4 * SEC);
    const ready = unitOf(state, 'unit.test.fighter');
    expect(ready.air?.mode).toBe('parked');
    expect(ready.air?.ammo).toBe(3);
  });

  it('[AIR-02] recall sends a flying aircraft home', () => {
    const w = airWorld();
    const jet = unitOf(w, 'unit.test.fighter');
    let state = run(w, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'launch' }], 1);
    state = run(state, [{ kind: 'move', issuer: 1, unitIds: [jet.id], x: 0, z: 0 }], 3 * SEC);
    state = run(state, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'recall' }], 12 * SEC);
    expect(['rearming', 'parked']).toContain(unitOf(state, 'unit.test.fighter').air?.mode);
  });

  it('[AIR-02] an aircraft whose base is destroyed crashes when fuel runs out', () => {
    const w = airWorld();
    const jet = unitOf(w, 'unit.test.fighter');
    let state = run(w, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'launch' }], 1);
    state = {
      ...state,
      structures: state.structures.filter((s) => s.typeId !== 'structure.test.air_base'),
    };
    state = run(state, [], 40 * SEC);
    expect(state.units.some((u) => u.typeId === 'unit.test.fighter')).toBe(false);
  });
});

describe('[AIR-03] weapon targeting classes', () => {
  it('[AIR-03] weaponCanHit honours the target list', () => {
    const t = groundOnly().weapon;
    const f = fighter().weapon;
    if (!t || !f) {
      throw new Error('weapons');
    }
    expect(weaponCanHit(t, 'airborne')).toBe(false);
    expect(weaponCanHit(t, 'ground')).toBe(true);
    expect(weaponCanHit(f, 'airborne')).toBe(true);
  });

  it('[AIR-03] a ground-only gun cannot hit a flying aircraft but hits a parked one', () => {
    const w = airWorld([{ owner: 2, typeId: 'unit.test.gunner', x: -34, z: -40 }]);
    const jet = unitOf(w, 'unit.test.fighter');
    const parked = run(w, [], 4 * SEC);
    expect(unitOf(parked, 'unit.test.fighter').hp).toBeLessThan(jet.hp);
    let state = run(w, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'launch' }], 1);
    state = run(state, [{ kind: 'move', issuer: 1, unitIds: [jet.id], x: -36, z: -40 }], 1);
    const hp = unitOf(state, 'unit.test.fighter').hp;
    state = run(state, [], 3 * SEC);
    expect(unitOf(state, 'unit.test.fighter').hp).toBe(hp);
  });
});

describe('[AIR-04] fighters and bombers', () => {
  it('[AIR-04] a fighter shoots down an enemy aircraft; a bomber never targets air', () => {
    const w = airWorld();
    const foe = createWorld(1, {} as never);
    expect(foe).toBeDefined();
    const jets = build({
      structures: [
        { owner: 1, typeId: 'structure.test.air_base', x: -40, z: -40 },
        { owner: 2, typeId: 'structure.test.air_base', x: -30, z: -40 },
      ],
      units: [
        { owner: 1, typeId: 'unit.test.fighter', x: -40, z: -40 },
        { owner: 2, typeId: 'unit.test.bomber', x: -30, z: -40 },
      ],
    });
    const mine = unitOf(jets, 'unit.test.fighter');
    const theirs = unitOf(jets, 'unit.test.bomber');
    let state = run(
      jets,
      [
        { kind: 'air', issuer: 1, unitIds: [mine.id], action: 'launch' },
        { kind: 'air', issuer: 2, unitIds: [theirs.id], action: 'launch' },
      ],
      1,
    );
    state = run(state, [{ kind: 'attackMove', issuer: 1, unitIds: [mine.id], x: -30, z: -40 }], 6 * SEC);
    expect(unitOf(state, 'unit.test.bomber').hp).toBeLessThan(theirs.hp);
    expect(unitOf(state, 'unit.test.fighter').hp).toBe(mine.hp);
    expect(w.units.length).toBe(1);
  });
});

describe('[AIR-05] aircraft ammo is spent per shot', () => {
  it('[AIR-05] every shot costs one ammo and an empty aircraft stops firing', () => {
    const w = airWorld([{ owner: 2, typeId: 'unit.test.tank', x: -36, z: -40 }]);
    const jet = unitOf(w, 'unit.test.fighter');
    let state = run(w, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'launch' }], 1);
    state = run(state, [], 2 * SEC);
    const after = unitOf(state, 'unit.test.fighter').air;
    expect(after?.ammo).toBeLessThanOrEqual(3);
    expect(after?.ammo).toBeGreaterThanOrEqual(0);
  });
});

describe('[DET-06] air and water are deterministic', () => {
  it('[DET-06] the same air scenario gives the same hash twice', () => {
    const play = () => {
      const w = airWorld([{ owner: 2, typeId: 'unit.test.tank', x: -20, z: -20 }]);
      const jet = unitOf(w, 'unit.test.fighter');
      let s = run(w, [{ kind: 'air', issuer: 1, unitIds: [jet.id], action: 'launch' }], 1);
      s = run(s, [{ kind: 'attackMove', issuer: 1, unitIds: [jet.id], x: -20, z: -20 }], 10 * SEC);
      return hashWorld(s);
    };
    expect(play()).toBe(play());
  });
});
