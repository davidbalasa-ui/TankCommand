import { readFileSync, readdirSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';
import { data, aiMatch, runMatch, hashWorld, stepWithAi } from './aiHelpers';
import { thinkAi } from '../../src/ai/ai';
import { addAi } from '../../src/ai/driver';
import { validateCommand } from '../../src/sim/commands';
import { relation } from '../../src/sim/diplomacy';
import { createSkirmishWorld } from '../../src/data/simData';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { perceivedUnits } from '../../src/sim/vision';
import { createWorld } from '../../src/sim/world';
import type { WorldState } from '../../src/sim/types';

interface Played {
  seed: number;
  hardFirst: boolean;
  world: WorldState;
  tick: number;
  stuck: number;
}

const played: Played[] = [];

function playMatch(seed: number): Played {
  const hardFirst = seed % 2 === 1;
  let world = aiMatch(seed, hardFirst ? 'hard' : 'easy', hardFirst ? 'easy' : 'hard');
  let stuck = 0;
  const limit = 45 * 60 * 20;
  while (world.result === null && world.tick < limit) {
    world = stepWithAi(world);
    if (world.tick % 200 === 0) {
      for (const unit of world.units) {
        if (unit.stuckTicks > 20 * 60) {
          stuck += 1;
        }
      }
    }
  }
  return { seed, hardFirst, world, tick: world.tick, stuck };
}

describe('enemy AI', () => {
  beforeAll(() => {
    for (let seed = 1; seed <= 10; seed += 1) {
      played.push(playMatch(seed));
    }
  }, 600_000);

  it('[AI-04] every one of 10 fixed-seed AI-vs-AI matches ends with a winner before 45 game minutes', () => {
    expect(played).toHaveLength(10);
    for (const match of played) {
      expect(match.world.result, `seed ${match.seed}`).not.toBeNull();
      expect(match.tick).toBeLessThan(45 * 60 * 20);
    }
  });

  it('[AI-07] hard beats easy in at least 8 of 10 fixed-seed matches', () => {
    const hardWins = played.filter((m) => m.world.result?.winner === (m.hardFirst ? 1 : 2)).length;
    expect(hardWins).toBeGreaterThanOrEqual(8);
  });

  it('[AI-08] no unit stays stuck longer than the re-plan time in any of the 10 matches', () => {
    expect(played.reduce((sum, m) => sum + m.stuck, 0)).toBe(0);
  });

  it('[AI-03] AI spending never exceeds its income plus starting resources', () => {
    for (const match of played) {
      for (const state of match.world.aiStates) {
        const stats = match.world.resources.find((r) => r.player === state.player);
        const income = (stats?.oreGathered ?? 0) + (stats?.metalGathered ?? 0) + 600;
        expect(state.spent, `seed ${match.seed} side ${state.player}`).toBeLessThanOrEqual(income);
        expect(stats?.ore ?? 0).toBeGreaterThanOrEqual(0);
        expect(stats?.metal ?? 0).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('[AI-01] AI issues only validated commands from its own side and cannot create state', () => {
    let world = aiMatch(3, 'normal', 'normal');
    let issued = 0;
    for (let i = 0; i < 20 * 120; i += 1) {
      for (const state of world.aiStates) {
        const { commands } = thinkAi(world, state);
        for (const command of commands) {
          expect(validateCommand(command)).not.toBeNull();
          expect(command.issuer).toBe(state.player);
          issued += 1;
        }
      }
      world = stepWithAi(world);
    }
    expect(issued).toBeGreaterThan(5);
    const files = readdirSync('src/ai').filter((f) => f.endsWith('.ts'));
    const allowed = [
      '../sim/types', '../sim/commands', '../sim/vision', '../sim/diplomacy', '../sim/spawn',
      '../sim/rng', '../sim/economy', '../sim/research', '../sim/world', './ai', './aiData', './driver',
    ];
    for (const file of files) {
      const text = readFileSync(`src/ai/${file}`, 'utf8');
      for (const match of text.matchAll(/from '([^']+)'/g)) {
        expect(allowed, `${file} imports ${match[1]}`).toContain(match[1]);
      }
      expect(text).not.toMatch(/world\.(units|structures)\s*=/);
    }
  });

  it('[AI-02] moving a hidden enemy unit never changes the AI commands', () => {
    let world = aiMatch(2, 'normal', 'normal');
    for (let i = 0; i < 20 * 45; i += 1) {
      world = stepWithAi(world);
    }
    const view = perceivedUnits(world, 1);
    const seen = new Set(view.units.map((u) => u.id));
    const contactsNear = (x: number, z: number): boolean =>
      view.contacts.some((c) => Math.hypot(c.x - x, c.z - z) < 1);
    const hidden = world.units.find((u) => u.owner === 2 && !seen.has(u.id) && !contactsNear(u.x, u.z));
    expect(hidden).toBeDefined();
    if (!hidden) {
      return;
    }
    const base = world.aiStates[0];
    if (!base) {
      return;
    }
    const baseline = JSON.stringify(thinkAi(world, base));
    const moved = structuredClone(world) as WorldState;
    const target = moved.units.find((u) => u.id === hidden.id);
    if (target) {
      target.x = hidden.x < 0 ? hidden.x + 6 : hidden.x - 6;
      target.z = hidden.z < 0 ? hidden.z + 6 : hidden.z - 6;
    }
    moved.vision = world.vision;
    expect(JSON.stringify(thinkAi(moved, base))).toBe(baseline);
  });

  it('[AI-06] against an idle player the normal AI destroys the pad within 20 game minutes', () => {
    let world = createSkirmishWorld(data, 5, [
      { player: 1, faction: 'human', controller: 'human' },
      { player: 2, faction: 'alien', controller: 'ai', difficulty: 'normal' },
    ]);
    while (world.result === null && world.tick < 20 * 60 * 20) {
      world = stepWithAi(world);
    }
    expect(world.result?.winner).toBe(2);
  }, 120_000);

  it('[AI-05] a side with no pads and no fighting units is eliminated', () => {
    let world = aiMatch(4, 'normal', 'normal');
    world.structures = world.structures.filter((s) => s.owner !== 2);
    world.units = world.units.filter((u) => u.owner !== 2 || !u.typeId.includes('tank'));
    world.pendingKits = [];
    world = stepWithAi(world);
    expect(world.result?.winner).toBe(1);
  });

  it('[AI-09] the AI never attacks allied or neutral units and handles two hostile opponents', () => {
    const tank = 'unit.human.light_tank';
    const world = createWorld(7, {
      unitTypes: data.unitTypes,
      structureTypes: data.structureTypes,
      researchTree: data.researchTree,
      deposits: data.mapData.deposits,
      factions: [1, 2, 3, 4].map((player) => ({ player, faction: 'human' as const })),
      startResources: [1, 2, 3].map((player) => ({ player, ore: 500, metal: 100 })),
      sides: [
        { player: 1, controller: 'ai', team: 1, groupId: null, provokable: true, forgiveAfterSec: null },
        { player: 2, controller: 'ai', team: 1, groupId: null, provokable: true, forgiveAfterSec: null },
        { player: 3, controller: 'ai', team: 3, groupId: null, provokable: true, forgiveAfterSec: null },
        { player: 4, controller: 'scripted', team: 4, groupId: null, provokable: true, forgiveAfterSec: null },
      ],
      startStructures: [
        { owner: 1, typeId: 'structure.human.landing_pad', x: -50, z: -50 },
        { owner: 2, typeId: 'structure.human.landing_pad', x: -50, z: 50 },
        { owner: 3, typeId: 'structure.human.landing_pad', x: 50, z: 0 },
      ],
      startUnits: [
        { owner: 1, typeId: tank, x: -46, z: -46 },
        { owner: 1, typeId: tank, x: -44, z: -46 },
        { owner: 2, typeId: tank, x: -46, z: 46 },
        { owner: 2, typeId: tank, x: -44, z: 46 },
        { owner: 3, typeId: tank, x: 46, z: 0 },
        { owner: 4, typeId: tank, x: -48, z: 0 },
        { owner: 4, typeId: tank, x: -46, z: 2 },
      ],
    });
    for (const player of [1, 2, 3]) {
      addAi(world, player, 'normal');
    }
    const neutralBefore = world.units.filter((u) => u.owner === 4).map((u) => u.hp);
    let state = world;
    for (let i = 0; i < 20 * 60 * 6 && state.result === null; i += 1) {
      state = stepWithAi(state);
      for (const unit of state.units.filter((u) => u.owner === 1 || u.owner === 2)) {
        expect(unit.hp).toBeGreaterThan(0);
      }
    }
    expect(state.units.filter((u) => u.owner === 4).map((u) => u.hp)).toEqual(neutralBefore);
    expect(relation(state, 4, 1)).toBe('neutral');
    expect(relation(state, 1, 2)).toBe('allied');
    const lostAllies = state.resources
      .filter((r) => r.player === 1 || r.player === 2)
      .reduce((sum, r) => sum + r.unitsLost, 0);
    const alliesAlive = state.units.filter((u) => (u.owner === 1 || u.owner === 2) && u.hp > 0).length;
    expect(lostAllies + alliesAlive).toBeGreaterThan(0);
  }, 120_000);

  it('[DET-05] AI-vs-AI is deterministic and save/load mid-match keeps the hash', () => {
    const a = runMatch(aiMatch(6, 'normal', 'normal'), 4);
    const b = runMatch(aiMatch(6, 'normal', 'normal'), 4);
    expect(hashWorld(a.world)).toBe(hashWorld(b.world));
    let world = aiMatch(6, 'normal', 'normal');
    for (let i = 0; i < 20 * 90; i += 1) {
      world = stepWithAi(world);
    }
    const loaded = decodeSave(encodeSave(world, { gameVersion: 't', savedAtIso: 'x' }));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) {
      return;
    }
    expect(hashWorld(loaded.world)).toBe(hashWorld(world));
    let straight = world;
    let resumed = loaded.world;
    for (let i = 0; i < 20 * 60; i += 1) {
      straight = stepWithAi(straight);
      resumed = stepWithAi(resumed);
    }
    expect(hashWorld(resumed)).toBe(hashWorld(straight));
  }, 120_000);
});
