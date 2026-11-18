import { describe, expect, it } from 'vitest';
import { data } from './aiHelpers';
import { botCommands } from './campaignBot';
import { MISSIONS, buildMissionWorld } from '../../src/data/missions';
import { createAiState, thinkAi } from '../../src/ai/ai';
import { stepWithAi } from '../../src/ai/driver';
import { decodeSave, encodeSave } from '../../src/platform/saves';
import { isBlockedAt } from '../../src/sim/map';
import { hashWorld, step } from '../../src/sim/world';
import type { Command } from '../../src/sim/commands';
import type { WorldState } from '../../src/sim/types';

const SEC = 20;
// A mission with a computer opponent that builds an army and attacks within the first minutes.
const MISSION_ID = 'mission.human.14_counterpunch';
const row = MISSIONS.find((m) => m.id === MISSION_ID);

function mission(seed: number): WorldState {
  if (!row) {
    throw new Error(`missing ${MISSION_ID}`);
  }
  return buildMissionWorld(data, row, seed);
}

// stepWithAi, also handing back the commands the computer sides gave this tick.
function stepRecording(world: WorldState, log: Command[]): WorldState {
  const aiCommands: Command[] = [];
  const states = world.aiStates.map((state) => {
    const result = thinkAi(world, state);
    aiCommands.push(...result.commands);
    return result.state;
  });
  log.push(...aiCommands);
  const next = step(world, [...botCommands(world), ...aiCommands]);
  next.aiStates = states;
  return next;
}

function play(seed: number, ticks: number): { world: WorldState; ai: Command[] } {
  let world = mission(seed);
  const ai: Command[] = [];
  while (world.tick < ticks && world.result === null) {
    world = stepRecording(world, ai);
  }
  return { world, ai };
}

describe('mission seeds and AI variety', () => {
  it('[DET-08] every seed plays on the same map with the same scripted start', () => {
    const a = mission(1);
    const b = mission(987_654_321);
    expect(b.seed).toBe(987_654_321);
    expect(Array.from(b.map.heights)).toEqual(Array.from(a.map.heights));
    expect(b.map.seed).toBe(a.map.seed);
    const layout = (w: WorldState): unknown => ({
      units: w.units.map((u) => [u.id, u.owner, u.typeId, u.x, u.z, u.heading]),
      structures: w.structures.map((s) => [s.id, s.owner, s.typeId, s.x, s.z]),
      deposits: w.deposits,
      resources: w.resources,
      mission: w.mission,
    });
    expect(layout(b)).toEqual(layout(a));
  });

  it('[DET-08] the same mission seed gives the same hash, and save/load keeps the seed and the hash', () => {
    const a = play(4242, 90 * SEC);
    const b = play(4242, 90 * SEC);
    expect(hashWorld(b.world)).toBe(hashWorld(a.world));
    const loaded = decodeSave(encodeSave(a.world, { gameVersion: 't', savedAtIso: 'x' }));
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) {
      return;
    }
    expect(loaded.world.seed).toBe(4242);
    expect(Array.from(loaded.world.map.heights)).toEqual(Array.from(a.world.map.heights));
    expect(hashWorld(loaded.world)).toBe(hashWorld(a.world));
    let straight = a.world;
    let resumed = loaded.world;
    for (let i = 0; i < 30 * SEC; i += 1) {
      straight = stepWithAi(straight, botCommands(straight));
      resumed = stepWithAi(resumed, botCommands(resumed));
    }
    expect(hashWorld(resumed)).toBe(hashWorld(straight));
  }, 120_000);

  it('[AI-17] different seeds give the mission AI a different play style', () => {
    const styles = [1, 2, 3, 4].map((seed) => {
      const state = mission(seed).aiStates[0];
      return { traitSeed: state?.traitSeed, attackScale: state?.attackScale };
    });
    expect(new Set(styles.map((s) => s.traitSeed)).size).toBe(4);
    for (const style of styles) {
      // This mission narrows the range to 0.8..1.0 (aiAttackScale), so its opening rush stays.
      expect(style.attackScale).toBeGreaterThanOrEqual(0.8);
      expect(style.attackScale).toBeLessThanOrEqual(1.0);
    }
    expect(mission(1).aiStates[0]?.attackScaleRange).toEqual([0.8, 1.0]);
  });

  it('[AI-17] two seeds make the mission AI give different orders, and its routes stay on open ground', () => {
    const ticks = 6 * 60 * SEC;
    const runs = [11, 12].map((seed) => play(seed, ticks));
    const summary = (ai: Command[]): string =>
      JSON.stringify(ai.filter((c) => c.kind !== 'noop').map((c) => ({ ...c, tick: Math.floor(c.tick / SEC) })));
    expect(runs[0]?.ai.length).toBeGreaterThan(0);
    expect(summary(runs[0]?.ai ?? [])).not.toBe(summary(runs[1]?.ai ?? []));
    for (const run of runs) {
      for (const c of run.ai) {
        if (c.kind === 'attackMove') {
          expect(isBlockedAt(run.world.map, c.x, c.z), `${c.x},${c.z}`).toBe(false);
        }
      }
    }
  }, 300_000);

  it('[AI-17] same world, different seeds: the AI attacks along a different route', () => {
    // Identical world, only the AI's own seed differs: whatever changes comes from its variety.
    // This mission's AI opens by sending its starting army straight at the player.
    const base = mission(21);
    const player = base.aiStates[0]?.player ?? 2;
    const difficulty = base.aiStates[0]?.difficulty ?? 'normal';
    const decisions = new Set<string>();
    for (let seed = 1; seed <= 8; seed += 1) {
      const range = base.aiStates[0]?.attackScaleRange;
      const fresh = createAiState(player, difficulty, seed, range ? { attackScaleRange: range } : {});
      const state = { ...(base.aiStates[0] ?? fresh), traitSeed: fresh.traitSeed, attackScale: fresh.attackScale, rngState: fresh.rngState };
      const orders: Command[] = [];
      let world: WorldState = { ...base, aiStates: [state] };
      for (let i = 0; i < 20 * SEC; i += 1) {
        world = stepRecording(world, orders);
      }
      const attacks = orders.filter((c) => c.kind === 'attackMove');
      // Every seed still makes the opening rush; only its route (and target) may change.
      expect(attacks.length, `seed ${seed}`).toBeGreaterThan(0);
      decisions.add(JSON.stringify(attacks));
    }
    expect(decisions.size).toBeGreaterThan(1);
  }, 300_000);

  it('[AI-17] an AI state saved before variety existed plays its plain style', () => {
    const world = mission(1);
    const old = world.aiStates.map(({ traitSeed: _t, attackScale: _a, ...rest }) => rest);
    const legacy: WorldState = { ...world, aiStates: old };
    let next = legacy;
    for (let i = 0; i < 30 * SEC; i += 1) {
      next = stepWithAi(next, botCommands(next));
    }
    expect(next.aiStates[0]?.traitSeed).toBeUndefined();
    expect(next.tick).toBe(30 * SEC);
  }, 60_000);
});
