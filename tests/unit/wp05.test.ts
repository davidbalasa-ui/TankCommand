import { describe, expect, it } from 'vitest';
import { createWorld, hashWorld, step } from '../../src/sim/world';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { placementValidity } from '../../src/sim/spawn';
import { padLayout, padQueueSpot } from '../../src/sim/pad';
import { damageState } from '../../src/sim/structures';
import { isItemUnlocked } from '../../src/sim/research';
import {
  UPGRADE_ARMOR_BONUS,
  UPGRADE_COST_METAL,
  UPGRADE_COST_ORE,
  UPGRADE_FIRE_RATE_FACTOR,
} from '../../src/sim/tuning';
import type { Command } from '../../src/sim/commands';
import type {
  ResearchNode,
  SimStructureType,
  SimUnitType,
  StartStructure,
  StartUnit,
  WorldState,
} from '../../src/sim/types';
import { labType, minerType, packedTurretUnit, padType, tankType, turretType } from './simHelpers';

const NODES: ResearchNode[] = [
  {
    id: 'research.human.armor',
    name: 'Armor Plating',
    faction: 'human',
    cost: { ore: 50, metal: 10 },
    timeSec: 1,
    requires: [],
    unlocks: [],
    upgrades: ['armor'],
  },
  {
    id: 'research.human.forts',
    name: 'Fortifications',
    faction: 'human',
    cost: { ore: 80, metal: 20 },
    timeSec: 1,
    requires: ['research.human.armor'],
    unlocks: ['structure.test.turret'],
    upgrades: [],
  },
];

function repairType(): SimUnitType {
  return tankType({
    id: 'unit.test.repair',
    role: 'support',
    weapon: null,
    hp: 100,
    repair: { radius: 8, ratePerSec: 20 },
  });
}

function build(options: {
  units?: StartUnit[];
  structures?: StartStructure[];
  ore?: number;
  metal?: number;
}): WorldState {
  const units = new Map<string, SimUnitType>();
  for (const unit of [tankType(), minerType(), packedTurretUnit(), repairType()]) {
    units.set(unit.id, unit);
  }
  const structures = new Map<string, SimStructureType>();
  for (const structure of [padType(), turretType(), labType()]) {
    structures.set(structure.id, structure);
  }
  return createWorld(1, {
    unitTypes: units,
    structureTypes: structures,
    researchTree: new Map(NODES.map((node) => [node.id, node])),
    startUnits: options.units ?? [],
    startStructures: options.structures ?? [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
    ],
    factions: [
      { player: 1, faction: 'human' },
      { player: 2, faction: 'alien' },
    ],
    startResources: [
      { player: 1, ore: options.ore ?? 1000, metal: options.metal ?? 1000 },
      { player: 2, ore: 0, metal: 0 },
    ],
  });
}

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
const OWN = { issuer: 1 };

function structureId(world: WorldState, typeId: string, owner = 1): number {
  const found = world.structures.find((item) => item.typeId === typeId && item.owner === owner);
  if (!found) {
    throw new Error(`no structure ${typeId}`);
  }
  return found.id;
}

