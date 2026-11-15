import { describe, expect, it } from 'vitest';
import { aiMatch, stepWithAi } from './aiHelpers';
import { thinkAi } from '../../src/ai/ai';
import { assignHome } from '../../src/sim/air';
import { addStructure, addUnit } from '../../src/sim/spawn';
import type { WorldState } from '../../src/sim/types';

// Research as normal play reaches it: Aviation needs Sensors.
const AVIATION = ['research.human.sensors', 'research.human.aviation'];

function setUp(): WorldState {
  const world = aiMatch(3, 'normal', 'hard', false);
  const side = world.research.find((r) => r.player === 1);
  if (side) {
    side.done = [...AVIATION];
  } else {
    world.research.push({ player: 1, done: [...AVIATION], active: null, queue: [] });
  }
  for (const stats of world.resources) {
    // Units and buildings cost ore only now; the old 1500 metal's worth moves into ore.
    stats.ore = 4500;
    stats.metal = 1500;
  }
  const pad = world.structures.find((s) => s.owner === 1);
  for (let i = 0; i < 6; i += 1) {
    addUnit(world, {
      typeId: 'unit.human.light_tank',
      owner: 1,
      x: (pad?.x ?? 0) + 8 + (i % 3) * 3,
      z: (pad?.z ?? 0) + 8 + Math.floor(i / 3) * 3,
    });
  }
  // A passive, sturdy enemy (no AI) so the match lasts long enough to see aircraft fly.
  world.aiStates = world.aiStates.filter((state) => state.player === 1);
  const enemyPad = world.structures.find((s) => s.owner === 2);
  if (enemyPad) {
    enemyPad.hp = 1_000_000; // can't fall, so the match outlasts the test window
  }
  for (let i = 0; i < 12; i += 1) {
    addUnit(world, {
      typeId: 'unit.alien.light_tank',
      owner: 2,
      x: (enemyPad?.x ?? 0) - 8 - (i % 4) * 3,
      z: (enemyPad?.z ?? 0) - 8 - Math.floor(i / 4) * 3,
    });
  }
  return world;
}

describe('enemy AI air', () => {
  it('[AI-10] the AI builds an air base, buys aircraft and strikes enemy structures', () => {
    let world = setUp();
    const enemyPad = world.structures.find((s) => s.owner === 2);
    let builtBase = false;
    let boughtAircraft = false;
    let launched = false;
    let struckBase = false;
    for (let tick = 0; tick < 8 * 60 * 20 && !(builtBase && boughtAircraft && launched && struckBase); tick += 1) {
      world = stepWithAi(world);
      builtBase ||= world.structures.some((s) => s.owner === 1 && s.typeId === 'structure.human.air_base');
      const aircraft = world.units.filter((u) => u.owner === 1 && u.air !== null);
      boughtAircraft ||= aircraft.length > 0;
      launched ||= aircraft.some((u) => u.air?.mode === 'flying');
      // A strike flies at an enemy structure (the pad is the only one on this map).
      struckBase ||= aircraft.some(
        (u) =>
          u.air?.mode === 'flying' &&
          enemyPad !== undefined &&
          (u.order.kind === 'attackMove' || u.order.kind === 'move') &&
          Math.hypot(u.order.x - enemyPad.x, u.order.z - enemyPad.z) < 10,
      );
    }
    expect(builtBase).toBe(true);
    expect(boughtAircraft).toBe(true);
    expect(launched).toBe(true);
    expect(struckBase).toBe(true);
  }, 120_000);

  it('[AI-10] a ready fighter is launched at an enemy aircraft over the base', () => {
    const world = setUp();
    const pad = world.structures.find((s) => s.owner === 1 && s.typeId.endsWith('landing_pad'));
    if (!pad) {
      throw new Error('no pad');
    }
    addStructure(world, { owner: 1, typeId: 'structure.human.air_base', x: pad.x + 14, z: pad.z });
    const fighter = addUnit(world, { owner: 1, typeId: 'unit.human.fighter', x: pad.x + 14, z: pad.z });
    if (!fighter) {
      throw new Error('no fighter');
    }
    assignHome(world, fighter);
    const intruder = addUnit(world, { owner: 2, typeId: 'unit.alien.fighter', x: pad.x + 6, z: pad.z + 6 });
    if (!intruder?.air) {
      throw new Error('no intruder');
    }
    intruder.air.mode = 'flying';
    const state = world.aiStates.find((s) => s.player === 1);
    if (!state) {
      throw new Error('no ai');
    }
    // Strategic steps run when (tick + 7 * player) is a multiple of the difficulty period (40 on normal).
    world.tick = 40 - 7;
    const { commands } = thinkAi(world, state);
    expect(commands).toContainEqual(expect.objectContaining({ kind: 'air', action: 'launch', unitIds: [fighter.id] }));
    expect(commands).toContainEqual(expect.objectContaining({ kind: 'attack', unitIds: [fighter.id], targetId: intruder.id }));
  });
});
