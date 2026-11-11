import { describe, expect, it } from 'vitest';
import { aiMatch, stepWithAi } from './aiHelpers';
import { addUnit } from '../../src/sim/spawn';
import type { WorldState } from '../../src/sim/types';

// A human normal AI that already has aviation research, money and an army should
// build an air base, buy aircraft and fly them at the enemy (AI-10).
function setUp(): WorldState {
  const world = aiMatch(3, 'normal', 'hard', false);
  const side = world.research.find((r) => r.player === 1);
  const done = ['research.human.fire_control', 'research.human.aviation'];
  if (side) {
    side.done = [...done];
  } else {
    world.research.push({ player: 1, done });
  }
  for (const stats of world.resources) {
    stats.ore = 3000;
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
  it('[AI-10] the AI builds an air base, buys aircraft and launches them', () => {
    let world = setUp();
    let builtBase = false;
    let boughtAircraft = false;
    let launched = false;
    for (let tick = 0; tick < 6 * 60 * 20 && !(builtBase && boughtAircraft && launched); tick += 1) {
      world = stepWithAi(world);
      builtBase ||= world.structures.some((s) => s.owner === 1 && s.typeId === 'structure.human.air_base');
      const aircraft = world.units.filter((u) => u.owner === 1 && u.air !== null);
      boughtAircraft ||= aircraft.length > 0;
      launched ||= aircraft.some((u) => u.air?.mode === 'flying');
    }
    expect(builtBase).toBe(true);
    expect(boughtAircraft).toBe(true);
    expect(launched).toBe(true);
  }, 120_000);
});