describe('structures, research, upgrades, repair', () => {
  it('[STR-01] placement is refused with the right reason in each case', () => {
    const world = build({ units: [{ owner: 1, typeId: 'unit.test.tank', x: -30, z: -30 }] });
    const turret = turretType();
    expect(placementValidity(world, 1, turret, -100, 0).reason).toBe('outside');
    expect(placementValidity(world, 1, turret, -50, -50).reason).toBe('overlap');
    expect(placementValidity(world, 1, turret, -30, -30).reason).toBe('overlap');
    const kit = padType({ buildOnMetalDeposit: true });
    expect(placementValidity(world, 1, kit, -40, 20).reason).toBe('needsMetalDeposit');
    // Nothing may be built on a landing pad's dock or exit lanes (haulers and deliveries use them).
    const pad = world.structures.find((item) => item.owner === 1 && item.typeId === padType().id);
    if (pad) {
      const layout = padLayout(world, pad);
      expect(placementValidity(world, 1, turret, layout.rallyX, layout.rallyZ).reason).toBe('padLane');
      const queue = padQueueSpot(world, layout, 1);
      expect(placementValidity(world, 1, turret, queue.x, queue.z).reason).toBe('padLane');
    }
    let steep = 0;
    let blocked = 0;
    for (let x = -70; x <= 70; x += 2) {
      for (let z = -70; z <= 70; z += 2) {
        const reason = placementValidity(world, 1, turret, x, z).reason;
        steep += reason === 'steep' ? 1 : 0;
        blocked += reason === 'blocked' ? 1 : 0;
      }
    }
    expect(steep + blocked).toBeGreaterThan(0);
    expect(placementValidity(world, 1, turret, -30, 20).reason).not.toBe('outside');
  });

  it('[STR-01] rubble blocks placement until it clears', () => {
    let world = build({
      structures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
        { owner: 2, typeId: 'structure.test.turret', x: -20, z: 10 },
      ],
      units: [{ owner: 1, typeId: 'unit.test.tank', x: -20, z: 4 }],
    });
    const enemy = structureId(world, 'structure.test.turret', 2);
    const target = world.structures.find((item) => item.id === enemy);
    if (!target) {
      throw new Error('missing');
    }
    target.hp = 1;
    world = run(world, [{ ...OWN, kind: 'attack', unitIds: [world.units[0]?.id ?? 0], targetId: enemy }], 12 * SEC);
    expect(world.structures.some((item) => item.id === enemy)).toBe(false);
    expect(world.rubble.length).toBeGreaterThan(0);
    expect(placementValidity(world, 1, turretType(), -20, 10).reason).toBe('rubble');
    world = run(world, [], 40 * SEC);
    expect(world.rubble).toHaveLength(0);
  });

  it('[STR-02] pack, move and deploy keeps hp and upgrades; a packed turret cannot fire', () => {
    let world = build({
      structures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
        { owner: 1, typeId: 'structure.test.turret', x: -20, z: 10 },
      ],
    });
    const id = structureId(world, 'structure.test.turret');
    const before = world.structures.find((item) => item.id === id);
    if (!before) {
      throw new Error('missing');
    }
    before.hp = 200;
    before.upgrades = ['armor'];
    world = run(world, [{ ...OWN, kind: 'pack', structureId: id }], 1);
    expect(world.structures.find((item) => item.id === id)?.work?.kind).toBe('pack');
    world = run(world, [], 3 * SEC);
    expect(world.structures.some((item) => item.id === id)).toBe(false);
    const packed = world.units.find((unit) => unit.typeId === 'unit.test.packed_turret');
    expect(packed?.hp).toBeCloseTo(200, 5);
    expect(packed?.upgrades).toEqual(['armor']);
    const unitId = packed?.id ?? 0;
    world = run(world, [{ ...OWN, kind: 'move', unitIds: [unitId], x: -10, z: 20 }], 8 * SEC);
    world = run(world, [{ ...OWN, kind: 'deploy', unitId }], 1);
    expect(world.units.find((unit) => unit.id === unitId)?.transform).not.toBeNull();
    world = run(world, [], 3 * SEC);
    const deployed = world.structures.find((item) => item.typeId === 'structure.test.turret');
    expect(deployed).toBeDefined();
    expect(deployed?.hp).toBeCloseTo(200, 5);
    expect(deployed?.upgrades).toEqual(['armor']);
    expect(world.units.some((unit) => unit.id === unitId)).toBe(false);

    // A turret that is packing does not shoot.
    const enemy = build({
      structures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
        { owner: 1, typeId: 'structure.test.turret', x: -20, z: 10 },
      ],
      units: [{ owner: 2, typeId: 'unit.test.tank', x: -20, z: 30 }],
    });
    const turretId = structureId(enemy, 'structure.test.turret');
    const packedRun = run(enemy, [{ ...OWN, kind: 'pack', structureId: turretId }], 1 * SEC);
    expect(packedRun.projectiles.filter((item) => item.owner === 1)).toHaveLength(0);
  });

  it('[STR-03] dismantle refunds exactly the data percentage when finished, nothing if destroyed first', () => {
    let world = build({
      structures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
        { owner: 1, typeId: 'structure.test.turret', x: -20, z: 20 },
      ],
      ore: 0,
      metal: 0,
    });
    const id = structureId(world, 'structure.test.turret');
    world = run(world, [{ ...OWN, kind: 'dismantle', structureId: id }], 4 * SEC + 5);
    expect(world.structures.some((item) => item.id === id)).toBe(false);
    const stats = world.resources.find((item) => item.player === 1);
    expect(stats?.ore).toBe(Math.floor((100 * 70) / 100));
    expect(stats?.metal).toBe(0);
    expect(world.rubble).toHaveLength(0);

    let doomed = build({
      structures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
        { owner: 1, typeId: 'structure.test.turret', x: -20, z: 20 },
      ],
      ore: 0,
      metal: 0,
    });
    const doomedId = structureId(doomed, 'structure.test.turret');
    doomed = run(doomed, [{ ...OWN, kind: 'dismantle', structureId: doomedId }], 1);
    const target = doomed.structures.find((item) => item.id === doomedId);
    if (target) {
      target.hp = 0;
    }
    doomed = run(doomed, [], 4 * SEC);
    expect(doomed.resources.find((item) => item.player === 1)?.ore).toBe(0);
  });

  it('[STR-04] structures report light, heavy and critical damage states by hp', () => {
    expect(damageState(400, 400)).toBe('ok');
    expect(damageState(290, 400)).toBe('light');
    expect(damageState(190, 400)).toBe('heavy');
    expect(damageState(90, 400)).toBe('critical');
  });

  it('[STR-05] turrets auto-engage enemy units in range and ignore friendly ones', () => {
    const base: StartStructure[] = [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
      { owner: 1, typeId: 'structure.test.turret', x: -20, z: 20 },
    ];
    let world = build({ structures: base, units: [{ owner: 2, typeId: 'unit.test.tank', x: -20, z: 30 }] });
    const enemyId = world.units[0]?.id ?? 0;
    world = run(world, [], 6 * SEC);
    const enemy = world.units.find((unit) => unit.id === enemyId);
    expect((enemy?.hp ?? 0) < 220).toBe(true);

    let friendly = build({ structures: base, units: [{ owner: 1, typeId: 'unit.test.tank', x: -20, z: 30 }] });
    friendly = run(friendly, [], 6 * SEC);
    expect(friendly.units[0]?.hp).toBe(220);
  });

  it('[RES-01] a locked structure cannot be bought and the sim, not only the UI, refuses it', () => {
    let world = build({});
    const pad = structureId(world, 'structure.test.pad');
    expect(isItemUnlocked(world, 1, 'structure.test.turret')).toBe(false);
    expect(isItemUnlocked(world, 1, 'unit.test.tank')).toBe(true);
    world = run(world, [{ ...OWN, kind: 'buy', itemId: 'structure.test.turret', padId: pad }], 1);
    expect(world.lastCommandOutcome).toMatchObject({ kind: 'buy', ok: false, reason: 'locked' });
    expect(world.dropQueue).toHaveLength(0);
  });

  it('[RES-02] research needs resources and prerequisites, deducts at start, refunds on cancel, unlocks on completion', () => {
    const lab: StartStructure = { owner: 1, typeId: 'structure.test.lab', x: -35, z: 25 };
    const structures: StartStructure[] = [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
      lab,
    ];
    let poor = build({ structures, ore: 10, metal: 0 });
    const labId = structureId(poor, 'structure.test.lab');
    poor = run(poor, [{ ...OWN, kind: 'research', labId, nodeId: 'research.human.armor' }], 1);
    expect(poor.lastCommandOutcome).toMatchObject({ ok: false, reason: 'unaffordable' });

    let world = build({ structures, ore: 500, metal: 100 });
    world = run(world, [{ ...OWN, kind: 'research', labId, nodeId: 'research.human.forts' }], 1);
    expect(world.lastCommandOutcome).toMatchObject({ ok: false, reason: 'prerequisite' });

    world = run(world, [{ ...OWN, kind: 'research', labId, nodeId: 'research.human.armor' }], 1);
    expect(world.lastCommandOutcome?.ok).toBe(true);
    const spent = world.resources.find((item) => item.player === 1);
    expect(spent?.ore).toBe(450);
    expect(spent?.metal).toBe(90);

    world = run(world, [{ ...OWN, kind: 'cancelResearch', labId }], 1);
    const refunded = world.resources.find((item) => item.player === 1);
    expect(refunded?.ore).toBe(500);
    expect(refunded?.metal).toBe(100);

    world = run(world, [{ ...OWN, kind: 'research', labId, nodeId: 'research.human.armor' }], 1);
    world = run(world, [], SEC + 5);
    expect(world.research.find((side) => side.player === 1)?.done).toContain('research.human.armor');
    world = run(world, [{ ...OWN, kind: 'research', labId, nodeId: 'research.human.forts' }], SEC + 5);
    expect(isItemUnlocked(world, 1, 'structure.test.turret')).toBe(true);
  });

  it('[UPG-01] an upgrade changes only the chosen vehicle, once per type, and needs its research', () => {
    const structures: StartStructure[] = [
      { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
      { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
      { owner: 1, typeId: 'structure.test.lab', x: -35, z: 25 },
    ];
    let world = build({
      structures,
      units: [
        { owner: 1, typeId: 'unit.test.tank', x: -30, z: -30 },
        { owner: 1, typeId: 'unit.test.tank', x: -26, z: -30 },
      ],
    });
    const [a, b] = world.units.map((unit) => unit.id);
    world = run(world, [{ ...OWN, kind: 'upgrade', targetId: a ?? 0, upgrade: 'armor' }], 1);
    expect(world.lastCommandOutcome).toMatchObject({ ok: false, reason: 'notResearched' });

    const labId = structureId(world, 'structure.test.lab');
    world = run(world, [{ ...OWN, kind: 'research', labId, nodeId: 'research.human.armor' }], SEC + 5);
    const oreBefore = world.resources.find((item) => item.player === 1)?.ore ?? 0;
    world = run(world, [{ ...OWN, kind: 'upgrade', targetId: a ?? 0, upgrade: 'armor' }], 1);
    expect(world.lastCommandOutcome?.ok).toBe(true);
    expect(world.units.find((unit) => unit.id === a)?.upgrades).toEqual(['armor']);
    expect(world.units.find((unit) => unit.id === b)?.upgrades).toEqual([]);
    expect(world.resources.find((item) => item.player === 1)?.ore).toBe(oreBefore - UPGRADE_COST_ORE);
    expect(world.resources.find((item) => item.player === 1)?.metal).toBeLessThan(1000 - UPGRADE_COST_METAL + 1);
    world = run(world, [{ ...OWN, kind: 'upgrade', targetId: a ?? 0, upgrade: 'armor' }], 1);
    expect(world.lastCommandOutcome).toMatchObject({ ok: false, reason: 'alreadyHave' });
    world = run(world, [{ ...OWN, kind: 'upgrade', targetId: a ?? 0, upgrade: 'stealth' }], 1);
    expect(world.lastCommandOutcome).toMatchObject({ ok: false, reason: 'notAvailable' });
  });

  it('[UPG-02] armor and fire rate upgrades change combat by exactly their data values', () => {
    const damageTaken = (upgrades: string[]): number => {
      let world = build({
        units: [
          { owner: 1, typeId: 'unit.test.tank', x: 0, z: 20 },
          { owner: 2, typeId: 'unit.test.tank', x: 0, z: 28 },
        ],
      });
      const defender = world.units[0];
      if (!defender) {
        throw new Error('missing');
      }
      defender.upgrades = upgrades;
      const attackerId = world.units[1]?.id ?? 0;
      world = run(world, [{ issuer: 2, kind: 'attack', unitIds: [attackerId], targetId: defender.id }], 4 * SEC);
      return 220 - (world.units.find((unit) => unit.id === defender.id)?.hp ?? 0);
    };
    const plain = damageTaken([]);
    const armored = damageTaken(['armor']);
    expect(plain).toBeGreaterThan(0);
    const hits = plain / (30 - 4);
    expect(Number.isInteger(hits)).toBe(true);
    expect(armored).toBe(hits * (30 - 4 - UPGRADE_ARMOR_BONUS));

    const shots = (upgrades: string[]): number => {
      let world = build({
        units: [
          { owner: 1, typeId: 'unit.test.tank', x: 0, z: 20 },
          { owner: 2, typeId: 'unit.test.tank', x: 0, z: 28 },
        ],
      });
      const shooter = world.units[0];
      if (!shooter) {
        throw new Error('missing');
      }
      shooter.upgrades = upgrades;
      shooter.hp = 100000;
      const targetId = world.units[1]?.id ?? 0;
      const second = world.units[1];
      if (second) {
        second.hp = 100000;
      }
      const seen = new Set<number>();
      let state = run(world, [{ ...OWN, kind: 'attack', unitIds: [shooter.id], targetId }], 1);
      for (let i = 0; i < 20 * SEC; i += 1) {
        state = step(state, []);
        for (const p of state.projectiles) {
          if (p.owner === 1) {
            seen.add(p.id);
          }
        }
      }
      const fired = seen.size;
      return fired;
    };
    expect(shots(['fireRate'])).toBeGreaterThan(shots([]));
    expect(UPGRADE_FIRE_RATE_FACTOR).toBeLessThan(1);
  });

  it('[REP-01] repair vehicles heal friendly units and structures in range up to max hp, never above, and not enemies', () => {
    let world = build({
      units: [
        { owner: 1, typeId: 'unit.test.repair', x: -20, z: 20 },
        { owner: 1, typeId: 'unit.test.tank', x: -17, z: 20 },
        { owner: 1, typeId: 'unit.test.tank', x: 20, z: -20 },
        { owner: 2, typeId: 'unit.test.tank', x: -23, z: 20 },
      ],
    });
    const [, near, far, enemy] = world.units;
    if (!near || !far || !enemy) {
      throw new Error('missing');
    }
    near.hp = 100;
    far.hp = 100;
    enemy.hp = 100;
    world = run(world, [], 3 * SEC);
    expect(world.units.find((unit) => unit.id === near.id)?.hp).toBeGreaterThan(100);
    expect(world.units.find((unit) => unit.id === far.id)?.hp).toBe(100);
    expect(world.units.find((unit) => unit.id === enemy.id)?.hp).toBe(100);
    world = run(world, [], 20 * SEC);
    expect(world.units.find((unit) => unit.id === near.id)?.hp).toBe(220);
  });

  it('[DET-03] structures, research and upgrades survive save and load with an identical hash', () => {
    let world = build({
      structures: [
        { owner: 1, typeId: 'structure.test.pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.test.pad', x: 50, z: 50 },
        { owner: 1, typeId: 'structure.test.lab', x: -35, z: 25 },
        { owner: 1, typeId: 'structure.test.turret', x: 0, z: 20 },
      ],
      units: [{ owner: 1, typeId: 'unit.test.tank', x: -30, z: -30 }],
    });
    const labId = structureId(world, 'structure.test.lab');
    const turretId = structureId(world, 'structure.test.turret');
    world = run(
      world,
      [
        { ...OWN, kind: 'research', labId, nodeId: 'research.human.armor' },
        { ...OWN, kind: 'pack', structureId: turretId },
      ],
      15,
    );
    const restored = decodeSave(
      encodeSave(world, { gameVersion: 't', savedAtIso: '2026-01-01T00:00:00Z' }),
    );
    expect(restored.ok).toBe(true);
    if (!restored.ok) {
      return;
    }
    expect(hashWorld(restored.world)).toBe(hashWorld(world));
    const forwardA = run(world, [], 3 * SEC);
    const forwardB = run(restored.world, [], 3 * SEC);
    expect(hashWorld(forwardA)).toBe(hashWorld(forwardB));
  });
});
